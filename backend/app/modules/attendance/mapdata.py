"""Lo que pinta el mapa operativo: obras con coordenadas, la última
ubicación conocida de cada persona y el orden sugerido de paradas.

Las coordenadas de la obra salen de `PropertyAddressMixin` (el GPS de la
visita del vendedor); no se geocodifica afuera. Una obra sin coordenadas va a
la lista «sin ubicar» y quien puede editar la obra la fija tocando el mapa.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance import geo
from app.modules.attendance.models import AttendanceEvent, TimeEntry, WorkShift
from app.modules.attendance.reports import last_locations
from app.modules.attendance.service import now, perms
from app.modules.crm.models import Customer
from app.modules.field_ops.access import get_visible_project, scope_projects_stmt
from app.modules.field_ops.models import Project, ProjectStatus
from app.modules.users.models import User
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import InvalidInputError

MAX_PROJECTS = 500


def _escape_like(q: str) -> str:
    """El texto tal cual: `%` y `_` no son comodines y el byte nulo se quita
    (Postgres lo rechaza con un 500, hallazgo M8 del ataque del 24 oct)."""
    q = q.replace("\x00", "").strip()[:100]
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _address(p: Project) -> str:
    return ", ".join(x for x in [p.address_street, p.address_unit, p.address_city, p.address_state, p.address_zip]
                     if x)


async def projects(db: AsyncSession, *, organization_id: uuid.UUID, user: User, status: str | None = None,
                   technician_id: uuid.UUID | None = None, customer_q: str | None = None,
                   on_date: date | None = None, ids: list[uuid.UUID] | None = None) -> dict:
    stmt = (select(Project, Customer.legal_name).join(Customer, Customer.id == Project.customer_id)
            .where(Project.organization_id == organization_id))
    stmt = scope_projects_stmt(stmt, user)
    if status:
        try:
            stmt = stmt.where(Project.status == ProjectStatus(status))
        except ValueError:
            raise InvalidInputError("Estado no válido.", code="invalid_status") from None
    elif not ids and not on_date:
        stmt = stmt.where(Project.status.in_((ProjectStatus.planning, ProjectStatus.scheduled,
                                              ProjectStatus.in_progress)))
    if technician_id:
        stmt = stmt.where(Project.primary_technician_user_id == technician_id)
    if customer_q:
        stmt = stmt.where(Customer.legal_name.ilike(f"%{_escape_like(customer_q)}%", escape="\\"))
    if ids:
        stmt = stmt.where(Project.id.in_(ids[:MAX_PROJECTS]))
    elif on_date:
        con_turno = select(WorkShift.project_id).where(
            WorkShift.organization_id == organization_id, WorkShift.shift_date == on_date,
            WorkShift.status == "scheduled", WorkShift.project_id.is_not(None))
        stmt = stmt.where(or_(Project.scheduled_date == on_date, Project.id.in_(con_turno)))
    filas = (await db.execute(stmt.order_by(Project.title).limit(MAX_PROJECTS))).all()
    tecnicos = {p.primary_technician_user_id for p, _ in filas if p.primary_technician_user_id}
    nombres = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(tecnicos))))
                   .all()) if tecnicos else {}
    ubicadas, sin_ubicar = [], []
    for p, cliente in filas:
        fila = {"id": str(p.id), "title": p.title, "customer_name": cliente, "status": p.status.value,
                "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
                "technician_user_id": str(p.primary_technician_user_id) if p.primary_technician_user_id else None,
                "technician_name": nombres.get(p.primary_technician_user_id), "address": _address(p),
                "latitude": p.latitude, "longitude": p.longitude}
        (ubicadas if geo.valid_point(p.latitude, p.longitude) else sin_ubicar).append(fila)
    return {"projects": ubicadas, "unlocated": sin_ubicar}


async def people(db: AsyncSession, *, organization_id: uuid.UUID, user: User,
                 user_id: uuid.UUID | None = None) -> list[dict]:
    """Última ubicación conocida, con su antigüedad. Sin `locations.view`,
    solo la propia."""
    ve_todo = "locations.view" in perms(user)
    if not ve_todo:
        ids = [user.id]
    elif user_id:
        ids = [user_id]
    else:
        desde = now() - timedelta(days=7)
        ids = list((await db.execute(select(AttendanceEvent.user_id).where(
            AttendanceEvent.organization_id == organization_id, AttendanceEvent.location_status == "ok",
            AttendanceEvent.occurred_at >= desde).distinct())).scalars())
    ubic = await last_locations(db, organization_id, ids)
    if not ubic:
        return []
    nombres = dict((await db.execute(select(User.id, User.full_name).where(
        User.organization_id == organization_id, User.id.in_(list(ubic))))).all())
    abiertas = set((await db.execute(select(TimeEntry.user_id).where(
        TimeEntry.organization_id == organization_id, TimeEntry.status == "open",
        TimeEntry.user_id.in_(list(ubic))))).scalars())
    ahora = now()
    salida = []
    for uid, u in ubic.items():
        if uid not in nombres:
            continue
        edad = int((ahora - as_utc(u["at"])).total_seconds() // 60)
        salida.append({"user_id": str(uid), "user_name": nombres[uid], "latitude": u["latitude"],
                       "longitude": u["longitude"], "accuracy_m": u["accuracy_m"], "event_type": u["event_type"],
                       "at": as_utc(u["at"]).isoformat(), "age_minutes": edad, "fresh": edad <= 15,
                       "shift_open": uid in abiertas, "project_id": u["project_id"]})
    return sorted(salida, key=lambda r: r["user_name"])


async def project_detail(db: AsyncSession, *, organization_id: uuid.UUID, user: User, project_id: uuid.UUID) -> dict:
    """El minimapa de la obra: su pin, el responsable con su última ubicación
    y la distancia en línea recta entre los dos."""
    p = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    tecnico = None
    if p.primary_technician_user_id:
        nombre = (await db.execute(select(User.full_name).where(User.id == p.primary_technician_user_id))
                  ).scalar_one_or_none()
        tecnico = {"user_id": str(p.primary_technician_user_id), "user_name": nombre, "location": None}
        if "locations.view" in perms(user) or p.primary_technician_user_id == user.id:
            u = (await last_locations(db, organization_id, [p.primary_technician_user_id])).get(
                p.primary_technician_user_id)
            if u:
                edad = int((now() - as_utc(u["at"])).total_seconds() // 60)
                tecnico["location"] = {"latitude": u["latitude"], "longitude": u["longitude"],
                                       "at": as_utc(u["at"]).isoformat(), "age_minutes": edad, "fresh": edad <= 15}
    ubicada = geo.valid_point(p.latitude, p.longitude)
    km = None
    if ubicada and tecnico and tecnico["location"]:
        km = round(geo.haversine_km(tecnico["location"]["latitude"], tecnico["location"]["longitude"],
                                    p.latitude, p.longitude), 2)
    origen = (tecnico["location"]["latitude"], tecnico["location"]["longitude"]) \
        if tecnico and tecnico["location"] else None
    return {"id": str(p.id), "title": p.title, "address": _address(p), "latitude": p.latitude,
            "longitude": p.longitude, "located": ubicada, "technician": tecnico, "straight_line_km": km,
            "directions_url": geo.google_maps_directions_url(
                origen, [{"latitude": p.latitude, "longitude": p.longitude}]) if ubicada else None}


async def set_project_location(db: AsyncSession, *, organization_id: uuid.UUID, user: User, project_id: uuid.UUID,
                               latitude: float, longitude: float) -> dict:
    if not geo.valid_point(latitude, longitude):
        raise InvalidInputError("La ubicación no es válida.", code="invalid_location")
    p = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    antes = {"latitude": p.latitude, "longitude": p.longitude}
    p.latitude, p.longitude = latitude, longitude
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="project.location_set", entity_type="project", entity_id=str(p.id),
                             before_data=antes, after_data={"latitude": latitude, "longitude": longitude})
    await db.commit()
    return {"id": str(p.id), "latitude": p.latitude, "longitude": p.longitude}


async def route(db: AsyncSession, *, organization_id: uuid.UUID, user: User, user_id: uuid.UUID,
                on_date: date) -> dict:
    """Orden sugerido de las obras de una persona en un día: la más cercana
    primero, empezando por su última ubicación. Distancia, no tiempo de manejo."""
    if user_id != user.id and "locations.view" not in perms(user):
        user_id = user.id
    con_turno = select(WorkShift.project_id).where(
        WorkShift.organization_id == organization_id, WorkShift.user_id == user_id,
        WorkShift.shift_date == on_date, WorkShift.status == "scheduled", WorkShift.project_id.is_not(None))
    stmt = select(Project).where(Project.organization_id == organization_id, or_(
        (Project.primary_technician_user_id == user_id) & (Project.scheduled_date == on_date),
        Project.id.in_(con_turno)))
    filas = (await db.execute(scope_projects_stmt(stmt, user).order_by(Project.title).limit(30))).scalars().all()
    paradas = [{"id": str(p.id), "title": p.title, "address": _address(p), "latitude": p.latitude,
                "longitude": p.longitude} for p in filas]
    u = (await last_locations(db, organization_id, [user_id])).get(user_id)
    origen = (u["latitude"], u["longitude"]) if u else None
    orden = geo.nearest_neighbor_order(origen, paradas)
    total = round(sum(s.get("km_from_previous") or 0 for s in orden), 2)
    return {"user_id": str(user_id), "date": on_date.isoformat(), "origin": {
        "latitude": origen[0], "longitude": origen[1], "at": as_utc(u["at"]).isoformat()} if origen else None,
            "stops": orden, "total_km": total, "distance_source": geo.STRAIGHT_LINE,
            "directions_url": geo.google_maps_directions_url(origen, orden)}


async def purge_old_locations(db: AsyncSession, organization_id: uuid.UUID | None = None) -> int:
    """Borra latitud, longitud y precisión de los eventos más viejos que la
    retención de su organización. El evento queda (las horas no dependen de
    la ubicación)."""
    from app.modules.attendance.models import AttendanceSettings
    from app.modules.organizations.models import Organization

    orgs = [organization_id] if organization_id else list(
        (await db.execute(select(Organization.id))).scalars())
    total = 0
    for org in orgs:
        s = (await db.execute(select(AttendanceSettings).where(
            AttendanceSettings.organization_id == org))).scalar_one_or_none()
        dias = s.location_retention_days if s else 90
        if not dias:
            continue
        r = await db.execute(update(AttendanceEvent).where(
            AttendanceEvent.organization_id == org, AttendanceEvent.location_status == "ok",
            AttendanceEvent.occurred_at < now() - timedelta(days=dias)).values(
            latitude=None, longitude=None, accuracy_m=None, location_status="purged"))
        total += r.rowcount or 0
    await db.commit()
    return total


async def purge_user_locations(db: AsyncSession, *, organization_id: uuid.UUID, actor: User,
                               user_id: uuid.UUID) -> int:
    """Borrado anticipado de las coordenadas de una persona (queda en auditoría)."""
    r = await db.execute(update(AttendanceEvent).where(
        AttendanceEvent.organization_id == organization_id, AttendanceEvent.user_id == user_id,
        AttendanceEvent.location_status == "ok").values(
        latitude=None, longitude=None, accuracy_m=None, location_status="purged"))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.locations_purged", entity_type="user", entity_id=str(user_id),
                             after_data={"events": r.rowcount or 0})
    await db.commit()
    return r.rowcount or 0



MAX_GEOCODE = 25


async def geocode_projects(db: AsyncSession, *, organization_id: uuid.UUID, user: User,
                           project_ids: list[uuid.UUID] | None = None) -> dict:
    """Ubica por su dirección las obras que no tienen coordenadas (las que la
    persona ve; las indicadas o, sin indicar, las abiertas). Hasta
    `MAX_GEOCODE` por llamada: el servicio es externo y cada obra es una
    consulta. Las que ya tienen punto no se tocan: el GPS de la visita o un
    punto fijado a mano vale más que la dirección."""
    from app.shared import geocoding

    if not geocoding.enabled():
        raise InvalidInputError("La ubicación por dirección está apagada en este servidor. "
                                "Fija la obra tocando el mapa.", code="geocoder_off")
    stmt = scope_projects_stmt(select(Project).where(Project.organization_id == organization_id), user)
    if project_ids:
        stmt = stmt.where(Project.id.in_(project_ids[:MAX_GEOCODE]))
    else:
        stmt = stmt.where(Project.status.in_((ProjectStatus.planning, ProjectStatus.scheduled,
                                              ProjectStatus.in_progress)))
    candidatas = [p for p in (await db.execute(stmt.order_by(Project.title))).scalars()
                  if not geo.valid_point(p.latitude, p.longitude)][:MAX_GEOCODE]
    ubicadas, sin_encontrar = [], []
    for p in candidatas:
        punto = await geocoding.geocode(p.address_street, p.address_city, p.address_state, p.address_zip)
        if not punto or not geo.valid_point(*punto):
            sin_encontrar.append({"id": str(p.id), "title": p.title, "address": _address(p)})
            continue
        p.latitude, p.longitude = punto
        await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                                 action="project.location_geocoded", entity_type="project", entity_id=str(p.id),
                                 after_data={"latitude": punto[0], "longitude": punto[1], "source": "census"})
        ubicadas.append({"id": str(p.id), "title": p.title, "latitude": punto[0], "longitude": punto[1]})
    await db.commit()
    return {"located": ubicadas, "not_found": sin_encontrar}
