"""Plan de cuentas, asientos manuales, cierre contable y reportes. Todos los
reportes salen de `journal_lines`: un mismo saldo no se calcula de dos formas.
"""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.chart import ensure_chart, settings_of
from app.modules.accounting.models import ACCOUNT_TYPES, DEBIT_NORMAL, Account, JournalEntry, JournalLine
from app.modules.accounting.posting import _new_entry, first_open_day, reverse
from app.modules.billing.money import ZERO, to_money
from app.modules.field_ops.clock import org_today
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

# Umbral del 1099-NEC por año de pago (P.L. 119-21: $2,000 desde 2026, y se ajusta
# por inflación después). `threshold` permite usar otro sin cambiar el código.
THRESHOLD_1099 = {2025: Decimal("600")}
DEFAULT_THRESHOLD_1099 = Decimal("2000")
KINDS_1099 = {"contractor", "services"}


def threshold_for(year: int) -> Decimal:
    return THRESHOLD_1099.get(year, DEFAULT_THRESHOLD_1099 if year >= 2026 else Decimal("600"))


def account_out(a: Account) -> dict:
    return {"id": str(a.id), "code": a.code, "name": a.name, "account_type": a.account_type,
            "account_type_label": ACCOUNT_TYPES[a.account_type], "system_key": a.system_key,
            "tax_category": a.tax_category, "active": a.active}


async def get_account(db: AsyncSession, organization_id, account_id) -> Account:
    a = await db.get(Account, account_id)
    if a is None or a.organization_id != organization_id:
        raise NotFoundError("La cuenta no existe.", code="account_not_found")
    return a


def accounts_stmt(organization_id):
    return select(Account).where(Account.organization_id == organization_id).order_by(Account.code)


async def save_account(db: AsyncSession, *, organization_id, user, data: dict, account_id=None) -> Account:
    await ensure_chart(db, organization_id)
    codigo = (data.get("code") or "").strip()
    a = await get_account(db, organization_id, account_id) if account_id else None
    if codigo:
        # Se revisa antes de tocar la cuenta: si no, la consulta guardaría el cambio y chocaría con el índice.
        repetido = select(Account.id).where(Account.organization_id == organization_id, Account.code == codigo)
        if a is not None:
            repetido = repetido.where(Account.id != a.id)
        if (await db.execute(repetido)).first():
            raise ConflictError(f"Ya existe una cuenta con el código {codigo}.", code="account_code_taken")
    if a is None:
        if not codigo or not (data.get("name") or "").strip():
            raise InvalidInputError("La cuenta necesita código y nombre.", code="account_fields_required")
        if data.get("account_type") not in ACCOUNT_TYPES:
            raise InvalidInputError("El tipo de cuenta no existe.", code="account_type_invalid")
        a = Account(organization_id=organization_id, code=codigo, name=data["name"].strip()[:120],
                    account_type=data["account_type"], active=True)
        db.add(a)
    elif codigo:
        a.code = codigo
    if a.system_key and data.get("active") is False:
        raise ConflictError("Esa cuenta la usan los asientos automáticos y no se desactiva.", code="account_system")
    if account_id and data.get("account_type") and data["account_type"] != a.account_type:
        usos = (await db.execute(select(func.count()).select_from(JournalLine).where(JournalLine.account_id == a.id))).scalar_one()
        if a.system_key or usos:
            raise ConflictError("El tipo de una cuenta con movimientos no se cambia.", code="account_type_locked")
        a.account_type = data["account_type"]
    if (data.get("name") or "").strip():
        a.name = data["name"].strip()[:120]
    if "tax_category" in data:
        a.tax_category = (data["tax_category"] or "").strip()[:80] or None
    if data.get("active") is not None:
        a.active = data["active"]
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="accounting.account_saved",
                             entity_type="Account", entity_id=str(a.id),
                             after_data={"code": a.code, "name": a.name, "active": a.active})
    await db.commit()
    return a


# ---------------------------------------------------------------------------
# Asientos
# ---------------------------------------------------------------------------

