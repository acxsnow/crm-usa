import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import Customer
from app.modules.notifications.email import send_email
from app.core.config import get_settings
from app.core.security import generate_secure_token, hash_token
from app.modules.field_ops.models import (
    Attestation,
    CustomerSignatureToken,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Evidence,
    EvidenceCategory,
    Project,
    ProjectChecklistItem,
    Task,
    TaskStatus,
)
from app.modules.field_ops.pdf import build_attestation_pdf, decode_signature_png
from app.modules.field_ops.storage import save_bytes
from app.modules.field_ops.watermark import WATERMARKABLE_MIME_TYPES, apply_gps_watermark
from app.shared.audit import record_audit_event

settings = get_settings()

# Evidence scope confirmed with Mateo (Sept 2026): photos only for now (no
# video support yet), ~10-20 photos per project in real use. Enforced as a
# generous ceiling — legitimate uploads should never hit it, but it catches
# accidental bulk-upload bugs and unsupported file types early.
ALLOWED_EVIDENCE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_EVIDENCE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB per photo
MAX_EVIDENCE_PER_PROJECT = 40  # generous ceiling above the ~10-20 typical count


# ---------------------------------------------------------------------------
# Projects + checklist
# ---------------------------------------------------------------------------

async def apply_checklist_template(
    db: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, template_id: uuid.UUID,
) -> list[ProjectChecklistItem]:
    result = await db.execute(
        select(ChecklistTemplate).where(
            ChecklistTemplate.id == template_id, ChecklistTemplate.organization_id == organization_id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown checklist template.")

    items = []
    for template_item in template.items:
        item = ProjectChecklistItem(
            project_id=project_id,
            source_template_item_id=template_item.id,
            label=template_item.label,
            sort_order=template_item.sort_order,
            is_required=template_item.is_required,
            requires_evidence=template_item.requires_evidence,
        )
        db.add(item)
        items.append(item)
    return items


async def create_project(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, data: dict,
) -> Project:
    apply_template_id = data.pop("apply_checklist_template_id", None)
    project = Project(organization_id=organization_id, **data)
    db.add(project)
    await db.flush()

    if apply_template_id:
        await apply_checklist_template(db, organization_id=organization_id, project_id=project.id, template_id=apply_template_id)

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="projects.created", entity_type="Project", entity_id=str(project.id),
        after_data={"title": project.title},
    )
    await db.commit()
    await db.refresh(project)
    return project


async def get_or_create_default_checklist_template(db: AsyncSession, *, organization_id: uuid.UUID) -> ChecklistTemplate:
    from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE

    result = await db.execute(
        select(ChecklistTemplate).where(
            ChecklistTemplate.organization_id == organization_id,
            ChecklistTemplate.name == DEFAULT_CHECKLIST_TEMPLATE["name"],
        )
    )
    template = result.scalar_one_or_none()
    if template:
        return template

    template = ChecklistTemplate(
        organization_id=organization_id, name=DEFAULT_CHECKLIST_TEMPLATE["name"],
        project_type=DEFAULT_CHECKLIST_TEMPLATE["project_type"],
    )
    db.add(template)
    await db.flush()
    for item_data in DEFAULT_CHECKLIST_TEMPLATE["items"]:
        db.add(ChecklistTemplateItem(template_id=template.id, **item_data))
    await db.flush()
    return template


async def auto_create_project_from_opportunity(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, opportunity,
) -> Project:
    """Confirmed with Mateo (Sept 2026): a Project is created automatically
    the moment an Opportunity reaches "Aprobada"/"Instalación", pre-loaded
    with the default checklist and ready to assign a technician. Idempotent —
    moving between those two stages more than once won't create duplicates."""
    existing = await db.execute(select(Project).where(Project.opportunity_id == opportunity.id))
    project = existing.scalar_one_or_none()
    if project:
        return project

    template = await get_or_create_default_checklist_template(db, organization_id=organization_id)

    project = Project(
        organization_id=organization_id,
        customer_id=opportunity.customer_id,
        opportunity_id=opportunity.id,
        title=opportunity.title,
        project_type="hvac_install",
        primary_technician_user_id=opportunity.owner_user_id,
        address_street=opportunity.address_street,
        address_unit=opportunity.address_unit,
        address_city=opportunity.address_city,
        address_state=opportunity.address_state,
        address_zip=opportunity.address_zip,
        latitude=opportunity.latitude,
        longitude=opportunity.longitude,
    )
    db.add(project)
    await db.flush()
    await apply_checklist_template(db, organization_id=organization_id, project_id=project.id, template_id=template.id)

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="projects.auto_created_from_opportunity", entity_type="Project", entity_id=str(project.id),
        after_data={"opportunity_id": str(opportunity.id)},
    )
    await db.commit()
    await db.refresh(project)
    return project


