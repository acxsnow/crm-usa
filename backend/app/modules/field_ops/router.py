import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.shared.datetime_utils import as_utc
from app.shared.pagination import paginate, paginate_list, pagination_params
from app.modules.field_ops.clock import org_today
from app.modules.field_ops import checklist as checklist_service
from app.modules.field_ops import inspections as inspections_service
from app.modules.field_ops import installation as installation_service
from app.modules.field_ops import permits as permits_service
from app.modules.field_ops import reviews as reviews_service
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.access import can_work, get_visible_project, get_workable_project, scope_projects_stmt
from app.shared.errors import InvalidInputError
from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE
from app.modules.field_ops.models import (
    Attestation,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Evidence,
    Inspection,
    Project,
    ProjectChecklistItem,
    ProjectStatus,
    Task,
    TaskComment,
)
from app.modules.field_ops.schemas import (
    AttestationResponse,
    AvailabilityUpdate,
    ChecklistItemUpdate,
    AgendaRow,
    ProjectReviewResponse,
    ReturnToTechnicianRequest,
    InstallerResponse,
    FieldCatalogsResponse,
    InspectionCreate,
    InspectionResponse,
    InspectionResultRequest,
    CloseInstallationRequest,
    EquipmentCreate,
    EquipmentResponse,
    InstallationGapsResponse,
    PendingReviewRow,
    InspectionQueueRow,
    MaterialCreate,
    MaterialResponse,
    PermitCreate,
    ScheduleInstallationRequest,
    PermitResponse,
    PermitUpdate,
    InstallationConditionsUpdate,
    ChecklistTemplateCreate,
    ChecklistTemplateResponse,
    CustomerSignatureCapture,
    EvidenceResponse,
    OverdueTaskResponse,
    ProjectChecklistItemResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SignatureCapture,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TechnicianMonitorRow,
    CustomerSignatureRequestResponse,
    PublicCustomerSignatureCapture,
    PublicSignatureResponse,
)
from app.shared.files.storage import absolute_path
from app.modules.field_ops.reviews import was_reopened_for_correction
from app.modules.users.models import Role, User, UserRole, UserStatus
from app.modules.warehouse import day_logs as day_logs_service

router = APIRouter(tags=["field-ops"])


# --- Checklist templates ----------------------------------------------------

@router.get("/checklist-templates", response_model=list[ChecklistTemplateResponse])
async def list_checklist_templates(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    limit, offset = pagination
    return await paginate(db, select(ChecklistTemplate).where(ChecklistTemplate.organization_id == organization_id)
                          .order_by(ChecklistTemplate.name, ChecklistTemplate.id),
                          limit=limit, offset=offset, response=response)


@router.post("/checklist-templates", response_model=ChecklistTemplateResponse, status_code=201)
async def create_checklist_template(
    payload: ChecklistTemplateCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    await _check_template_program(db, organization_id, payload.program_id)
    template = ChecklistTemplate(
        organization_id=organization_id, name=payload.name,
        project_type=payload.project_type, program_id=payload.program_id,
    )
    db.add(template)
    await db.flush()
    for item_data in payload.items:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data.model_dump()))
    await db.commit()
    await db.refresh(template)
    return template


async def _check_template_program(db, organization_id, program_id, template_id=None) -> None:
    """El programa es de la organización y no tiene ya otra plantilla: con
    dos, cuál se aplica a la instalación dependería de cuál se creó último."""
    if program_id is None:
        return
    from app.modules.cases.models import Program
    from app.shared.errors import ConflictError

    programa = (
        await db.execute(select(Program.id).where(Program.id == program_id, Program.organization_id == organization_id))
    ).first()
    if programa is None:
        raise InvalidInputError("El programa no existe.", code="program_not_found")
    stmt = select(ChecklistTemplate.id).where(
        ChecklistTemplate.organization_id == organization_id, ChecklistTemplate.program_id == program_id
    )
    if template_id is not None:
        stmt = stmt.where(ChecklistTemplate.id != template_id)
    otra = (await db.execute(stmt)).first()
    if otra is not None:
        raise ConflictError("Ese programa ya tiene su plantilla de checklist; edítala en vez de crear otra.",
                            code="program_template_exists")


