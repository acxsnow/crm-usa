"""Asientos automáticos: la contabilidad se deriva de los documentos que ya
existen, sin tocar sus módulos.

`desired()` calcula, desde cero, qué asiento le corresponde a cada documento.
`sync()` lo compara con lo registrado:
- documento nuevo → asiento nuevo;
- documento cambiado → reversa el anterior y registra el nuevo;
- documento anulado o borrado → reversa.
Correrla dos veces no cambia nada. Un período cerrado no se toca: el movimiento
cae en el primer día abierto, y el documento conserva su fecha en `source_date`.

Criterios (base de causación, los valida el contador):
- Factura emitida: Cuentas por cobrar contra ingresos. Pago: banco o Stripe por
  liquidar contra Cuentas por cobrar; la comisión de Stripe es gasto.
- Factura de proveedor aprobada: gasto o costo contra Cuentas por pagar; lo que
  entró a bodega va a Inventario y pasa a costo cuando sale.
- Gasto aprobado: contra la tarjeta o el banco (según de dónde vino el
  movimiento), o contra reembolsos por pagar si fue dinero propio.
- Nómina y mano de obra no se causan solas: el sistema no calcula ni paga
  nómina, y `warehouse/labor.py` es un costo de gestión. Entran por asiento manual.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.chart import ensure_chart, settings_of
from app.modules.accounting.models import Account, JournalEntry, JournalLine
from app.modules.billing.money import ZERO, to_money
from app.modules.billing.numbering import next_number
from app.modules.field_ops.clock import org_today
from app.shared.audit import record_audit_event

EXPENSE_ACCOUNT = {"fuel": "exp_fuel", "per_diem": "exp_per_diem", "lodging": "exp_lodging", "meals": "exp_meals",
                   "tolls_parking": "exp_tolls", "small_materials": "exp_small_materials", "tools": "exp_tools",
                   "other": "exp_other"}
COST_ACCOUNT = {"equipment": "cogs_equipment", "materials": "cogs_materials", "contractor": "cogs_contractor",
                "permit": "cogs_permit", "services": "cogs_services", "other": "exp_other"}


@dataclass
class Desired:
    key: str
    on: date
    memo: str
    # (cuenta del sistema, débito, crédito, obra)
    lines: list = field(default_factory=list)

    def dr(self, cuenta: str, monto, project_id=None) -> None:
        monto = to_money(monto)
        if monto > ZERO:
            self.lines.append((cuenta, monto, ZERO, project_id))
        elif monto < ZERO:
            self.lines.append((cuenta, ZERO, -monto, project_id))

    def cr(self, cuenta: str, monto, project_id=None) -> None:
        self.dr(cuenta, -to_money(monto), project_id)


def _firma(on: date, lineas) -> tuple:
    """Lo que hace distinto a un asiento: fecha del documento y líneas, sin importar el orden."""
    return on, tuple(sorted((str(c), to_money(d), to_money(h), str(p) if p else "") for c, d, h, p in lineas))


async def _invoices(db, org, out: list) -> None:
    from app.modules.billing.models import DocumentStatus, Invoice, InvoiceKind, InvoicePayment

    for inv in (await db.execute(select(Invoice).where(Invoice.organization_id == org,
                                                       Invoice.document_status == DocumentStatus.issued))).scalars():
        d = Desired(f"invoice:{inv.id}", inv.issue_date or inv.created_at.date(), f"Factura {inv.invoice_number}")
        ingreso = "income_rebate" if inv.kind == InvoiceKind.rebate else "income_particular"
        d.dr("ar", inv.amount)
        d.cr(ingreso, inv.amount, inv.project_id)
        out.append(d)
    filas = await db.execute(select(InvoicePayment, Invoice.invoice_number, Invoice.project_id).join(
        Invoice, Invoice.id == InvoicePayment.invoice_id).where(Invoice.organization_id == org))
    for p, numero, obra in filas.all():
        d = Desired(f"invoice-payment:{p.id}", p.paid_at, f"Pago de la factura {numero}")
        cuenta = "stripe_clearing" if (p.provider or "").startswith("stripe") else "bank"
        d.dr(cuenta, p.amount)
        d.cr("ar", p.amount)
        if p.fee_amount:
            d.dr("exp_merchant_fees", p.fee_amount, obra)
            d.cr("stripe_clearing", p.fee_amount)
        out.append(d)


async def _payables(db, org, out: list) -> None:
    from app.modules.finance.models import SupplierInvoice, SupplierInvoiceLine, SupplierPayment
    from app.modules.warehouse.costing import warehouse_entry_key
    from app.modules.warehouse.models import WarehouseMovement

    en_bodega = set((await db.execute(select(WarehouseMovement.source_key).where(
        WarehouseMovement.organization_id == org, WarehouseMovement.source_key.like("supplier-invoice-line:%")))).scalars())
    facturas = (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == org, SupplierInvoice.status.not_in(("pending_approval", "void"))))).scalars().all()
    lineas: dict = {}
    if facturas:
        for l in (await db.execute(select(SupplierInvoiceLine).where(
                SupplierInvoiceLine.invoice_id.in_([f.id for f in facturas])))).scalars():
            lineas.setdefault(l.invoice_id, []).append(l)
    for f in facturas:
        d = Desired(f"supplier-invoice:{f.id}", f.invoice_date, f"Factura de proveedor {f.number}")
        renglones = lineas.get(f.id, [])
        for l in renglones:
            cuenta = "inventory" if warehouse_entry_key(l.id) in en_bodega else COST_ACCOUNT.get(l.category, "exp_other")
            d.dr(cuenta, l.amount, l.project_id)
        d.dr("exp_purchase_tax", f.tax)
        d.dr("exp_freight", f.shipping)
        if not renglones:  # sin renglones, el total entero va a otros gastos
            d.dr("exp_other", to_money(f.total) - to_money(f.tax) - to_money(f.shipping))
        d.cr("ap", sum((x[1] - x[2] for x in d.lines), ZERO))
        out.append(d)
    for p in (await db.execute(select(SupplierPayment).where(SupplierPayment.organization_id == org))).scalars():
        d = Desired(f"supplier-payment:{p.id}", p.paid_on, f"Pago a proveedor {p.reference or ''}".strip())
        d.dr("ap", p.amount)
        d.cr("credit_card" if p.method == "card" else "bank", p.amount)
        out.append(d)


async def _expenses(db, org, out: list) -> None:
    from app.modules.finance.models import Expense
    from app.modules.payments.models import BankAccount, BankTransaction

    # El gasto que vino de la banca conectada sale de la cuenta real: tarjeta o banco.
    origen = dict((await db.execute(select(BankTransaction.expense_id, BankAccount.type).join(
        BankAccount, BankAccount.id == BankTransaction.account_id).where(
        BankTransaction.organization_id == org, BankTransaction.expense_id.is_not(None)))).all())
    for e in (await db.execute(select(Expense).where(
            Expense.organization_id == org, Expense.status.in_(("approved", "reimbursed"))))).scalars():
        d = Desired(f"expense:{e.id}", e.expense_date, f"Gasto: {e.description}"[:500])
        d.dr(EXPENSE_ACCOUNT.get(e.category, "exp_other"), e.amount, e.project_id)
        if e.payment_method == "company_card":
            d.cr("bank" if origen.get(e.id) == "depository" else "credit_card", e.amount)
        else:
            d.cr("reimbursements", e.amount)
        out.append(d)
        if e.status == "reimbursed" and e.payment_method != "company_card":
            r = Desired(f"expense-reimbursement:{e.id}", e.reimbursed_at or e.expense_date,
                        f"Reembolso: {e.description}"[:500])
            r.dr("reimbursements", e.amount)
            r.cr("bank", e.amount)
            out.append(r)


async def _warehouse(db, org, out: list) -> None:
    from app.modules.warehouse.models import WarehouseItem, WarehouseMovement

    filas = await db.execute(select(WarehouseMovement, WarehouseItem.category, WarehouseItem.unit_cost).join(
        WarehouseItem, WarehouseItem.id == WarehouseMovement.item_id).where(
        WarehouseMovement.organization_id == org,
        WarehouseMovement.movement_type.in_(("entrada", "salida", "devolucion", "ajuste"))))
    for m, categoria, costo_catalogo in filas.all():
        clave = m.source_key or ""
        if clave.startswith("supplier-invoice-line:"):
            continue  # ya entró a Inventario con la factura del proveedor
        costo = m.unit_cost if m.unit_cost is not None else costo_catalogo
        valor = to_money(abs(Decimal(str(m.quantity))) * to_money(costo or ZERO))
        if not valor:
            continue
        d = Desired(f"warehouse:{m.id}", m.movement_date, f"Bodega ({m.movement_type}) {m.reference or ''}".strip())
        consumo = "cogs_equipment" if categoria == "equipment" else "cogs_materials"
        if m.movement_type == "salida":
            d.dr(consumo, valor, m.project_id)
            d.cr("inventory", valor)
        elif m.movement_type == "devolucion":
            d.dr("inventory", valor)
            d.cr(consumo, valor, m.project_id)
        elif m.movement_type == "ajuste":
            contra = "exp_inventory_adjust"
            if Decimal(str(m.quantity)) >= 0:
                d.dr("inventory", valor)
                d.cr(contra, valor)
            else:
                d.dr(contra, valor)
                d.cr("inventory", valor)
        else:  # conteo inicial o entrada a mano: el inventario con el que se arranca
            d.dr("inventory", valor)
            d.cr("opening_equity", valor)
        out.append(d)


async def _extra_charges(db, org, out: list) -> None:
    from app.modules.warehouse.models import ProjectExtraCharge

    for c in (await db.execute(select(ProjectExtraCharge).where(ProjectExtraCharge.organization_id == org))).scalars():
        d = Desired(f"extra-charge:{c.id}", c.charge_date, f"Cobro adicional en obra: {c.description}"[:500])
        d.dr("undeposited", c.amount)
        d.cr("income_extra", c.amount, c.project_id)
        out.append(d)


async def desired(db: AsyncSession, organization_id) -> dict[str, Desired]:
    salida: list[Desired] = []
    for fuente in (_invoices, _payables, _expenses, _warehouse, _extra_charges):
        await fuente(db, organization_id, salida)
    return {d.key: d for d in salida if d.lines}


async def _new_entry(db, org, *, on: date, memo: str, source_key: str | None, source_date: date | None, revision: int,
                     lines: list, reversal_of=None, user_id=None) -> JournalEntry:
    e = JournalEntry(organization_id=org, number=await next_number(db, organization_id=org, series="AS", year=on.year),
                     entry_date=on, memo=memo[:500], source_key=source_key, source_date=source_date, revision=revision,
                     reversal_of_id=reversal_of, created_by_user_id=user_id,
                     lines=[JournalLine(organization_id=org, account_id=a, sort_order=i, debit=d, credit=c, project_id=p,
                                        memo=m) for i, (a, d, c, p, m) in enumerate(lines)])
    db.add(e)
    await db.flush()
    return e


async def reverse(db, entry: JournalEntry, *, on: date, memo: str, user_id=None, revision: int = 1) -> JournalEntry:
    r = await _new_entry(db, entry.organization_id, on=on, memo=memo, source_key=entry.source_key, source_date=None,
                         revision=revision, reversal_of=entry.id, user_id=user_id,
                         lines=[(l.account_id, l.credit, l.debit, l.project_id, l.memo) for l in entry.lines])
    entry.reversed_by_id = r.id
    return r


async def first_open_day(db, organization_id) -> date | None:
    s = await settings_of(db, organization_id)
    return s.locked_through + timedelta(days=1) if s.locked_through else None


async def sync(db: AsyncSession, organization_id) -> dict:
    """Deja la contabilidad al día con los documentos. Devuelve lo que cambió."""
    await ensure_chart(db, organization_id)
    cuentas = dict((await db.execute(select(Account.system_key, Account.id).where(
        Account.organization_id == organization_id, Account.system_key.is_not(None)))).all())
    por_id = {v: k for k, v in cuentas.items()}
    objetivo = await desired(db, organization_id)
    vigentes = {e.source_key: e for e in (await db.execute(select(JournalEntry).where(
        JournalEntry.organization_id == organization_id, JournalEntry.source_key.is_not(None),
        JournalEntry.reversal_of_id.is_(None), JournalEntry.reversed_by_id.is_(None)))).scalars()}
    revisiones = dict((await db.execute(select(JournalEntry.source_key, func.max(JournalEntry.revision)).where(
        JournalEntry.organization_id == organization_id, JournalEntry.source_key.is_not(None))
        .group_by(JournalEntry.source_key))).all())
    hoy = await org_today(db, organization_id)
    abierto = await first_open_day(db, organization_id)

    def en_abierto(dia: date) -> date:
        return max(dia, abierto) if abierto else dia

    nuevos = reversados = 0
    for clave, e in vigentes.items():
        d = objetivo.get(clave)
        actual = _firma(e.source_date, [(por_id.get(l.account_id), l.debit, l.credit, l.project_id) for l in e.lines])
        if d is not None and actual == _firma(d.on, d.lines):
            objetivo.pop(clave)
            continue
        revisiones[clave] = revisiones.get(clave, 1) + 1
        # Anulado: la reversa cae hoy. Corregido: en la fecha del documento, si está abierta.
        await reverse(db, e, on=en_abierto(hoy if d is None else d.on),
                      memo=f"Reversa de {e.number}: {'el documento se anuló o se borró' if d is None else 'el documento cambió'}",
                      revision=revisiones[clave])
        reversados += 1
    for clave, d in objetivo.items():
        revisiones[clave] = revisiones.get(clave, 0) + 1
        await _new_entry(db, organization_id, on=en_abierto(d.on), memo=d.memo, source_key=clave, source_date=d.on,
                         revision=revisiones[clave],
                         lines=[(cuentas[c], de, ha, p, None) for c, de, ha, p in d.lines])
        nuevos += 1
    if nuevos or reversados:
        await record_audit_event(db, organization_id=organization_id, actor_user_id=None, action="accounting.synced",
                                 entity_type="journal", after_data={"posted": nuevos, "reversed": reversados})
    await db.commit()
    return {"posted": nuevos, "reversed": reversados}


async def sync_all(db: AsyncSession) -> int:
    from app.modules.organizations.models import Organization

    hechas = 0
    for org_id in (await db.execute(select(Organization.id))).scalars().all():
        try:
            await sync(db, org_id)
            hechas += 1
        except Exception:  # noqa: BLE001 — una organización con un dato malo no frena a las otras
            await db.rollback()
            import structlog

            structlog.get_logger(__name__).exception("accounting.sync_failed", organization_id=str(org_id))
    return hechas
