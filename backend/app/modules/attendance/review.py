"""Novedades, correcciones, aprobación de horas y períodos de nómina.

Reglas que no se negocian (spec, «Permisos y privacidad»):

- Nadie aprueba sus propias horas ni sus propias novedades.
- Una corrección guarda el valor original, quién la hizo, cuándo y por qué
  (`time_entry_corrections`) antes de cambiar la marcación.
- Un período cerrado no se toca; reabrirlo exige motivo y queda en su
  historial.
"""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance import calc
from app.modules.attendance.models import (
    AttendanceEvent,
    AttendanceNovelty,
    NoveltyReason,
    PayrollPeriod,
    PayrollPeriodEvent,
    TimeEntry,
    TimeEntryCorrection,
    WorkShift,
)
from app.modules.attendance.service import (
    ensure_period_open,
    entry_out,
    get_settings,
    now,
    perms,
)
from app.modules.field_ops import clock
from app.modules.users.models import User
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

NOVELTY_KINDS = {
    "late_arrival": "Llegada tarde",
    "early_departure": "Salida anticipada",
    "missed_clock_in": "Olvidé marcar la entrada",
    "missed_clock_out": "Olvidé marcar la salida",
    "correction": "Corregir una marcación",
    "absence": "Ausencia",
    "connectivity": "Sin señal o sin GPS",
    "other": "Otra",
}
# Las que, aprobadas, cambian las horas.
CORRECTING_KINDS = {"missed_clock_in", "missed_clock_out", "correction"}

DEFAULT_REASONS = [
    ("traffic", "Tráfico o vía cerrada"),
    ("vehicle", "Falla del vehículo"),
    ("medical", "Cita médica o enfermedad"),
    ("family", "Calamidad familiar"),
    ("no_signal", "Sin señal en el sitio"),
    ("phone", "Celular sin batería o dañado"),
    ("forgot", "Olvidé marcar"),
    ("assigned_task", "Tarea asignada por la oficina"),
    ("other", "Otro"),
]


def _not_self(actor: User, user_id: uuid.UUID, que: str) -> None:
    if actor.id == user_id:
        raise ForbiddenError(f"No puedes {que} lo tuyo; debe hacerlo otra persona.", code="self_review")


# ---------------------------------------------------------------------------
# Catálogo de motivos
# ---------------------------------------------------------------------------

async def ensure_reasons(db: AsyncSession, organization_id: uuid.UUID) -> None:
    hay = (await db.execute(select(NoveltyReason.id).where(
        NoveltyReason.organization_id == organization_id).limit(1))).first()
    if hay:
        return
    for i, (code, name) in enumerate(DEFAULT_REASONS):
        db.add(NoveltyReason(organization_id=organization_id, code=code, name=name, active=True, sort_order=i))
    await db.commit()


def reason_out(r: NoveltyReason) -> dict:
    return {"id": str(r.id), "code": r.code, "name": r.name, "active": r.active, "sort_order": r.sort_order}


async def list_reasons(db: AsyncSession, organization_id: uuid.UUID, *, include_inactive: bool) -> list[dict]:
    await ensure_reasons(db, organization_id)
    stmt = select(NoveltyReason).where(NoveltyReason.organization_id == organization_id)
    if not include_inactive:
        stmt = stmt.where(NoveltyReason.active.is_(True))
    return [reason_out(r) for r in (await db.execute(stmt.order_by(NoveltyReason.sort_order,
                                                                    NoveltyReason.name))).scalars()]


async def save_reason(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, data: dict,
                      reason_id: uuid.UUID | None = None) -> dict:
    await ensure_reasons(db, organization_id)
    if reason_id:
        r = (await db.execute(select(NoveltyReason).where(
            NoveltyReason.id == reason_id, NoveltyReason.organization_id == organization_id))).scalar_one_or_none()
        if r is None:
            raise NotFoundError("El motivo no existe.", code="reason_not_found")
        r.name = data["name"]
        r.active = data.get("active", r.active)
    else:
        code = data.get("code") or data["name"].strip().lower().replace(" ", "_")[:40]
        existe = (await db.execute(select(NoveltyReason.id).where(
            NoveltyReason.organization_id == organization_id, NoveltyReason.code == code))).first()
        if existe:
            raise ConflictError("Ya hay un motivo con ese código.", code="reason_exists")
        r = NoveltyReason(organization_id=organization_id, code=code, name=data["name"],
                          active=data.get("active", True), sort_order=100)
        db.add(r)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.reason_saved", entity_type="novelty_reason",
                             entity_id=str(r.id), after_data=reason_out(r))
    await db.commit()
    return reason_out(r)