async def _get_template(db, organization_id, template_id) -> ChecklistTemplate:
    from app.shared.errors import NotFoundError

    t = await db.get(ChecklistTemplate, template_id)
    if t is None or t.organization_id != organization_id:
        raise NotFoundError("La plantilla no existe.", code="checklist_template_not_found")
    return t


@router.put("/checklist-templates/{template_id}", response_model=ChecklistTemplateResponse)
async def update_checklist_template(
    template_id: uuid.UUID, payload: ChecklistTemplateCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    """Reemplaza nombre, programa e ítems. Las instalaciones que ya la usaron
    no cambian: al aplicarse, cada ítem se copió al proyecto."""
    from app.shared.audit import record_audit_event

    template = await _get_template(db, organization_id, template_id)
    await _check_template_program(db, organization_id, payload.program_id, template.id)
    antes = {"name": template.name, "program_id": str(template.program_id) if template.program_id else None,
             "items": len(template.items)}
    template.name, template.project_type, template.program_id = payload.name, payload.project_type, payload.program_id
    template.items.clear()
    await db.flush()
    for item_data in payload.items:
        template.items.append(ChecklistTemplateItem(**item_data.model_dump()))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id,
                             action="checklist_templates.updated", entity_type="checklist_template",
                             entity_id=str(template.id), before_data=antes,
                             after_data={"name": payload.name, "items": len(payload.items)})
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/checklist-templates/{template_id}", status_code=204)
async def delete_checklist_template(
    template_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    from app.shared.audit import record_audit_event

    template = await _get_template(db, organization_id, template_id)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id,
                             action="checklist_templates.deleted", entity_type="checklist_template",
                             entity_id=str(template.id), before_data={"name": template.name})
    await db.delete(template)
    await db.commit()
    return Response(status_code=204)


@router.post("/checklist-templates/seed-default", response_model=ChecklistTemplateResponse, status_code=201)
async def seed_default_checklist_template(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    """Convenience endpoint: creates the default HVAC install checklist for
    this org if one with the same name doesn't already exist."""
    existing = await db.execute(
        select(ChecklistTemplate).where(
            ChecklistTemplate.organization_id == organization_id,
            ChecklistTemplate.name == DEFAULT_CHECKLIST_TEMPLATE["name"],
        )
    )
    found = existing.scalar_one_or_none()
    if found:
        return found

    template = ChecklistTemplate(
        organization_id=organization_id, name=DEFAULT_CHECKLIST_TEMPLATE["name"],
        project_type=DEFAULT_CHECKLIST_TEMPLATE["project_type"],
    )
    db.add(template)
    await db.flush()
    for item_data in DEFAULT_CHECKLIST_TEMPLATE["items"]:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data))
    await db.commit()
    await db.refresh(template)
    return template


# --- Technician monitor (GTR-style) -----------------------------------

@router.get("/technician-monitor", response_model=list[TechnicianMonitorRow])
async def technician_monitor(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.operations")),
):
    # Se pagina la lista de técnicos; los datos de cada uno se calculan solo
    # para los de la página.
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
        limit=limit, offset=offset, response=response,
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
            1 for p in projects
            if p.status in (ProjectStatus.planning, ProjectStatus.scheduled, ProjectStatus.in_progress)
        )
        completed_today = [p for p in projects if p.completed_date == today]
        avg_days = (
            sum((p.completed_date - p.created_at.date()).days for p in completed_today) / len(completed_today)
            if completed_today else None
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
        raise HTTPException(status_code=404, detail="Technician not found.")
    technician.is_available = payload.is_available
    await db.commit()


# --- Projects ----------------------------------------------------------

def _scope_projects_stmt(stmt, current_user: User):
    return scope_projects_stmt(stmt, current_user)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    q: str | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Project).where(Project.organization_id == organization_id).order_by(Project.created_at.desc())
    stmt = _scope_projects_stmt(stmt, current_user)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Project.title.ilike(like)) | (Project.address_street.ilike(like)))
    if technician_id:
        stmt = stmt.where(Project.primary_technician_user_id == technician_id)
    limit, offset = pagination
    return [_with_access(p, current_user) for p in await paginate(db, stmt, limit=limit, offset=offset,
                                                                  response=response)]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.create")),
):
    project = await field_ops_service.create_project(
        db, organization_id=organization_id, actor_id=current_user.id, data=payload.model_dump(),
    )
    return project


async def _get_project_or_404(db: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, current_user: User) -> Project:
    return await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )


async def _get_workable_or_403(db: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID,
                               current_user: User) -> Project:
    """Para lo que escribe: el técnico que ve la obra en solo lectura recibe 403."""
    return await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)


def _with_access(project: Project, user: User) -> Project:
    """Le dice a la pantalla si quien pide llena la obra o solo la ve."""
    project.my_access = "full" if can_work(project, user) else "read_only"
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    return _with_access(await _get_project_or_404(db, organization_id=organization_id, project_id=project_id,
                                                  current_user=current_user), current_user)


@router.get("/projects/{project_id}/assignments")
async def project_assignments(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> list[dict]:
    """Quién fue el técnico responsable de la obra y desde/hasta cuándo."""
    from app.modules.field_ops.installation import assignments_of
    from app.shared.pagination import paginate_list

    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    limit, offset = pagination
    return paginate_list(await assignments_of(db, organization_id=organization_id, project_id=project_id),
                         limit=limit, offset=offset, response=response)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    project = await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}/checklist", response_model=list[ProjectChecklistItemResponse])
async def get_project_checklist(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    limit, offset = pagination
    return await paginate(db, select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == project_id)
                          .order_by(ProjectChecklistItem.sort_order, ProjectChecklistItem.id),
                          limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/checklist/apply-template", response_model=list[ProjectChecklistItemResponse])
async def apply_checklist_template_to_project(
    project_id: uuid.UUID, template_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    items = await field_ops_service.apply_checklist_template(
        db, organization_id=organization_id, project_id=project_id, template_id=template_id,
    )
    await db.commit()
    for item in items:
        await db.refresh(item)
    return items


@router.patch("/checklist-items/{item_id}", response_model=ProjectChecklistItemResponse)
async def update_checklist_item(
    item_id: uuid.UUID, payload: ChecklistItemUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    """Lo usa el técnico en campo: `checklists.complete` y proyecto asignado.
    Antes exigía `checklists.manage`, que es de Administración, y el técnico no
    podía marcar su propio checklist."""
    return await checklist_service.update_checklist_item(
        db, organization_id=organization_id, user=current_user, item_id=item_id,
        is_complete=payload.is_complete, not_applicable=payload.not_applicable, reason=payload.reason,
    )


@router.patch("/projects/{project_id}/conditions", response_model=ProjectResponse)
async def set_installation_conditions(
    project_id: uuid.UUID, payload: InstallationConditionsUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    """Las condiciones de la casa que vuelven obligatorios ciertos ítems."""
    return await checklist_service.set_installation_conditions(
        db, organization_id=organization_id, user=current_user,
        project_id=project_id, conditions=payload.conditions,
    )


# --- Tasks ---------------------------------------------------------------

@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    limit, offset = pagination
    return await paginate(db, select(Task).where(Task.project_id == project_id)
                          .order_by(Task.due_date.asc().nulls_last(), Task.id),
                          limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: uuid.UUID, payload: TaskCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    await _get_workable_or_403(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    task = Task(organization_id=organization_id, project_id=project_id, **payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _get_task_or_404(db: AsyncSession, *, organization_id: uuid.UUID, task_id: uuid.UUID, current_user: User) -> Task:
    """Fetches a task and enforces the same assigned-vs-all project scoping
    used everywhere else in this module: a task belongs to a project, so
    reaching it has to go through the same _get_project_or_404 check a
    field_technician (projects.read_assigned only) already hits on every
    other task/evidence/checklist route — otherwise tasks.manage alone would
    let a technician touch a task on a project they aren't assigned to."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == organization_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    await _get_project_or_404(db, organization_id=organization_id, project_id=task.project_id, current_user=current_user)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    task = await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    await _get_workable_or_403(db, organization_id=organization_id, project_id=task.project_id,
                               current_user=current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks/overdue", response_model=list[OverdueTaskResponse])
async def list_overdue_tasks(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    perms = get_effective_permissions(current_user)
    restrict_to = None if "projects.read_all" in perms else current_user.id
    limit, offset = pagination
    pairs = await paginate(db, field_ops_service.overdue_tasks_query(
        organization_id=organization_id, restrict_to_technician_id=restrict_to),
        limit=limit, offset=offset, response=response, scalars=False)
    return [
        OverdueTaskResponse(**TaskResponse.model_validate(task).model_dump(), project_title=project_title)
        for task, project_title in pairs
    ]


# --- Task comments -----------------------------------------------------

@router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(
    task_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    limit, offset = pagination
    return await paginate(db, select(TaskComment).where(TaskComment.task_id == task_id)
                          .order_by(TaskComment.created_at.asc(), TaskComment.id),
                          limit=limit, offset=offset, response=response)


@router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
async def create_task_comment(
    task_id: uuid.UUID, payload: TaskCommentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    task = await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    await _get_workable_or_403(db, organization_id=organization_id, project_id=task.project_id,
                               current_user=current_user)
    comment = TaskComment(task_id=task_id, author_user_id=current_user.id, body=payload.body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


# --- Evidence ----------------------------------------------------------

@router.get("/projects/{project_id}/evidence", response_model=list[EvidenceResponse])
async def list_project_evidence(
    project_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("evidence.read_all", "evidence.read_assigned")),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    stmt = (
        select(Evidence).where(Evidence.project_id == project_id, Evidence.deleted_at.is_(None))
        .order_by(Evidence.created_at.desc())
    )
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/evidence", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    category: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    captured_at: datetime | None = Form(None),
    task_id: uuid.UUID | None = Form(None),
    checklist_item_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    """Upload endpoint (spec 18 item 2/3: GPS mandatory when the browser
    allows it). Confirmed requirement: a visible GPS watermark is burned
    into the stored image — see shared/files/watermark.py."""
    # El técnico solo sube evidencias a sus proyectos asignados.
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    return await field_ops_service.upload_evidence(
        db, organization_id=organization_id, actor_id=current_user.id, project_id=project_id, file=file,
        category=category, latitude=latitude, longitude=longitude, captured_at=captured_at,
        task_id=task_id, checklist_item_id=checklist_item_id,
    )


@router.get("/evidence/{evidence_id}/file")
async def download_evidence_file(
    evidence_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("evidence.read_all", "evidence.read_assigned")),
):
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id, Evidence.organization_id == organization_id))
    evidence = result.scalar_one_or_none()
    if not evidence or evidence.deleted_at:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return FileResponse(str(absolute_path(evidence.file_path)), media_type=evidence.mime_type or "application/octet-stream")


# --- Attestation (digital signatures) --------------------------------------

@router.post("/projects/{project_id}/attestation/technician-sign", response_model=AttestationResponse)
async def sign_as_technician(
    project_id: uuid.UUID, payload: SignatureCapture, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    attestation = await field_ops_service.technician_sign(
        db, organization_id=organization_id, actor_id=current_user.id, project_id=project_id,
        signature_base64=payload.signature_base64,
    )
    return AttestationResponse.model_validate(attestation)


@router.post("/projects/{project_id}/attestation/customer-signature-request", response_model=CustomerSignatureRequestResponse)
async def request_customer_signature(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    token = await field_ops_service.create_customer_signature_request(
        db, organization_id=organization_id, actor_id=current_user.id, project_id=project_id
    )
    return CustomerSignatureRequestResponse(
        status="sent", recipient_email=token.recipient_email, expires_at=token.expires_at
    )


@router.post("/projects/{project_id}/attestation/customer-sign", response_model=AttestationResponse)
async def sign_as_customer(
    project_id: uuid.UUID, payload: CustomerSignatureCapture, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    attestation = await field_ops_service.customer_sign(
        db, organization_id=organization_id, actor_id=current_user.id, project_id=project_id,
        customer_name=payload.customer_name, signature_base64=payload.signature_base64,
    )
    return AttestationResponse.model_validate(attestation)


@router.get("/projects/{project_id}/attestation", response_model=AttestationResponse)
async def get_attestation(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    result = await db.execute(
        select(Attestation).where(Attestation.project_id == project_id, Attestation.organization_id == organization_id)
    )
    attestation = result.scalar_one_or_none()
    if not attestation:
        raise HTTPException(status_code=404, detail="No attestation started for this project yet.")
    respuesta = AttestationResponse.model_validate(attestation)
    enlace = await field_ops_service.pending_signature_link(db, attestation.id)
    if enlace:
        respuesta.customer_link_sent_to = enlace.recipient_email
        respuesta.customer_link_expires_at = enlace.expires_at
    return respuesta


@router.get("/attestations/{attestation_id}/pdf")
async def download_attestation_pdf(
    attestation_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    # Quien ve el proyecto descarga su acta: el técnico, la de sus órdenes
    # (antes pedía `reports.generate` y el técnico no podía bajar el acta que firmó).
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    result = await db.execute(select(Attestation).where(Attestation.id == attestation_id, Attestation.organization_id == organization_id))
    attestation = result.scalar_one_or_none()
    if not attestation or not attestation.pdf_path:
        raise HTTPException(status_code=404, detail="Attestation PDF not generated yet (both signatures required).")
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=attestation.project_id)
    return FileResponse(str(absolute_path(attestation.pdf_path)), media_type="application/pdf", filename="acta-de-instalacion.pdf")


# Public customer signing endpoints. They intentionally do not use CRM auth;
# access is granted only by the hashed, expiring, single-use token.
@router.get("/public/customer-signature", response_model=PublicSignatureResponse)
async def public_customer_signature_details(token: str, db: AsyncSession = Depends(get_db)):
    signature_token, attestation, project = await field_ops_service.get_public_signature_request(db, raw_token=token)
    return PublicSignatureResponse(
        project_title=project.title, customer_name=attestation.customer_name,
        expires_at=signature_token.expires_at, technician_signed=bool(attestation.technician_signed_at),
    )


@router.post("/public/customer-signature", response_model=AttestationResponse)
async def public_customer_signature(
    payload: PublicCustomerSignatureCapture, token: str | None = None, db: AsyncSession = Depends(get_db)
):
    raw = payload.token or token
    if not raw:
        raise HTTPException(status_code=404, detail="El enlace no es válido o ya expiró.")
    return AttestationResponse.model_validate(await field_ops_service.public_customer_sign(
        db, raw_token=raw, customer_name=payload.customer_name, signature_base64=payload.signature_base64
    ))


# --- Módulo 5: permisos municipales ----------------------------------------

@router.get("/projects/{project_id}/permits", response_model=list[PermitResponse])
async def list_project_permits(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(await permits_service.list_permits(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    ), limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/permits", response_model=PermitResponse, status_code=201)
async def record_project_permit(
    project_id: uuid.UUID, payload: PermitCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("permits.manage")),
):
    """Registra un permiso. Si es el primero, el expediente pasa a «Permiso en
    trámite»; si con él quedan todos despejados, a «Listo para instalar»."""
    return await permits_service.record_permit(
        db, organization_id=organization_id, user=current_user,
        project_id=project_id, data=payload.model_dump(),
    )


@router.patch("/permits/{permit_id}", response_model=PermitResponse)
async def update_project_permit(
    permit_id: uuid.UUID, payload: PermitUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("permits.manage")),
):
    return await permits_service.update_permit(
        db, organization_id=organization_id, user=current_user,
        permit_id=permit_id, changes=payload.model_dump(exclude_unset=True),
    )


# --- Módulo 5: equipos instalados -------------------------------------------

@router.get("/projects/{project_id}/equipment", response_model=list[EquipmentResponse])
async def list_project_equipment(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(await installation_service.list_equipment(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    ), limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/equipment", response_model=EquipmentResponse, status_code=201)
async def add_project_equipment(
    project_id: uuid.UUID, payload: EquipmentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    return await installation_service.add_equipment(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        data=payload.model_dump(),
    )


@router.post("/projects/{project_id}/equipment/confirm", response_model=ProjectResponse)
async def confirm_project_equipment(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    """«Guardar equipos instalados»: completa el paso del acta."""
    return await installation_service.confirm_equipment(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )


@router.delete("/equipment/{equipment_id}", status_code=204)
async def delete_project_equipment(
    equipment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    await installation_service.delete_equipment(
        db, organization_id=organization_id, user=current_user, equipment_id=equipment_id
    )
    return Response(status_code=204)


# --- Módulo 5: materiales de la orden ---------------------------------------

@router.get("/projects/{project_id}/materials", response_model=list[MaterialResponse])
async def list_project_materials(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(await installation_service.list_materials(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    ), limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/materials", response_model=MaterialResponse, status_code=201)
async def add_project_material(
    project_id: uuid.UUID, payload: MaterialCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    return await installation_service.add_material(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        data=payload.model_dump(),
    )


@router.delete("/materials/{material_id}", status_code=204)
async def delete_project_material(
    material_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    await installation_service.delete_material(
        db, organization_id=organization_id, user=current_user, material_id=material_id
    )
    return Response(status_code=204)


# --- Módulo 5: agenda y cierre ---------------------------------------------

@router.patch("/projects/{project_id}/schedule", response_model=ProjectResponse)
async def schedule_project_installation(
    project_id: uuid.UUID, payload: ScheduleInstallationRequest, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    """Asigna técnico y fecha. Con el expediente en «Listo para instalar» marca
    «Instalación programada» y libera la orden."""
    return await installation_service.schedule_installation(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        technician_id=payload.technician_user_id, scheduled_date=payload.scheduled_date,
    )


@router.get("/dispatch/technicians", response_model=list[InstallerResponse])
async def dispatch_technicians(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    """A quién se le puede asignar una orden. Existe aparte de `/users` porque
    Administración despacha pero no administra usuarios (`users.manage`)."""
    limit, offset = pagination
    return paginate_list(await installation_service.list_installers(db, organization_id=organization_id),
                         limit=limit, offset=offset, response=response)


@router.get("/dispatch/agenda", response_model=list[AgendaRow])
async def dispatch_agenda(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    date_from: date | None = Query(None), date_to: date | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    view: str | None = Query(None, description="pending (lo que falta, atrasado incluido) o history (lo cerrado)"),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("dispatch.manage", "dispatch.read_own")),
):
    """Administración ve la agenda de todos; el técnico, solo la suya.
    Vistas en spec 2026-10-16-agenda-pendientes-historial."""

    stmt = installation_service.agenda_query(
        organization_id=organization_id, user=current_user, date_from=date_from, date_to=date_to,
        technician_id=technician_id, view=view,
    )
    limit, offset = pagination
    filas = await paginate(db, stmt, limit=limit, offset=offset, response=response, scalars=False)
    hoy = await org_today(db, organization_id)
    # Las jornadas del diario marcan las obras de varios días (punto 4).
    jornadas = await day_logs_service.day_count_by_project(db, organization_id, [p.id for p, _ in filas])
    return [
        AgendaRow(
            project_id=p.id, title=p.title, status=p.status, scheduled_date=p.scheduled_date,
            primary_technician_user_id=p.primary_technician_user_id,
            address_street=p.address_street, address_unit=p.address_unit, address_city=p.address_city,
            case_id=c.id if c else None, case_number=c.case_number if c else None,
            stage_code=c.stage_code if c else None, substatus_code=c.substatus_code if c else None,
            days_late=installation_service.days_late(p, hoy),
            day_count=jornadas.get(p.id, 0),
        )
        for p, c in filas
    ]


@router.get("/projects/{project_id}/installation/gaps", response_model=InstallationGapsResponse)
async def installation_gaps(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    """Lo que falta para cerrar, para mostrarlo antes de que el técnico lo intente."""
    project = await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    faltan = await installation_service.installation_gaps(db, project=project)
    return InstallationGapsResponse(can_close=not faltan, missing=faltan)


@router.post("/projects/{project_id}/installation/close", response_model=ProjectResponse)
async def close_project_installation(
    project_id: uuid.UUID, payload: CloseInstallationRequest, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    return await installation_service.close_installation(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        observations=payload.observations,
    )


# --- Módulo 5: inspección -----------------------------------------------------

@router.get("/projects/{project_id}/inspections", response_model=list[InspectionResponse])
async def list_project_inspections(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(await inspections_service.list_inspections(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    ), limit=limit, offset=offset, response=response)


@router.post("/projects/{project_id}/inspections", response_model=InspectionResponse, status_code=201)
async def schedule_project_inspection(
    project_id: uuid.UUID, payload: InspectionCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    return await inspections_service.schedule_inspection(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        scheduled_for=payload.scheduled_for, inspector_name=payload.inspector_name,
    )


@router.post("/inspections/{inspection_id}/result", response_model=InspectionResponse)
async def record_project_inspection_result(
    inspection_id: uuid.UUID, payload: InspectionResultRequest, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    return await inspections_service.record_inspection_result(
        db, organization_id=organization_id, user=current_user, inspection_id=inspection_id,
        result=payload.result, observations=payload.observations, inspector_name=payload.inspector_name,
    )


@router.get("/field-ops/catalogs", response_model=FieldCatalogsResponse)
async def field_catalogs(
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    """Los catálogos de campo con sus etiquetas, para que el frontend no los repita."""
    from app.modules.field_ops import catalogs

    return FieldCatalogsResponse(
        evidence_categories=catalogs.EVIDENCE_CATEGORIES,
        installation_conditions=catalogs.INSTALLATION_CONDITIONS,
        equipment_types=catalogs.EQUIPMENT_TYPES,
        permit_statuses={str(k): v for k, v in catalogs.PERMIT_STATUS_LABELS.items()},
        inspection_results={str(k): v for k, v in catalogs.INSPECTION_RESULT_LABELS.items()},
    )


# --- Módulo 6: revisión administrativa del acta --------------------------------

@router.get("/inspection-queue", response_model=list[InspectionQueueRow])
async def inspection_queue(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    """«Por revisar» › Inspección municipal: instalaciones cerradas sin
    inspección aprobada (spec 2026-10-19-bandeja-por-revisar)."""
    limit, offset = pagination
    filas = await paginate(db, inspections_service.inspection_queue_stmt(organization_id), limit=limit,
                           offset=offset, response=response, scalars=False)
    hoy = await org_today(db, organization_id)
    estado = {None: "unscheduled", "pending": "scheduled", "failed": "failed"}
    return [
        InspectionQueueRow(project_id=f[0], case_id=f[1], case_number=f[2], title=f[3], customer_name=f[4],
                           completed_date=f[5], status=estado.get(f[6], "scheduled"), scheduled_for=f[7],
                           days_since_close=(hoy - f[5]).days if f[5] else None)
        for f in filas
    ]


@router.get("/acta-reviews/pending", response_model=list[PendingReviewRow])
async def pending_acta_reviews(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    """«Actas por confirmar»: instalaciones cerradas que esperan a Administración,
    la más vieja primero (spec 2026-10-19-actas-por-confirmar)."""
    limit, offset = pagination
    filas = await paginate(db, reviews_service.pending_reviews_stmt(organization_id), limit=limit, offset=offset,
                           response=response, scalars=False)
    hoy = await org_today(db, organization_id)
    return [
        PendingReviewRow(project_id=f[0], case_id=f[1], case_number=f[2], title=f[3], customer_name=f[4],
                         technician_name=f[5], completed_date=f[6],
                         days_waiting=(hoy - f[6]).days if f[6] else None)
        for f in filas
    ]


@router.post("/projects/{project_id}/review/confirm", response_model=ProjectResponse)
async def confirm_technician_info(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    """Administración confirma la información técnica del acta cerrada."""
    return await reviews_service.confirm_technician_info(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )


@router.post("/projects/{project_id}/review/return", response_model=ProjectResponse)
async def return_to_technician(
    project_id: uuid.UUID, payload: ReturnToTechnicianRequest, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    """Devuelve el acta al técnico con lo que debe corregir; se reabre."""
    return await reviews_service.return_to_technician(
        db, organization_id=organization_id, user=current_user, project_id=project_id, reason=payload.reason
    )


@router.get("/projects/{project_id}/reviews", response_model=list[ProjectReviewResponse])
async def list_project_reviews(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    project = await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    limit, offset = pagination
    return paginate_list(project.reviews, limit=limit, offset=offset, response=response)



@router.post("/inspections/{inspection_id}/signed-permit", response_model=EvidenceResponse, status_code=201)
async def upload_signed_permit(
    inspection_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    """El permiso con la firma del inspector: la prueba de la inspección
    aprobada (módulo 6, spec D6.4). Lo sube quien registra la inspección
    (Administración), que no tiene `evidence.create`; por eso tiene ruta propia
    en vez de pasar por las evidencias de campo."""
    inspeccion = (
        await db.execute(
            select(Inspection).where(Inspection.id == inspection_id, Inspection.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if inspeccion is None:
        raise NotFoundError("La inspección no existe.", code="inspection_not_found")
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=inspeccion.project_id)
    return await field_ops_service.upload_evidence(
        db, organization_id=organization_id, actor_id=current_user.id, project_id=inspeccion.project_id,
        file=file, category="permit_signed", latitude=None, longitude=None, captured_at=None,
        task_id=None, checklist_item_id=None,
    )


@router.get("/cases/{case_id}/project")
async def project_of_case(
    case_id: uuid.UUID, db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> dict:
    """El proyecto de instalación de un expediente (para enlazarlo desde la revisión)."""
    from app.shared.errors import NotFoundError

    stmt = select(Project).where(Project.organization_id == organization_id, Project.case_id == case_id)
    stmt = _scope_projects_stmt(stmt, current_user)
    project = (await db.execute(stmt)).scalars().first()
    if project is None:
        raise NotFoundError("Este expediente no tiene proyecto.", code="project_not_found")
    return {"id": str(project.id), "title": project.title, "status": project.status}


# --- Permisos e inspecciones de todos los proyectos (vista de oficina) ---------

_permits_view = require_any_permission("permits.manage", "inspections.manage", "projects.read_all")


async def _project_titles(db, ids) -> dict:
    ids = {i for i in ids if i}
    return {p.id: p.title for p in (await db.execute(select(Project).where(Project.id.in_(ids)))).scalars().all()} \
        if ids else {}


@router.get("/permits")
async def list_all_permits(
    response: Response, status: str | None = None, expiring_within_days: int | None = Query(None, ge=0, le=365),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    pagination: tuple[int, int] = Depends(pagination_params), current_user: User = Depends(_permits_view),
) -> list[dict]:
    """Todos los permisos municipales, con su estado y vencimiento."""
    from app.modules.field_ops.catalogs import PERMIT_STATUS_LABELS
    from app.modules.field_ops.models import Permit

    hoy = await org_today(db, organization_id)
    stmt = select(Permit).join(Project, Project.id == Permit.project_id).where(Project.organization_id == organization_id)
    stmt = _scope_projects_stmt(stmt, current_user)
    if status:
        stmt = stmt.where(Permit.status == status)
    if expiring_within_days is not None:
        stmt = stmt.where(Permit.expires_on.is_not(None), Permit.expires_on >= hoy,
                          Permit.expires_on <= hoy + timedelta(days=expiring_within_days))
    limit, offset = pagination
    items = await paginate(db, stmt.order_by(Permit.expires_on.asc().nulls_last(), Permit.id), limit=limit,
                           offset=offset, response=response)
    titulos = await _project_titles(db, {p.project_id for p in items})
    return [{"id": str(p.id), "project_id": str(p.project_id), "project_title": titulos.get(p.project_id),
             "jurisdiction": p.jurisdiction, "permit_number": p.permit_number, "permit_type": p.permit_type,
             "status": str(p.status), "status_label": PERMIT_STATUS_LABELS.get(p.status, str(p.status)),
             "filed_on": p.filed_on.isoformat() if p.filed_on else None,
             "approved_on": p.approved_on.isoformat() if p.approved_on else None,
             "expires_on": p.expires_on.isoformat() if p.expires_on else None,
             "days_to_expiry": (p.expires_on - hoy).days if p.expires_on else None} for p in items]


@router.get("/inspections")
async def list_all_inspections(
    response: Response, result: str | None = None, upcoming: bool = False,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    pagination: tuple[int, int] = Depends(pagination_params), current_user: User = Depends(_permits_view),
) -> list[dict]:
    """Todas las inspecciones: agendadas y resultados."""
    from app.modules.field_ops.catalogs import INSPECTION_RESULT_LABELS
    from app.modules.field_ops.models import Inspection

    stmt = select(Inspection).join(Project, Project.id == Inspection.project_id).where(
        Project.organization_id == organization_id)
    stmt = _scope_projects_stmt(stmt, current_user)
    if result:
        stmt = stmt.where(Inspection.result == result)
    if upcoming:
        stmt = stmt.where(Inspection.result == "pending", Inspection.scheduled_for >= datetime.now(timezone.utc))
    limit, offset = pagination
    orden = Inspection.scheduled_for.asc() if upcoming else Inspection.scheduled_for.desc()
    items = await paginate(db, stmt.order_by(orden, Inspection.id), limit=limit, offset=offset, response=response)
    titulos = await _project_titles(db, {i.project_id for i in items})
    return [{"id": str(i.id), "project_id": str(i.project_id), "project_title": titulos.get(i.project_id),
             "scheduled_for": i.scheduled_for.isoformat(), "inspector_name": i.inspector_name,
             "result": str(i.result), "result_label": INSPECTION_RESULT_LABELS.get(i.result, str(i.result)),
             "result_recorded_at": i.result_recorded_at.isoformat() if i.result_recorded_at else None,
             "observations": i.observations} for i in items]
