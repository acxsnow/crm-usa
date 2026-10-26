"""Conciliación bancaria: el extracto del banco contra lo registrado.

Cada movimiento del extracto se cruza con un movimiento registrado del mismo
monto y fecha cercana (±5 días):
- entra dinero (positivo) → pago recibido de una factura (`invoice_payments`:
  cobros a programas y trabajo particular);
- sale dinero (negativo) → pago a proveedor o reembolso de un gasto.
Si hay exactamente un candidato, se concilia solo. Si hay varios o ninguno,
queda para que Contabilidad elija o lo marque como «otro» con una nota.
"""
import csv
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import to_money
from app.modules.finance.models import BankStatement, BankStatementLine, Expense, SupplierPayment
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

WINDOW_DAYS = 5
MATCH_TYPES = {"invoice_payment": "Pago recibido", "supplier_payment": "Pago a proveedor",
               "expense": "Reembolso de gasto"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(texto: str) -> date:
    texto = texto.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    raise ValueError(texto)


def _parse_amount(texto: str) -> Decimal | None:
    t = (texto or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not t:
        return None
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise ValueError(texto) from None
    return to_money(-valor if negativo else valor)


def parse_statement(text: str) -> tuple[list[dict], list[str]]:
    """CSV del banco. Reconoce columnas de fecha, descripción, referencia y monto
    (una columna con signo, o «débito»/«crédito» separadas), en inglés o español."""
    lector = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not lector.fieldnames:
        raise InvalidInputError("El archivo está vacío o no es un CSV.", code="statement_empty")
    cols = {re.sub(r"[^a-z]", "", c.lower()): c for c in lector.fieldnames}
    pick = lambda *opts: next((cols[o] for o in opts if o in cols), None)
    c_fecha = pick("date", "fecha", "postingdate", "transactiondate", "fechaoperacion")
    c_desc = pick("description", "descripcion", "concepto", "memo", "details", "detalle")
    c_ref = pick("reference", "referencia", "checknumber", "check", "ref")
    c_monto = pick("amount", "monto", "importe", "valor")
    c_deb = pick("debit", "debito", "withdrawal", "retiro", "cargo")
    c_cred = pick("credit", "credito", "deposit", "deposito", "abono")
    if not c_fecha or not (c_monto or c_deb or c_cred):
        raise InvalidInputError("El CSV necesita columnas de fecha y monto (o débito/crédito).",
                                code="statement_columns")
    filas, malas = [], []
    for n, f in enumerate(lector, start=2):
        try:
            fecha = _parse_date(f.get(c_fecha) or "")
            if c_monto and (f.get(c_monto) or "").strip():
                monto = _parse_amount(f[c_monto])
            else:
                deb, cred = _parse_amount(f.get(c_deb) or "") if c_deb else None, \
                    _parse_amount(f.get(c_cred) or "") if c_cred else None
                monto = (cred or Decimal("0")) - abs(deb or Decimal("0"))
            if monto is None or monto == 0:
                raise ValueError("sin monto")
        except ValueError:
            malas.append(f"fila {n}")
            continue
        filas.append({"date": fecha, "amount": monto,
                      "description": ((f.get(c_desc) or "") if c_desc else "").strip()[:500] or "(sin descripción)",
                      "reference": ((f.get(c_ref) or "") if c_ref else "").strip()[:120] or None})
    if len(filas) > 5000:
        raise InvalidInputError("Máximo 5.000 movimientos por extracto.", code="statement_too_long")
    return filas, malas


async def _matched_ids(db, organization_id, kind: str) -> set:
    return set((await db.execute(select(BankStatementLine.matched_id).where(
        BankStatementLine.organization_id == organization_id, BankStatementLine.matched_type == kind,
        BankStatementLine.status == "matched"))).scalars().all())


async def candidates(db, organization_id, line: BankStatementLine) -> list[dict]:
    """Movimientos registrados que podrían ser esta línea del banco."""
    from app.modules.billing.models import Invoice, InvoicePayment

    desde, hasta = line.line_date - timedelta(days=WINDOW_DAYS), line.line_date + timedelta(days=WINDOW_DAYS)
    monto = abs(to_money(line.amount))
    salida = []
    if line.amount > 0:
        usados = await _matched_ids(db, organization_id, "invoice_payment")
        filas = (await db.execute(select(InvoicePayment, Invoice).join(Invoice, Invoice.id == InvoicePayment.invoice_id)
                                  .where(Invoice.organization_id == organization_id, InvoicePayment.amount == monto,
                                         InvoicePayment.paid_at >= desde, InvoicePayment.paid_at <= hasta))).all()
        for p, inv in filas:
            if p.id not in usados:
                salida.append({"type": "invoice_payment", "id": str(p.id), "date": p.paid_at.isoformat(),
                               "amount": str(to_money(p.amount)),
                               "label": f"Pago de la factura {inv.invoice_number or ''}".strip()})
    else:
        usados = await _matched_ids(db, organization_id, "supplier_payment")
        from app.modules.finance.models import Supplier

        filas = (await db.execute(select(SupplierPayment, Supplier).join(Supplier, Supplier.id == SupplierPayment.supplier_id)
                                  .where(SupplierPayment.organization_id == organization_id,
                                         SupplierPayment.amount == monto, SupplierPayment.paid_on >= desde,
                                         SupplierPayment.paid_on <= hasta))).all()
        for p, s in filas:
            if p.id not in usados:
                salida.append({"type": "supplier_payment", "id": str(p.id), "date": p.paid_on.isoformat(),
                               "amount": str(to_money(p.amount)), "label": f"Pago a {s.name}"})
        usados_g = await _matched_ids(db, organization_id, "expense")
        gastos = (await db.execute(select(Expense).where(
            Expense.organization_id == organization_id, Expense.status == "reimbursed", Expense.amount == monto,
            Expense.reimbursed_at >= desde, Expense.reimbursed_at <= hasta))).scalars().all()
        for g in gastos:
            if g.id not in usados_g:
                salida.append({"type": "expense", "id": str(g.id), "date": g.reimbursed_at.isoformat(),
                               "amount": str(to_money(g.amount)), "label": f"Reembolso: {g.description[:60]}"})
    # Primero la fecha más cercana.
    return sorted(salida, key=lambda c: abs((date.fromisoformat(c["date"]) - line.line_date).days))


async def import_statement(db: AsyncSession, *, organization_id, user, account_label: str, filename: str | None,
                           text: str) -> dict:
    filas, malas = parse_statement(text)
    if not filas:
        raise InvalidInputError("No encontré movimientos válidos en el archivo.", code="statement_empty")
    filas, repetidas = await _sin_repetidas(db, organization_id, (account_label or "Cuenta principal").strip()[:120],
                                            filas)
    if not filas:
        raise ConflictError("Ese extracto ya estaba importado: todos sus movimientos ya están en la cuenta.",
                            code="statement_already_imported")
    st = BankStatement(organization_id=organization_id, account_label=(account_label or "Cuenta principal").strip()[:120],
                       original_filename=filename, period_start=min(f["date"] for f in filas),
                       period_end=max(f["date"] for f in filas), imported_by_user_id=user.id)
    db.add(st)
    await db.flush()
    lineas = [BankStatementLine(organization_id=organization_id, statement_id=st.id, line_date=f["date"],
                                description=f["description"], reference=f["reference"], amount=f["amount"],
                                status="unmatched") for f in filas]
    db.add_all(lineas)
    await db.flush()
    auto = 0
    for l in lineas:
        cands = await candidates(db, organization_id, l)
        if len(cands) == 1:
            l.status, l.matched_type, l.matched_id = "matched", cands[0]["type"], uuid.UUID(cands[0]["id"])
            l.matched_at, l.auto_matched = _now(), True
            await db.flush()
            auto += 1
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="reconciliation.statement_imported", entity_type="bank_statement",
                             entity_id=str(st.id), after_data={"lines": len(lineas), "auto_matched": auto})
    await db.commit()
    return {"statement_id": str(st.id), "lines": len(lineas), "auto_matched": auto, "invalid": malas[:20],
            "duplicated": repetidas}


async def _sin_repetidas(db: AsyncSession, organization_id, cuenta: str, filas: list[dict]) -> tuple[list[dict], int]:
    """Quita los movimientos que ya entraron en otro extracto de la misma
    cuenta (D-017: importar el mismo archivo dos veces duplicaba todo).

    Se cuenta por ocurrencias y no por fila: dos compras iguales el mismo día
    son dos movimientos, y un extracto que se solapa con el anterior solo
    agrega lo que le falta."""
    from collections import Counter

    def clave(fecha, descripcion, referencia, monto):
        return fecha, (descripcion or "").strip(), (referencia or "").strip(), to_money(monto)

    ya = Counter(clave(*f) for f in (await db.execute(
        select(BankStatementLine.line_date, BankStatementLine.description, BankStatementLine.reference,
               BankStatementLine.amount)
        .join(BankStatement, BankStatement.id == BankStatementLine.statement_id)
        .where(BankStatementLine.organization_id == organization_id,
               BankStatement.account_label == cuenta))).all())
    nuevas, repetidas = [], 0
    for f in filas:
        k = clave(f["date"], f["description"], f["reference"], f["amount"])
        if ya[k] > 0:
            ya[k] -= 1
            repetidas += 1
        else:
            nuevas.append(f)
    return nuevas, repetidas


async def get_line(db, organization_id, line_id) -> BankStatementLine:
    l = await db.get(BankStatementLine, line_id)
    if l is None or l.organization_id != organization_id:
        raise NotFoundError("El movimiento no existe.", code="bank_line_not_found")
    return l


async def match_line(db, *, organization_id, user, line_id, matched_type: str, matched_id) -> BankStatementLine:
    l = await get_line(db, organization_id, line_id)
    if l.status == "matched":
        raise ConflictError("Ese movimiento ya está conciliado; deshazlo primero.", code="bank_line_matched")
    validos = {(c["type"], c["id"]) for c in await candidates(db, organization_id, l)}
    if (matched_type, str(matched_id)) not in validos:
        raise InvalidInputError("Ese registro no corresponde al movimiento (monto, fecha o ya conciliado).",
                                code="bank_match_invalid")
    l.status, l.matched_type, l.matched_id = "matched", matched_type, uuid.UUID(str(matched_id))
    l.matched_by_user_id, l.matched_at, l.auto_matched = user.id, _now(), False
    await db.commit()
    await db.refresh(l)
    return l


async def ignore_line(db, *, organization_id, user, line_id, notes: str) -> BankStatementLine:
    l = await get_line(db, organization_id, line_id)
    if not (notes or "").strip():
        raise InvalidInputError("Escribe qué es el movimiento (comisión bancaria, traspaso…).", code="notes_required")
    l.status, l.notes, l.matched_type, l.matched_id = "ignored", notes.strip()[:500], None, None
    l.matched_by_user_id, l.matched_at = user.id, _now()
    await db.commit()
    await db.refresh(l)
    return l


async def unmatch_line(db, *, organization_id, user, line_id) -> BankStatementLine:
    l = await get_line(db, organization_id, line_id)
    l.status, l.matched_type, l.matched_id, l.notes, l.auto_matched = "unmatched", None, None, None, False
    l.matched_by_user_id, l.matched_at = None, None
    await db.commit()
    await db.refresh(l)
    return l


async def summary(db, organization_id) -> dict:
    lineas = (await db.execute(select(BankStatementLine.status, BankStatementLine.amount).where(
        BankStatementLine.organization_id == organization_id))).all()
    cuenta = {"unmatched": 0, "matched": 0, "ignored": 0}
    for st, _ in lineas:
        cuenta[st] = cuenta.get(st, 0) + 1
    return {"lines": len(lineas), **cuenta}


def line_out(l: BankStatementLine) -> dict:
    return {"id": str(l.id), "statement_id": str(l.statement_id), "date": l.line_date.isoformat(),
            "description": l.description, "reference": l.reference, "amount": str(to_money(l.amount)),
            "status": l.status, "matched_type": l.matched_type,
            "matched_label": MATCH_TYPES.get(l.matched_type) if l.matched_type else None,
            "matched_id": str(l.matched_id) if l.matched_id else None, "auto_matched": l.auto_matched,
            "notes": l.notes}