# ---------------------------------------------------------------------------
# Novedades
# ---------------------------------------------------------------------------

async def _novelty_names(db, items: list[AttendanceNovelty]) -> tuple[dict, dict]:
    uids = {n.user_id for n in items} | {n.reviewed_by_user_id for n in items if n.reviewed_by_user_id}
    nombres = {}
    if uids:
        nombres = dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(uids)))).all())
    rids = {n.reason_id for n in items if n.reason_id}
    motivos = {}
    if rids:
        motivos = dict((await db.execute(select(NoveltyReason.id, NoveltyReason.name).where(
            NoveltyReason.id.in_(rids)))).all())
    return nombres, motivos


def novelty_out(n: AttendanceNovelty, nombres: dict, motivos: dict) -> dict:
    return {
        "id": str(n.id), "user_id": str(n.user_id), "user_name": nombres.get(n.user_id),
        "kind": n.kind, "kind_label": NOVELTY_KINDS.get(n.kind, n.kind),
        "reason_id": str(n.reason_id) if n.reason_id else None, "reason_name": motivos.get(n.reason_id),
        "work_date": n.work_date.isoformat(), "description": n.description,
        "time_entry_id": str(n.time_entry_id) if n.time_entry_id else None,
        "shift_id": str(n.shift_id) if n.shift_id else None,
        "requested_clock_in_at": as_utc(n.requested_clock_in_at).isoformat() if n.requested_clock_in_at else None,
        "requested_clock_out_at": as_utc(n.requested_clock_out_at).isoformat() if n.requested_clock_out_at
        else None,
        "status": n.status, "reviewed_by_name": nombres.get(n.reviewed_by_user_id),
        "reviewed_at": as_utc(n.reviewed_at).isoformat() if n.reviewed_at else None,
        "review_note": n.review_note, "created_at": as_utc(n.created_at).isoformat() if n.created_at else None,
    }


async def create_novelty(db: AsyncSession, *, organization_id: uuid.UUID, user: User, data: dict) -> dict:
    if data["kind"] not in NOVELTY_KINDS:
        raise InvalidInputError("Tipo de novedad no válido.", code="invalid_kind")
    if data.get("reason_id"):
        ok = (await db.execute(select(NoveltyReason.id).where(
            NoveltyReason.id == data["reason_id"], NoveltyReason.organization_id == organization_id,
            NoveltyReason.active.is_(True)))).first()
        if not ok:
            raise InvalidInputError("El motivo no existe.", code="invalid_reason")
    for campo, modelo in (("time_entry_id", TimeEntry), ("shift_id", WorkShift)):
        if data.get(campo):
            fila = await db.get(modelo, data[campo])
            # Solo sobre lo propio: una marcación ajena responde como si no existiera.
            if fila is None or fila.organization_id != organization_id or fila.user_id != user.id:
                raise NotFoundError("No existe.", code="not_found")
    entrada, salida = data.get("requested_clock_in_at"), data.get("requested_clock_out_at")
    if entrada and salida and as_utc(salida) <= as_utc(entrada):
        raise InvalidInputError("La salida debe ser después de la entrada.", code="invalid_range")
    for momento in (entrada, salida):
        if momento and as_utc(momento) > now() + timedelta(minutes=5):
            raise InvalidInputError("No se puede pedir una hora en el futuro.", code="future_time")
    dia = data.get("work_date") or await clock.org_today(db, organization_id)
    if data["kind"] in CORRECTING_KINDS and not (entrada or salida):
        raise InvalidInputError("Indica la hora que debe quedar.", code="time_required")
    n = AttendanceNovelty(organization_id=organization_id, user_id=user.id, kind=data["kind"],
                          reason_id=data.get("reason_id"), work_date=dia,
                          description=(data.get("description") or None),
                          time_entry_id=data.get("time_entry_id"), shift_id=data.get("shift_id"),
                          requested_clock_in_at=entrada, requested_clock_out_at=salida, status="pending",
                          created_by_user_id=user.id)
    db.add(n)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="attendance.novelty_created", entity_type="attendance_novelty",
                             entity_id=str(n.id), after_data={"kind": n.kind, "work_date": dia.isoformat()})
    await db.commit()
    nombres, motivos = await _novelty_names(db, [n])
    return novelty_out(n, nombres, motivos)