async def complete_checklist_item(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, item_id: uuid.UUID, is_complete: bool,
) -> ProjectChecklistItem:
    result = await db.execute(
        select(ProjectChecklistItem).join(Project, Project.id == ProjectChecklistItem.project_id).where(
            ProjectChecklistItem.id == item_id, Project.organization_id == organization_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found.")

    if is_complete and item.requires_evidence:
        evidence_count = (
            await db.execute(select(Evidence).where(Evidence.checklist_item_id == item.id, Evidence.deleted_at.is_(None)))
        ).scalars().all()
        if not evidence_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This checklist item requires at least one evidence upload before it can be marked complete.",
            )

    item.is_complete = is_complete
    item.completed_at = datetime.now(timezone.utc) if is_complete else None
    item.completed_by_user_id = actor_id if is_complete else None
    await db.commit()
    await db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Evidence — GPS watermark burned into the image (confirmed requirement)
# ---------------------------------------------------------------------------

async def upload_evidence(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, project_id: uuid.UUID,
    file: UploadFile, category: EvidenceCategory, latitude: float | None, longitude: float | None,
    captured_at: datetime | None, task_id: uuid.UUID | None, checklist_item_id: uuid.UUID | None,
) -> Evidence:
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {mime_type or 'unknown'}. Only photos are accepted (JPEG, PNG, WEBP, HEIC).",
        )

    existing_count = len(
        (await db.execute(select(Evidence).where(Evidence.project_id == project_id, Evidence.deleted_at.is_(None)))).scalars().all()
    )
    if existing_count >= MAX_EVIDENCE_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This project already has {existing_count} evidence files, the maximum allowed ({MAX_EVIDENCE_PER_PROJECT}).",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_EVIDENCE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large ({len(raw_bytes) // (1024 * 1024)} MB). Max allowed is {MAX_EVIDENCE_SIZE_BYTES // (1024 * 1024)} MB.",
        )
    watermarked = False

    if mime_type in WATERMARKABLE_MIME_TYPES:
        try:
            raw_bytes = apply_gps_watermark(raw_bytes, latitude=latitude, longitude=longitude, captured_at=captured_at)
            mime_type = "image/jpeg"
            watermarked = True
        except Exception:
            # Corrupt/unsupported image bytes: store the original rather than failing the upload.
            watermarked = False

    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project_id}/evidence",
        filename=file.filename or "evidence", data=raw_bytes,
    )

    evidence = Evidence(
        organization_id=organization_id,
        project_id=project_id,
        task_id=task_id,
        checklist_item_id=checklist_item_id,
        category=category,
        file_path=relative_path,
        original_filename=file.filename,
        mime_type=mime_type,
        size_bytes=len(raw_bytes),
        latitude=latitude,
        longitude=longitude,
        captured_at=captured_at or datetime.now(timezone.utc),
        watermarked=watermarked,
        uploaded_by_user_id=actor_id,
    )
    db.add(evidence)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="evidence.uploaded", entity_type="Evidence",
        after_data={"project_id": str(project_id), "category": category.value, "watermarked": watermarked},
    )
    await db.commit()
    await db.refresh(evidence)
    return evidence


