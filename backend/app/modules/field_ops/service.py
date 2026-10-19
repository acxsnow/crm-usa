import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import Customer
from app.modules.organizations.models import Organization
from app.modules.notifications.email import send_email
from app.core.config import get_settings
from app.core.security import generate_secure_token, hash_token
from app.modules.field_ops.models import (
    Attestation,
    CustomerSignatureToken,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Evidence,
    InstalledEquipment,
    Project,
    ProjectChecklistItem,
    Task,
    TaskStatus,
)
from app.modules.field_ops.pdf import build_attestation_pdf, decode_signature_png
from app.shared.files.storage import save_bytes
from app.shared.datetime_utils import as_utc
from app.shared.files.watermark import VIDEO_MIME_TYPES, WATERMARKABLE_MIME_TYPES, apply_gps_watermark, apply_video_watermark
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError

settings = get_settings()
logger = structlog.get_logger(__name__)

# Evidence scope confirmed with Mateo (Sept 2026): photos and short videos,
# ~10-20 evidence items per project in real use. Enforced as a
# generous ceiling — legitimate uploads should never hit it, but it catches
# accidental bulk-upload bugs and unsupported file types early.
ALLOWED_EVIDENCE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", *VIDEO_MIME_TYPES}
MAX_EVIDENCE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB per evidence item
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
            section=template_item.section,
            evidence_category=template_item.evidence_category,
            condition_code=template_item.condition_code,
            allows_not_applicable=template_item.allows_not_applicable,
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


async def auto_create_project_from_case(db: AsyncSession, *, case, actor_id: uuid.UUID | None) -> Project:
    """Crea el proyecto de instalación al aprobarse el expediente.

    Contrato `docs/contratos/case.md` §4: al entrar a `approved` se crea el
    `Project`, una sola vez. Reemplaza a `auto_create_project_from_opportunity`.

    **No hace commit**: corre como efecto dentro de la transacción del cambio de
    etapa, así que el expediente aprobado y su proyecto se guardan juntos o no
    se guarda ninguno. Idempotente: volver a entrar a `approved` desde `on_hold`
    devuelve el proyecto existente.
    """
    existing = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalar_one_or_none()
    if existing:
        return existing

    if case.customer_id is None:
        # `Project.customer_id` es obligatorio. Un expediente sin cliente no
        # debería llegar a aprobado; si llega, el mensaje dice qué falta en vez
        # de reventar con un error de base de datos.
        raise InvalidInputError(
            f"El expediente {case.case_number} no tiene cliente, así que no se "
            "puede crear el proyecto de instalación.",
            code="case_without_customer",
        )

    from app.modules.field_ops.checklist import select_template_for_case

    # La plantilla del programa del expediente; si el programa no tiene la
    # suya, la de la organización (spec D5.3).
    template = await select_template_for_case(db, case=case) or (
        await get_or_create_default_checklist_template(db, organization_id=case.organization_id)
    )
    project = Project(
        organization_id=case.organization_id,
        customer_id=case.customer_id,
        case_id=case.id,
        # El número del expediente va en el título porque es lo que la gente se
        # dice por teléfono entre Administración y el técnico.
        title=f"Instalación · {case.case_number}",
        project_type="hvac_install",
        address_street=case.address_street,
        address_unit=case.address_unit,
        address_city=case.address_city,
        address_state=case.address_state,
        address_zip=case.address_zip,
        latitude=case.latitude,
        longitude=case.longitude,
    )
    db.add(project)
    await db.flush()
    await apply_checklist_template(
        db, organization_id=case.organization_id, project_id=project.id, template_id=template.id
    )
    await record_audit_event(
        db,
        organization_id=case.organization_id,
        actor_user_id=actor_id,
        action="projects.auto_created_from_case",
        entity_type="Project",
        entity_id=str(project.id),
        after_data={"case_id": str(case.id), "case_number": case.case_number},
    )
    return project


# ---------------------------------------------------------------------------
# Evidence — GPS/date watermark burned into images and videos
# ---------------------------------------------------------------------------

