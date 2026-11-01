"""Mano de obra por técnico desde las horas aprobadas (como el «job costing»
de Housecall Pro).

- Cada técnico tiene una tarifa por hora (`LaborRate`); quien no tiene tarifa
  no suma por horas (por ejemplo, a quien se le paga por trabajo y ya se anota
  a mano en el costo).
- Las horas de una obra salen de las marcas del turno: desde «en camino» o
  «llegué» a esa obra hasta «salí de la obra» (o hasta la siguiente obra, o el
  fin del turno). El viaje cuenta, como en Housecall Pro.
- Solo cuentan los turnos **aprobados**; si lo aprobado es menos que lo
  marcado en obras, se reparte en proporción.
- El resultado suma a «Mano de obra» en el costo real de la obra.
"""
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.warehouse.models import LaborRate
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import InvalidInputError, NotFoundError

STARTS = {"en_route", "arrived"}
MAX_RATE = Decimal("1000")


async def rates(db: AsyncSession, organization_id) -> dict:
    return {r.user_id: r.hourly_rate for r in (await db.execute(select(LaborRate).where(
        LaborRate.organization_id == organization_id))).scalars().all()}


async def list_rates(db: AsyncSession, organization_id) -> list[dict]:
    """Los técnicos activos con su tarifa (vacía si no tiene)."""
    from app.modules.field_ops.installation import list_installers

    tarifas = await rates(db, organization_id)
    return [{"user_id": str(u.id), "name": u.full_name,
             "hourly_rate": str(tarifas[u.id]) if u.id in tarifas else None}
            for u in await list_installers(db, organization_id=organization_id)]


async def set_rate(db: AsyncSession, *, organization_id, user, user_id, hourly_rate: Decimal | None) -> dict:
    from app.modules.users.models import User

    persona = await db.get(User, user_id)
    if persona is None or persona.organization_id != organization_id:
        raise NotFoundError("La persona no existe.", code="user_not_found")
    fila = (await db.execute(select(LaborRate).where(LaborRate.organization_id == organization_id,
                                                     LaborRate.user_id == user_id))).scalar_one_or_none()
    antes = str(fila.hourly_rate) if fila else None
    if hourly_rate is None:
        if fila is not None:
            await db.delete(fila)
    else:
        valor = to_money(hourly_rate)
        if valor <= 0 or valor > MAX_RATE:
            raise InvalidInputError("La tarifa por hora debe ser mayor que cero y razonable.", code="invalid_rate")
        if fila is None:
            fila = LaborRate(organization_id=organization_id, user_id=user_id, hourly_rate=valor)
            db.add(fila)
        fila.hourly_rate = valor
        fila.updated_by_user_id = user.id
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="jobcost.labor_rate_set", entity_type="User", entity_id=str(user_id),
                             before_data={"hourly_rate": antes},
                             after_data={"hourly_rate": str(hourly_rate) if hourly_rate is not None else None})
    await db.commit()
    return {"user_id": str(user_id), "name": persona.full_name,
            "hourly_rate": str(to_money(hourly_rate)) if hourly_rate is not None else None}


def _intervals(eventos, fin_turno: datetime | None) -> dict:
    """{project_id: minutos} de un turno, a partir de sus marcas de obra en orden."""
    minutos: dict = defaultdict(float)
    actual, desde = None, None
    for ev in eventos:
        momento = as_utc(ev.occurred_at)
        if ev.event_type in STARTS:
            if actual is not None and actual != ev.project_id:
                minutos[actual] += (momento - desde).total_seconds() / 60
                actual, desde = None, None
            if actual is None:
                actual, desde = ev.project_id, momento
        elif ev.event_type == "left_site" and actual is not None:
            minutos[actual] += (momento - desde).total_seconds() / 60
            actual, desde = None, None
    if actual is not None and fin_turno is not None:
        minutos[actual] += (as_utc(fin_turno) - desde).total_seconds() / 60
    return {k: max(v, 0.0) for k, v in minutos.items()}


async def minutes_by_project(db: AsyncSession, organization_id, project_ids: set) -> dict:
    """{project_id: {user_id: minutos}} de los turnos aprobados."""
    from app.modules.attendance.models import AttendanceEvent, TimeEntry

    if not project_ids:
        return {}
    turnos_stmt = (
        select(AttendanceEvent.time_entry_id)
        .where(
            AttendanceEvent.organization_id == organization_id,
            AttendanceEvent.project_id.in_(project_ids),
            AttendanceEvent.time_entry_id.is_not(None),
        )
        .distinct()
    )
    turnos_ids = {t for (t,) in (await db.execute(turnos_stmt)).all()}
    if not turnos_ids:
        return {}
    turnos = {t.id: t for t in (await db.execute(select(TimeEntry).where(
        TimeEntry.id.in_(turnos_ids), TimeEntry.status == "approved"))).scalars().all()}
    if not turnos:
        return {}
    eventos = defaultdict(list)
    for ev in (await db.execute(select(AttendanceEvent).where(
            AttendanceEvent.time_entry_id.in_(turnos.keys()),
            AttendanceEvent.event_type.in_(STARTS | {"left_site"}))
            .order_by(AttendanceEvent.occurred_at, AttendanceEvent.received_at))).scalars().all():
        eventos[ev.time_entry_id].append(ev)
    resultado: dict = defaultdict(lambda: defaultdict(float))
    for tid, turno in turnos.items():
        por_obra = _intervals(eventos[tid], turno.clock_out_at)
        marcado = sum(por_obra.values())
        if marcado <= 0:
            continue
        aprobado = turno.approved_minutes
        factor = min(1.0, aprobado / marcado) if aprobado is not None else 1.0
        for pid, mins in por_obra.items():
            if pid in project_ids:
                resultado[pid][turno.user_id] += mins * factor
    return resultado


async def costs_by_project(db: AsyncSession, organization_id, project_ids: set) -> dict:
    """{project_id: Decimal} de mano de obra por horas, solo de quien tiene tarifa."""
    tarifas = await rates(db, organization_id)
    costos: dict = {}
    for pid, por_persona in (await minutes_by_project(db, organization_id, project_ids)).items():
        total = ZERO
        for uid, mins in por_persona.items():
            if uid in tarifas:
                total += to_money(Decimal(str(mins)) / 60 * tarifas[uid])
        if total:
            costos[pid] = total
    return costos


async def project_detail(db: AsyncSession, organization_id, project_id: uuid.UUID) -> dict:
    from app.modules.users.models import User

    tarifas = await rates(db, organization_id)
    por_persona = (await minutes_by_project(db, organization_id, {project_id})).get(project_id, {})
    nombres = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(por_persona.keys())))).all()) \
        if por_persona else {}
    filas, total = [], ZERO
    for uid, mins in sorted(por_persona.items(), key=lambda x: -x[1]):
        tarifa = tarifas.get(uid)
        costo = to_money(Decimal(str(mins)) / 60 * tarifa) if tarifa is not None else None
        total += costo or ZERO
        filas.append({"user_id": str(uid), "name": nombres.get(uid, "—"), "minutes": round(mins),
                      "hourly_rate": str(tarifa) if tarifa is not None else None,
                      "cost": str(costo) if costo is not None else None})
    return {"rows": filas, "total": str(to_money(total)),
            "missing_rate": [f["name"] for f in filas if f["hourly_rate"] is None]}
