"""Tablero de cobros, cuentas por cobrar (spec D6.10).

Se calcula al leer, con la fecha de la organización: no hay estados guardados
que se desincronicen. Cinco grupos:

- **Por cobrar**: instalaciones con el acta confirmada que todavía no tienen
  ningún cobro. Alerta desde el día siguiente a la confirmación (el ciclo
  diario del cliente).
- **Por radicar**: cobros creados sin radicar, con si su checklist está
  completo. Alerta desde el día siguiente.
- **Radicados**: días desde la última radicación; alerta al pasar los días
  esperados de pago del programa.
- **Rechazados en corrección**: días desde el rechazo.
- **Por programa**: pagado este mes y esperado (radicado y por radicar).
- **Particular**: facturas vencidas y por vencer.
"""
import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing import program_config
from app.modules.billing.claims import claim_checklist
from app.modules.billing.models import (
    BillingProgramProfile,
    ClaimStatus,
    DocumentStatus,
    Invoice,
    InvoiceKind,
    RebateClaim,
)
from app.modules.billing.money import ZERO, money_sum
from app.modules.billing.service import DUE_SOON_DAYS
from app.modules.cases.models import Case
from app.modules.crm.models import Customer
from app.modules.field_ops.clock import local_date, org_today, org_zone
from app.modules.field_ops.models import Project, ProjectStatus

DEFAULT_PAYMENT_DAYS = 45
CLOSED_STAGES = {"paid", "closed"}


async def billing_dashboard(db: AsyncSession, *, organization_id: uuid.UUID) -> dict:
    hoy = await org_today(db, organization_id)
    zona = await org_zone(db, organization_id)
    cobros = list(
        (
            await db.execute(
                select(RebateClaim).where(RebateClaim.organization_id == organization_id)
                .order_by(RebateClaim.created_at)
            )
        ).scalars().all()
    )
    dias_pago = {
        p.program_id: p.expected_payment_days
        for p in (
            await db.execute(select(BillingProgramProfile).where(
                BillingProgramProfile.organization_id == organization_id))
        ).scalars().all()
    }
    contexto = await project_context(db, organization_id, {c.project_id for c in cobros})

    por_radicar, radicados, rechazados, pagados = [], [], [], []
    for c in cobros:
        if c.status == ClaimStatus.preparing:
            dias = max((hoy - local_date(c.created_at, zona)).days, 0)
            requisitos = await claim_checklist(db, claim=c)
            por_radicar.append({**_item(c, contexto), "days": dias, "alert": dias >= 1,
                                "ready_to_submit": all(r["met"] for r in requisitos),
                                "pending_requirements": sum(1 for r in requisitos if not r["met"])})
        elif c.status == ClaimStatus.submitted:
            desde = c.attempts[-1].submitted_on if c.attempts else local_date(c.created_at, zona)
            dias = (hoy - desde).days
            umbral = dias_pago.get(c.program_id, DEFAULT_PAYMENT_DAYS)
            radicados.append({**_item(c, contexto), "days": dias, "alert": dias > umbral,
                              "expected_payment_days": umbral, "submitted_on": desde})
        elif c.status == ClaimStatus.rejected:
            intento = c.attempts[-1] if c.attempts else None
            desde = (intento.resolved_on if intento and intento.resolved_on else local_date(c.updated_at, zona))
            rechazados.append({**_item(c, contexto), "days": (hoy - desde).days, "alert": True,
                               "rejection_reason": intento.rejection_reason if intento else None,
                               "rejection_category": intento.rejection_category if intento else None})
        elif c.status == ClaimStatus.paid and c.paid_on and (c.paid_on.year, c.paid_on.month) == (hoy.year, hoy.month):
            pagados.append({**_item(c, contexto), "days": (hoy - c.paid_on).days, "alert": False,
                            "paid_on": c.paid_on, "paid_amount": c.paid_amount, "difference": c.difference})

    radicados.sort(key=lambda i: -i["days"])
    rechazados.sort(key=lambda i: -i["days"])

    return {
        "today": hoy,
        "to_create": await _to_create(db, organization_id, hoy, zona, cobros),
        "to_submit": por_radicar,
        "submitted": radicados,
        "rejected": rechazados,
        "paid_this_month": sorted(pagados, key=lambda i: i["paid_on"], reverse=True),
        "aging": _aging(cobros, hoy, zona),
        "by_program": await _by_program(db, organization_id, hoy, cobros),
        "particular": await _particular(db, organization_id, hoy),
    }


# ---------------------------------------------------------------------------

AGING_BUCKETS = (("d0_30", 0, 30), ("d31_45", 31, 45), ("d46_plus", 46, None))


def _aging(cobros: list[RebateClaim], hoy: date, zona) -> dict:
    """Lo que los programas deben, por antigüedad desde que se emitió la
    factura del cobro (cuentas por cobrar). Solo cobros abiertos."""
    tramos = {nombre: ZERO for nombre, _, _ in AGING_BUCKETS}
    for c in cobros:
        if not c.is_open:
            continue
        factura = c.invoice
        desde = factura.issue_date if factura and factura.issue_date else local_date(c.created_at, zona)
        dias = max((hoy - desde).days, 0)
        for nombre, minimo, maximo in AGING_BUCKETS:
            if dias >= minimo and (maximo is None or dias <= maximo):
                tramos[nombre] = money_sum([tramos[nombre], c.amount])
                break
    return {**tramos, "open_total": money_sum(tramos.values())}