async def ensure_open(db: AsyncSession, organization_id, dia: date) -> None:
    abierto = await first_open_day(db, organization_id)
    if abierto and dia < abierto:
        raise ConflictError(f"El período está cerrado hasta el {abierto.isoformat()} (excluido). Usa una fecha posterior.",
                            code="accounting_period_closed")


async def create_manual_entry(db: AsyncSession, *, organization_id, user, on: date, memo: str, lines: list[dict]) -> JournalEntry:
    from app.modules.field_ops.models import Project

    await ensure_chart(db, organization_id)
    await ensure_open(db, organization_id, on)
    if not (memo or "").strip():
        raise InvalidInputError("Explica el asiento.", code="journal_memo_required")
    if len(lines) < 2:
        raise InvalidInputError("Un asiento necesita al menos dos líneas.", code="journal_lines_required")
    armadas, debe, haber = [], ZERO, ZERO
    for l in lines:
        d, c = to_money(l.get("debit") or 0), to_money(l.get("credit") or 0)
        if d < ZERO or c < ZERO or (d > ZERO) == (c > ZERO):
            raise InvalidInputError("Cada línea lleva un débito o un crédito, positivo, no los dos.", code="journal_line_invalid")
        cuenta = await get_account(db, organization_id, l["account_id"])
        if not cuenta.active:
            raise InvalidInputError(f"La cuenta {cuenta.code} está inactiva.", code="account_inactive")
        if l.get("project_id"):
            obra = await db.get(Project, l["project_id"])
            if obra is None or obra.organization_id != organization_id:
                raise NotFoundError("La obra no existe.", code="project_not_found")
        armadas.append((cuenta.id, d, c, l.get("project_id"), (l.get("memo") or "").strip()[:255] or None))
        debe, haber = debe + d, haber + c
    if debe != haber:
        raise InvalidInputError(f"El asiento no cuadra: débitos {debe} y créditos {haber}.", code="journal_unbalanced")
    e = await _new_entry(db, organization_id, on=on, memo=memo.strip(), source_key=None, source_date=None, revision=1,
                         lines=armadas, user_id=user.id)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="accounting.entry_created",
                             entity_type="JournalEntry", entity_id=str(e.id), after_data={"number": e.number, "total": str(debe)})
    await db.commit()
    return e


async def get_entry(db: AsyncSession, organization_id, entry_id) -> JournalEntry:
    e = (await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id,
                                                     JournalEntry.organization_id == organization_id))).scalar_one_or_none()
    if e is None:
        raise NotFoundError("El asiento no existe.", code="journal_entry_not_found")
    return e


async def reverse_manual(db: AsyncSession, *, organization_id, user, entry_id, on: date | None, reason: str) -> JournalEntry:
    e = await get_entry(db, organization_id, entry_id)
    if e.source_key:
        raise ConflictError("Un asiento automático se corrige en su documento (factura, gasto o pago).", code="journal_automatic")
    if e.reversed_by_id or e.reversal_of_id:
        raise ConflictError("Ese asiento ya se reversó o es una reversa.", code="journal_already_reversed")
    if len((reason or "").strip()) < 3:
        raise InvalidInputError("Escribe el motivo.", code="journal_reason_required")
    dia = on or await org_today(db, organization_id)
    await ensure_open(db, organization_id, dia)
    r = await reverse(db, e, on=dia, memo=f"Reversa de {e.number}: {reason.strip()}", user_id=user.id)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="accounting.entry_reversed",
                             entity_type="JournalEntry", entity_id=str(e.id), after_data={"reversal": r.number, "reason": reason.strip()})
    await db.commit()
    return r


def entries_stmt(organization_id, *, date_from=None, date_to=None, source: str | None = None, q: str | None = None):
    stmt = select(JournalEntry).where(JournalEntry.organization_id == organization_id)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    if source == "manual":
        stmt = stmt.where(JournalEntry.source_key.is_(None))
    elif source == "automatic":
        stmt = stmt.where(JournalEntry.source_key.is_not(None))
    if q:
        patron = "%" + q.strip()[:80].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(JournalEntry.memo.ilike(patron, escape="\\") | JournalEntry.number.ilike(patron, escape="\\"))
    return stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.number.desc())


