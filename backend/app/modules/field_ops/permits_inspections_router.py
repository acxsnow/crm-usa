import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import inspections as inspections_service
from app.modules.field_ops import installation as installation_service
from app.modules.field_ops import permits as permits_service
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.access import get_visible_project, scope_projects_stmt
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import Inspection, Project
from app.modules.field_ops.schemas import (
    EquipmentCreate,
    EquipmentResponse,
    EvidenceResponse,
    InspectionCreate,
    InspectionResponse,
    InspectionResultRequest,
    MaterialCreate,
    MaterialResponse,
    PermitCreate,
    PermitResponse,
    PermitUpdate,
    ProjectResponse,
)
from app.modules.users.models import User
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/projects/{project_id}/permits", response_model=list[PermitResponse])
async def list_project_permits(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(
        await permits_service.list_permits(
            db, organization_id=organization_id, user=current_user, project_id=project_id
        ),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/permits", response_model=PermitResponse, status_code=201)
async def record_project_permit(
    project_id: uuid.UUID,
    payload: PermitCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("permits.manage")),
):
    return await permits_service.record_permit(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        data=payload.model_dump(),
    )


@router.patch("/permits/{permit_id}", response_model=PermitResponse)
async def update_project_permit(
    permit_id: uuid.UUID,
    payload: PermitUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("permits.manage")),
):
    return await permits_service.update_permit(
        db,
        organization_id=organization_id,
        user=current_user,
        permit_id=permit_id,
        changes=payload.model_dump(exclude_unset=True),
    )


