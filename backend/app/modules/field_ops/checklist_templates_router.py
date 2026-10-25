import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.modules.cases.models import Program
from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE
from app.modules.field_ops.models import ChecklistTemplate, ChecklistTemplateItem
from app.modules.field_ops.schemas import ChecklistTemplateCreate, ChecklistTemplateResponse
from app.modules.users.models import User
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/checklist-templates", response_model=list[ChecklistTemplateResponse])
async def list_checklist_templates(
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    limit, offset = pagination
    return await paginate(
        db,
        select(ChecklistTemplate).where(ChecklistTemplate.organization_id == organization_id).order_by(
            ChecklistTemplate.name, ChecklistTemplate.id
        ),
        limit=limit,
        offset=offset,
        response=response,
    )


@router.post("/checklist-templates", response_model=ChecklistTemplateResponse, status_code=201)
async def create_checklist_template(
    payload: ChecklistTemplateCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    await _check_template_program(db, organization_id, payload.program_id)
    template = ChecklistTemplate(
        organization_id=organization_id,
        name=payload.name,
        project_type=payload.project_type,
        program_id=payload.program_id,
    )
    db.add(template)
    await db.flush()
    for item_data in payload.items:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data.model_dump()))
    await db.commit()
    await db.refresh(template)
    return template


async def _check_template_program(
    db: AsyncSession, organization_id: uuid.UUID, program_id: uuid.UUID | None, template_id: uuid.UUID | None = None
) -> None:
    """El programa es de la organización y no tiene ya otra plantilla."""
    if program_id is None:
        return
    programa = (
        await db.execute(select(Program.id).where(Program.id == program_id, Program.organization_id == organization_id))
    ).first()
    if programa is None:
        raise InvalidInputError("El programa no existe.", code="program_not_found")
    stmt = select(ChecklistTemplate.id).where(
        ChecklistTemplate.organization_id == organization_id,
        ChecklistTemplate.program_id == program_id,
    )
    if template_id is not None:
        stmt = stmt.where(ChecklistTemplate.id != template_id)
    otra = (await db.execute(stmt)).first()
    if otra is not None:
        raise ConflictError(
            "Ese programa ya tiene su plantilla de checklist; edítala en vez de crear otra.",
            code="program_template_exists",
        )


async def _get_template(db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID) -> ChecklistTemplate:
    template = await db.get(ChecklistTemplate, template_id)
    if template is None or template.organization_id != organization_id:
        raise NotFoundError("La plantilla no existe.", code="checklist_template_not_found")
    return template


@router.put("/checklist-templates/{template_id}", response_model=ChecklistTemplateResponse)
async def update_checklist_template(
    template_id: uuid.UUID, payload: ChecklistTemplateCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    template = await _get_template(db, organization_id, template_id)
    await _check_template_program(db, organization_id, payload.program_id, template.id)
    before = {
        "name": template.name,
        "program_id": str(template.program_id) if template.program_id else None,
        "items": len(template.items),
    }
    template.name = payload.name
    template.project_type = payload.project_type
    template.program_id = payload.program_id
    template.items.clear()
    await db.flush()
    for item_data in payload.items:
        template.items.append(ChecklistTemplateItem(**item_data.model_dump()))
    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="checklist_templates.updated",
        entity_type="checklist_template",
        entity_id=str(template.id),
        before_data=before,
        after_data={"name": payload.name, "items": len(payload.items)},
    )
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/checklist-templates/{template_id}", status_code=204)
async def delete_checklist_template(
    template_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
    template = await _get_template(db, organization_id, template_id)
    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="checklist_templates.deleted",
        entity_type="checklist_template",
        entity_id=str(template.id),
        before_data={"name": template.name},
    )
    await db.delete(template)
    await db.commit()
    return Response(status_code=204)


@router.post("/checklist-templates/seed-default", response_model=ChecklistTemplateResponse, status_code=201)
async def seed_default_checklist_template(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("checklists.manage")),
):
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
        organization_id=organization_id,
        name=DEFAULT_CHECKLIST_TEMPLATE["name"],
        project_type=DEFAULT_CHECKLIST_TEMPLATE["project_type"],
    )
    db.add(template)
    await db.flush()
    for item_data in DEFAULT_CHECKLIST_TEMPLATE["items"]:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data))
    await db.commit()
    await db.refresh(template)
    return template
