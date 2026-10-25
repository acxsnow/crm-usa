import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import installation as installation_service
from app.modules.field_ops import visits as visits_service
from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import Project, ProjectStatus
from app.modules.field_ops.schemas import (
    AgendaRow,
    AvailabilityUpdate,
    CancelProjectRequest,
    CloseInstallationRequest,
    FailedVisitRequest,
    FieldCatalogsResponse,
    FieldOpsSettingsIn,
    InstallationGapsResponse,
    InstallerResponse,
    ProjectResponse,
    ReasonRequest,
    ScheduleInstallationRequest,
    TechnicianMonitorRow,
)
from app.modules.users.models import Role, User, UserRole, UserStatus
from app.modules.warehouse import day_logs as day_logs_service
from app.shared.datetime_utils import as_utc
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/technician-monitor", response_model=list[TechnicianMonitorRow])
async def technician_monitor(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.operations")),
):
    limit, offset = pagination
    technicians = await paginate(
        db,
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.organization_id == organization_id,
            Role.code == "field_technician",
            User.status == UserStatus.active,
        )
        .distinct()
        .order_by(User.full_name, User.id),
        limit=limit,
        offset=offset,
        response=response,
    )

    today = date.today()
    now = datetime.now(timezone.utc)
    rows: list[TechnicianMonitorRow] = []
    for tech in technicians:
        projects = (
            await db.execute(
                select(Project).where(
                    Project.organization_id == organization_id,
                    Project.primary_technician_user_id == tech.id,
                )
            )
        ).scalars().all()
        assigned = sum(
            1
            for project in projects
            if project.status in (ProjectStatus.planning, ProjectStatus.scheduled, ProjectStatus.in_progress)
        )
        completed_today = [project for project in projects if project.completed_date == today]
        avg_days = (
            sum((project.completed_date - project.created_at.date()).days for project in completed_today)
            / len(completed_today)
            if completed_today
            else None
        )
        logueado = tech.last_seen_at is not None and (now - as_utc(tech.last_seen_at)) <= timedelta(minutes=5)
        rows.append(
            TechnicianMonitorRow(
                user_id=tech.id,
                full_name=tech.full_name,
                logueado=logueado,
                en_cola=tech.is_available,
                casos_asignados=assigned,
                casos_gestionados_hoy=len(completed_today),
                tiempo_gestion_hoy_dias=avg_days,
            )
        )
    return rows


@router.patch("/technicians/{user_id}/availability", status_code=204)
async def update_technician_availability(
    user_id: uuid.UUID,
    payload: AvailabilityUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.operations")),
):
    technician = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.id == user_id,
                User.organization_id == organization_id,
                Role.code == "field_technician",
            )
        )
    ).scalar_one_or_none()
    if not technician:
        raise NotFoundError("El técnico no existe.", code="technician_not_found")
    technician.is_available = payload.is_available
    await db.commit()