async def _resolve_evidence_category(
    db: AsyncSession, *, project_id: uuid.UUID, checklist_item_id: uuid.UUID | None,
    category: str | None, mime_type: str,
) -> str:
    """La categoría con la que se guarda la evidencia (spec D5.4).

    Si es para un ítem del checklist que exige una categoría, se usa esa; si
    llega otra distinta se rechaza: la foto de la etiqueta exterior no puede
    quedar guardada como fachada. Sin ítem ni categoría, la genérica del tipo
    de archivo."""
    from app.modules.field_ops.catalogs import EVIDENCE_CATEGORIES, default_evidence_category

    if category is not None and category not in EVIDENCE_CATEGORIES:
        raise InvalidInputError(
            f"La categoría de evidencia «{category}» no existe.", code="unknown_evidence_category"
        )

    if checklist_item_id is not None:
        item = (
            await db.execute(
                select(ProjectChecklistItem).where(
                    ProjectChecklistItem.id == checklist_item_id,
                    ProjectChecklistItem.project_id == project_id,
                )
            )
        ).scalar_one_or_none()
        if item is None:
            # Un ítem de otro proyecto (u otra organización) no se puede
            # adjuntar a este: se responde como si no existiera.
            raise InvalidInputError(
                "El ítem del checklist no pertenece a este proyecto.",
                code="checklist_item_not_in_project",
            )
        if item.evidence_category:
            if category is not None and category != item.evidence_category:
                raise InvalidInputError(
                    f"La evidencia de «{item.label}» debe ser de la categoría "
                    f"«{EVIDENCE_CATEGORIES[item.evidence_category]}».",
                    code="evidence_category_mismatch",
                )
            return item.evidence_category

    return category or default_evidence_category(mime_type)


async def upload_evidence(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, project_id: uuid.UUID,
    file: UploadFile, category: str | None, latitude: float | None, longitude: float | None,
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
            detail=f"Unsupported file type: {mime_type or 'unknown'}. Accepted: photos (JPEG, PNG, WEBP, HEIC) and videos (MP4, MOV, WEBM).",
        )

    category = await _resolve_evidence_category(
        db, project_id=project_id, checklist_item_id=checklist_item_id,
        category=category, mime_type=mime_type,
    )

    existing_count = len(
        (await db.execute(select(Evidence).where(Evidence.project_id == project_id, Evidence.deleted_at.is_(None)))).scalars().all()
    )
    if existing_count >= MAX_EVIDENCE_PER_PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This project already has {existing_count} evidence files, the maximum allowed ({MAX_EVIDENCE_PER_PROJECT}).",
        )

    # Tamaño mientras se recibe y tipo real por contenido (SEG-01, SEG-02).
    from app.shared.files.validation import check_type, read_limited

    raw_bytes = await read_limited(file, MAX_EVIDENCE_SIZE_BYTES)
    check_type(raw_bytes, mime_type, ALLOWED_EVIDENCE_MIME_TYPES)
    watermarked = False

    if mime_type in WATERMARKABLE_MIME_TYPES:
        try:
            raw_bytes = apply_gps_watermark(raw_bytes, latitude=latitude, longitude=longitude, captured_at=captured_at)
            mime_type = "image/jpeg"
            watermarked = True
        except Exception:
            # Corrupt/unsupported image bytes: store the original rather than failing the upload.
            watermarked = False
    elif mime_type in VIDEO_MIME_TYPES:
        try:
            raw_bytes = apply_video_watermark(raw_bytes, latitude=latitude, longitude=longitude, captured_at=captured_at)
            mime_type = "video/mp4"
            watermarked = True
        except Exception as exc:
            # El detalle de ffmpeg trae rutas temporales del servidor y versiones
            # de librerías: se registra, no se devuelve. Al cliente le basta con
            # saber que el archivo no es un video procesable, y eso es un 400
            # (lo que mandó está mal), no un 422.
            logger.warning(
                "evidence.video_watermark_failed",
                project_id=str(project_id),
                organization_id=str(organization_id),
                filename=file.filename,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se pudo procesar el video. Verifica que el archivo esté "
                    "completo y sea un video válido (MP4, MOV o WEBM)."
                ),
            ) from exc

    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project_id}/evidence",
        filename=(f"{file.filename.rsplit('.', 1)[0]}.mp4" if mime_type == "video/mp4" and file.filename else (file.filename or "evidence")), data=raw_bytes,
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
        after_data={"project_id": str(project_id), "category": category, "watermarked": watermarked},
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

    equipos = (
        await db.execute(
            select(InstalledEquipment).where(InstalledEquipment.project_id == project.id).order_by(InstalledEquipment.created_at)
        )
    ).scalars().all()
    organizacion = await db.get(Organization, organization_id)

    pdf_bytes = build_attestation_pdf(
        project=project, customer=customer, checklist_items=checklist_items, attestation=attestation,
        equipment=equipos, organization_name=organizacion.name if organizacion else "",
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
    _ensure_not_signed(attestation.technician_signed_at, "El técnico ya firmó el acta.")
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
    _ensure_not_signed(attestation.customer_signed_at, "El cliente ya firmó el acta.")
    signature_bytes = decode_signature_png(signature_base64)
    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"projects/{project_id}/attestation",
        filename="customer_signature.png", data=signature_bytes,
    )
    now = datetime.now(timezone.utc)
    attestation.customer_name = customer_name.strip()
    attestation.customer_signature_path = relative_path
    attestation.customer_signed_at = now
    # Firmó en persona: el enlace que se le haya enviado ya no sirve.
    pendiente = await pending_signature_link(db, attestation.id)
    if pendiente:
        pendiente.revoked_at = now

    await _maybe_generate_pdf(db, organization_id=organization_id, project=project, attestation=attestation)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="attestation.customer_signed", entity_type="Attestation", entity_id=str(attestation.id),
        # En el celular del técnico (spec 2026-10-18-firmas-del-acta); la del
        # enlace queda como `attestation.customer_signed_public`.
        after_data={"method": "in_person", "customer_name": attestation.customer_name},
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
    _ensure_not_signed(attestation.customer_signed_at, "El cliente ya firmó el acta.")
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
    enviado = await send_email(to=customer.email, template="customer_signature_request", context={"signing_link": link, "project_title": project.title, "expires_at": token.expires_at.isoformat()})
    if not enviado:
        # El enlace quedó creado; pedirlo de nuevo genera otro. Decir «enviado»
        # aquí dejaba al cliente esperando un correo que nunca llegó.
        from app.shared.errors import ExternalServiceError

        raise ExternalServiceError(f"No se pudo enviar el correo a {customer.email}. Revisa la configuración de correo "
                                   "e inténtalo de nuevo.", code="email_not_sent")
    return token