async def list_novelties(db: AsyncSession, *, organization_id: uuid.UUID, user: User, status: str | None,
                         user_id: uuid.UUID | None, date_from: date | None, date_to: date | None,
                         limit: int, offset: int) -> tuple[list[dict], int]:
    from sqlalchemy import func

    stmt = select(AttendanceNovelty).where(AttendanceNovelty.organization_id == organization_id)
    if "attendance.review" not in perms(user):
        stmt = stmt.where(AttendanceNovelty.user_id == user.id)
    elif user_id:
        stmt = stmt.where(AttendanceNovelty.user_id == user_id)
    if status:
        stmt = stmt.where(AttendanceNovelty.status == status)
    if date_from:
        stmt = stmt.where(AttendanceNovelty.work_date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceNovelty.work_date <= date_to)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    items = list((await db.execute(stmt.order_by(AttendanceNovelty.created_at.desc(), AttendanceNovelty.id)
                                   .limit(limit).offset(offset))).scalars())
    nombres, motivos = await _novelty_names(db, items)
    return [novelty_out(n, nombres, motivos) for n in items], total


async def _get_novelty(db, organization_id, novelty_id) -> AttendanceNovelty:
    n = (await db.execute(select(AttendanceNovelty).where(
        AttendanceNovelty.id == novelty_id, AttendanceNovelty.organization_id == organization_id)
    )).scalar_one_or_none()
    if n is None:
        raise NotFoundError("La novedad no existe.", code="novelty_not_found")
    if n.status != "pending":
        raise ConflictError("La novedad ya fue revisada.", code="novelty_reviewed")
    return n


async def review_novelty(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, novelty_id: uuid.UUID,
                         approve: bool, note: str | None) -> dict:
    n = await _get_novelty(db, organization_id, novelty_id)
    _not_self(actor, n.user_id, "aprobar ni rechazar")
    if not approve and not (note or "").strip():
        raise InvalidInputError("Escribe por qué se rechaza.", code="note_required")
    if approve and n.kind in CORRECTING_KINDS:
        await _apply_novelty(db, organization_id=organization_id, actor=actor, n=n, note=note)
    n.status = "approved" if approve else "rejected"
    n.reviewed_by_user_id, n.reviewed_at, n.review_note = actor.id, now(), note
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action=f"attendance.novelty_{n.status}", entity_type="attendance_novelty",
                             entity_id=str(n.id), after_data={"note": note})
    await db.commit()
    nombres, motivos = await _novelty_names(db, [n])
    return novelty_out(n, nombres, motivos)


async def _apply_novelty(db, *, organization_id, actor, n: AttendanceNovelty, note) -> None:
    """Aprobar una corrección cambia la marcación (o crea la que faltó)."""
    motivo = f"Novedad aprobada: {NOVELTY_KINDS[n.kind]}" + (f" · {note}" if note else "")
    entry = None
    if n.time_entry_id:
        entry = await db.get(TimeEntry, n.time_entry_id)
    elif n.shift_id:
        entry = (await db.execute(select(TimeEntry).where(
            TimeEntry.organization_id == organization_id, TimeEntry.shift_id == n.shift_id))).scalar_one_or_none()
    if entry is None:
        if not n.requested_clock_in_at:
            raise InvalidInputError("Para crear la marcación que faltó se necesita la hora de entrada.",
                                    code="time_required")
        await _create_entry(db, organization_id=organization_id, actor=actor, user_id=n.user_id,
                            shift_id=n.shift_id, work_date=n.work_date, clock_in_at=n.requested_clock_in_at,
                            clock_out_at=n.requested_clock_out_at, reason=motivo, novelty_id=n.id)
        return
    await correct_entry(db, organization_id=organization_id, actor=actor, entry_id=entry.id,
                        clock_in_at=n.requested_clock_in_at, clock_out_at=n.requested_clock_out_at,
                        reason=motivo, novelty_id=n.id, commit=False)


