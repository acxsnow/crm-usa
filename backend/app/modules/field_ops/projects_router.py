import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import checklist as checklist_service
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.access import can_work, get_visible_project, scope_projects_stmt
from app.modules.field_ops.models import Project, ProjectChecklistItem, ProjectStatus
from app.modules.field_ops.schemas import (
    ChecklistItemUpdate,
    InstallationConditionsUpdate,
    ProjectChecklistItemResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.modules.users.models import User
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, paginate_list, pagination_params
from app.shared.text_search import LIKE_ESCAPE, contains_pattern

router = APIRouter(tags=["field-ops"])


def _with_access(project: Project, user: User) -> Project:
    project.my_access = "full" if can_work(project, user) else "read_only"
    return project


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    response: Response,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    q: str | None = Query(None),
    technician_id: uuid.UUID | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Project).where(Project.organization_id == organization_id).order_by(Project.created_at.desc())
    stmt = scope_projects_stmt(stmt, current_user)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if q:
        like = contains_pattern(q)
        stmt = stmt.where((Project.title.ilike(like, escape=LIKE_ESCAPE)) | (Project.address_street.ilike(like, escape=LIKE_ESCAPE)))
    if technician_id:
        stmt = stmt.where(Project.primary_technician_user_id == technician_id)
    limit, offset = pagination
    return [
        _with_access(project, current_user)
        for project in await paginate(db, stmt, limit=limit, offset=offset, response=response)
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.create")),
):
    return await field_ops_service.create_project(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        data=payload.model_dump(),
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    project = await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )
    return _with_access(project, current_user)


@router.get("/projects/{project_id}/assignments")
async def project_assignments(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> list[dict]:
    from app.modules.field_ops.installation import assignments_of

    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    limit, offset = pagination
    return paginate_list(
        await assignments_of(db, organization_id=organization_id, project_id=project_id),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    project = await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}/checklist", response_model=list[ProjectChecklistItemResponse])
async def get_project_checklist(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    limit, offset = pagination
    return await paginate(
        db,
        select(ProjectChecklistItem)
        .where(ProjectChecklistItem.project_id == project_id)
        .order_by(ProjectChecklistItem.sort_order, ProjectChecklistItem.id),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/checklist/apply-template", response_model=list[ProjectChecklistItemResponse])
async def apply_checklist_template_to_project(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    items = await field_ops_service.apply_checklist_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        template_id=template_id,
    )
    await db.commit()
    for item in items:
        await db.refresh(item)
    return items


@router.patch("/checklist-items/{item_id}", response_model=ProjectChecklistItemResponse)
async def update_checklist_item(
    item_id: uuid.UUID,
    payload: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    return await checklist_service.update_checklist_item(
        db,
        organization_id=organization_id,
        user=current_user,
        item_id=item_id,
        is_complete=payload.is_complete,
        not_applicable=payload.not_applicable,
        reason=payload.reason,
    )


@router.patch("/projects/{project_id}/conditions", response_model=ProjectResponse)
async def set_installation_conditions(
    project_id: uuid.UUID,
    payload: InstallationConditionsUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.complete")),
):
    return await checklist_service.set_installation_conditions(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        conditions=payload.conditions,
    )


@router.get("/cases/{case_id}/project")
async def project_of_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
) -> dict:
    stmt = select(Project).where(Project.organization_id == organization_id, Project.case_id == case_id)
    stmt = scope_projects_stmt(stmt, current_user)
    project = (await db.execute(stmt)).scalars().first()
    if project is None:
        raise NotFoundError("Este expediente no tiene proyecto.", code="project_not_found")
    return {"id": str(project.id), "title": project.title, "status": project.status}