async def _to_create(db, organization_id, hoy: date, zona, cobros: list[RebateClaim]) -> list[dict]:
    """Actas confirmadas sin ningún cobro vivo (y expediente sin cerrar)."""
    con_cobro = {c.project_id for c in cobros if c.status != ClaimStatus.withdrawn}
    proyectos = [
        p for p in (
            await db.execute(select(Project).where(Project.organization_id == organization_id,
                                                   Project.status == ProjectStatus.completed))
        ).scalars().all()
        if p.technician_info_confirmed and p.id not in con_cobro
    ]
    contexto = await project_context(db, organization_id, {p.id for p in proyectos})
    items = []
    for p in proyectos:
        datos = contexto[p.id]
        if datos["stage"] in CLOSED_STAGES:
            continue
        confirmada = next((local_date(r.created_at, zona) for r in reversed(p.reviews) if r.action == "confirmed"), hoy)
        dias = max((hoy - confirmada).days, 0)
        items.append({**_project_fields(p.id, contexto), "confirmed_on": confirmada, "days": dias,
                      "alert": dias >= 1, "installation_date": p.completed_date})
    items.sort(key=lambda i: -i["days"])
    return items


async def _by_program(db, organization_id, hoy: date, cobros: list[RebateClaim]) -> list[dict]:
    pagado, esperado, radicados = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), defaultdict(int)
    for c in cobros:
        if c.status == ClaimStatus.paid and c.paid_on and (c.paid_on.year, c.paid_on.month) == (hoy.year, hoy.month):
            pagado[c.program_id] = money_sum([pagado[c.program_id], c.paid_amount])
        elif c.status in (ClaimStatus.preparing, ClaimStatus.submitted, ClaimStatus.rejected):
            esperado[c.program_id] = money_sum([esperado[c.program_id], c.amount])
            if c.status == ClaimStatus.submitted:
                radicados[c.program_id] += 1
    filas = []
    for programa in await program_config.list_programs(db, organization_id=organization_id):
        if programa.id not in pagado and programa.id not in esperado:
            continue
        filas.append({"program_id": programa.id, "program_code": programa.code, "program_name": programa.name,
                      "paid_this_month": pagado[programa.id], "expected": esperado[programa.id],
                      "submitted_count": radicados[programa.id]})
    return filas


async def _particular(db, organization_id, hoy: date) -> dict:
    facturas = [
        i for i in (
            await db.execute(select(Invoice).where(Invoice.organization_id == organization_id,
                                                   Invoice.kind == InvoiceKind.particular,
                                                   Invoice.document_status == DocumentStatus.issued))
        ).scalars().all()
    ]
    vencidas = [i for i in facturas if i.payment_status_on(hoy) == "overdue"]
    por_vencer = [
        i for i in facturas
        if i.payment_status_on(hoy) in ("unpaid", "partial") and i.due_date
        and (i.due_date - hoy).days <= DUE_SOON_DAYS
    ]
    borradores = (
        await db.execute(select(Invoice.id).where(Invoice.organization_id == organization_id,
                                                  Invoice.kind == InvoiceKind.particular,
                                                  Invoice.document_status == DocumentStatus.draft))
    ).scalars().all()
    return {
        "overdue_count": len(vencidas),
        "overdue_total": money_sum(i.balance for i in vencidas),
        "due_soon_count": len(por_vencer),
        "due_soon_total": money_sum(i.balance for i in por_vencer),
        "outstanding_total": money_sum(max(i.balance, ZERO) for i in facturas),
        "draft_count": len(borradores),
    }


async def project_context(db, organization_id, project_ids: set) -> dict:
    """Cliente, dirección y expediente de cada proyecto, en tres consultas.
    Lo usan también las respuestas de cobro (`claims_router`)."""
    if not project_ids:
        return {}
    proyectos = (
        await db.execute(select(Project).where(Project.organization_id == organization_id,
                                               Project.id.in_(project_ids)))
    ).scalars().all()
    clientes = {
        c.id: c.legal_name for c in (
            await db.execute(select(Customer).where(Customer.id.in_({p.customer_id for p in proyectos})))
        ).scalars().all()
    }
    casos = {
        c.id: c for c in (
            await db.execute(select(Case).where(Case.id.in_({p.case_id for p in proyectos if p.case_id})))
        ).scalars().all()
    }
    return {
        p.id: {
            "customer_name": clientes.get(p.customer_id),
            "address": ", ".join(x for x in (p.address_street, p.address_unit, p.address_city) if x) or p.title,
            "case_id": p.case_id,
            "case_number": casos[p.case_id].case_number if p.case_id in casos else None,
            "stage": casos[p.case_id].stage_code if p.case_id in casos else None,
        }
        for p in proyectos
    }


def _project_fields(project_id, contexto) -> dict:
    datos = contexto.get(project_id, {})
    return {"project_id": project_id, "customer_name": datos.get("customer_name"),
            "address": datos.get("address"), "case_id": datos.get("case_id"),
            "case_number": datos.get("case_number")}


def _item(c: RebateClaim, contexto) -> dict:
    return {**_project_fields(c.project_id, contexto), "claim_id": c.id, "program_id": c.program_id,
            "program_code": c.program.code, "program_name": c.program.name, "amount": c.amount}