# ---------------------------------------------------------------------------
# Correcciones y aprobación
# ---------------------------------------------------------------------------

def _snapshot(e: TimeEntry) -> dict:
    return {"clock_in_at": as_utc(e.clock_in_at).isoformat(),
            "clock_out_at": as_utc(e.clock_out_at).isoformat() if e.clock_out_at else None,
            "status": e.status, "approved_minutes": e.approved_minutes}


async def get_entry(db: AsyncSession, organization_id: uuid.UUID, entry_id: uuid.UUID) -> TimeEntry:
    e = (await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id,
                                                  TimeEntry.organization_id == organization_id))).scalar_one_or_none()
    if e is None:
        raise NotFoundError("La marcación no existe.", code="entry_not_found")
    return e


async def _create_entry(db, *, organization_id, actor, user_id, shift_id, work_date, clock_in_at, clock_out_at,
                        reason, novelty_id=None) -> TimeEntry:
    await ensure_period_open(db, organization_id, work_date)
    abierta = clock_out_at is None
    if abierta:
        raise InvalidInputError("Una marcación creada por la oficina necesita entrada y salida.",
                                code="time_required")
    e = TimeEntry(organization_id=organization_id, user_id=user_id, shift_id=shift_id, work_date=work_date,
                  clock_in_at=clock_in_at, clock_in_received_at=now(), clock_out_at=clock_out_at,
                  clock_out_received_at=now(), status="closed", closed_by="admin", pauses=[])
    db.add(e)
    await db.flush()
    db.add(TimeEntryCorrection(organization_id=organization_id, time_entry_id=e.id, novelty_id=novelty_id,
                               corrected_by_user_id=actor.id, corrected_at=now(), reason=reason,
                               before_data={}, after_data=_snapshot(e)))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.entry_created", entity_type="time_entry", entity_id=str(e.id),
                             after_data=_snapshot(e))
    return e


async def correct_entry(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, entry_id: uuid.UUID,
                        clock_in_at: datetime | None, clock_out_at: datetime | None, reason: str,
                        novelty_id: uuid.UUID | None = None, commit: bool = True) -> dict:
    """Corrige entrada y/o salida. Cerrar una marcación olvidada abierta es
    también una corrección (la regulariza Administración)."""
    if not (reason or "").strip():
        raise InvalidInputError("Escribe el motivo de la corrección.", code="reason_required")
    e = await get_entry(db, organization_id, entry_id)
    _not_self(actor, e.user_id, "corregir")
    if e.status == "approved":
        raise ConflictError("La marcación ya está aprobada; quita la aprobación para corregirla.",
                            code="entry_approved")
    nueva_entrada = as_utc(clock_in_at) if clock_in_at else as_utc(e.clock_in_at)
    nueva_salida = as_utc(clock_out_at) if clock_out_at else (as_utc(e.clock_out_at) if e.clock_out_at else None)
    if nueva_salida is not None and nueva_salida <= nueva_entrada:
        raise InvalidInputError("La salida debe ser después de la entrada.", code="invalid_range")
    if nueva_salida is not None and nueva_salida - nueva_entrada > timedelta(hours=24):
        raise InvalidInputError("Una jornada no puede pasar de 24 horas.", code="invalid_range")
    zona = await clock.org_zone(db, organization_id)
    await ensure_period_open(db, organization_id, e.work_date, clock.local_date(nueva_entrada, zona))
    antes = _snapshot(e)
    e.clock_in_at = nueva_entrada
    if nueva_salida is not None:
        e.clock_out_at = nueva_salida
        if e.status == "open":
            e.status, e.closed_by, e.clock_out_received_at = "closed", "admin", now()
            for p in e.pauses:
                if p.ended_at is None:
                    p.ended_at = max(nueva_salida, as_utc(p.started_at))
    db.add(TimeEntryCorrection(organization_id=organization_id, time_entry_id=e.id, novelty_id=novelty_id,
                               corrected_by_user_id=actor.id, corrected_at=now(), reason=reason.strip(),
                               before_data=antes, after_data=_snapshot(e)))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.entry_corrected", entity_type="time_entry", entity_id=str(e.id),
                             before_data=antes, after_data=_snapshot(e))
    if commit:
        await db.commit()
    s = await get_settings(db, organization_id)
    return entry_out(e, now=now(), paid_pauses=s.paid_pauses)