# ---------------------------------------------------------------------------
# Attestation — digital signature capture (technician + customer)
# ---------------------------------------------------------------------------

async def _get_or_create_attestation(db: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Attestation:
    result = await db.execute(
        select(Attestation).where(Attestation.project_id == project_id, Attestation.organization_id == organization_id)
    )
    attestation = result.scalar_one_or_none()
    if not attestation:
        attestation = Attestation(organization_id=organization_id, project_id=project_id)
        db.add(attestation)
        await db.flush()
    return attestation


async def _maybe_generate_pdf(db: AsyncSession, *, organization_id: uuid.UUID, project: Project, attestation: Attestation) -> None:
    if not attestation.is_fully_signed:
        return
    customer_result = await db.execute(select(Customer).where(Customer.id == project.customer_id))
    customer = customer_result.scalar_one_or_none()
    checklist_items = (
        await db.execute(
            select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == project.id).order_by(ProjectChecklistItem.sort_order)
        )
    ).scalars().all()

    pdf_bytes = build_attestation_pdf(
        project=project, customer=customer, checklist_items=checklist_items, attestation=attestation,
        organization_name="CRM Field Ops",
    )
    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project.id}/attestation",
        filename="attestation.pdf", data=pdf_bytes,
    )
    attestation.pdf_path = relative_path
    attestation.generated_at = datetime.now(timezone.utc)


async def technician_sign(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, project_id: uuid.UUID, signature_base64: str,
) -> Attestation:
    project = (
        await db.execute(select(Project).where(Project.id == project_id, Project.organization_id == organization_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    attestation = await _get_or_create_attestation(db, organization_id=organization_id, project_id=project_id)
    signature_bytes = decode_signature_png(signature_base64)
    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project_id}/attestation",
        filename="technician_signature.png", data=signature_bytes,
    )
    attestation.technician_user_id = actor_id
    attestation.technician_signature_path = relative_path
    attestation.technician_signed_at = datetime.now(timezone.utc)

    await _maybe_generate_pdf(db, organization_id=organization_id, project=project, attestation=attestation)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="attestation.technician_signed", entity_type="Attestation", entity_id=str(attestation.id),
    )
    await db.commit()
    await db.refresh(attestation)
    return attestation


async def customer_sign(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, project_id: uuid.UUID,
    customer_name: str, signature_base64: str,
) -> Attestation:
    project = (
        await db.execute(select(Project).where(Project.id == project_id, Project.organization_id == organization_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    attestation = await _get_or_create_attestation(db, organization_id=organization_id, project_id=project_id)
    signature_bytes = decode_signature_png(signature_base64)
    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project_id}/attestation",
        filename="customer_signature.png", data=signature_bytes,
    )
    attestation.customer_name = customer_name
    attestation.customer_signature_path = relative_path
    attestation.customer_signed_at = datetime.now(timezone.utc)

    await _maybe_generate_pdf(db, organization_id=organization_id, project=project, attestation=attestation)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="attestation.customer_signed", entity_type="Attestation", entity_id=str(attestation.id),
    )
    await db.commit()
    await db.refresh(attestation)
    return attestation