async def entries_out(db: AsyncSession, organization_id, filas: list[JournalEntry]) -> list[dict]:
    cuentas = {a.id: a for a in (await db.execute(select(Account).where(Account.organization_id == organization_id))).scalars()}
    salida = []
    for e in filas:
        salida.append({
            "id": str(e.id), "number": e.number, "entry_date": e.entry_date.isoformat(), "memo": e.memo,
            "automatic": bool(e.source_key), "source_type": (e.source_key or "").split(":")[0] or None,
            "is_reversal": bool(e.reversal_of_id), "reversed": bool(e.reversed_by_id),
            "total": str(sum((l.debit for l in e.lines), ZERO)),
            "lines": [{"account_code": cuentas[l.account_id].code, "account_name": cuentas[l.account_id].name,
                       "debit": str(l.debit), "credit": str(l.credit),
                       "project_id": str(l.project_id) if l.project_id else None, "memo": l.memo} for l in e.lines]})
    return salida


async def set_lock(db: AsyncSession, *, organization_id, user, locked_through: date | None) -> dict:
    s = await settings_of(db, organization_id)
    hoy = await org_today(db, organization_id)
    if locked_through and locked_through > hoy:
        raise InvalidInputError("No se cierra un período que no ha terminado.", code="accounting_lock_future")
    antes = s.locked_through
    s.locked_through, s.locked_by_user_id = locked_through, user.id
    s.locked_at = datetime.now(timezone.utc)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="accounting.period_locked",
                             entity_type="AccountingSettings", entity_id=str(s.id),
                             before_data={"locked_through": antes.isoformat() if antes else None},
                             after_data={"locked_through": locked_through.isoformat() if locked_through else None})
    await db.commit()
    return lock_out(s)


def lock_out(s) -> dict:
    return {"locked_through": s.locked_through.isoformat() if s.locked_through else None,
            "locked_at": as_utc(s.locked_at).isoformat() if s.locked_at else None}


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

async def _totals(db, organization_id, *, date_from=None, date_to=None, project_id=None) -> dict:
    """{account_id: (débitos, créditos)} en el rango."""
    stmt = select(JournalLine.account_id, func.sum(JournalLine.debit), func.sum(JournalLine.credit)).join(
        JournalEntry, JournalEntry.id == JournalLine.entry_id).where(JournalLine.organization_id == organization_id)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    if project_id:
        stmt = stmt.where(JournalLine.project_id == project_id)
    return {a: (to_money(d or 0), to_money(c or 0)) for a, d, c in (await db.execute(stmt.group_by(JournalLine.account_id))).all()}


def _balance(tipo: str, debe: Decimal, haber: Decimal) -> Decimal:
    return debe - haber if tipo in DEBIT_NORMAL else haber - debe


async def _accounts(db, organization_id) -> list[Account]:
    return list((await db.execute(accounts_stmt(organization_id))).scalars())


def _row(a: Account, saldo: Decimal) -> dict:
    return {"account_id": str(a.id), "code": a.code, "name": a.name, "amount": str(saldo)}


async def trial_balance(db, organization_id, as_of: date) -> dict:
    totales = await _totals(db, organization_id, date_to=as_of)
    filas, debe, haber = [], ZERO, ZERO
    for a in await _accounts(db, organization_id):
        d, c = totales.get(a.id, (ZERO, ZERO))
        if not d and not c:
            continue
        # Se muestra el saldo neto en su lado, como un balance de comprobación.
        neto = d - c
        filas.append({"account_id": str(a.id), "code": a.code, "name": a.name, "account_type": ACCOUNT_TYPES[a.account_type],
                      "debit": str(neto if neto > 0 else ZERO), "credit": str(-neto if neto < 0 else ZERO)})
        debe, haber = debe + max(neto, ZERO), haber + max(-neto, ZERO)
    return {"as_of": as_of.isoformat(), "rows": filas, "total_debit": str(debe), "total_credit": str(haber),
            "balanced": debe == haber}