@router.patch("/projects/{project_id}/schedule", response_model=ProjectResponse)
async def schedule_project_installation(
    project_id: uuid.UUID,
    payload: ScheduleInstallationRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    return await installation_service.schedule_installation(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        technician_id=payload.technician_user_id,
        scheduled_date=payload.scheduled_date,
    )


@router.get("/dispatch/technicians", response_model=list[InstallerResponse])
async def dispatch_technicians(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    limit, offset = pagination
    return paginate_list(
        await installation_service.list_installers(db, organization_id=organization_id),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.get("/dispatch/agenda", response_model=list[AgendaRow])
async def dispatch_agenda(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    view: str | None = Query(None, description="pending (lo que falta, atrasado incluido) o history (lo cerrado)"),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("dispatch.manage", "dispatch.read_own")),
):
    stmt = installation_service.agenda_query(
        organization_id=organization_id,
        user=current_user,
        date_from=date_from,
        date_to=date_to,
        technician_id=technician_id,
        view=view,
    )
    limit, offset = pagination
    rows = await paginate(db, stmt, limit=limit, offset=offset, response=response, scalars=False)
    hoy = await org_today(db, organization_id)
    jornadas = await day_logs_service.day_count_by_project(db, organization_id, [project.id for project, _ in rows])
    return [
        AgendaRow(
            project_id=project.id,
            title=project.title,
            status=project.status,
            scheduled_date=project.scheduled_date,
            primary_technician_user_id=project.primary_technician_user_id,
            address_street=project.address_street,
            address_unit=project.address_unit,
            address_city=project.address_city,
            case_id=case.id if case else None,
            case_number=case.case_number if case else None,
            stage_code=case.stage_code if case else None,
            substatus_code=case.substatus_code if case else None,
            days_late=installation_service.days_late(project, hoy),
            day_count=jornadas.get(project.id, 0),
        )
        for project, case in rows
    ]


@router.get("/projects/{project_id}/installation/gaps", response_model=InstallationGapsResponse)
async def installation_gaps(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    project = await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )
    missing = await installation_service.installation_gaps(db, project=project)
    return InstallationGapsResponse(can_close=not missing, missing=missing)


@router.post("/projects/{project_id}/installation/close", response_model=ProjectResponse)
async def close_project_installation(
    project_id: uuid.UUID,
    payload: CloseInstallationRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    return await installation_service.close_installation(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        observations=payload.observations,
    )


@router.get("/field-ops/catalogs", response_model=FieldCatalogsResponse)
async def field_catalogs(
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    from app.modules.field_ops import catalogs

    return FieldCatalogsResponse(
        evidence_categories=catalogs.EVIDENCE_CATEGORIES,
        installation_conditions=catalogs.INSTALLATION_CONDITIONS,
        equipment_types=catalogs.EQUIPMENT_TYPES,
        permit_statuses={str(key): value for key, value in catalogs.PERMIT_STATUS_LABELS.items()},
        inspection_results={str(key): value for key, value in catalogs.INSPECTION_RESULT_LABELS.items()},
        visit_failure_reasons=catalogs.VISIT_FAILURE_REASONS,
    )


# ---------------------------------------------------------------------------
# Visitas fallidas, límite de reagendamiento y cancelación (D-001)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/failed-visits", status_code=201)
async def record_failed_visit(
    project_id: uuid.UUID,
    payload: FailedVisitRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
) -> dict:
    return await visits_service.record_failed_visit(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        reason_code=payload.reason_code, notes=payload.notes,
        latitude=payload.latitude, longitude=payload.longitude)


@router.get("/projects/{project_id}/failed-visits")
async def list_failed_visits(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> list[dict]:
    stmt = await visits_service.list_failed_visits(db, organization_id=organization_id, user=current_user,
                                                   project_id=project_id)
    limit, offset = pagination
    intentos = await paginate(db, stmt, limit=limit, offset=offset, response=response)
    ids = {i for a in intentos for i in (a.technician_user_id, a.recorded_by_user_id) if i}
    nombres = dict((await db.execute(select(User.id, User.full_name).where(
        User.organization_id == organization_id, User.id.in_(ids)))).all()) if ids else {}
    return [visits_service.attempt_out(a, nombres) for a in intentos]


@router.get("/projects/{project_id}/visit-status")
async def project_visit_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> dict:
    project = await get_visible_project(db, organization_id=organization_id, user=current_user,
                                        project_id=project_id)
    estado = await visits_service.visit_status(db, project)
    await db.commit()
    return estado


@router.post("/projects/{project_id}/extra-visit")
async def authorize_extra_visit(
    project_id: uuid.UUID,
    payload: ReasonRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
) -> dict:
    return await visits_service.authorize_extra_visit(
        db, organization_id=organization_id, user=current_user, project_id=project_id, reason=payload.reason)


@router.get("/projects/{project_id}/cancellation-check")
async def project_cancellation_check(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.close")),
) -> dict:
    datos = await visits_service.cancellation_check(db, organization_id=organization_id, user=current_user,
                                                    project_id=project_id)
    await db.commit()
    return datos


@router.post("/projects/{project_id}/cancel", response_model=ProjectResponse)
async def cancel_project(
    project_id: uuid.UUID,
    payload: CancelProjectRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.close")),
):
    return await visits_service.cancel_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        reason=payload.reason, material_note=payload.material_note)


@router.get("/field-ops/settings")
async def get_field_ops_settings(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("dispatch.manage", "projects.read_all")),
) -> dict:
    datos = visits_service.settings_out(await visits_service.get_settings(db, organization_id))
    await db.commit()
    return datos


@router.put("/field-ops/settings")
async def put_field_ops_settings(
    payload: FieldOpsSettingsIn,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.close")),
) -> dict:
    return await visits_service.update_settings(db, organization_id=organization_id, user=current_user,
                                                max_failed_visits=payload.max_failed_visits)