def _ensure_not_signed(signed_at, message: str) -> None:
    """Una firma no se reescribe (spec 2026-10-18-firmas-del-acta)."""
    if signed_at is not None:
        raise ConflictError(message, code="already_signed")


async def pending_signature_link(db: AsyncSession, attestation_id: uuid.UUID) -> CustomerSignatureToken | None:
    """El enlace de firma enviado y todavía usable: sin firmar, sin revocar y sin vencer."""
    token = (await db.execute(
        select(CustomerSignatureToken).where(CustomerSignatureToken.attestation_id == attestation_id)
    )).scalar_one_or_none()
    if not token or token.signed_at or token.revoked_at or as_utc(token.expires_at) < datetime.now(timezone.utc):
        return None
    return token


async def get_public_signature_request(db: AsyncSession, *, raw_token: str) -> tuple[CustomerSignatureToken, Attestation, Project]:
    token = (await db.execute(select(CustomerSignatureToken).where(CustomerSignatureToken.token_hash == hash_token(raw_token)))).scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El enlace no es válido o ya expiró.")
    if not token or token.revoked_at or token.signed_at or as_utc(token.expires_at) < datetime.now(timezone.utc):
        raise invalid
    attestation = (await db.execute(select(Attestation).where(Attestation.id == token.attestation_id))).scalar_one()
    if attestation.customer_signed_at:
        raise invalid
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

def overdue_tasks_query(
    *, organization_id: uuid.UUID, restrict_to_technician_id: uuid.UUID | None = None,
):
    """The query of (task, project_title) pairs for every not-done task whose
    due date has passed; the router paginates it (it grows with the backlog). This is the same lazy, computed-on-read approach as
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
    return stmt.order_by(Task.id)