async def approve_entries(db: AsyncSession, *, organization_id: uuid.UUID, actor: User,
                          entry_ids: list[uuid.UUID], approved_minutes: int | None = None) -> dict:
    s = await get_settings(db, organization_id)
    aprobadas, errores = [], []
    for eid in dict.fromkeys(entry_ids):
        try:
            e = await get_entry(db, organization_id, eid)
            _not_self(actor, e.user_id, "aprobar")
            if e.status != "closed":
                raise ConflictError("Solo se aprueban marcaciones cerradas.", code="entry_not_closed")
            await ensure_period_open(db, organization_id, e.work_date)
            horas = calc.entry_hours(e, now=now(), paid_pauses=s.paid_pauses)
            minutos = approved_minutes if approved_minutes is not None and len(entry_ids) == 1 else horas.effective
            if minutos < 0 or minutos > 24 * 60:
                raise InvalidInputError("Minutos aprobados no válidos.", code="invalid_minutes")
            antes = _snapshot(e)
            e.status, e.approved_minutes, e.approved_by_user_id, e.approved_at = "approved", minutos, actor.id, now()
            await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                                     action="attendance.entry_approved", entity_type="time_entry",
                                     entity_id=str(e.id), before_data=antes, after_data=_snapshot(e))
            aprobadas.append(str(e.id))
        except (ConflictError, ForbiddenError, InvalidInputError, NotFoundError) as exc:
            errores.append({"entry_id": str(eid), "code": exc.code, "message": exc.message})
    await db.commit()
    return {"approved": aprobadas, "errors": errores}


async def unapprove_entry(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, entry_id: uuid.UUID,
                          reason: str) -> None:
    if not (reason or "").strip():
        raise InvalidInputError("Escribe el motivo.", code="reason_required")
    e = await get_entry(db, organization_id, entry_id)
    if e.status != "approved":
        raise ConflictError("La marcación no está aprobada.", code="entry_not_approved")
    await ensure_period_open(db, organization_id, e.work_date)
    antes = _snapshot(e)
    e.status, e.approved_minutes, e.approved_by_user_id, e.approved_at = "closed", None, None, None
    db.add(TimeEntryCorrection(organization_id=organization_id, time_entry_id=e.id, corrected_by_user_id=actor.id,
                               corrected_at=now(), reason=f"Aprobación retirada: {reason.strip()}",
                               before_data=antes, after_data=_snapshot(e)))
    await db.commit()


async def entry_detail(db: AsyncSession, *, organization_id: uuid.UUID, user: User, entry_id: uuid.UUID) -> dict:
    e = await get_entry(db, organization_id, entry_id)
    p = perms(user)
    if e.user_id != user.id and not ({"attendance.review", "attendance.dashboard"} & p):
        raise NotFoundError("La marcación no existe.", code="entry_not_found")
    ve_ubicacion = e.user_id == user.id or "locations.view" in p
    s = await get_settings(db, organization_id)
    eventos = (await db.execute(select(AttendanceEvent).where(
        AttendanceEvent.organization_id == organization_id, AttendanceEvent.time_entry_id == e.id
    ).order_by(AttendanceEvent.occurred_at))).scalars().all()
    correcciones = (await db.execute(select(TimeEntryCorrection, User.full_name).join(
        User, User.id == TimeEntryCorrection.corrected_by_user_id).where(
        TimeEntryCorrection.organization_id == organization_id, TimeEntryCorrection.time_entry_id == e.id
    ).order_by(TimeEntryCorrection.corrected_at))).all()
    return {
        **entry_out(e, now=now(), paid_pauses=s.paid_pauses),
        "events": [event_out(ev, with_location=ve_ubicacion) for ev in eventos],
        "corrections": [{"by": nombre, "at": as_utc(c.corrected_at).isoformat(), "reason": c.reason,
                         "before": c.before_data, "after": c.after_data} for c, nombre in correcciones],
    }


