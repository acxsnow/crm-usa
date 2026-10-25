"""Banca conectada, como el «Banking» de QuickBooks.

- Arriba, las cuentas y tarjetas conectadas (Plaid) con su saldo y la última
  sincronización.
- Abajo, tres pestañas: **Por revisar**, **Categorizados** y **Excluidos**.
- En cada movimiento por revisar:
  - **Agregar**: crea el gasto de la empresa (tarjeta de la empresa, ya
    aprobado), con categoría y obra. Lo que va a una obra suma solo al costo
    del trabajo y a la rentabilidad.
  - **Coincidir**: lo enlaza con lo que ya estaba registrado (el gasto que
    subió el técnico con su recibo, un pago a proveedor o un pago de una
    factura), para no contar dos veces.
  - **Excluir**: lo saca (transferencias entre cuentas, pagos de la tarjeta).
- **Reglas**: «si la descripción contiene HOME DEPOT, categoría Material menor»;
  proponen la categoría y la obra, y con «agregar sola» lo hacen sin pasar por
  revisión.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import to_money
from app.modules.finance.models import EXPENSE_CATEGORIES, Expense, SupplierPayment
from app.modules.payments import providers
from app.modules.payments.models import BankAccount, BankConnection, BankRule, BankTransaction
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

MATCH_WINDOW_DAYS = 5
# Préstamos, hipotecas, 401k e IRA no son gasto del día a día: llegan ocultos y
# se pueden mostrar. De una cuenta oculta no se ven movimientos por revisar.
HIDDEN_BY_DEFAULT = {"loan", "investment"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Conexiones
# ---------------------------------------------------------------------------

async def link_token(organization_id: uuid.UUID, user) -> str:
    from app.core.config import get_settings

    s = get_settings()
    cuerpo = {"client_name": "PAP CRM", "language": "es", "country_codes": ["US"], "products": ["transactions"],
              "user": {"client_user_id": str(organization_id)}, "transactions": {"days_requested": 180}}
    if s.PUBLIC_API_URL:
        cuerpo["webhook"] = f"{s.PUBLIC_API_URL.rstrip('/')}/api/v1/webhooks/plaid"
    return (await providers.plaid_request("/link/token/create", cuerpo))["link_token"]


def connection_out(c: BankConnection) -> dict:
    return {"id": str(c.id), "institution_name": c.institution_name, "status": c.status,
            "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None, "last_error": c.last_error,
            "accounts": [{"id": str(a.id), "name": a.name, "mask": a.mask, "type": a.type, "subtype": a.subtype,
                          "current_balance": str(a.current_balance) if a.current_balance is not None else None,
                          "available_balance": str(a.available_balance) if a.available_balance is not None else None,
                          "active": a.active} for a in c.accounts]}


async def connect(db: AsyncSession, *, organization_id: uuid.UUID, user, public_token: str,
                  institution_name: str, institution_id: str | None) -> dict:
    datos = await providers.plaid_request("/item/public_token/exchange", {"public_token": public_token})
    conexion = BankConnection(organization_id=organization_id, institution_name=institution_name[:255] or "Banco",
                              institution_id=institution_id, plaid_item_id=datos["item_id"],
                              access_token_encrypted=providers.encrypt(datos["access_token"]), status="active",
                              connected_by_user_id=user.id, accounts=[])
    db.add(conexion)
    await db.flush()
    await _refresh_accounts(db, conexion)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="bankfeeds.connected", entity_type="BankConnection", entity_id=str(conexion.id),
                             after_data={"institution": conexion.institution_name,
                                         "accounts": [f"{a.name} ····{a.mask}" for a in conexion.accounts]})
    await db.commit()
    await sync(db, organization_id=organization_id, connection_id=conexion.id)
    return connection_out(await get_connection(db, organization_id, conexion.id))


async def _refresh_accounts(db: AsyncSession, conexion: BankConnection) -> None:
    datos = await providers.plaid_request("/accounts/get",
                                          {"access_token": providers.decrypt(conexion.access_token_encrypted)})
    existentes = {a.plaid_account_id: a for a in conexion.accounts}
    for a in datos.get("accounts", []):
        cuenta = existentes.get(a["account_id"])
        if cuenta is None:
            cuenta = BankAccount(organization_id=conexion.organization_id, connection_id=conexion.id,
                                 plaid_account_id=a["account_id"], name=a.get("name") or "Cuenta",
                                 active=a.get("type") not in HIDDEN_BY_DEFAULT)
            conexion.accounts.append(cuenta)
        cuenta.name = (a.get("official_name") or a.get("name") or "Cuenta")[:255]
        cuenta.mask, cuenta.type, cuenta.subtype = a.get("mask"), a.get("type"), a.get("subtype")
        saldos = a.get("balances") or {}
        cuenta.current_balance, cuenta.available_balance = _dec(saldos.get("current")), _dec(saldos.get("available"))
        cuenta.currency = saldos.get("iso_currency_code")
    await db.flush()


async def get_connection(db: AsyncSession, organization_id, connection_id) -> BankConnection:
    c = (await db.execute(select(BankConnection).where(BankConnection.id == connection_id,
                                                       BankConnection.organization_id == organization_id))
         ).scalar_one_or_none()
    if c is None:
        raise NotFoundError("La conexión no existe.", code="bank_connection_not_found")
    return c


async def list_connections(db: AsyncSession, organization_id) -> list[dict]:
    filas = (await db.execute(select(BankConnection).where(
        BankConnection.organization_id == organization_id, BankConnection.status != "disconnected")
        .order_by(BankConnection.institution_name))).scalars().all()
    return [connection_out(c) for c in filas]


async def disconnect(db: AsyncSession, *, organization_id, user, connection_id) -> None:
    c = await get_connection(db, organization_id, connection_id)
    try:
        await providers.plaid_request("/item/remove", {"access_token": providers.decrypt(c.access_token_encrypted)})
    except Exception:  # noqa: BLE001 — se desconecta aquí aunque Plaid no responda
        pass
    c.status = "disconnected"
    c.access_token_encrypted = providers.encrypt("revoked")
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="bankfeeds.disconnected", entity_type="BankConnection", entity_id=str(c.id))
    await db.commit()


async def set_account_visible(db: AsyncSession, *, organization_id, user, account_id, visible: bool) -> dict:
    cuenta = (await db.execute(select(BankAccount).where(BankAccount.id == account_id,
                                                         BankAccount.organization_id == organization_id))
              ).scalar_one_or_none()
    if cuenta is None:
        raise NotFoundError("La cuenta no existe.", code="bank_account_not_found")
    cuenta.active = visible
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="bankfeeds.account_shown" if visible else "bankfeeds.account_hidden",
                             entity_type="BankAccount", entity_id=str(cuenta.id))
    await db.commit()
    return connection_out(await get_connection(db, organization_id, cuenta.connection_id))


def _visible_accounts(organization_id):
    return select(BankAccount.id).where(BankAccount.organization_id == organization_id, BankAccount.active.is_(True))


# ---------------------------------------------------------------------------
# Sincronización (transactions/sync con cursor) y reglas
# ---------------------------------------------------------------------------

async def sync(db: AsyncSession, *, organization_id, connection_id) -> dict:
    c = await get_connection(db, organization_id, connection_id)
    if c.status == "disconnected":
        raise ConflictError("La conexión está desconectada.", code="bank_disconnected")
    token = providers.decrypt(c.access_token_encrypted)
    cuentas = {a.plaid_account_id: a for a in c.accounts}
    reglas = await _rules(db, organization_id)
    nuevos = modificados = borrados = 0
    try:
        mas, cursor = True, c.sync_cursor
        while mas:
            cuerpo = {"access_token": token, "count": 500}
            if cursor:
                cuerpo["cursor"] = cursor
            datos = await providers.plaid_request("/transactions/sync", cuerpo)
            for t in datos.get("added", []):
                if await _upsert(db, organization_id, cuentas, t, reglas, nuevo=True):
                    nuevos += 1
            for t in datos.get("modified", []):
                if await _upsert(db, organization_id, cuentas, t, reglas, nuevo=False):
                    modificados += 1
            for t in datos.get("removed", []):
                fila = await _by_plaid_id(db, organization_id, t.get("transaction_id"))
                if fila is not None and fila.review_status == "review":
                    await db.delete(fila)
                    borrados += 1
            cursor, mas = datos.get("next_cursor"), bool(datos.get("has_more"))
        c.sync_cursor = cursor
        c.status, c.last_error, c.last_synced_at = "active", None, _now()
        await _refresh_accounts(db, c)
    except Exception as exc:  # noqa: BLE001
        codigo = getattr(exc, "code", "")
        c.status = "needs_login" if codigo == "bank_login_required" else c.status
        c.last_error = str(getattr(exc, "message", exc))[:500]
        await db.commit()
        raise
    await db.commit()
    return {"added": nuevos, "modified": modificados, "removed": borrados}


async def sync_item(db: AsyncSession, plaid_item_id: str) -> None:
    """Desde el webhook de Plaid: sincroniza la conexión de ese Item."""
    c = (await db.execute(select(BankConnection).where(BankConnection.plaid_item_id == plaid_item_id,
                                                       BankConnection.status != "disconnected"))).scalars().first()
    if c is not None:
        await sync(db, organization_id=c.organization_id, connection_id=c.id)


async def sync_all(db: AsyncSession) -> int:
    filas = (await db.execute(select(BankConnection).where(BankConnection.status == "active"))).scalars().all()
    hechas = 0
    for c in filas:
        try:
            await sync(db, organization_id=c.organization_id, connection_id=c.id)
            hechas += 1
        except Exception:  # noqa: BLE001 — una conexión caída no detiene las demás
            await db.rollback()
    return hechas


async def _by_plaid_id(db, organization_id, plaid_id) -> BankTransaction | None:
    return (await db.execute(select(BankTransaction).where(
        BankTransaction.organization_id == organization_id,
        BankTransaction.plaid_transaction_id == plaid_id))).scalar_one_or_none()


async def _upsert(db, organization_id, cuentas: dict, t: dict, reglas: list[BankRule], *, nuevo: bool) -> bool:
    cuenta = cuentas.get(t.get("account_id"))
    if cuenta is None:
        return False
    fila = await _by_plaid_id(db, organization_id, t["transaction_id"])
    categoria = t.get("personal_finance_category") or {}
    datos = dict(posted_date=date.fromisoformat(t.get("date")), amount=_dec(t.get("amount")) or Decimal("0"),
                 description=(t.get("name") or t.get("merchant_name") or "Movimiento")[:500],
                 merchant_name=(t.get("merchant_name") or None), pending=bool(t.get("pending")),
                 plaid_category=(categoria.get("detailed") or categoria.get("primary") or None))
    if fila is None:
        if not nuevo and t.get("pending"):
            return False
        fila = BankTransaction(organization_id=organization_id, account_id=cuenta.id,
                               plaid_transaction_id=t["transaction_id"], review_status="review", **datos)
        db.add(fila)
        await db.flush()
        await _apply_rules(db, fila, reglas)
        return True
    if fila.review_status == "review":
        for k, v in datos.items():
            setattr(fila, k, v)
    return True


async def _rules(db, organization_id) -> list[BankRule]:
    return list((await db.execute(select(BankRule).where(BankRule.organization_id == organization_id,
                                                         BankRule.active.is_(True))
                                  .order_by(BankRule.priority, BankRule.created_at))).scalars())


def rule_matches(r: BankRule, t: BankTransaction) -> bool:
    texto = f"{t.description} {t.merchant_name or ''}".lower()
    if r.contains.lower() not in texto:
        return False
    sale = t.amount > 0
    if (r.direction == "out" and not sale) or (r.direction == "in" and sale):
        return False
    if r.account_id and r.account_id != t.account_id:
        return False
    monto = abs(t.amount)
    if r.amount_min is not None and monto < r.amount_min:
        return False
    if r.amount_max is not None and monto > r.amount_max:
        return False
    return True


async def _apply_rules(db, t: BankTransaction, reglas: list[BankRule]) -> None:
    for r in reglas:
        if rule_matches(r, t):
            t.suggested_category, t.suggested_project_id, t.suggested_rule_id = r.category, r.project_id, r.id
            if r.auto_add and t.amount > 0 and not t.pending:
                await _add_expense(db, t, category=r.category, project_id=r.project_id, user_id=None,
                                   memo=r.memo or f"Regla: {r.name}", reviewer=None)
            return


# ---------------------------------------------------------------------------
# Revisión: agregar, coincidir, excluir
# ---------------------------------------------------------------------------

async def get_tx(db, organization_id, tx_id) -> BankTransaction:
    t = (await db.execute(select(BankTransaction).where(BankTransaction.id == tx_id,
                                                        BankTransaction.organization_id == organization_id))
         ).scalar_one_or_none()
    if t is None:
        raise NotFoundError("El movimiento no existe.", code="bank_tx_not_found")
    return t


def _pendiente(t: BankTransaction) -> None:
    if t.review_status != "review":
        raise ConflictError("Este movimiento ya fue revisado; deshazlo para cambiarlo.", code="bank_tx_reviewed")
    if t.pending:
        raise ConflictError("El banco todavía no confirma este movimiento; revísalo cuando quede publicado.",
                            code="bank_tx_pending")


async def _check_project(db, organization_id, project_id) -> None:
    if project_id is None:
        return
    from app.modules.field_ops.models import Project

    ok = (await db.execute(select(Project.id).where(Project.id == project_id,
                                                    Project.organization_id == organization_id))).first()
    if not ok:
        raise InvalidInputError("La obra no existe.", code="invalid_project")


async def _add_expense(db, t: BankTransaction, *, category: str, project_id, user_id, memo, reviewer) -> Expense:
    if category not in EXPENSE_CATEGORIES:
        raise InvalidInputError("Categoría no válida.", code="invalid_category")
    if t.amount <= 0:
        raise InvalidInputError("Un depósito no se agrega como gasto; haz que coincida con un pago o exclúyelo.",
                                code="bank_tx_is_deposit")
    gasto = Expense(organization_id=t.organization_id, user_id=user_id or reviewer or await _any_owner(db, t),
                    project_id=project_id, expense_date=t.posted_date, category=category, amount=t.amount,
                    description=(memo or t.merchant_name or t.description)[:500], payment_method="company_card",
                    status="approved", reviewed_by_user_id=reviewer, reviewed_at=_now(),
                    review_notes="Desde la banca conectada")
    db.add(gasto)
    await db.flush()
    t.expense_id, t.category, t.project_id, t.memo = gasto.id, category, project_id, memo
    t.review_status, t.reviewed_by_user_id, t.reviewed_at = "categorized", reviewer, _now()
    return gasto


async def _any_owner(db, t: BankTransaction):
    """Quién conectó el banco: queda como titular de los gastos que agrega una regla."""
    cuenta = await db.get(BankAccount, t.account_id)
    conexion = await db.get(BankConnection, cuenta.connection_id) if cuenta else None
    return conexion.connected_by_user_id if conexion else None


async def add(db: AsyncSession, *, organization_id, user, tx_id, category: str, project_id=None,
              person_id=None, memo: str | None = None) -> dict:
    t = await get_tx(db, organization_id, tx_id)
    _pendiente(t)
    await _check_project(db, organization_id, project_id)
    if person_id:
        from app.modules.users.models import User

        p = await db.get(User, person_id)
        if p is None or p.organization_id != organization_id:
            raise InvalidInputError("La persona no existe.", code="invalid_user")
    gasto = await _add_expense(db, t, category=category, project_id=project_id, user_id=person_id, memo=memo,
                               reviewer=user.id)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.added",
                             entity_type="BankTransaction", entity_id=str(t.id),
                             after_data={"expense_id": str(gasto.id), "category": category,
                                         "project_id": str(project_id) if project_id else None})
    await db.commit()
    return await tx_out(db, t)


async def candidates(db: AsyncSession, organization_id, t: BankTransaction) -> list[dict]:
    """Con qué puede coincidir: mismo monto y fecha cercana, aún sin enlazar."""
    desde, hasta = t.posted_date - timedelta(days=MATCH_WINDOW_DAYS), t.posted_date + timedelta(days=MATCH_WINDOW_DAYS)
    usados = select(BankTransaction.matched_id).where(BankTransaction.organization_id == organization_id,
                                                      BankTransaction.matched_id.is_not(None))
    usados_gasto = select(BankTransaction.expense_id).where(BankTransaction.organization_id == organization_id,
                                                            BankTransaction.expense_id.is_not(None))
    salida = []
    monto = abs(t.amount)
    if t.amount > 0:
        gastos = (await db.execute(select(Expense).where(
            Expense.organization_id == organization_id, Expense.amount == monto,
            Expense.expense_date.between(desde, hasta), Expense.status.in_(("submitted", "approved", "reimbursed")),
            Expense.id.not_in(usados), Expense.id.not_in(usados_gasto)).limit(10))).scalars().all()
        salida += [{"type": "expense", "id": str(g.id), "date": g.expense_date.isoformat(), "amount": str(g.amount),
                    "label": f"Gasto: {g.description}", "has_receipt": bool(g.receipt_path)} for g in gastos]
        pagos = (await db.execute(select(SupplierPayment).where(
            SupplierPayment.organization_id == organization_id, SupplierPayment.amount == monto,
            SupplierPayment.paid_on.between(desde, hasta), SupplierPayment.id.not_in(usados)).limit(10))).scalars().all()
        salida += [{"type": "supplier_payment", "id": str(p.id), "date": p.paid_on.isoformat(), "amount": str(p.amount),
                    "label": f"Pago a proveedor {p.reference or ''}".strip()} for p in pagos]
    else:
        from app.modules.billing.models import Invoice, InvoicePayment

        pagos = (await db.execute(select(InvoicePayment, Invoice.invoice_number).join(
            Invoice, Invoice.id == InvoicePayment.invoice_id).where(
            Invoice.organization_id == organization_id, InvoicePayment.amount == monto,
            InvoicePayment.paid_at.between(desde, hasta), InvoicePayment.id.not_in(usados)).limit(10))).all()
        salida += [{"type": "invoice_payment", "id": str(p.id), "date": p.paid_at.isoformat(), "amount": str(p.amount),
                    "label": f"Pago de la factura {num} ({p.method or 'sin método'})"} for p, num in pagos]
    return salida


async def match(db: AsyncSession, *, organization_id, user, tx_id, matched_type: str, matched_id) -> dict:
    t = await get_tx(db, organization_id, tx_id)
    _pendiente(t)
    validos = {c["type"] + ":" + c["id"] for c in await candidates(db, organization_id, t)}
    if f"{matched_type}:{matched_id}" not in validos:
        raise InvalidInputError("Ese registro no coincide con el movimiento (monto o fecha).", code="invalid_match")
    if matched_type == "expense":
        gasto = await db.get(Expense, uuid.UUID(str(matched_id)))
        t.expense_id, t.category, t.project_id = gasto.id, gasto.category, gasto.project_id
        # El gasto lo pagó la tarjeta de la empresa: ya no se reembolsa.
        gasto.payment_method = "company_card"
    t.matched_type, t.matched_id = matched_type, uuid.UUID(str(matched_id))
    t.review_status, t.reviewed_by_user_id, t.reviewed_at = "categorized", user.id, _now()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.matched",
                             entity_type="BankTransaction", entity_id=str(t.id),
                             after_data={"type": matched_type, "id": str(matched_id)})
    await db.commit()
    return await tx_out(db, t)


async def exclude(db: AsyncSession, *, organization_id, user, tx_id, memo: str | None) -> dict:
    t = await get_tx(db, organization_id, tx_id)
    if t.review_status != "review":
        raise ConflictError("Este movimiento ya fue revisado.", code="bank_tx_reviewed")
    t.review_status, t.memo, t.reviewed_by_user_id, t.reviewed_at = "excluded", memo, user.id, _now()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.excluded",
                             entity_type="BankTransaction", entity_id=str(t.id), after_data={"memo": memo})
    await db.commit()
    return await tx_out(db, t)


async def undo(db: AsyncSession, *, organization_id, user, tx_id) -> dict:
    """Deshacer (como «Undo» en QuickBooks): vuelve a «Por revisar». Si el
    movimiento creó un gasto, ese gasto se borra; si coincidió, solo se suelta."""
    t = await get_tx(db, organization_id, tx_id)
    if t.review_status == "review":
        raise ConflictError("El movimiento ya está por revisar.", code="bank_tx_in_review")
    if t.expense_id and t.matched_type is None:
        gasto = await db.get(Expense, t.expense_id)
        if gasto is not None:
            await db.delete(gasto)
    antes = {"status": t.review_status, "expense_id": str(t.expense_id) if t.expense_id else None,
             "matched": f"{t.matched_type}:{t.matched_id}" if t.matched_type else None}
    t.review_status, t.expense_id, t.matched_type, t.matched_id = "review", None, None, None
    t.category = t.project_id = t.reviewed_by_user_id = t.reviewed_at = None
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.undone",
                             entity_type="BankTransaction", entity_id=str(t.id), before_data=antes)
    await db.commit()
    return await tx_out(db, t)


async def accept_suggested(db: AsyncSession, *, organization_id, user, tx_ids: list) -> dict:
    """«Aceptar» en lote lo que una regla ya propuso."""
    hechos, errores = 0, []
    for tid in tx_ids:
        t = await get_tx(db, organization_id, tid)
        if t.review_status != "review" or not t.suggested_category or t.pending or t.amount <= 0:
            errores.append(str(tid))
            continue
        await _add_expense(db, t, category=t.suggested_category, project_id=t.suggested_project_id, user_id=None,
                           memo=None, reviewer=user.id)
        hechos += 1
    await db.commit()
    return {"accepted": hechos, "skipped": errores}


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------

async def tx_out(db, t: BankTransaction, *, cuentas: dict | None = None, obras: dict | None = None) -> dict:
    if cuentas is None:
        a = await db.get(BankAccount, t.account_id)
        cuentas = {t.account_id: a}
    cuenta = cuentas.get(t.account_id)
    return {
        "id": str(t.id), "date": t.posted_date.isoformat(), "description": t.description,
        "merchant_name": t.merchant_name, "pending": t.pending,
        "spent": str(t.amount) if t.amount > 0 else None, "received": str(-t.amount) if t.amount < 0 else None,
        "account": {"id": str(cuenta.id), "name": cuenta.name, "mask": cuenta.mask, "type": cuenta.type} if cuenta else None,
        "status": t.review_status, "plaid_category": t.plaid_category,
        "suggested_category": t.suggested_category,
        "suggested_project_id": str(t.suggested_project_id) if t.suggested_project_id else None,
        "suggested_by_rule": bool(t.suggested_rule_id),
        "category": t.category, "project_id": str(t.project_id) if t.project_id else None,
        "project_title": (obras or {}).get(t.project_id or t.suggested_project_id),
        "expense_id": str(t.expense_id) if t.expense_id else None,
        "matched_type": t.matched_type, "matched_id": str(t.matched_id) if t.matched_id else None, "memo": t.memo,
    }


async def list_transactions(db: AsyncSession, *, organization_id, status: str, account_id=None, q: str | None = None,
                            limit: int, offset: int) -> tuple[list[dict], int]:
    from app.modules.field_ops.models import Project

    stmt = select(BankTransaction).where(BankTransaction.organization_id == organization_id,
                                         BankTransaction.review_status == status,
                                         BankTransaction.account_id.in_(_visible_accounts(organization_id)))
    if account_id:
        stmt = stmt.where(BankTransaction.account_id == account_id)
    if q:
        patron = "%" + q.replace("\x00", "").strip()[:80].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(BankTransaction.description.ilike(patron, escape="\\"),
                              BankTransaction.merchant_name.ilike(patron, escape="\\")))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    filas = list((await db.execute(stmt.order_by(BankTransaction.posted_date.desc(), BankTransaction.id)
                                   .limit(limit).offset(offset))).scalars())
    cuentas = {a.id: a for a in (await db.execute(select(BankAccount).where(
        BankAccount.organization_id == organization_id))).scalars()}
    ids = {t.project_id or t.suggested_project_id for t in filas} - {None}
    obras = dict((await db.execute(select(Project.id, Project.title).where(Project.id.in_(ids)))).all()) if ids else {}
    return [await tx_out(db, t, cuentas=cuentas, obras=obras) for t in filas], total


async def counts(db: AsyncSession, organization_id) -> dict:
    filas = (await db.execute(select(BankTransaction.review_status, func.count()).where(
        BankTransaction.organization_id == organization_id,
        BankTransaction.account_id.in_(_visible_accounts(organization_id)))
        .group_by(BankTransaction.review_status))).all()
    return {k: v for k, v in filas}


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------

def rule_out(r: BankRule) -> dict:
    return {"id": str(r.id), "name": r.name, "contains": r.contains, "direction": r.direction,
            "amount_min": str(r.amount_min) if r.amount_min is not None else None,
            "amount_max": str(r.amount_max) if r.amount_max is not None else None,
            "account_id": str(r.account_id) if r.account_id else None, "category": r.category,
            "project_id": str(r.project_id) if r.project_id else None, "auto_add": r.auto_add,
            "priority": r.priority, "active": r.active, "memo": r.memo}


async def save_rule(db: AsyncSession, *, organization_id, user, data: dict, rule_id=None) -> dict:
    if data["category"] not in EXPENSE_CATEGORIES:
        raise InvalidInputError("Categoría no válida.", code="invalid_category")
    if data.get("direction", "out") not in ("out", "in", "any"):
        raise InvalidInputError("Dirección no válida.", code="invalid_direction")
    await _check_project(db, organization_id, data.get("project_id"))
    if data.get("account_id"):
        cuenta = await db.get(BankAccount, data["account_id"])
        if cuenta is None or cuenta.organization_id != organization_id:
            raise InvalidInputError("La cuenta no existe.", code="invalid_account")
    if rule_id:
        r = (await db.execute(select(BankRule).where(BankRule.id == rule_id,
                                                     BankRule.organization_id == organization_id))).scalar_one_or_none()
        if r is None:
            raise NotFoundError("La regla no existe.", code="bank_rule_not_found")
    else:
        r = BankRule(organization_id=organization_id)
        db.add(r)
    for campo in ("name", "contains", "direction", "account_id", "category", "project_id", "auto_add", "priority",
                  "active", "memo"):
        if campo in data and data[campo] is not None:
            setattr(r, campo, data[campo])
    r.amount_min = to_money(data["amount_min"]) if data.get("amount_min") not in (None, "") else None
    r.amount_max = to_money(data["amount_max"]) if data.get("amount_max") not in (None, "") else None
    await db.flush()
    # Aplica la regla a lo que ya está por revisar, como QuickBooks.
    pendientes = (await db.execute(select(BankTransaction).where(
        BankTransaction.organization_id == organization_id, BankTransaction.review_status == "review",
        BankTransaction.suggested_rule_id.is_(None)))).scalars().all()
    for t in pendientes:
        if r.active and rule_matches(r, t):
            await _apply_rules(db, t, [r])
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.rule_saved",
                             entity_type="BankRule", entity_id=str(r.id), after_data=rule_out(r))
    await db.commit()
    return rule_out(r)


async def delete_rule(db: AsyncSession, *, organization_id, user, rule_id) -> None:
    r = (await db.execute(select(BankRule).where(BankRule.id == rule_id,
                                                 BankRule.organization_id == organization_id))).scalar_one_or_none()
    if r is None:
        raise NotFoundError("La regla no existe.", code="bank_rule_not_found")
    await db.delete(r)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="bankfeeds.rule_deleted",
                             entity_type="BankRule", entity_id=str(rule_id))
    await db.commit()


async def list_rules(db: AsyncSession, organization_id) -> list[dict]:
    return [rule_out(r) for r in (await db.execute(select(BankRule).where(BankRule.organization_id == organization_id)
                                                   .order_by(BankRule.priority, BankRule.name))).scalars()]