@router.get("/projects/{project_id}/equipment", response_model=list[EquipmentResponse])
async def list_project_equipment(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(
        await installation_service.list_equipment(
            db, organization_id=organization_id, user=current_user, project_id=project_id
        ),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/equipment", response_model=EquipmentResponse, status_code=201)
async def add_project_equipment(
    project_id: uuid.UUID,
    payload: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    return await installation_service.add_equipment(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        data=payload.model_dump(),
    )


@router.post("/projects/{project_id}/equipment/confirm", response_model=ProjectResponse)
async def confirm_project_equipment(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    return await installation_service.confirm_equipment(
        db, organization_id=organization_id, user=current_user, project_id=project_id
    )


@router.delete("/equipment/{equipment_id}", status_code=204)
async def delete_project_equipment(
    equipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("equipment.manage")),
):
    await installation_service.delete_equipment(
        db, organization_id=organization_id, user=current_user, equipment_id=equipment_id
    )
    return Response(status_code=204)


@router.get("/projects/{project_id}/materials", response_model=list[MaterialResponse])
async def list_project_materials(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(
        await installation_service.list_materials(
            db, organization_id=organization_id, user=current_user, project_id=project_id
        ),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/materials", response_model=MaterialResponse, status_code=201)
async def add_project_material(
    project_id: uuid.UUID,
    payload: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    return await installation_service.add_material(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        data=payload.model_dump(),
    )


@router.delete("/materials/{material_id}", status_code=204)
async def delete_project_material(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("projects.update")),
):
    await installation_service.delete_material(
        db, organization_id=organization_id, user=current_user, material_id=material_id
    )
    return Response(status_code=204)


@router.get("/projects/{project_id}/inspections", response_model=list[InspectionResponse])
async def list_project_inspections(
    project_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    limit, offset = pagination
    return paginate_list(
        await inspections_service.list_inspections(
            db, organization_id=organization_id, user=current_user, project_id=project_id
        ),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/projects/{project_id}/inspections", response_model=InspectionResponse, status_code=201)
async def schedule_project_inspection(
    project_id: uuid.UUID,
    payload: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    return await inspections_service.schedule_inspection(
        db,
        organization_id=organization_id,
        user=current_user,
        project_id=project_id,
        scheduled_for=payload.scheduled_for,
        inspector_name=payload.inspector_name,
    )


@router.post("/inspections/{inspection_id}/result", response_model=InspectionResponse)
async def record_project_inspection_result(
    inspection_id: uuid.UUID,
    payload: InspectionResultRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    return await inspections_service.record_inspection_result(
        db,
        organization_id=organization_id,
        user=current_user,
        inspection_id=inspection_id,
        result=payload.result,
        observations=payload.observations,
        inspector_name=payload.inspector_name,
    )


@router.post("/inspections/{inspection_id}/signed-permit", response_model=EvidenceResponse, status_code=201)
async def upload_signed_permit(
    inspection_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("inspections.manage")),
):
    inspection = (
        await db.execute(
            select(Inspection).where(Inspection.id == inspection_id, Inspection.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if inspection is None:
        raise NotFoundError("La inspección no existe.", code="inspection_not_found")
    await get_visible_project(
        db, organization_id=organization_id, user=current_user, project_id=inspection.project_id
    )
    return await field_ops_service.upload_evidence(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        project_id=inspection.project_id,
        file=file,
        category="permit_signed",
        latitude=None,
        longitude=None,
        captured_at=None,
        task_id=None,
        checklist_item_id=None,
    )


_permits_view = require_any_permission("permits.manage", "inspections.manage", "projects.read_all")


async def _project_titles(db: AsyncSession, ids) -> dict:
    ids = {project_id for project_id in ids if project_id}
    if not ids:
        return {}
    projects = (await db.execute(select(Project).where(Project.id.in_(ids)))).scalars().all()
    return {project.id: project.title for project in projects}


@router.get("/permits")
async def list_all_permits(
    response: Response,
    status: str | None = None,
    expiring_within_days: int | None = Query(None, ge=0, le=365),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    current_user: User = Depends(_permits_view),
) -> list[dict]:
    from app.modules.field_ops.catalogs import PERMIT_STATUS_LABELS
    from app.modules.field_ops.models import Permit

    hoy = await org_today(db, organization_id)
    stmt = select(Permit).join(Project, Project.id == Permit.project_id).where(Project.organization_id == organization_id)
    stmt = scope_projects_stmt(stmt, current_user)
    if status:
        stmt = stmt.where(Permit.status == status)
    if expiring_within_days is not None:
        stmt = stmt.where(
            Permit.expires_on.is_not(None),
            Permit.expires_on >= hoy,
            Permit.expires_on <= hoy + timedelta(days=expiring_within_days),
        )
    limit, offset = pagination
    items = await paginate(
        db,
        stmt.order_by(Permit.expires_on.asc().nulls_last(), Permit.id),
        limit=limit,
        offset=offset,
        response=response,
    )
    titles = await _project_titles(db, {permit.project_id for permit in items})
    return [
        {
            "id": str(permit.id),
            "project_id": str(permit.project_id),
            "project_title": titles.get(permit.project_id),
            "jurisdiction": permit.jurisdiction,
            "permit_number": permit.permit_number,
            "permit_type": permit.permit_type,
            "status": str(permit.status),
            "status_label": PERMIT_STATUS_LABELS.get(permit.status, str(permit.status)),
            "filed_on": permit.filed_on.isoformat() if permit.filed_on else None,
            "approved_on": permit.approved_on.isoformat() if permit.approved_on else None,
            "expires_on": permit.expires_on.isoformat() if permit.expires_on else None,
            "days_to_expiry": (permit.expires_on - hoy).days if permit.expires_on else None,
        }
        for permit in items
    ]


@router.get("/inspections")
async def list_all_inspections(
    response: Response,
    result: str | None = None,
    upcoming: bool = False,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    current_user: User = Depends(_permits_view),
) -> list[dict]:
    from app.modules.field_ops.catalogs import INSPECTION_RESULT_LABELS

    stmt = select(Inspection).join(Project, Project.id == Inspection.project_id).where(
        Project.organization_id == organization_id
    )
    stmt = scope_projects_stmt(stmt, current_user)
    if result:
        stmt = stmt.where(Inspection.result == result)
    if upcoming:
        stmt = stmt.where(
            Inspection.result == "pending",
            Inspection.scheduled_for >= datetime.now(timezone.utc),
        )
    limit, offset = pagination
    order = Inspection.scheduled_for.asc() if upcoming else Inspection.scheduled_for.desc()
    items = await paginate(db, stmt.order_by(order, Inspection.id), limit=limit, offset=offset, response=response)
    titles = await _project_titles(db, {inspection.project_id for inspection in items})
    return [
        {
            "id": str(inspection.id),
            "project_id": str(inspection.project_id),
            "project_title": titles.get(inspection.project_id),
            "scheduled_for": inspection.scheduled_for.isoformat(),
            "inspector_name": inspection.inspector_name,
            "result": str(inspection.result),
            "result_label": INSPECTION_RESULT_LABELS.get(inspection.result, str(inspection.result)),
            "result_recorded_at": inspection.result_recorded_at.isoformat()
            if inspection.result_recorded_at
            else None,
            "observations": inspection.observations,
        }
        for inspection in items
    ]
