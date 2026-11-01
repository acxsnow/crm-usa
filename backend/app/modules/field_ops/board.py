"""Tablero de despacho (como el «Dispatch» de Housecall Pro): una fila por
técnico y una columna por día, con sus obras y su turno de la malla, más la
bandeja de obras sin agendar.

Solo lee. Mover o asignar una obra usa la ruta de siempre
(`PATCH /projects/{id}/schedule`), con sus reglas: no se agenda en el pasado,
el técnico debe poder instalar y las salidas de bodega siguen al técnico.
"""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field_ops.clock import org_today
from app.modules.field_ops.installation import CLOSED_STATUSES, days_late, list_installers
from app.modules.field_ops.models import Project, ProjectStatus
from app.shared.datetime_utils import as_utc
from app.shared.errors import InvalidInputError

MAX_DAYS = 31
MAX_UNSCHEDULED = 200


def _job(p: Project, case, hoy: date) -> dict:
    return {"project_id": str(p.id), "title": p.title, "status": p.status.value if hasattr(p.status, "value")
            else str(p.status), "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
            "technician_id": str(p.primary_technician_user_id) if p.primary_technician_user_id else None,
            "address": ", ".join(x for x in (p.address_street, p.address_unit, p.address_city) if x) or None,
            "case_number": case.case_number if case else None, "days_late": days_late(p, hoy)}


async def board(db: AsyncSession, *, organization_id, date_from: date, date_to: date) -> dict:
    from app.modules.attendance.models import WorkShift
    from app.modules.cases.models import Case

    if date_to < date_from:
        raise InvalidInputError("La fecha final es anterior a la inicial.", code="agenda_range_inverted")
    if (date_to - date_from).days >= MAX_DAYS:
        raise InvalidInputError(f"El tablero se ve en rangos de hasta {MAX_DAYS} días.", code="agenda_range_too_long")
    hoy = await org_today(db, organization_id)
    dias = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
    tecnicos = await list_installers(db, organization_id=organization_id)

    agendadas = (await db.execute(select(Project, Case).outerjoin(Case, Case.id == Project.case_id).where(
        Project.organization_id == organization_id, Project.scheduled_date >= date_from,
        Project.scheduled_date <= date_to, Project.status != ProjectStatus.cancelled)
        .order_by(Project.scheduled_date, Project.created_at))).all()
    por_tecnico: dict = defaultdict(lambda: defaultdict(list))
    for p, case in agendadas:
        clave = str(p.primary_technician_user_id) if p.primary_technician_user_id else "none"
        por_tecnico[clave][p.scheduled_date.isoformat()].append(_job(p, case, hoy))

    turnos: dict = defaultdict(lambda: defaultdict(list))
    for t in (await db.execute(select(WorkShift).where(
            WorkShift.organization_id == organization_id, WorkShift.shift_date >= date_from,
            WorkShift.shift_date <= date_to, WorkShift.status == "scheduled"))).scalars().all():
        turnos[str(t.user_id)][t.shift_date.isoformat()].append(
            {"starts_at": as_utc(t.starts_at).isoformat(), "ends_at": as_utc(t.ends_at).isoformat()})

    sin_agendar = (await db.execute(select(Project, Case).outerjoin(Case, Case.id == Project.case_id).where(
        Project.organization_id == organization_id, Project.status.not_in(CLOSED_STATUSES),
        (Project.scheduled_date.is_(None)) | (Project.primary_technician_user_id.is_(None)))
        .order_by(Project.created_at).limit(MAX_UNSCHEDULED))).all()

    filas = [{"id": str(u.id), "name": u.full_name, "jobs": dict(por_tecnico.get(str(u.id), {})),
              "shifts": dict(turnos.get(str(u.id), {}))} for u in tecnicos]
    return {"days": [d.isoformat() for d in dias], "today": hoy.isoformat(), "technicians": filas,
            "unassigned_in_range": dict(por_tecnico.get("none", {})),
            "unscheduled": [_job(p, case, hoy) for p, case in sin_agendar]}
