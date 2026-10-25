"""Marcaciones y eventos del turno, y la malla.

Cada marca llega como un **evento** con el id que le puso el teléfono
(`client_event_id`). Así la misma función sirve en línea y para la cola sin
señal, y un reintento devuelve lo mismo sin duplicar (spec, «Geolocalización
y sin señal»).
"""
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.attendance import calc, geo
from app.modules.attendance.models import (
    AttendanceEvent,
    AttendanceSettings,
    PayrollPeriod,
    TimeEntry,
    TimeEntryPause,
    WorkShift,
)
from app.modules.field_ops import clock
from app.modules.field_ops.models import Project
from app.modules.users.models import User, UserStatus
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

# La hora del teléfono se usa solo si llegó sin señal y es creíble.
ONLINE_GAP = timedelta(minutes=5)
MAX_OFFLINE_AGE = timedelta(hours=72)
FUTURE_SLACK = timedelta(minutes=2)
# Desde cuándo se ofrece «Iniciar turno» antes de la hora programada.
EARLY_START_WINDOW = timedelta(hours=4)

EVENT_TYPES = {
    "clock_in", "clock_out", "pause_start", "pause_end", "en_route", "arrived", "left_site", "tracking",
    "login", "logout", "connectivity_lost", "connectivity_restored", "location_denied", "location_unavailable",
}
# Los que necesitan un turno abierto.
NEEDS_OPEN_ENTRY = {"clock_out", "pause_start", "pause_end", "en_route", "arrived", "left_site", "tracking"}
# Los que apuntan a una obra.
PROJECT_EVENTS = {"en_route", "arrived", "left_site"}
LOCATION_STATUSES = {"ok", "denied", "unavailable", "timeout", "not_requested"}


def now() -> datetime:
    return clock._utcnow()


def perms(user) -> set[str]:
    return get_effective_permissions(user)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

SETTING_FIELDS = (
    "late_tolerance_minutes", "early_leave_tolerance_minutes", "daily_overtime_after_minutes",
    "weekly_overtime_after_minutes", "tracking_interval_minutes", "location_retention_days",
    "require_clock_in_for_field_work", "paid_pauses",
)


async def get_settings(db: AsyncSession, organization_id: uuid.UUID) -> AttendanceSettings:
    fila = (await db.execute(select(AttendanceSettings).where(
        AttendanceSettings.organization_id == organization_id))).scalar_one_or_none()
    if fila is None:
        fila = AttendanceSettings(organization_id=organization_id, late_tolerance_minutes=10,
                                  early_leave_tolerance_minutes=10, daily_overtime_after_minutes=480,
                                  weekly_overtime_after_minutes=2400, tracking_interval_minutes=0,
                                  location_retention_days=90, require_clock_in_for_field_work=False,
                                  paid_pauses=False)
        db.add(fila)
        await db.flush()
    return fila


def settings_out(s: AttendanceSettings) -> dict:
    return {f: getattr(s, f) for f in SETTING_FIELDS}


async def update_settings(db: AsyncSession, *, organization_id: uuid.UUID, user: User, data: dict) -> dict:
    s = await get_settings(db, organization_id)
    antes = settings_out(s)
    for campo, valor in data.items():
        if campo in SETTING_FIELDS and valor is not None:
            setattr(s, campo, valor)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="attendance.settings_updated", entity_type="attendance_settings",
                             entity_id=str(s.id), before_data=antes, after_data=settings_out(s))
    await db.commit()
    return settings_out(s)


# ---------------------------------------------------------------------------
# Períodos cerrados
# ---------------------------------------------------------------------------

async def ensure_period_open(db: AsyncSession, organization_id: uuid.UUID, *days: date) -> None:
    for dia in {d for d in days if d is not None}:
        cerrado = (await db.execute(select(PayrollPeriod.id).where(
            PayrollPeriod.organization_id == organization_id, PayrollPeriod.status == "closed",
            PayrollPeriod.start_date <= dia, PayrollPeriod.end_date >= dia))).first()
        if cerrado:
            raise ConflictError(f"El período de nómina que incluye el {dia.isoformat()} está cerrado. "
                                "Pide que lo reabran para cambiarlo.", code="period_closed")


# ---------------------------------------------------------------------------
# Lecturas de apoyo
# ---------------------------------------------------------------------------