def event_out(ev: AttendanceEvent, *, with_location: bool) -> dict:
    fuera = {"id": str(ev.id), "event_type": ev.event_type, "occurred_at": as_utc(ev.occurred_at).isoformat(),
             "received_at": as_utc(ev.received_at).isoformat(),
             "device_at": as_utc(ev.device_at).isoformat() if ev.device_at else None,
             "offline": ev.offline, "project_id": str(ev.project_id) if ev.project_id else None,
             "location_status": ev.location_status, "note": ev.note,
             "distance_km": ev.distance_km, "distance_source": ev.distance_source}
    if with_location:
        fuera.update(latitude=ev.latitude, longitude=ev.longitude, accuracy_m=ev.accuracy_m)
    return fuera


# ---------------------------------------------------------------------------
# Períodos de nómina
# ---------------------------------------------------------------------------

def period_out(p: PayrollPeriod) -> dict:
    return {"id": str(p.id), "start_date": p.start_date.isoformat(), "end_date": p.end_date.isoformat(),
            "status": p.status, "closed_at": as_utc(p.closed_at).isoformat() if p.closed_at else None}


async def create_period(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, start: date,
                        end: date) -> dict:
    if end < start or (end - start).days > 31:
        raise InvalidInputError("Un período va de 1 a 31 días.", code="invalid_range")
    choca = (await db.execute(select(PayrollPeriod.id).where(
        PayrollPeriod.organization_id == organization_id, PayrollPeriod.start_date <= end,
        PayrollPeriod.end_date >= start))).first()
    if choca:
        raise ConflictError("Se cruza con otro período.", code="period_overlap")
    p = PayrollPeriod(organization_id=organization_id, start_date=start, end_date=end, status="open")
    db.add(p)
    await db.flush()
    db.add(PayrollPeriodEvent(organization_id=organization_id, period_id=p.id, action="created", user_id=actor.id,
                              at=now()))
    await db.commit()
    return period_out(p)


async def list_periods(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    filas = (await db.execute(select(PayrollPeriod).where(PayrollPeriod.organization_id == organization_id)
                              .order_by(PayrollPeriod.start_date.desc()).limit(60))).scalars().all()
    salida = []
    for p in filas:
        hist = (await db.execute(select(PayrollPeriodEvent, User.full_name).join(
            User, User.id == PayrollPeriodEvent.user_id).where(PayrollPeriodEvent.period_id == p.id)
            .order_by(PayrollPeriodEvent.at))).all()
        salida.append({**period_out(p), "history": [
            {"action": ev.action, "by": nombre, "at": as_utc(ev.at).isoformat(), "reason": ev.reason}
            for ev, nombre in hist]})
    return salida


async def set_period_status(db: AsyncSession, *, organization_id: uuid.UUID, actor: User, period_id: uuid.UUID,
                            close: bool, reason: str | None) -> dict:
    p = (await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id,
                                                      PayrollPeriod.organization_id == organization_id))
         ).scalar_one_or_none()
    if p is None:
        raise NotFoundError("El período no existe.", code="period_not_found")
    if close:
        if p.status == "closed":
            raise ConflictError("El período ya está cerrado.", code="period_closed")
        abiertas = (await db.execute(select(TimeEntry.id).where(
            TimeEntry.organization_id == organization_id, TimeEntry.status == "open",
            TimeEntry.work_date >= p.start_date, TimeEntry.work_date <= p.end_date).limit(1))).first()
        if abiertas:
            raise ConflictError("Hay marcaciones sin salida en el período; regularízalas antes de cerrar.",
                                code="period_has_open_entries")
        p.status, p.closed_by_user_id, p.closed_at = "closed", actor.id, now()
    else:
        if p.status != "closed":
            raise ConflictError("El período no está cerrado.", code="period_not_closed")
        if not (reason or "").strip():
            raise InvalidInputError("Escribe por qué se reabre.", code="reason_required")
        p.status, p.closed_by_user_id, p.closed_at = "open", None, None
    db.add(PayrollPeriodEvent(organization_id=organization_id, period_id=p.id,
                              action="closed" if close else "reopened", user_id=actor.id, at=now(),
                              reason=(reason or None)))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.period_closed" if close else "attendance.period_reopened",
                             entity_type="payroll_period", entity_id=str(p.id), after_data={"reason": reason})
    await db.commit()
    return period_out(p)
