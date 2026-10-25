import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import inspections as inspections_service
from app.modules.field_ops import reviews as reviews_service
from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.schemas import (
    InspectionQueueRow,
    PendingReviewRow,
    ProjectResponse,
    ProjectReviewResponse,
    ReturnToTechnicianRequest,
)
from app.modules.users.models import User
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/inspection-queue", response_model=list[InspectionQueueRow])
async def inspection_queue(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    limit, offset = pagination
    rows = await paginate(
        db,
        inspections_service.inspection_queue_stmt(organization_id),
        limit=limit,
        offset=offset,
        response=response,
        scalars=False,
    )
    hoy = await org_today(db, organization_id)
    state = {None: "unscheduled", "pending": "scheduled", "failed": "failed"}
    return [
        InspectionQueueRow(
            project_id=row[0],
            case_id=row[1],
            case_number=row[2],
            title=row[3],
            customer_name=row[4],
            completed_date=row[5],
            status=state.get(row[6], "scheduled"),
            scheduled_for=row[7],
            days_since_close=(hoy - row[5]).days if row[5] else None,
        )
        for row in rows
    ]


@router.get("/acta-reviews/pending", response_model=list[PendingReviewRow])
async def pending_acta_reviews(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    limit, offset = pagination
    rows = await paginate(
        db,
        reviews_service.pending_reviews_stmt(organization_id),
        limit=limit,
        offset=offset,
        response=response,
        scalars=False,
    )
    hoy = await org_today(db, organization_id)
    return [
        PendingReviewRow(
            project_id=row[0],
            case_id=row[1],
            case_number=row[2],
            title=row[3],
            customer_name=row[4],
            technician_name=row[5],
            completed_date=row[6],
            days_waiting=(hoy - row[6]).days if row[6] else None,
        )
        for row in rows
    ]


@router.post("/projects/{project_id}/review/confirm", response_model=ProjectResponse)
async def confirm_technician_info(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    return await reviews_service.confirm_technician_info(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )


@router.post("/projects/{project_id}/review/return", response_model=ProjectResponse)
async def return_to_technician(
    project_id: uuid.UUID,
    payload: ReturnToTechnicianRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.approve")),
):
    return await reviews_service.return_to_technician(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        reason=payload.reason,
    )


@router.get("/projects/{project_id}/reviews", response_model=list[ProjectReviewResponse])
async def list_project_reviews(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    project = await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )
    limit, offset = pagination
    return paginate_list(project.reviews, limit=limit, offset=offset, response=response)