async def open_entry(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> TimeEntry | None:
    return (await db.execute(select(TimeEntry).where(
        TimeEntry.organization_id == organization_id, TimeEntry.user_id == user_id,
        TimeEntry.status == "open"))).scalar_one_or_none()


async def current_shift(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID,
                        at: datetime) -> WorkShift | None:
    """El turno que toca marcar ahora: de hoy o de ayer (nocturno), que no
    haya terminado, que ya esté por empezar y que nadie haya marcado."""
    at = as_utc(at)
    marcados = select(TimeEntry.shift_id).where(TimeEntry.organization_id == organization_id,
                                                TimeEntry.shift_id.is_not(None))
    filas = (await db.execute(select(WorkShift).where(
        WorkShift.organization_id == organization_id, WorkShift.user_id == user_id,
        WorkShift.status == "scheduled", WorkShift.ends_at > at,
        WorkShift.starts_at <= at + EARLY_START_WINDOW, WorkShift.id.not_in(marcados),
    ).order_by(WorkShift.starts_at))).scalars().all()
    return filas[0] if filas else None


async def shifts_today(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[WorkShift]:
    hoy = await clock.org_today(db, organization_id)
    return list((await db.execute(select(WorkShift).where(
        WorkShift.organization_id == organization_id, WorkShift.user_id == user_id,
        WorkShift.shift_date.in_([hoy, hoy - timedelta(days=1)]), WorkShift.status == "scheduled",
    ).order_by(WorkShift.starts_at))).scalars().all())


async def _check_project(db: AsyncSession, organization_id: uuid.UUID, user: User, project_id) -> uuid.UUID | None:
    if project_id is None:
        return None
    from app.modules.field_ops.access import get_visible_project

    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return project_id


def _resolve_time(device_at: datetime | None, received: datetime) -> tuple[datetime, bool]:
    """(hora que cuenta, ¿llegó sin señal?). La del servidor manda salvo que
    la marca haya esperado en el teléfono un rato creíble."""
    if device_at is None:
        return received, False
    device_at = as_utc(device_at)
    if device_at > received + FUTURE_SLACK or received - device_at > MAX_OFFLINE_AGE:
        return received, False
    if received - device_at <= ONLINE_GAP:
        return received, False
    return device_at, True


def _location(data: dict) -> tuple[float | None, float | None, float | None, str]:
    lat, lng, acc = data.get("latitude"), data.get("longitude"), data.get("accuracy_m")
    estado = data.get("location_status") or ("ok" if lat is not None else "not_requested")
    if estado not in LOCATION_STATUSES:
        raise InvalidInputError("Estado de ubicación no válido.", code="invalid_location_status")
    if estado == "ok":
        if not geo.valid_point(lat, lng):
            raise InvalidInputError("La ubicación no es válida.", code="invalid_location")
        if acc is not None and (acc < 0 or acc > 100_000):
            raise InvalidInputError("La precisión no es válida.", code="invalid_location")
        return float(lat), float(lng), (float(acc) if acc is not None else None), "ok"
    return None, None, None, estado


async def _last_located(db: AsyncSession, organization_id: uuid.UUID, entry_id: uuid.UUID,
                        before: datetime) -> AttendanceEvent | None:
    return (await db.execute(select(AttendanceEvent).where(
        AttendanceEvent.organization_id == organization_id, AttendanceEvent.time_entry_id == entry_id,
        AttendanceEvent.location_status == "ok", AttendanceEvent.occurred_at <= before,
    ).order_by(AttendanceEvent.occurred_at.desc()).limit(1))).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Registrar un evento (en línea o desde la cola sin señal)
# ---------------------------------------------------------------------------

async def record_event(db: AsyncSession, *, organization_id: uuid.UUID, user: User, data: dict) -> dict:
    """Aplica el evento y devuelve `{"event_id", "duplicate", "entry"}`. Con un
    `client_event_id` ya visto devuelve el resultado de la primera vez."""
    tipo = data.get("event_type")
    if tipo not in EVENT_TYPES:
        raise InvalidInputError("Tipo de evento no válido.", code="invalid_event_type")
    client_id = data.get("client_event_id")
    if client_id:
        previo = (await db.execute(select(AttendanceEvent).where(
            AttendanceEvent.organization_id == organization_id, AttendanceEvent.user_id == user.id,
            AttendanceEvent.client_event_id == client_id))).scalar_one_or_none()
        if previo is not None:
            return {**(previo.result or {}), "event_id": str(previo.id), "duplicate": True}

    from app.shared.errors import DomainError

    # Todo el evento va en un savepoint: si choca (otro teléfono, el mismo id
    # del teléfono) o rompe una regla, se deshace solo esto. Un `rollback`
    # completo caducaría al usuario de la petición y el manejador de errores
    # respondería 500 al leerlo (pasó con dos entradas simultáneas en Postgres).
    punto = await db.begin_nested()
    try:
        recibido = now()
        ocurrio, sin_senal = _resolve_time(data.get("device_at"), recibido)
        lat, lng, acc, estado = _location(data)
        project_id = await _check_project(db, organization_id, user, data.get("project_id")) \
            if tipo in PROJECT_EVENTS or data.get("project_id") else None
        if tipo in PROJECT_EVENTS and project_id is None:
            raise InvalidInputError("Elige la obra.", code="project_required")

        entry = await open_entry(db, organization_id, user.id)
        if tipo in NEEDS_OPEN_ENTRY and entry is None:
            raise ConflictError("No tienes un turno iniciado.", code="no_open_entry")

        if tipo == "clock_in":
            entry = await _clock_in(db, organization_id=organization_id, user=user, entry=entry, at=ocurrio,
                                    received=recibido, device_at=data.get("device_at"), offline=sin_senal)
        elif tipo == "clock_out":
            await _clock_out(db, organization_id=organization_id, entry=entry, at=ocurrio, received=recibido,
                             device_at=data.get("device_at"), offline=sin_senal, notes=data.get("note"))
        elif tipo == "pause_start":
            if any(p.ended_at is None for p in entry.pauses):
                raise ConflictError("Ya estás en pausa.", code="already_paused")
            entry.pauses.append(TimeEntryPause(organization_id=organization_id, started_at=ocurrio,
                                               reason=(data.get("note") or None)))
        elif tipo == "pause_end":
            abierta = next((p for p in entry.pauses if p.ended_at is None), None)
            if abierta is None:
                raise ConflictError("No estás en pausa.", code="not_paused")
            abierta.ended_at = max(ocurrio, as_utc(abierta.started_at))

        distancia = None
        if estado == "ok" and entry is not None and tipo != "clock_in":
            anterior = await _last_located(db, organization_id, entry.id, ocurrio)
            if anterior is not None:
                distancia = round(geo.haversine_km(anterior.latitude, anterior.longitude, lat, lng), 3)

        resultado = {"entry": entry_out(entry, now=recibido) if entry is not None else None}
        evento = AttendanceEvent(
            organization_id=organization_id, user_id=user.id, time_entry_id=entry.id if entry else None,
            project_id=project_id, event_type=tipo, client_event_id=client_id, device_at=data.get("device_at"),
            received_at=recibido, occurred_at=ocurrio, offline=sin_senal, latitude=lat, longitude=lng,
            accuracy_m=acc, location_status=estado, distance_km=distancia,
            distance_source=geo.STRAIGHT_LINE if distancia is not None else None,
            note=(data.get("note") or None) and str(data["note"])[:255], result=_json_safe(resultado))
        db.add(evento)
        await db.flush()
    except IntegrityError:
        await punto.rollback()
        if client_id:
            previo = (await db.execute(select(AttendanceEvent).where(
                AttendanceEvent.organization_id == organization_id, AttendanceEvent.user_id == user.id,
                AttendanceEvent.client_event_id == client_id))).scalar_one_or_none()
            if previo is not None:
                return {**(previo.result or {}), "event_id": str(previo.id), "duplicate": True}
        raise ConflictError("Ya tienes un turno iniciado.", code="entry_already_open") from None
    except DomainError:
        await punto.rollback()
        raise
    await punto.commit()
    await db.commit()
    return {**resultado, "event_id": str(evento.id), "duplicate": False}


def _json_safe(valor):
    if isinstance(valor, dict):
        return {k: _json_safe(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_json_safe(v) for v in valor]
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, uuid.UUID):
        return str(valor)
    return valor


async def _clock_in(db, *, organization_id, user, entry, at, received, device_at, offline) -> TimeEntry:
    if entry is not None:
        raise ConflictError("Ya tienes un turno iniciado.", code="entry_already_open")
    zona = await clock.org_zone(db, organization_id)
    dia = clock.local_date(at, zona)
    await ensure_period_open(db, organization_id, dia)
    turno = await current_shift(db, organization_id, user.id, at)
    entry = TimeEntry(organization_id=organization_id, user_id=user.id, shift_id=turno.id if turno else None,
                      work_date=turno.shift_date if turno else dia, clock_in_at=at, clock_in_received_at=received,
                      clock_in_device_at=device_at, clock_in_offline=offline, status="open", pauses=[])
    db.add(entry)
    # Si otro teléfono de la misma persona abrió turno en este instante, el
    # índice parcial `uq_time_entries_one_open` lo rechaza aquí y `record_event`
    # responde 409.
    await db.flush()
    return entry


async def _clock_out(db, *, organization_id, entry, at, received, device_at, offline, notes) -> None:
    await ensure_period_open(db, organization_id, entry.work_date)
    salida = max(at, as_utc(entry.clock_in_at))
    for p in entry.pauses:
        if p.ended_at is None:
            p.ended_at = max(salida, as_utc(p.started_at))
    entry.clock_out_at = salida
    entry.clock_out_received_at = received
    entry.clock_out_device_at = device_at
    entry.clock_out_offline = offline
    entry.status = "closed"
    entry.closed_by = "self"
    if notes:
        entry.notes = str(notes)[:2000]


async def record_events_batch(db: AsyncSession, *, organization_id: uuid.UUID, user: User,
                              events: list[dict]) -> list[dict]:
    """La cola del teléfono. Cada evento va en su propia transacción: uno que
    falla no tumba a los demás, y se responde uno por uno."""
    from app.shared.errors import DomainError

    orden = sorted(events, key=lambda e: as_utc(e["device_at"]) if e.get("device_at") else now())
    salida = []
    for e in orden:
        try:
            r = await record_event(db, organization_id=organization_id, user=user, data=e)
            salida.append({"client_event_id": e.get("client_event_id"),
                           "status": "duplicate" if r["duplicate"] else "ok", "event_id": r["event_id"]})
        except DomainError as exc:
            salida.append({"client_event_id": e.get("client_event_id"), "status": "error",
                           "code": exc.code, "message": exc.message})
    return salida


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------

def entry_out(entry: TimeEntry, *, now: datetime, paid_pauses: bool = False) -> dict:
    horas = calc.entry_hours(entry, now=now, paid_pauses=paid_pauses)
    return {
        "id": str(entry.id), "user_id": str(entry.user_id),
        "shift_id": str(entry.shift_id) if entry.shift_id else None,
        "work_date": entry.work_date.isoformat(), "status": entry.status,
        "clock_in_at": as_utc(entry.clock_in_at).isoformat(),
        "clock_in_offline": entry.clock_in_offline,
        "clock_out_at": as_utc(entry.clock_out_at).isoformat() if entry.clock_out_at else None,
        "clock_out_offline": entry.clock_out_offline, "closed_by": entry.closed_by, "notes": entry.notes,
        "elapsed_minutes": horas.elapsed, "pause_minutes": horas.pauses, "effective_minutes": horas.effective,
        "approved_minutes": entry.approved_minutes,
        "paused": any(p.ended_at is None for p in entry.pauses),
        "pauses": [{"started_at": as_utc(p.started_at).isoformat(),
                    "ended_at": as_utc(p.ended_at).isoformat() if p.ended_at else None,
                    "reason": p.reason} for p in entry.pauses],
    }


def shift_out(s: WorkShift, *, user_name: str | None = None, project_title: str | None = None) -> dict:
    return {"id": str(s.id), "user_id": str(s.user_id), "user_name": user_name,
            "shift_date": s.shift_date.isoformat(), "starts_at": as_utc(s.starts_at).isoformat(),
            "ends_at": as_utc(s.ends_at).isoformat(), "break_minutes": s.break_minutes,
            "scheduled_minutes": calc.scheduled_minutes(s),
            "project_id": str(s.project_id) if s.project_id else None, "project_title": project_title,
            "notes": s.notes, "status": s.status}


async def me(db: AsyncSession, *, organization_id: uuid.UUID, user: User) -> dict:
    """Lo que ve la ventana obligatoria y la pantalla «Mi turno»."""
    ahora = now()
    s = await get_settings(db, organization_id)
    entry = await open_entry(db, organization_id, user.id)
    turno = None
    if entry is not None and entry.shift_id:
        turno = await db.get(WorkShift, entry.shift_id)
    elif entry is None:
        turno = await current_shift(db, organization_id, user.id, ahora)
    estado = None
    if turno is not None:
        estado = calc.shift_status(turno, entry, now=ahora, late_tolerance=s.late_tolerance_minutes,
                                   early_tolerance=s.early_leave_tolerance_minutes)
    proyecto = None
    if turno is not None and turno.project_id:
        p = await db.get(Project, turno.project_id)
        proyecto = {"id": str(p.id), "title": p.title} if p and p.organization_id == organization_id else None
    return {
        "server_time": ahora.isoformat(),
        "timezone": str(await clock.org_zone(db, organization_id)),
        "user": {"id": str(user.id), "full_name": user.full_name},
        "shift": shift_out(turno) if turno else None,
        "shift_status": estado,
        "late_minutes": calc.late_minutes(turno, entry.clock_in_at if entry else ahora, s.late_tolerance_minutes)
        if turno else 0,
        "shift_project": proyecto,
        "entry": entry_out(entry, now=ahora, paid_pauses=s.paid_pauses) if entry else None,
        # La ventana obligatoria: hay un turno para marcar y no hay marcación.
        "must_clock_in": entry is None and turno is not None,
        "tracking_interval_minutes": s.tracking_interval_minutes,
        "location_retention_days": s.location_retention_days,
        "projects_today": await _projects_for(db, organization_id, user),
    }


async def _projects_for(db: AsyncSession, organization_id: uuid.UUID, user: User) -> list[dict]:
    """Las obras que puede marcar en «En camino / Llegué»: las que trabaja hoy."""
    from app.modules.field_ops.access import scope_projects_stmt
    from app.modules.field_ops.models import ProjectStatus

    abiertas = (ProjectStatus.planning, ProjectStatus.scheduled, ProjectStatus.in_progress)
    stmt = select(Project).where(Project.organization_id == organization_id, Project.status.in_(abiertas))
    if "projects.read_all" in perms(user):
        stmt = stmt.where(Project.primary_technician_user_id == user.id)
    else:
        stmt = scope_projects_stmt(stmt, user)
    filas = (await db.execute(stmt.order_by(Project.scheduled_date, Project.title).limit(50))).scalars().all()
    return [{"id": str(p.id), "title": p.title, "address": _address(p),
             "latitude": p.latitude, "longitude": p.longitude} for p in filas]


def _address(p) -> str:
    partes = [p.address_street, p.address_unit, p.address_city, p.address_state, p.address_zip]
    return ", ".join(x for x in partes if x)


async def clock_out_summary(db: AsyncSession, *, organization_id: uuid.UUID, user: User) -> dict:
    """El resumen que se ve antes de confirmar FINALIZAR TURNO."""
    entry = await open_entry(db, organization_id, user.id)
    if entry is None:
        raise ConflictError("No tienes un turno iniciado.", code="no_open_entry")
    s = await get_settings(db, organization_id)
    ahora = now()
    horas = calc.entry_hours(entry, now=ahora, paid_pauses=s.paid_pauses)
    turno = await db.get(WorkShift, entry.shift_id) if entry.shift_id else None
    obras = (await db.execute(select(Project.id, Project.title).join(
        AttendanceEvent, AttendanceEvent.project_id == Project.id).where(
        AttendanceEvent.organization_id == organization_id, AttendanceEvent.time_entry_id == entry.id,
        AttendanceEvent.event_type == "arrived").distinct())).all()
    programadas = calc.scheduled_minutes(turno) if turno else None
    return {
        "clock_in_at": as_utc(entry.clock_in_at).isoformat(), "clock_out_at": ahora.isoformat(),
        "elapsed_minutes": horas.elapsed, "pause_minutes": horas.pauses, "effective_minutes": horas.effective,
        "pauses": len(entry.pauses), "shift": shift_out(turno) if turno else None,
        "scheduled_minutes": programadas,
        "difference_minutes": horas.effective - programadas if programadas is not None else None,
        "early_leave_minutes": calc.early_leave_minutes(turno, ahora, s.early_leave_tolerance_minutes)
        if turno else 0,
        "projects": [{"id": str(i), "title": t} for i, t in obras],
    }


# ---------------------------------------------------------------------------
# Marcación obligatoria para el trabajo de campo (apagada por defecto)
# ---------------------------------------------------------------------------

async def ensure_clocked_in(db: AsyncSession, *, organization_id: uuid.UUID, user) -> None:
    """Con `require_clock_in_for_field_work`, quien tiene turno ahora y no ha
    marcado no llena la obra. La oficina (`projects.read_all`) no marca para eso."""
    if "projects.read_all" in perms(user):
        return
    s = (await db.execute(select(AttendanceSettings).where(
        AttendanceSettings.organization_id == organization_id))).scalar_one_or_none()
    if s is None or not s.require_clock_in_for_field_work:
        return
    if await open_entry(db, organization_id, user.id) is not None:
        return
    if await current_shift(db, organization_id, user.id, now()) is not None:
        raise ForbiddenError("Inicia tu turno antes de trabajar en la obra.", code="shift_not_started")


# ---------------------------------------------------------------------------
# Malla de turnos
# ---------------------------------------------------------------------------

MAX_BULK_DAYS = 62
MAX_BULK_SHIFTS = 1500


async def _check_user(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> User:
    u = (await db.execute(select(User).where(User.id == user_id, User.organization_id == organization_id,
                                             User.status == UserStatus.active))).scalar_one_or_none()
    if u is None:
        raise InvalidInputError("La persona no existe o no está activa.", code="invalid_user")
    return u


async def _check_shift_project(db: AsyncSession, organization_id: uuid.UUID, project_id) -> None:
    if project_id is None:
        return
    ok = (await db.execute(select(Project.id).where(Project.id == project_id,
                                                    Project.organization_id == organization_id))).first()
    if not ok:
        raise InvalidInputError("La obra no existe.", code="invalid_project")


def _parse_hhmm(valor: str) -> time:
    try:
        h, m = valor.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        raise InvalidInputError(f"«{valor}» no es una hora válida (HH:MM).", code="invalid_time") from None


def local_window(dia: date, inicio: str, fin: str, zona) -> tuple[datetime, datetime]:
    """Inicio y fin en UTC de un turno local. Si el fin es igual o anterior al
    inicio, el turno cruza la medianoche y termina al día siguiente."""
    a, b = _parse_hhmm(inicio), _parse_hhmm(fin)
    desde = datetime.combine(dia, a, tzinfo=zona)
    hasta = datetime.combine(dia + timedelta(days=1) if b <= a else dia, b, tzinfo=zona)
    return as_utc(desde), as_utc(hasta)


def _validate_window(desde: datetime, hasta: datetime, break_minutes: int) -> None:
    duracion = (hasta - desde).total_seconds() / 60
    if duracion > 24 * 60:
        raise InvalidInputError("Un turno no puede pasar de 24 horas.", code="invalid_shift")
    if break_minutes < 0 or break_minutes >= duracion:
        raise InvalidInputError("El descanso debe ser menor que el turno.", code="invalid_shift")


async def _overlaps(db, organization_id, user_id, desde, hasta, *, except_id=None) -> bool:
    stmt = select(WorkShift.id).where(
        WorkShift.organization_id == organization_id, WorkShift.user_id == user_id,
        WorkShift.status == "scheduled", WorkShift.starts_at < hasta, WorkShift.ends_at > desde)
    if except_id:
        stmt = stmt.where(WorkShift.id != except_id)
    return (await db.execute(stmt.limit(1))).first() is not None


async def create_shifts(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, data: dict) -> dict:
    """Malla por persona o por grupo: un horario repetido en los días de la
    semana elegidos entre dos fechas. Los que chocan con otro turno se saltan
    y se informan."""
    desde_dia, hasta_dia = data["date_from"], data["date_to"]
    if hasta_dia < desde_dia or (hasta_dia - desde_dia).days >= MAX_BULK_DAYS:
        raise InvalidInputError(f"El rango debe ser de 1 a {MAX_BULK_DAYS} días.", code="invalid_range")
    dias_semana = set(data.get("weekdays") or range(7))
    if not dias_semana <= set(range(7)):
        raise InvalidInputError("Días de la semana no válidos (0 = lunes … 6 = domingo).", code="invalid_weekdays")
    user_ids = list(dict.fromkeys(data["user_ids"]))
    personas = {uid: await _check_user(db, organization_id, uid) for uid in user_ids}
    await _check_shift_project(db, organization_id, data.get("project_id"))
    zona = await clock.org_zone(db, organization_id)
    dias = [desde_dia + timedelta(days=i) for i in range((hasta_dia - desde_dia).days + 1)]
    dias = [d for d in dias if d.weekday() in dias_semana]
    if len(dias) * len(user_ids) > MAX_BULK_SHIFTS:
        raise InvalidInputError("Son demasiados turnos de una vez.", code="too_many_shifts")
    await ensure_period_open(db, organization_id, *dias)
    creados, saltados = [], []
    for uid in user_ids:
        for dia in dias:
            a, b = local_window(dia, data["start_time"], data["end_time"], zona)
            _validate_window(a, b, data.get("break_minutes") or 0)
            if await _overlaps(db, organization_id, uid, a, b):
                saltados.append({"user_id": str(uid), "user_name": personas[uid].full_name,
                                 "shift_date": dia.isoformat()})
                continue
            t = WorkShift(organization_id=organization_id, user_id=uid, shift_date=dia, starts_at=a, ends_at=b,
                          break_minutes=data.get("break_minutes") or 0, project_id=data.get("project_id"),
                          notes=data.get("notes"), status="scheduled", created_by_user_id=actor.id)
            db.add(t)
            await db.flush()
            creados.append(t)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.shifts_created", entity_type="work_shift",
                             after_data={"count": len(creados), "users": [str(u) for u in user_ids],
                                         "from": desde_dia.isoformat(), "to": hasta_dia.isoformat()})
    await db.commit()
    return {"created": [shift_out(t, user_name=personas[t.user_id].full_name) for t in creados],
            "skipped": saltados}


async def get_shift(db: AsyncSession, organization_id: uuid.UUID, shift_id: uuid.UUID) -> WorkShift:
    t = (await db.execute(select(WorkShift).where(WorkShift.id == shift_id,
                                                  WorkShift.organization_id == organization_id))).scalar_one_or_none()
    if t is None:
        raise NotFoundError("El turno no existe.", code="shift_not_found")
    return t


async def update_shift(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, shift_id: uuid.UUID,
                       data: dict) -> dict:
    t = await get_shift(db, organization_id, shift_id)
    if t.status == "cancelled":
        raise ConflictError("El turno está cancelado.", code="shift_cancelled")
    antes = shift_out(t)
    dia = data.get("shift_date") or t.shift_date
    await ensure_period_open(db, organization_id, t.shift_date, dia)
    zona = await clock.org_zone(db, organization_id)
    if data.get("start_time") and data.get("end_time"):
        a, b = local_window(dia, data["start_time"], data["end_time"], zona)
    elif data.get("shift_date"):
        delta = datetime.combine(dia, time()) - datetime.combine(t.shift_date, time())
        a, b = as_utc(t.starts_at) + delta, as_utc(t.ends_at) + delta
    else:
        a, b = as_utc(t.starts_at), as_utc(t.ends_at)
    descanso = data["break_minutes"] if data.get("break_minutes") is not None else t.break_minutes
    _validate_window(a, b, descanso)
    if await _overlaps(db, organization_id, t.user_id, a, b, except_id=t.id):
        raise ConflictError("Choca con otro turno de la misma persona.", code="shift_overlap")
    if "project_id" in data:
        await _check_shift_project(db, organization_id, data["project_id"])
        t.project_id = data["project_id"]
    if "notes" in data:
        t.notes = data["notes"]
    t.shift_date, t.starts_at, t.ends_at, t.break_minutes = dia, a, b, descanso
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.shift_updated", entity_type="work_shift", entity_id=str(t.id),
                             before_data=antes, after_data=shift_out(t))
    await db.commit()
    return shift_out(t)


async def cancel_shift(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, shift_id: uuid.UUID,
                       reason: str | None) -> None:
    t = await get_shift(db, organization_id, shift_id)
    await ensure_period_open(db, organization_id, t.shift_date)
    marcado = (await db.execute(select(TimeEntry.id).where(TimeEntry.organization_id == organization_id,
                                                           TimeEntry.shift_id == t.id))).first()
    if marcado:
        raise ConflictError("El turno ya tiene marcación; corrígela en lugar de cancelar el turno.",
                            code="shift_has_entry")
    t.status = "cancelled"
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.shift_cancelled", entity_type="work_shift", entity_id=str(t.id),
                             after_data={"reason": reason})
    await db.commit()


