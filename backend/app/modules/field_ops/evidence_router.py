import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import service as field_ops_service
from app.modules.field_ops.access import get_visible_project, get_workable_project
from app.modules.field_ops.models import Attestation, Evidence
from app.modules.field_ops.schemas import (
    AttestationResponse,
    CustomerSignatureCapture,
    CustomerSignatureRequestResponse,
    EvidenceResponse,
    PublicCustomerSignatureCapture,
    PublicSignatureResponse,
    SignatureCapture,
)
from app.modules.users.models import User
from app.shared.errors import NotFoundError
from app.shared.files.storage import absolute_path
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["field-ops"])


@router.get("/projects/{project_id}/evidence", response_model=list[EvidenceResponse])
async def list_project_evidence(
    project_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("evidence.read_all", "evidence.read_assigned")),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    stmt = select(Evidence).where(Evidence.project_id == project_id, Evidence.deleted_at.is_(None)).order_by(Evidence.created_at.desc())
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
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    return await field_ops_service.upload_evidence(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        project_id=project_id,
        file=file,
        category=category,
        latitude=latitude,
        longitude=longitude,
        captured_at=captured_at,
        task_id=task_id,
        checklist_item_id=checklist_item_id,
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
        raise NotFoundError("La evidencia no existe.", code="evidence_not_found")
    # La misma regla que la lista: un técnico solo abre las fotos de sus obras.
    # Antes bastaba con conocer el id para bajar la foto de otra obra (D-013).
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=evidence.project_id)
    return FileResponse(str(absolute_path(evidence.file_path)), media_type=evidence.mime_type or "application/octet-stream")


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.delete")),
):
    """Quita una foto o video subido por error (D-014: el permiso existía y no
    hacía nada). Se marca como borrada, no se pierde el archivo, y solo con la
    instalación abierta: cerrada, el acta queda como se firmó. Si era la única
    evidencia de un renglón del checklist que la exige y ya estaba completo,
    el renglón vuelve a pendiente."""
    from datetime import timezone as tz

    from app.modules.field_ops.checklist import _has_evidence, ensure_installation_open
    from app.modules.field_ops.models import ProjectChecklistItem
    from app.shared.audit import record_audit_event

    evidence = (await db.execute(select(Evidence).where(
        Evidence.id == evidence_id, Evidence.organization_id == organization_id))).scalar_one_or_none()
    if not evidence or evidence.deleted_at:
        raise NotFoundError("La evidencia no existe.", code="evidence_not_found")
    project = await get_visible_project(db, organization_id=organization_id, user=current_user,
                                        project_id=evidence.project_id)
    ensure_installation_open(project)
    evidence.deleted_at = datetime.now(tz.utc)
    await db.flush()
    reabierto = None
    if evidence.checklist_item_id:
        item = await db.get(ProjectChecklistItem, evidence.checklist_item_id)
        if item and item.requires_evidence and item.is_complete and not await _has_evidence(db, item.id):
            item.is_complete, item.completed_at, item.completed_by_user_id = False, None, None
            reabierto = item.label
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=current_user.id,
        action="evidence.deleted", entity_type="Evidence", entity_id=str(evidence.id),
        before_data={"project_id": str(evidence.project_id), "category": evidence.category,
                     "original_filename": evidence.original_filename},
        after_data={"checklist_item_reopened": reabierto},
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/attestation/technician-sign", response_model=AttestationResponse)
async def sign_as_technician(
    project_id: uuid.UUID, payload: SignatureCapture, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    attestation = await field_ops_service.technician_sign(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        project_id=project_id,
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
    return CustomerSignatureRequestResponse(status="sent", recipient_email=token.recipient_email, expires_at=token.expires_at)


@router.post("/projects/{project_id}/attestation/customer-sign", response_model=AttestationResponse)
async def sign_as_customer(
    project_id: uuid.UUID, payload: CustomerSignatureCapture, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("evidence.create")),
):
    await get_workable_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    attestation = await field_ops_service.customer_sign(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        project_id=project_id,
        customer_name=payload.customer_name,
        signature_base64=payload.signature_base64,
    )
    return AttestationResponse.model_validate(attestation)


@router.get("/projects/{project_id}/attestation", response_model=AttestationResponse)
async def get_attestation(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    result = await db.execute(select(Attestation).where(Attestation.project_id == project_id, Attestation.organization_id == organization_id))
    attestation = result.scalar_one_or_none()
    if not attestation:
        raise NotFoundError("Todavía no existe un acta iniciada para este proyecto.", code="attestation_not_found")
    response = AttestationResponse.model_validate(attestation)
    link = await field_ops_service.pending_signature_link(db, attestation.id)
    if link:
        response.customer_link_sent_to = link.recipient_email
        response.customer_link_expires_at = link.expires_at
    return response


@router.get("/attestations/{attestation_id}/pdf")
async def download_attestation_pdf(
    attestation_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("projects.read_all", "projects.read_assigned")),
):
    result = await db.execute(select(Attestation).where(Attestation.id == attestation_id, Attestation.organization_id == organization_id))
    attestation = result.scalar_one_or_none()
    if not attestation or not attestation.pdf_path:
        raise NotFoundError(
            "El PDF del acta todavía no existe. Deben estar las dos firmas.",
            code="attestation_pdf_not_found",
        )
    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=attestation.project_id)
    return FileResponse(str(absolute_path(attestation.pdf_path)), media_type="application/pdf", filename="acta-de-instalacion.pdf")


@router.get("/public/customer-signature", response_model=PublicSignatureResponse)
async def public_customer_signature_details(token: str, db: AsyncSession = Depends(get_db)):
    signature_token, attestation, project = await field_ops_service.get_public_signature_request(db, raw_token=token)
    return PublicSignatureResponse(
        project_title=project.title,
        customer_name=attestation.customer_name,
        expires_at=signature_token.expires_at,
        technician_signed=bool(attestation.technician_signed_at),
    )


@router.post("/public/customer-signature", response_model=AttestationResponse)
async def public_customer_signature(
    request: Request, payload: PublicCustomerSignatureCapture, token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    raw = payload.token or token
    if not raw:
        raise NotFoundError("El enlace no es válido o ya expiró.", code="public_signature_token_missing")
    return AttestationResponse.model_validate(
        await field_ops_service.public_customer_sign(
            db,
            raw_token=raw,
            customer_name=payload.customer_name,
            signature_base64=payload.signature_base64,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
