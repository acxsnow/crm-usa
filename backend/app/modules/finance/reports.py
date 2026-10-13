"""Reportes de gestión: comercial, operación y finanzas (Flujo Operativo §7).

Los tiempos salen del historial `case_stage_events`, la única fuente de
tiempos y rechazos. Cada reporte devuelve secciones con filas, y la misma
estructura se exporta a CSV.
"""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, money_sum, to_money


def _rango(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    hasta = date_to or date.today()
    desde = date_from or (hasta - timedelta(days=90))
    return (datetime.combine(desde, time.min, tzinfo=timezone.utc),
            datetime.combine(hasta, time.max, tzinfo=timezone.utc))


def business_days(a: datetime, b: datetime) -> int:
    d, fin, n = a.date(), b.date(), 0
    while d < fin:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _avg(valores: list) -> float | None:
    return round(sum(valores) / len(valores), 1) if valores else None


async def _names(db, ids) -> dict:
    from app.modules.users.models import User

    ids = {i for i in ids if i}
    return {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()} \
        if ids else {}


async def commercial(db: AsyncSession, *, organization_id, date_from=None, date_to=None) -> dict:
    from app.modules.cases import stages
    from app.modules.cases.models import VISIT_RESULTS, VISIT_STEP, Case, CaseStageEvent, CaseStepSubmission

    desde, hasta = _rango(date_from, date_to)
    visitas = (await db.execute(select(CaseStepSubmission.answers, CaseStepSubmission.submitted_by_user_id).where(
        CaseStepSubmission.organization_id == organization_id, CaseStepSubmission.step_code == VISIT_STEP,
        CaseStepSubmission.submitted_at >= desde, CaseStepSubmission.submitted_at <= hasta))).all()
    por_resultado: dict = defaultdict(int)
    por_vendedor: dict = defaultdict(lambda: {"visits": 0, "submitted": 0, "approved": 0, "rejected": 0})
    for answers, uid in visitas:
        por_resultado[(answers or {}).get("result", "?")] += 1
        por_vendedor[uid]["visits"] += 1
    etapas = (await db.execute(select(Case.stage_code, func.count()).where(
        Case.organization_id == organization_id).group_by(Case.stage_code))).all()
    eventos = (await db.execute(select(CaseStageEvent).where(
        CaseStageEvent.organization_id == organization_id, CaseStageEvent.occurred_at >= desde,
        CaseStageEvent.occurred_at <= hasta).order_by(CaseStageEvent.occurred_at))).scalars().all()
    casos = {c.id: c for c in (await db.execute(select(Case).where(
        Case.id.in_({e.case_id for e in eventos})))).scalars().all()} if eventos else {}
    # Primer envío de cada caso (de todo el historial, para medir hasta la aprobación).
    envios = {cid: t for cid, t in (await db.execute(select(CaseStageEvent.case_id, func.min(CaseStageEvent.occurred_at))
                                                      .where(CaseStageEvent.organization_id == organization_id,
                                                             CaseStageEvent.to_stage_code == "pending_approval",
                                                             CaseStageEvent.from_stage_code != "pending_approval")
                                                      .group_by(CaseStageEvent.case_id))).all()}
    enviados = aprobados = rechazados = devueltos = 0
    dias_aprobacion, motivos = [], defaultdict(int)
    for e in eventos:
        cambio_etapa = e.from_stage_code != e.to_stage_code
        vend = casos[e.case_id].assigned_salesperson_id if e.case_id in casos else None
        if cambio_etapa and e.to_stage_code == "pending_approval":
            enviados += 1
            por_vendedor[vend]["submitted"] += 1
        if cambio_etapa and e.to_stage_code == "approved":
            aprobados += 1
            por_vendedor[vend]["approved"] += 1
            inicio = envios.get(e.case_id)
            if inicio:
                dias_aprobacion.append(business_days(inicio, e.occurred_at))
        if cambio_etapa and e.to_stage_code == "rejected":
            rechazados += 1
            por_vendedor[vend]["rejected"] += 1
            motivos[(e.reason or "Sin motivo").strip()[:80]] += 1
        if e.to_substatus_code == "returned" and not cambio_etapa:
            devueltos += 1
    nombres = await _names(db, set(por_vendedor))
    return {"title": "Comercial", "range": [desde.date().isoformat(), hasta.date().isoformat()], "kpis": [
        {"label": "Visitas", "value": len(visitas)}, {"label": "Enviados a revisión", "value": enviados},
        {"label": "Aprobados", "value": aprobados}, {"label": "Rechazados", "value": rechazados},
        {"label": "Devueltos al vendedor", "value": devueltos},
        {"label": "Días hábiles promedio hasta aprobación", "value": _avg(dias_aprobacion)},
        {"label": "Tasa de aprobación (aprobados / enviados)",
         "value": f"{round(aprobados / enviados * 100)}%" if enviados else None},
    ], "sections": [
        {"title": "Visitas por resultado", "columns": ["Resultado", "Visitas"],
         "rows": [[VISIT_RESULTS.get(k, k), v] for k, v in sorted(por_resultado.items(), key=lambda x: -x[1])]},
        {"title": "Expedientes por etapa (hoy)", "columns": ["Etapa", "Expedientes"],
         "rows": [[stages.STAGE_LABELS.get(k, k), n] for k, n in sorted(etapas, key=lambda x: -x[1])]},
        {"title": "Por vendedor", "columns": ["Vendedor", "Visitas", "Enviados", "Aprobados", "Rechazados"],
         "rows": [[nombres.get(uid, "Sin vendedor"), v["visits"], v["submitted"], v["approved"], v["rejected"]]
                  for uid, v in sorted(por_vendedor.items(), key=lambda x: -x[1]["visits"])]},
        {"title": "Motivos de rechazo", "columns": ["Motivo", "Veces"],
         "rows": [[m, n] for m, n in sorted(motivos.items(), key=lambda x: -x[1])]},
    ]}


async def operations(db: AsyncSession, *, organization_id, date_from=None, date_to=None) -> dict:
    from app.modules.cases.models import CaseStageEvent
    from app.modules.field_ops.models import Inspection, Project

    desde, hasta = _rango(date_from, date_to)
    proyectos = (await db.execute(select(Project).where(
        Project.organization_id == organization_id, Project.completed_date >= desde.date(),
        Project.completed_date <= hasta.date()))).scalars().all()
    por_semana: dict = defaultdict(int)
    por_tecnico: dict = defaultdict(int)
    for p in proyectos:
        lunes = p.completed_date - timedelta(days=p.completed_date.weekday())
        por_semana[lunes] += 1
        por_tecnico[p.primary_technician_user_id] += 1
    inspecciones = (await db.execute(select(Inspection.result, func.count()).join(Project, Project.id == Inspection.project_id)
                                     .where(Project.organization_id == organization_id,
                                            Inspection.result_recorded_at >= desde,
                                            Inspection.result_recorded_at <= hasta)
                                     .group_by(Inspection.result))).all()
    ins = dict(inspecciones)
    aprob = {cid: t for cid, t in (await db.execute(select(CaseStageEvent.case_id, func.min(CaseStageEvent.occurred_at))
                                                     .where(CaseStageEvent.organization_id == organization_id,
                                                            CaseStageEvent.to_stage_code == "approved")
                                                     .group_by(CaseStageEvent.case_id))).all()}
    instalados = (await db.execute(select(CaseStageEvent.case_id, func.min(CaseStageEvent.occurred_at)).where(
        CaseStageEvent.organization_id == organization_id, CaseStageEvent.to_stage_code == "installed",
        CaseStageEvent.occurred_at >= desde, CaseStageEvent.occurred_at <= hasta).group_by(CaseStageEvent.case_id))).all()
    dias = [business_days(aprob[c], t) for c, t in instalados if c in aprob]
    nombres = await _names(db, set(por_tecnico))
    pasadas, fallidas = ins.get("passed", 0), ins.get("failed", 0)
    return {"title": "Operación", "range": [desde.date().isoformat(), hasta.date().isoformat()], "kpis": [
        {"label": "Instalaciones cerradas", "value": len(proyectos)},
        {"label": "Inspecciones aprobadas", "value": pasadas}, {"label": "Inspecciones fallidas", "value": fallidas},
        {"label": "Aprobación en primera visita del inspector",
         "value": f"{round(pasadas / (pasadas + fallidas) * 100)}%" if pasadas + fallidas else None},
        {"label": "Días hábiles promedio de aprobado a instalado", "value": _avg(dias)},
    ], "sections": [
        {"title": "Instalaciones por semana", "columns": ["Semana (lunes)", "Instalaciones"],
         "rows": [[k.isoformat(), v] for k, v in sorted(por_semana.items())]},
        {"title": "Instalaciones por técnico", "columns": ["Técnico", "Instalaciones"],
         "rows": [[nombres.get(k, "Sin técnico"), v] for k, v in sorted(por_tecnico.items(), key=lambda x: -x[1])]},
    ]}


async def finance(db: AsyncSession, *, organization_id, date_from=None, date_to=None) -> dict:
    from app.modules.billing.models import Invoice, InvoicePayment
    from app.modules.finance.models import EXPENSE_CATEGORIES, Expense, SupplierPayment
    from app.modules.finance.payables import aging

    desde, hasta = _rango(date_from, date_to)
    pagos = (await db.execute(select(InvoicePayment.paid_at, InvoicePayment.amount).join(
        Invoice, Invoice.id == InvoicePayment.invoice_id).where(
        Invoice.organization_id == organization_id, InvoicePayment.paid_at >= desde.date(),
        InvoicePayment.paid_at <= hasta.date()))).all()
    por_mes: dict = defaultdict(lambda: ZERO)
    for fecha, monto in pagos:
        por_mes[fecha.strftime("%Y-%m")] += to_money(monto)
    pagado_prov: dict = defaultdict(lambda: ZERO)
    for fecha, monto in (await db.execute(select(SupplierPayment.paid_on, SupplierPayment.amount).where(
            SupplierPayment.organization_id == organization_id, SupplierPayment.paid_on >= desde.date(),
            SupplierPayment.paid_on <= hasta.date()))).all():
        pagado_prov[fecha.strftime("%Y-%m")] += to_money(monto)
    abiertas = (await db.execute(select(Invoice).where(
        Invoice.organization_id == organization_id, Invoice.document_status != "void"))).scalars().all()
    por_cobrar = money_sum(max(f.balance, ZERO) for f in abiertas)
    gastos = (await db.execute(select(Expense.category, func.sum(Expense.amount)).where(
        Expense.organization_id == organization_id, Expense.status.in_(("approved", "reimbursed")),
        Expense.expense_date >= desde.date(), Expense.expense_date <= hasta.date()).group_by(Expense.category))).all()
    ap = await aging(db, organization_id=organization_id)
    meses = sorted(set(por_mes) | set(pagado_prov))
    return {"title": "Finanzas", "range": [desde.date().isoformat(), hasta.date().isoformat()], "kpis": [
        {"label": "Cobrado en el periodo", "value": str(money_sum(por_mes.values()))},
        {"label": "Pagado a proveedores en el periodo", "value": str(money_sum(pagado_prov.values()))},
        {"label": "Por cobrar (hoy)", "value": str(por_cobrar)},
        {"label": "Por pagar a proveedores (hoy)", "value": ap["totals"]["total"]},
        {"label": "Gastos de campo aprobados", "value": str(money_sum(v for _, v in gastos))},
    ], "sections": [
        {"title": "Cobrado y pagado por mes", "columns": ["Mes", "Cobrado", "Pagado a proveedores", "Neto"],
         "rows": [[m, str(por_mes[m]), str(pagado_prov[m]), str(por_mes[m] - pagado_prov[m])] for m in meses]},
        {"title": "Por pagar por antigüedad", "columns": ["Tramo", "Monto"],
         "rows": [[b["label"], ap["totals"][b["key"]]] for b in ap["buckets"]]},
        {"title": "Gastos de campo por categoría", "columns": ["Categoría", "Monto"],
         "rows": [[EXPENSE_CATEGORIES.get(c, c), str(to_money(v))] for c, v in sorted(gastos, key=lambda x: -x[1])]},
    ]}


REPORTS = {"commercial": commercial, "operations": operations, "finance": finance}


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"Reporte {report['title']}", f"{report['range'][0]} a {report['range'][1]}"])
    w.writerow([])
    for k in report["kpis"]:
        w.writerow([k["label"], k["value"] if k["value"] is not None else ""])
    for s in report["sections"]:
        w.writerow([])
        w.writerow([s["title"]])
        w.writerow(s["columns"])
        for fila in s["rows"]:
            w.writerow(fila)
    return buf.getvalue()


def _dec(v):
    return str(v) if isinstance(v, Decimal) else v