async def copy_week(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, source_monday: date,
                    target_monday: date, user_ids: list[uuid.UUID] | None) -> dict:
    """Copia la malla de una semana a otra (rotaciones que se repiten)."""
    if source_monday.weekday() != 0 or target_monday.weekday() != 0:
        raise InvalidInputError("Las semanas empiezan el lunes.", code="invalid_week")
    if source_monday == target_monday:
        raise InvalidInputError("Elige otra semana de destino.", code="invalid_week")
    stmt = select(WorkShift).where(
        WorkShift.organization_id == organization_id, WorkShift.status == "scheduled",
        WorkShift.shift_date >= source_monday, WorkShift.shift_date < source_monday + timedelta(days=7))
    if user_ids:
        stmt = stmt.where(WorkShift.user_id.in_(user_ids))
    origen = (await db.execute(stmt)).scalars().all()
    delta = target_monday - source_monday
    await ensure_period_open(db, organization_id, *[t.shift_date + delta for t in origen])
    creados, saltados = 0, 0
    for t in origen:
        a, b = as_utc(t.starts_at) + delta, as_utc(t.ends_at) + delta
        if await _overlaps(db, organization_id, t.user_id, a, b):
            saltados += 1
            continue
        db.add(WorkShift(organization_id=organization_id, user_id=t.user_id, shift_date=t.shift_date + delta,
                         starts_at=a, ends_at=b, break_minutes=t.break_minutes, project_id=t.project_id,
                         notes=t.notes, status="scheduled", created_by_user_id=actor.id))
        await db.flush()
        creados += 1
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.week_copied", entity_type="work_shift",
                             after_data={"from": source_monday.isoformat(), "to": target_monday.isoformat(),
                                         "created": creados, "skipped": saltados})
    await db.commit()
    return {"created": creados, "skipped": saltados}


