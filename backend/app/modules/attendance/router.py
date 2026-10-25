"""Rutas de turnos, asistencia, nómina y mapa operativo. Cada una con su
permiso; la organización sale del token (spec, «Permisos y privacidad»)."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.attendance import mapdata, reports, review
from app.modules.attendance import service as svc
from app.modules.users.models import User
from app.shared.pagination import paginate_list, pagination_params

router = APIRouter(tags=["attendance"])

_clock = require_permission("attendance.clock")
_shifts = require_permission("shifts.manage")
_review = require_permission("attendance.review")
_dashboard = require_permission("attendance.dashboard")
_payroll_close = require_permission("payroll.close")
_shifts_read = require_any_permission("shifts.manage", "attendance.review", "attendance.dashboard")
_entries_read = require_any_permission("attendance.review", "attendance.dashboard")
_novelties = require_any_permission("attendance.clock", "attendance.review")
_map = require_any_permission("locations.view", "projects.read_all", "projects.read_assigned")
_project_location = require_permission("projects.update")


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------

class EventIn(BaseModel):
    event_type: str = Field(max_length=30)
    client_event_id: str | None = Field(default=None, min_length=8, max_length=64)
    device_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    location_status: str | None = Field(default=None, max_length=20)
    project_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class EventBatchIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=100)


class SettingsIn(BaseModel):
    late_tolerance_minutes: int | None = Field(default=None, ge=0, le=240)
    early_leave_tolerance_minutes: int | None = Field(default=None, ge=0, le=240)
    daily_overtime_after_minutes: int | None = Field(default=None, ge=0, le=1440)
    weekly_overtime_after_minutes: int | None = Field(default=None, ge=0, le=10080)
    tracking_interval_minutes: int | None = Field(default=None, ge=0, le=240)
    location_retention_days: int | None = Field(default=None, ge=1, le=730)
    require_clock_in_for_field_work: bool | None = None
    paid_pauses: bool | None = None


class ShiftsIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    date_from: date
    date_to: date
    weekdays: list[int] | None = Field(default=None, max_length=7)
    start_time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    break_minutes: int = Field(default=0, ge=0, le=480)
    project_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=255)


class ShiftUpdateIn(BaseModel):
    model_config = {"extra": "forbid"}
    shift_date: date | None = None
    start_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    break_minutes: int | None = Field(default=None, ge=0, le=480)
    project_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=255)


class CopyWeekIn(BaseModel):
    source_monday: date
    target_monday: date
    user_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class ReasonIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9_]+$")
    active: bool = True


class NoveltyIn(BaseModel):
    kind: str = Field(max_length=30)
    reason_id: uuid.UUID | None = None
    work_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    time_entry_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    requested_clock_in_at: datetime | None = None
    requested_clock_out_at: datetime | None = None


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class CorrectionIn(BaseModel):
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=2000)


class ApproveIn(BaseModel):
    entry_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    approved_minutes: int | None = Field(default=None, ge=0, le=1440)


class ReasonOnlyIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class PeriodIn(BaseModel):
    start_date: date
    end_date: date


class PeriodStatusIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


# ---------------------------------------------------------------------------
# Mi turno
# ---------------------------------------------------------------------------

@router.get("/attendance/me")
async def my_attendance(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_clock)) -> dict:
    return await svc.me(db, organization_id=organization_id, user=current_user)


@router.get("/attendance/me/summary")
async def my_clock_out_summary(db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_clock)) -> dict:
    return await svc.clock_out_summary(db, organization_id=organization_id, user=current_user)


@router.get("/attendance/me/entries")
async def my_entries(response: Response, date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_clock)) -> list[dict]:
    return paginate_list(await _entries(db, organization_id, date_from, date_to, current_user.id, None),
                         limit=pag[0], offset=pag[1], response=response)


@router.post("/attendance/events", status_code=201)
async def post_event(payload: EventIn, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_clock)) -> dict:
    return await svc.record_event(db, organization_id=organization_id, user=current_user, data=payload.model_dump())


@router.post("/attendance/events/batch")
async def post_events_batch(payload: EventBatchIn, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_clock)) -> dict:
    """La cola del teléfono: cada evento con su resultado."""
    return {"results": await svc.record_events_batch(
        db, organization_id=organization_id, user=current_user, events=[e.model_dump() for e in payload.events])}


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

@router.get("/attendance/settings")
async def get_attendance_settings(db: AsyncSession = Depends(get_db),
                                  organization_id: uuid.UUID = Depends(get_organization_id),
                                  current_user: User = Depends(_shifts_read)) -> dict:
    s = svc.settings_out(await svc.get_settings(db, organization_id))
    await db.commit()
    return s


@router.put("/attendance/settings")
async def put_attendance_settings(payload: SettingsIn, db: AsyncSession = Depends(get_db),
                                  organization_id: uuid.UUID = Depends(get_organization_id),
                                  current_user: User = Depends(_review)) -> dict:
    return await svc.update_settings(db, organization_id=organization_id, user=current_user,
                                     data=payload.model_dump(exclude_none=True))


@router.get("/attendance/people")
async def attendance_people(response: Response, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            pag: tuple[int, int] = Depends(pagination_params),
                            current_user: User = Depends(_shifts_read)) -> list[dict]:
    return paginate_list(await svc.people(db, organization_id), limit=pag[0], offset=pag[1], response=response)


# ---------------------------------------------------------------------------
# Malla
# ---------------------------------------------------------------------------

@router.get("/attendance/shifts")
async def list_shifts(response: Response, date_from: date, date_to: date, user_id: uuid.UUID | None = None,
                      include_cancelled: bool = False, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      pag: tuple[int, int] = Depends(pagination_params),
                      current_user: User = Depends(_shifts_read)) -> list[dict]:
    filas = await svc.list_shifts(db, organization_id=organization_id, date_from=date_from, date_to=date_to,
                                  user_id=user_id, include_cancelled=include_cancelled)
    await db.commit()
    return paginate_list(filas, limit=pag[0], offset=pag[1], response=response)


@router.get("/attendance/me/shifts")
async def my_shifts(response: Response, date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    pag: tuple[int, int] = Depends(pagination_params),
                    current_user: User = Depends(_clock)) -> list[dict]:
    filas = await svc.list_shifts(db, organization_id=organization_id, date_from=date_from, date_to=date_to,
                                  user_id=current_user.id)
    await db.commit()
    return paginate_list(filas, limit=pag[0], offset=pag[1], response=response)


@router.post("/attendance/shifts", status_code=201)
async def create_shifts(payload: ShiftsIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_shifts)) -> dict:
    return await svc.create_shifts(db, organization_id=organization_id, actor=current_user,
                                   data=payload.model_dump())


@router.post("/attendance/shifts/copy-week", status_code=201)
async def copy_week(payload: CopyWeekIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_shifts)) -> dict:
    return await svc.copy_week(db, organization_id=organization_id, actor=current_user,
                               source_monday=payload.source_monday, target_monday=payload.target_monday,
                               user_ids=payload.user_ids)


@router.patch("/attendance/shifts/{shift_id}")
async def update_shift(shift_id: uuid.UUID, payload: ShiftUpdateIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_shifts)) -> dict:
    return await svc.update_shift(db, organization_id=organization_id, actor=current_user, shift_id=shift_id,
                                  data=payload.model_dump(exclude_unset=True))


@router.delete("/attendance/shifts/{shift_id}", status_code=204)
async def cancel_shift(shift_id: uuid.UUID, reason: str | None = Query(default=None, max_length=255),
                       db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_shifts)) -> None:
    await svc.cancel_shift(db, organization_id=organization_id, actor=current_user, shift_id=shift_id, reason=reason)


# ---------------------------------------------------------------------------
# Marcaciones (oficina)
# ---------------------------------------------------------------------------

async def _entries(db, organization_id, date_from, date_to, user_id, status) -> list[dict]:
    from sqlalchemy import select

    from app.modules.attendance.models import TimeEntry
    from app.shared.errors import InvalidInputError

    if date_to < date_from or (date_to - date_from).days >= reports.MAX_RANGE_DAYS:
        raise InvalidInputError(f"El rango debe ser de 1 a {reports.MAX_RANGE_DAYS} días.", code="invalid_range")
    stmt = select(TimeEntry).where(TimeEntry.organization_id == organization_id,
                                   TimeEntry.work_date >= date_from, TimeEntry.work_date <= date_to)
    if user_id:
        stmt = stmt.where(TimeEntry.user_id == user_id)
    if status:
        stmt = stmt.where(TimeEntry.status == status)
    filas = list((await db.execute(stmt.order_by(TimeEntry.work_date.desc(), TimeEntry.clock_in_at.desc())
                                   .limit(2000))).scalars())
    s = await svc.get_settings(db, organization_id)
    nombres = await reports._names(db, organization_id, list({e.user_id for e in filas}))
    ahora = svc.now()
    return [{**svc.entry_out(e, now=ahora, paid_pauses=s.paid_pauses), "user_name": nombres.get(e.user_id)}
            for e in filas]


@router.get("/attendance/entries")
async def list_entries(response: Response, date_from: date, date_to: date, user_id: uuid.UUID | None = None,
                       status: str | None = Query(default=None, pattern="^(open|closed|approved)$"),
                       db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_entries_read)) -> list[dict]:
    return paginate_list(await _entries(db, organization_id, date_from, date_to, user_id, status),
                         limit=pag[0], offset=pag[1], response=response)


@router.get("/attendance/entries/{entry_id}")
async def get_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_novelties)) -> dict:
    return await review.entry_detail(db, organization_id=organization_id, user=current_user, entry_id=entry_id)


@router.post("/attendance/entries/{entry_id}/correct")
async def correct_entry(entry_id: uuid.UUID, payload: CorrectionIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_review)) -> dict:
    return await review.correct_entry(db, organization_id=organization_id, actor=current_user, entry_id=entry_id,
                                      clock_in_at=payload.clock_in_at, clock_out_at=payload.clock_out_at,
                                      reason=payload.reason)


@router.post("/attendance/entries/approve")
async def approve_entries(payload: ApproveIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_review)) -> dict:
    return await review.approve_entries(db, organization_id=organization_id, actor=current_user,
                                        entry_ids=payload.entry_ids, approved_minutes=payload.approved_minutes)


@router.post("/attendance/entries/{entry_id}/unapprove", status_code=204)
async def unapprove_entry(entry_id: uuid.UUID, payload: ReasonOnlyIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_review)) -> None:
    await review.unapprove_entry(db, organization_id=organization_id, actor=current_user, entry_id=entry_id,
                                 reason=payload.reason)


# ---------------------------------------------------------------------------
# Novedades
# ---------------------------------------------------------------------------

@router.get("/attendance/novelty-reasons")
async def list_reasons(response: Response, include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_novelties)) -> list[dict]:
    return paginate_list(await review.list_reasons(db, organization_id, include_inactive=include_inactive),
                         limit=pag[0], offset=pag[1], response=response)


@router.post("/attendance/novelty-reasons", status_code=201)
async def create_reason(payload: ReasonIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_review)) -> dict:
    return await review.save_reason(db, organization_id=organization_id, actor=current_user,
                                    data=payload.model_dump())


@router.put("/attendance/novelty-reasons/{reason_id}")
async def update_reason(reason_id: uuid.UUID, payload: ReasonIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_review)) -> dict:
    return await review.save_reason(db, organization_id=organization_id, actor=current_user,
                                    data=payload.model_dump(), reason_id=reason_id)


@router.post("/attendance/novelties", status_code=201)
async def create_novelty(payload: NoveltyIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_clock)) -> dict:
    return await review.create_novelty(db, organization_id=organization_id, user=current_user,
                                       data=payload.model_dump())


@router.get("/attendance/novelties")
async def list_novelties(response: Response,
                         status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
                         user_id: uuid.UUID | None = None, date_from: date | None = None,
                         date_to: date | None = None, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         pag: tuple[int, int] = Depends(pagination_params),
                         current_user: User = Depends(_novelties)) -> list[dict]:
    items, total = await review.list_novelties(db, organization_id=organization_id, user=current_user,
                                               status=status, user_id=user_id, date_from=date_from,
                                               date_to=date_to, limit=pag[0], offset=pag[1])
    response.headers["X-Total-Count"] = str(total)
    return items


@router.post("/attendance/novelties/{novelty_id}/approve")
async def approve_novelty(novelty_id: uuid.UUID, payload: ReviewIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_review)) -> dict:
    return await review.review_novelty(db, organization_id=organization_id, actor=current_user,
                                       novelty_id=novelty_id, approve=True, note=payload.note)


@router.post("/attendance/novelties/{novelty_id}/reject")
async def reject_novelty(novelty_id: uuid.UUID, payload: ReviewIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_review)) -> dict:
    return await review.review_novelty(db, organization_id=organization_id, actor=current_user,
                                       novelty_id=novelty_id, approve=False, note=payload.note)


# ---------------------------------------------------------------------------
# Panel y nómina
# ---------------------------------------------------------------------------

@router.get("/attendance/dashboard")
async def attendance_dashboard(date_from: date, date_to: date, user_id: uuid.UUID | None = None,
                               project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_dashboard)) -> dict:
    datos = await reports.dashboard(db, organization_id=organization_id, date_from=date_from, date_to=date_to,
                                    user_id=user_id, project_id=project_id)
    await db.commit()
    return datos


@router.get("/attendance/live")
async def attendance_live(response: Response, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          pag: tuple[int, int] = Depends(pagination_params),
                          current_user: User = Depends(_dashboard)) -> list[dict]:
    """Tablero de hoy: turno, ubicación (con su antigüedad) y verificado, por
    separado. La ubicación solo con `locations.view`."""
    from app.api.deps import get_effective_permissions

    filas = await reports.live_board(db, organization_id=organization_id,
                                     with_locations="locations.view" in get_effective_permissions(current_user))
    await db.commit()
    return paginate_list(filas, limit=pag[0], offset=pag[1], response=response)


@router.get("/attendance/payroll/report")
async def payroll_report(date_from: date, date_to: date, user_id: uuid.UUID | None = None,
                         db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_dashboard)) -> dict:
    datos = await reports.payroll_report(db, organization_id=organization_id, date_from=date_from,
                                         date_to=date_to, user_id=user_id)
    await db.commit()
    return datos


@router.get("/attendance/payroll/report.xlsx")
async def payroll_report_xlsx(date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_dashboard)) -> Response:
    datos = await reports.payroll_report(db, organization_id=organization_id, date_from=date_from, date_to=date_to)
    await db.commit()
    return Response(reports.to_xlsx(datos),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="nomina-{date_from}-{date_to}.xlsx"'})


@router.get("/attendance/payroll/report.pdf")
async def payroll_report_pdf(date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(_dashboard)) -> Response:
    from app.modules.organizations.models import Organization

    datos = await reports.payroll_report(db, organization_id=organization_id, date_from=date_from, date_to=date_to)
    org = await db.get(Organization, organization_id)
    await db.commit()
    return Response(reports.to_pdf(datos, org.name if org else ""), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="nomina-{date_from}-{date_to}.pdf"'})


@router.get("/attendance/payroll/periods")
async def list_periods(response: Response, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_dashboard)) -> list[dict]:
    return paginate_list(await review.list_periods(db, organization_id), limit=pag[0], offset=pag[1],
                         response=response)


@router.post("/attendance/payroll/periods", status_code=201)
async def create_period(payload: PeriodIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_payroll_close)) -> dict:
    return await review.create_period(db, organization_id=organization_id, actor=current_user,
                                      start=payload.start_date, end=payload.end_date)


@router.post("/attendance/payroll/periods/{period_id}/close")
async def close_period(period_id: uuid.UUID, payload: PeriodStatusIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_payroll_close)) -> dict:
    return await review.set_period_status(db, organization_id=organization_id, actor=current_user,
                                          period_id=period_id, close=True, reason=payload.reason)


@router.post("/attendance/payroll/periods/{period_id}/reopen")
async def reopen_period(period_id: uuid.UUID, payload: PeriodStatusIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_payroll_close)) -> dict:
    return await review.set_period_status(db, organization_id=organization_id, actor=current_user,
                                          period_id=period_id, close=False, reason=payload.reason)


@router.delete("/attendance/users/{user_id}/locations")
async def purge_user_locations(user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_review)) -> dict:
    """Borra antes de tiempo las coordenadas de una persona (sus horas quedan)."""
    return {"purged": await mapdata.purge_user_locations(db, organization_id=organization_id, actor=current_user,
                                                         user_id=user_id)}


# ---------------------------------------------------------------------------
# Mapa operativo
# ---------------------------------------------------------------------------

@router.get("/operations-map/projects")
async def map_projects(status: str | None = None, technician_user_id: uuid.UUID | None = None,
                       customer: str | None = Query(default=None, max_length=100), on_date: date | None = None,
                       ids: list[uuid.UUID] | None = Query(default=None, max_length=500),
                       db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_map)) -> dict:
    return await mapdata.projects(db, organization_id=organization_id, user=current_user, status=status,
                                  technician_id=technician_user_id, customer_q=customer, on_date=on_date, ids=ids)


@router.get("/operations-map/people")
async def map_people(response: Response, user_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_map)) -> list[dict]:
    return paginate_list(await mapdata.people(db, organization_id=organization_id, user=current_user,
                                              user_id=user_id), limit=pag[0], offset=pag[1], response=response)


@router.get("/operations-map/projects/{project_id}")
async def map_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_map)) -> dict:
    return await mapdata.project_detail(db, organization_id=organization_id, user=current_user,
                                        project_id=project_id)


@router.put("/operations-map/projects/{project_id}/location")
async def set_project_location(project_id: uuid.UUID, payload: LocationIn, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_project_location)) -> dict:
    return await mapdata.set_project_location(db, organization_id=organization_id, user=current_user,
                                              project_id=project_id, latitude=payload.latitude,
                                              longitude=payload.longitude)


@router.get("/operations-map/route")
async def map_route(on_date: date, user_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_map)) -> dict:
    return await mapdata.route(db, organization_id=organization_id, user=current_user,
                               user_id=user_id or current_user.id, on_date=on_date)