async def create_customer_signature_request(
    db: AsyncSession, *, organization_id: uuid.UUID, project_id: uuid.UUID, actor_id: uuid.UUID,
) -> CustomerSignatureToken:
    project = (await db.execute(select(Project).where(Project.id == project_id, Project.organization_id == organization_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    customer = (await db.execute(select(Customer).where(Customer.id == project.customer_id))).scalar_one_or_none()
    if not customer or not customer.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente no tiene un correo registrado.")
    attestation = await _get_or_create_attestation(db, organization_id=organization_id, project_id=project_id)
    existing = (await db.execute(select(CustomerSignatureToken).where(CustomerSignatureToken.attestation_id == attestation.id))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing and existing.signed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La atestación ya fue firmada por el cliente.")
    raw_token, token_hash = generate_secure_token()
    if existing:
        token = existing
        token.token_hash = token_hash
        token.recipient_email = customer.email
        token.expires_at = now + timedelta(hours=settings.CUSTOMER_SIGNATURE_EXPIRE_HOURS)
        token.opened_at = None
        token.revoked_at = None
    else:
        token = CustomerSignatureToken(
            attestation_id=attestation.id, organization_id=organization_id, token_hash=token_hash,
            recipient_email=customer.email, expires_at=now + timedelta(hours=settings.CUSTOMER_SIGNATURE_EXPIRE_HOURS),
        )
        db.add(token)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor_id, action="attestation.customer_signature_requested", entity_type="Attestation", entity_id=str(attestation.id))
    await db.commit()
    await db.refresh(token)
    link = f"{settings.FRONTEND_APP_URL}/customer-signature?token={raw_token}"
    await send_email(to=customer.email, template="customer_signature_request", context={"signing_link": link, "project_title": project.title, "expires_at": token.expires_at.isoformat()})
    return token


async def get_public_signature_request(db: AsyncSession, *, raw_token: str) -> tuple[CustomerSignatureToken, Attestation, Project]:
    token = (await db.execute(select(CustomerSignatureToken).where(CustomerSignatureToken.token_hash == hash_token(raw_token)))).scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El enlace no es válido o ya expiró.")
    if not token or token.revoked_at or token.signed_at or token.expires_at < datetime.now(timezone.utc):
        raise invalid
    attestation = (await db.execute(select(Attestation).where(Attestation.id == token.attestation_id))).scalar_one()
    project = (await db.execute(select(Project).where(Project.id == attestation.project_id))).scalar_one()
    if not token.opened_at:
        token.opened_at = datetime.now(timezone.utc)
        await db.commit()
    return token, attestation, project


async def public_customer_sign(db: AsyncSession, *, raw_token: str, customer_name: str, signature_base64: str) -> Attestation:
    token, attestation, project = await get_public_signature_request(db, raw_token=raw_token)
    signature_bytes = decode_signature_png(signature_base64)
    attestation.customer_name = customer_name.strip()
    attestation.customer_signature_path = save_bytes(organization_id=token.organization_id, subfolder=f"projects/{project.id}/attestation", filename="customer_signature.png", data=signature_bytes)
    now = datetime.now(timezone.utc)
    attestation.customer_signed_at = now
    token.signed_at = now
    await _maybe_generate_pdf(db, organization_id=token.organization_id, project=project, attestation=attestation)
    await record_audit_event(
        db, organization_id=token.organization_id, actor_user_id=None,
        action="attestation.customer_signed_public", entity_type="Attestation", entity_id=str(attestation.id),
    )
    await db.commit()
    await db.refresh(attestation)
    return attestation


# ---------------------------------------------------------------------------
# Overdue tasks
# ---------------------------------------------------------------------------

async def list_overdue_tasks(
    db: AsyncSession, *, organization_id: uuid.UUID, restrict_to_technician_id: uuid.UUID | None = None,
) -> list[tuple[Task, str]]:
    """Returns (task, project_title) pairs for every not-done task whose due
    date has passed. This is the same lazy, computed-on-read approach as
    Invoice's overdue detection — no scheduled job persists an "overdue"
    state (TaskStatus has none to persist into); it's just filtered here
    instead of per-row in Python, since a task board or an overdue-tasks
    view is exactly the kind of place this would be read from anyway.
    `restrict_to_technician_id` scopes to one technician's assigned
    projects, mirroring the assigned-vs-all scoping used everywhere else in
    this module."""
    stmt = (
        select(Task, Project.title)
        .join(Project, Project.id == Task.project_id)
        .where(
            Task.organization_id == organization_id,
            Task.status != TaskStatus.done,
            Task.due_date.isnot(None),
            Task.due_date < datetime.now(timezone.utc),
        )
        .order_by(Task.due_date.asc())
    )
    if restrict_to_technician_id:
        stmt = stmt.where(Project.primary_technician_user_id == restrict_to_technician_id)
    result = await db.execute(stmt)
    return list(result.all())
