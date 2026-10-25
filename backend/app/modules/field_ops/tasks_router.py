import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.access import get_visible_project, get_workable_project
from app.modules.field_ops.models import Task, TaskComment
from app.modules.field_ops.schemas import (
    OverdueTaskResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.modules.users.models import User
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    limit, offset = pagination
    return await paginate(
        db,
        select(Task).where(Task.project_id == project_id).order_by(Task.due_date.asc().nulls_last(), Task.id),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: uuid.UUID, payload: TaskCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    task = Task(organization_id=organization_id, project_id=project_id, **payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _get_task_or_404(
    db: AsyncSession, *, organization_id: uuid.UUID, task_id: uuid.UUID, current_user: User
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.organization_id == organization_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("La tarea no existe.", code="task_not_found")
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=task.project_id)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    task = await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=task.project_id)
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
    permissions = get_effective_permissions(current_user)
    restrict_to = None if "projects.read_all" in permissions else current_user.id
    limit, offset = pagination
    pairs = await paginate(
        db,
        field_ops_service.overdue_tasks_query(organization_id=organization_id, restrict_to_technician_id=restrict_to),
        limit=limit,
        offset=offset,
        response=response,
        scalars=False,
    )
    return [
        OverdueTaskResponse(**TaskResponse.model_validate(task).model_dump(), project_title=project_title)
        for task, project_title in pairs
    ]


@router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(
    task_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    limit, offset = pagination
    return await paginate(
        db,
        select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at.asc(), TaskComment.id),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
async def create_task_comment(
    task_id: uuid.UUID, payload: TaskCommentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("tasks.manage")),
):
    task = await _get_task_or_404(db, organization_id=organization_id, task_id=task_id, current_user=current_user)
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=task.project_id)
    comment = TaskComment(task_id=task_id, author_user_id=current_user.id, body=payload.body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment
