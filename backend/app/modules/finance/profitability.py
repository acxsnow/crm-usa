"""Rentabilidad por proyecto (Flujo Operativo §4.5).

- **Esperado:** lo facturado al proyecto (cobros a programas y trabajo
  particular), sin facturas anuladas.
- **Cobrado:** los pagos recibidos de esas facturas.
- **Costos:** líneas de facturas de proveedor asignadas al proyecto (con su
  parte proporcional de impuestos y envío) y gastos de campo aprobados del
  proyecto.
- **Margen** = cobrado − costos; **margen esperado** = esperado − costos.
La comisión del vendedor queda fuera hasta que el cliente diga cómo se calcula.
"""
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, money_sum, to_money
from app.modules.finance.models import COST_CATEGORIES, Expense, SupplierInvoice, SupplierInvoiceLine

COST_KEYS = list(COST_CATEGORIES) + ["field_expenses"]
COST_LABELS = {**COST_CATEGORIES, "field_expenses": "Gastos de campo"}
# Lo que se compró para la obra con un gasto (material menor, herramienta) suma
# como material; lo demás (gasolina, comida, hotel...) queda en gastos de campo.
EXPENSE_COST_KEY = {"small_materials": "materials", "tools": "materials"}


def _spread(total_extra: Decimal, partes: list[Decimal]) -> list[Decimal]:
    """Reparte impuestos y envío en proporción a cada línea, sin perder centavos."""
    base = money_sum(partes)
    if total_extra == ZERO or base == ZERO:
        return [ZERO for _ in partes]
    repartos = [(total_extra * p / base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for p in partes]
    repartos[-1] += total_extra - money_sum(repartos)
    return repartos


async def project_costs(db: AsyncSession, organization_id, project_ids: set, *,
                        exclude_line_ids: set | None = None) -> dict:
    """{project_id: {categoría: Decimal}} para los proyectos dados.

    `exclude_line_ids` deja fuera líneas concretas: lo usa el costo real del
    proyecto (bodega) para no contar dos veces el material que entró a bodega
    (decisión D-BOD-2), porque ese costo llega cuando el material sale.
    """
    costos: dict = {pid: {k: ZERO for k in COST_KEYS} for pid in project_ids}
    if not project_ids:
        return costos
    facturas = (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == organization_id, SupplierInvoice.status != "void",
        SupplierInvoice.id.in_(select(SupplierInvoiceLine.invoice_id).where(
            SupplierInvoiceLine.project_id.in_(project_ids)))))).scalars().all()
    for inv in facturas:
        extra = to_money(inv.tax) + to_money(inv.shipping)
        lineas = [l for l in inv.lines if exclude_line_ids is None or l.id not in exclude_line_ids]
        if not lineas:
            continue
        repartos = _spread(extra, [to_money(l.amount) for l in lineas])
        for l, r in zip(lineas, repartos):
            if l.project_id in costos:
                cat = l.category if l.category in COST_CATEGORIES else "other"
                costos[l.project_id][cat] += to_money(l.amount) + r
    gastos = (await db.execute(select(Expense).where(
        Expense.organization_id == organization_id, Expense.project_id.in_(project_ids),
        Expense.status.in_(("approved", "reimbursed"))))).scalars().all()
    for g in gastos:
        costos[g.project_id][EXPENSE_COST_KEY.get(g.category, "field_expenses")] += to_money(g.amount)
    return costos