async def list_shifts(db: AsyncSession, *, organization_id: uuid.UUID, date_from: date, date_to: date,
                      user_id: uuid.UUID | None = None, include_cancelled: bool = False) -> list[dict]:
    if date_to < date_from or (date_to - date_from).days >= MAX_BULK_DAYS:
        raise InvalidInputError(f"El rango debe ser de 1 a {MAX_BULK_DAYS} días.", code="invalid_range")
    stmt = (select(WorkShift, User.full_name, Project.title)
            .join(User, User.id == WorkShift.user_id)
            .outerjoin(Project, Project.id == WorkShift.project_id)
            .where(WorkShift.organization_id == organization_id, WorkShift.shift_date >= date_from,
                   WorkShift.shift_date <= date_to))
    if user_id:
        stmt = stmt.where(WorkShift.user_id == user_id)
    if not include_cancelled:
        stmt = stmt.where(WorkShift.status == "scheduled")
    filas = (await db.execute(stmt.order_by(WorkShift.shift_date, User.full_name, WorkShift.starts_at))).all()
    s = await get_settings(db, organization_id)
    ids = [t.id for t, _, _ in filas]
    marcas = {}
    if ids:
        for e in (await db.execute(select(TimeEntry).where(TimeEntry.organization_id == organization_id,
                                                           TimeEntry.shift_id.in_(ids)))).scalars():
            marcas[e.shift_id] = e
    ahora = now()
    salida = []
    for t, nombre, titulo in filas:
        e = marcas.get(t.id)
        fila = shift_out(t, user_name=nombre, project_title=titulo)
        fila["compliance"] = calc.shift_status(t, e, now=ahora, late_tolerance=s.late_tolerance_minutes,
                                               early_tolerance=s.early_leave_tolerance_minutes)
        fila["entry_id"] = str(e.id) if e else None
        salida.append(fila)
    return salida


async def people(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Personas activas para la malla y los filtros (solo id, nombre y roles)."""
    filas = (await db.execute(select(User).where(User.organization_id == organization_id,
                                                 User.status == UserStatus.active)
                              .order_by(User.full_name))).scalars().all()
    return [{"id": str(u.id), "full_name": u.full_name,
             "roles": sorted(ur.role.code for ur in u.roles)} for u in filas]


def own_or_permission(user: User, target_user_id: uuid.UUID, permission: str) -> None:
    if target_user_id != user.id and permission not in perms(user):
        raise NotFoundError("No existe.", code="not_found")