async def income_statement(db, organization_id, date_from: date, date_to: date, project_id=None) -> dict:
    if date_to < date_from:
        raise InvalidInputError("La fecha final es anterior a la inicial.", code="invalid_range")
    totales = await _totals(db, organization_id, date_from=date_from, date_to=date_to, project_id=project_id)
    secciones: dict = {"income": [], "cogs": [], "expense": []}
    suma: dict = defaultdict(lambda: ZERO)
    for a in await _accounts(db, organization_id):
        if a.account_type not in secciones or a.id not in totales:
            continue
        saldo = _balance(a.account_type, *totales[a.id])
        if saldo:
            secciones[a.account_type].append(_row(a, saldo))
            suma[a.account_type] += saldo
    bruta = suma["income"] - suma["cogs"]
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "income": secciones["income"],
            "cogs": secciones["cogs"], "expenses": secciones["expense"], "total_income": str(suma["income"]),
            "total_cogs": str(suma["cogs"]), "gross_profit": str(bruta), "total_expenses": str(suma["expense"]),
            "net_income": str(bruta - suma["expense"])}


async def balance_sheet(db, organization_id, as_of: date) -> dict:
    totales = await _totals(db, organization_id, date_to=as_of)
    grupos: dict = {"asset": [], "liability": [], "equity": []}
    suma: dict = defaultdict(lambda: ZERO)
    resultado = ZERO
    for a in await _accounts(db, organization_id):
        d, c = totales.get(a.id, (ZERO, ZERO))
        if a.account_type in grupos:
            saldo = _balance(a.account_type, d, c)
            if saldo:
                grupos[a.account_type].append(_row(a, saldo))
                suma[a.account_type] += saldo
        else:
            resultado += c - d
    pasivo_y_patrimonio = suma["liability"] + suma["equity"] + resultado
    return {"as_of": as_of.isoformat(), "assets": grupos["asset"], "liabilities": grupos["liability"],
            "equity": grupos["equity"], "total_assets": str(suma["asset"]), "total_liabilities": str(suma["liability"]),
            "retained_earnings": str(resultado), "total_equity": str(suma["equity"] + resultado),
            "total_liabilities_equity": str(pasivo_y_patrimonio), "balanced": suma["asset"] == pasivo_y_patrimonio}


def ledger_stmt(organization_id, account_id, date_from=None, date_to=None):
    stmt = select(JournalLine, JournalEntry).join(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(
        JournalLine.organization_id == organization_id, JournalLine.account_id == account_id)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    return stmt.order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.sort_order)


async def account_ledger(db, organization_id, account_id, date_from=None, date_to=None) -> dict:
    a = await get_account(db, organization_id, account_id)
    apertura = ZERO
    if date_from:
        d, c = (await db.execute(select(func.sum(JournalLine.debit), func.sum(JournalLine.credit)).join(
            JournalEntry, JournalEntry.id == JournalLine.entry_id).where(
            JournalLine.organization_id == organization_id, JournalLine.account_id == a.id,
            JournalEntry.entry_date < date_from))).one()
        apertura = _balance(a.account_type, to_money(d or 0), to_money(c or 0))
    filas, saldo = [], apertura
    for l, e in (await db.execute(ledger_stmt(organization_id, a.id, date_from, date_to))).all():
        saldo += _balance(a.account_type, l.debit, l.credit)
        filas.append({"id": str(l.id), "entry_id": str(e.id), "number": e.number, "entry_date": e.entry_date.isoformat(),
                      "memo": l.memo or e.memo, "debit": str(l.debit), "credit": str(l.credit), "balance": str(saldo)})
    return {"account": account_out(a), "opening_balance": str(apertura), "closing_balance": str(saldo), "rows": filas}