async def report(db: AsyncSession, *, organization_id, date_from: date | None = None, date_to: date | None = None,
                 program_id=None, project_id=None) -> dict:
    from app.modules.billing.models import Invoice
    from app.modules.cases.models import Case, Program
    from app.modules.field_ops.models import Project

    stmt = select(Project).where(Project.organization_id == organization_id)
    if project_id:
        stmt = stmt.where(Project.id == project_id)
    if date_from:
        stmt = stmt.where(Project.completed_date >= date_from)
    if date_to:
        stmt = stmt.where(Project.completed_date <= date_to)
    if program_id:
        stmt = stmt.where(Project.case_id.in_(select(Case.id).where(Case.program_id == program_id)))
    proyectos = (await db.execute(stmt.order_by(Project.completed_date.desc().nulls_last()).limit(1000))).scalars().all()
    ids = {p.id for p in proyectos}
    # Mismo costo que el panel «Costo del trabajo» (spec 2026-10-22): el costo
    # real completo (bodega, compras, gastos y lo anotado a mano) y el ingreso
    # facturado más cobros adicionales. Ojo con los nombres: aquí `margin` es
    # **cobrado** − costo (lo que de verdad entró a caja) y `expected_margin` es
    # facturado − costo, que es lo que el panel llama «Ganancia».
    from app.modules.warehouse.budgets import budget_lines_of, budget_totals, current_budgets, estimate_summary
    from app.modules.warehouse.costing import ACTUAL_LABELS, project_actual_costs, project_revenue

    ingresos = await project_revenue(db, organization_id, ids)
    esperado: dict = {pid: to_money(i["invoiced"] + i["extras"]) for pid, i in ingresos.items()}
    cobrado: dict = {pid: to_money(i["collected"] + i["extras_received"]) for pid, i in ingresos.items()}
    costos = await project_actual_costs(db, organization_id, ids)
    # El margen estimado de cada obra, en lote: una consulta de presupuestos y una de renglones.
    vigentes = await current_budgets(db, organization_id, ids)
    renglones = await budget_lines_of(db, organization_id, [b.id for b in vigentes.values()])
    margen_estimado: dict = {
        pid: estimate_summary(b, budget_totals(renglones.get(b.id, []))["total"], None,
                              fallback_revenue=esperado.get(pid))["expected_margin_pct"]
        for pid, b in vigentes.items()}
    casos = {c.id: c for c in (await db.execute(select(Case).where(
        Case.id.in_({p.case_id for p in proyectos if p.case_id})))).scalars().all()} if proyectos else {}
    programas = {p.id: p.name for p in (await db.execute(select(Program).where(
        Program.organization_id == organization_id))).scalars().all()}
    filas = []
    tot = {"expected": ZERO, "collected": ZERO, "costs": ZERO, **{k: ZERO for k in ACTUAL_LABELS}}
    for p in proyectos:
        c = costos[p.id]
        total_costos = money_sum(c.values())
        caso = casos.get(p.case_id)
        margen = cobrado[p.id] - total_costos
        filas.append({
            "project_id": str(p.id), "title": p.title, "status": str(getattr(p.status, "value", p.status)),
            "completed_date": p.completed_date.isoformat() if p.completed_date else None,
            "case_number": caso.case_number if caso else None,
            "program": programas.get(caso.program_id) if caso and caso.program_id else None,
            "expected": str(esperado[p.id]), "collected": str(cobrado[p.id]), "costs": str(total_costos),
            "cost_breakdown": {k: str(v) for k, v in c.items()},
            "margin": str(margen), "expected_margin": str(esperado[p.id] - total_costos),
            "estimated_margin_pct": margen_estimado.get(p.id),
            "margin_pct": float((margen / cobrado[p.id] * 100).quantize(Decimal("0.1"))) if cobrado[p.id] > 0 else None,
        })
        tot["expected"] += esperado[p.id]
        tot["collected"] += cobrado[p.id]
        tot["costs"] += total_costos
        for k, v in c.items():
            tot[k] += v
    margen_total = tot["collected"] - tot["costs"]
    return {
        "cost_labels": ACTUAL_LABELS, "rows": filas,
        "totals": {**{k: str(v) for k, v in tot.items()}, "margin": str(margen_total),
                   "expected_margin": str(tot["expected"] - tot["costs"]),
                   "margin_pct": float((margen_total / tot["collected"] * 100).quantize(Decimal("0.1")))
                   if tot["collected"] > 0 else None, "projects": len(filas)},
    }


def parse_uuid(v):
    return uuid.UUID(str(v)) if v else None
