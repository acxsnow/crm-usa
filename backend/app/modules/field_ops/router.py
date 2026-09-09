import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.shared.pagination import paginate, pagination_params
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE
from app.modules.field_ops.models import (
    Attestation,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Evidence,
    EvidenceCategory,
    Project,
    ProjectChecklistItem,
    ProjectStatus,
    Task,
    TaskComment,
)
from app.modules.field_ops.schemas import (
    AttestationResponse,
    ChecklistItemComplete,
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
    CustomerSignatureRequestResponse,
    PublicCustomerSignatureCapture,
    PublicSignatureResponse,
)
from app.modules.field_ops.storage import absolute_path
from app.modules.users.models import User

router = APIRouter(tags=["field-ops"])


# --- Checklist templates ----------------------------------------------------

@router.get("/checklist-templates", response_model=list[ChecklistTemplateResponse])
async def list_checklist_templates(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    result = await db.execute(select(ChecklistTemplate).where(ChecklistTemplate.organization_id == organization_id))
    return result.scalars().all()


@router.post("/checklist-templates", response_model=ChecklistTemplateResponse, status_code=201)
async def create_checklist_template(
    payload: ChecklistTemplateCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    template = ChecklistTemplate(organization_id=organization_id, name=payload.name, project_type=payload.project_type)
    db.add(template)
    await db.flush()
    for item_data in payload.items:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data.model_dump()))
    await db.commit()
    await db.refresh(template)
    return template


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


# --- Projects ----------------------------------------------------------

def _scope_projects_stmt(stmt, current_user: User):
    perms = get_effective_permissions(current_user)
    if "projects.read_all" not in perms:
        stmt = stmt.where(Project.primary_technician_user_id == current_user.id)
    return stmt


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
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


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
    stmt = select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    stmt = _scope_projects_stmt(stmt, current_user)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    return await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)


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
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    result = await db.execute(
        select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == project_id).order_by(ProjectChecklistItem.sort_order)
    )
    return result.scalars().all()


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
async def complete_checklist_item(
    item_id: uuid.UUID, payload: ChecklistItemComplete, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    return await field_ops_service.complete_checklist_item(
        db, organization_id=organization_id, actor_id=current_user.id, item_id=item_id, is_complete=payload.is_complete,
    )


# --- Tasks ---------------------------------------------------------------

@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
    result = await db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.due_date.asc().nulls_last()))
    return result.scalars().all()


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: uuid.UUID, payload: TaskCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    await _get_project_or_404(db, organization_id=organization_id, project_id=project_id, current_user=current_user)
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks/overdue", response_model=list[OverdueTaskResponse])
async def list_overdue_tasks(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    perms = get_effective_permissions(current_user)
    restrict_to = None if "projects.read_all" in perms else current_user.id
    pairs = await field_ops_service.list_overdue_tasks(
        db, organization_id=organization_id, restrict_to_technician_id=restrict_to
    )
    return [
        OverdueTaskResponse(**TaskResponse.model_validate(task).model_dump(), project_title=project_title)
        for task, project_title in pairs
    ]


# --- Task comments -----------------------------------------------------

@router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    result = await db.execute(
        select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at.asc())
    )
    return result.scalars().all()


@router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
async def create_task_comment(
    task_id: uuid.UUID, payload: TaskCommentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
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
    category: EvidenceCategory = Form(EvidenceCategory.other),
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
    into the stored image — see field_ops/watermark.py."""
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
    result = await db.execute(
        select(Attestation).where(Attestation.project_id == project_id, Attestation.organization_id == organization_id)
    )
    attestation = result.scalar_one_or_none()
    if not attestation:
        raise HTTPException(status_code=404, detail="No attestation started for this project yet.")
    return AttestationResponse.model_validate(attestation)


@router.get("/attestations/{attestation_id}/pdf")
async def download_attestation_pdf(
    attestation_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("reports.generate")),
):
    result = await db.execute(select(Attestation).where(Attestation.id == attestation_id, Attestation.organization_id == organization_id))
    attestation = result.scalar_one_or_none()
    if not attestation or not attestation.pdf_path:
        raise HTTPException(status_code=404, detail="Attestation PDF not generated yet (both signatures required).")
    return FileResponse(str(absolute_path(attestation.pdf_path)), media_type="application/pdf", filename="atestacion.pdf")


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
    payload: PublicCustomerSignatureCapture, token: str, db: AsyncSession = Depends(get_db)
):
    return AttestationResponse.model_validate(await field_ops_service.public_customer_sign(
        db, raw_token=token, customer_name=payload.customer_name, signature_base64=payload.signature_base64
    ))