async def tax_summary(db, organization_id, year: int, threshold: Decimal | None = None) -> dict:
    """Lo que el contador necesita para declarar: resultado del año por renglón y
    pagos a proveedores para el 1099-NEC. No reemplaza su revisión ni presenta nada."""
    from app.modules.finance.models import Supplier, SupplierPayment

    desde, hasta = date(year, 1, 1), date(year, 12, 31)
    totales = await _totals(db, organization_id, date_from=desde, date_to=hasta)
    renglones: dict = defaultdict(lambda: {"amount": ZERO, "accounts": []})
    for a in await _accounts(db, organization_id):
        if a.account_type not in ("income", "cogs", "expense") or a.id not in totales:
            continue
        saldo = _balance(a.account_type, *totales[a.id])
        if not saldo:
            continue
        r = renglones[(a.account_type, a.tax_category or "Sin renglón asignado")]
        r["amount"] += saldo
        r["accounts"].append(f"{a.code} {a.name}")
    orden = {"income": 0, "cogs": 1, "expense": 2}
    filas = [{"group": ACCOUNT_TYPES[t], "tax_category": c, "amount": str(v["amount"]), "accounts": v["accounts"]}
             for (t, c), v in sorted(renglones.items(), key=lambda x: (orden[x[0][0]], x[0][1]))]
    umbral = threshold if threshold is not None else threshold_for(year)
    # Lo pagado con tarjeta no va en el 1099-NEC: lo reporta el procesador de la tarjeta.
    pagos = (await db.execute(select(SupplierPayment.supplier_id, func.sum(SupplierPayment.amount)).where(
        SupplierPayment.organization_id == organization_id, SupplierPayment.paid_on >= desde, SupplierPayment.paid_on <= hasta,
        SupplierPayment.method != "card").group_by(SupplierPayment.supplier_id))).all()
    proveedores = {s.id: s for s in (await db.execute(select(Supplier).where(
        Supplier.organization_id == organization_id, Supplier.id.in_([p for p, _ in pagos])))).scalars()} if pagos else {}
    lista = []
    for sid, total in pagos:
        s = proveedores.get(sid)
        total = to_money(total)
        # La compra de mercancía no va en el 1099-NEC: solo servicios y contratistas.
        if s is None or total < umbral or not set(s.kinds or []) & KINDS_1099:
            continue
        faltan = [n for n, ok in (("W-9", s.w9_on_file), ("TIN", bool(s.tax_id)), ("dirección", bool(s.address))) if not ok]
        lista.append({"supplier_id": str(sid), "name": s.legal_name or s.name, "tax_id": s.tax_id, "address": s.address,
                      "kinds": s.kinds or [], "total_paid": str(total), "w9_on_file": s.w9_on_file, "missing": faltan})
    lista.sort(key=lambda x: x["name"])
    ingresos = sum((Decimal(f["amount"]) for f in filas if f["group"] == ACCOUNT_TYPES["income"]), ZERO)
    costos = sum((Decimal(f["amount"]) for f in filas if f["group"] != ACCOUNT_TYPES["income"]), ZERO)
    return {"year": year, "threshold_1099": str(umbral), "lines": filas, "total_income": str(ingresos),
            "total_costs": str(costos), "net_income": str(ingresos - costos), "contractors_1099": lista}


def _safe(valor) -> str:
    """Evita que un nombre con «=» se ejecute como fórmula al abrir el CSV en Excel."""
    texto = "" if valor is None else str(valor)
    if texto[:1] in ("=", "+", "@", "\t", "\r") or (texto[:1] == "-" and not texto[1:].replace(".", "", 1).isdigit()):
        return "'" + texto
    return texto


def to_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    for fila in rows:
        w.writerow([_safe(x) for x in fila])
    return buf.getvalue()


def statement_csv(title: str, rango: str, secciones: list[tuple[str, list[dict]]], totales: list[tuple[str, str]]) -> str:
    filas: list[list] = [[title, rango], []]
    for nombre, renglones in secciones:
        filas.append([nombre])
        filas.extend([[r["code"], r["name"], r["amount"]] for r in renglones])
        filas.append([])
    filas.extend([[k, "", v] for k, v in totales])
    return to_csv(filas)


