"""Rutas del vendedor (módulo 2, spec §3).

El tablero va en `/case-board` y no en `/cases/board`: el router de
expedientes se registra antes y tomaría "board" como un `case_id`."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.cases import intake
from app.modules.cases.models import VISIT_RESULTS
from app.modules.cases.router import _to_response
from app.modules.cases.schemas import CaseResponse
from app.modules.users.models import User
from app.shared.files.storage import absolute_path

router = APIRouter(tags=["cases-intake"])

_create = require_permission("cases.create")
_read = require_any_permission("cases.read_own", "cases.read_all")
_submit = require_permission("cases.submit")
_doc_review = require_permission("documents.review")
_doc_manage = require_permission("documents.manage")


class VisitIn(BaseModel):
    result: str
    address_street: str = Field(min_length=1, max_length=255)
    address_unit: str | None = Field(default=None, max_length=50)
    address_city: str | None = Field(default=None, max_length=120)
    address_state: str | None = Field(default=None, max_length=2)
    address_zip: str | None = Field(default=None, max_length=10)
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = Field(default=None, max_length=2000)
    program_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None


class VisitOut(BaseModel):
    outcome: str
    case: CaseResponse


class ProgramIn(BaseModel):
    program_id: uuid.UUID
    zone_id: uuid.UUID | None = None


class StepIn(BaseModel):
    answers: dict
    latitude: float | None = None
    longitude: float | None = None


class TermsIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    signature: str = Field(min_length=10)
    latitude: float | None = None
    longitude: float | None = None


@router.get("/visits/results")
async def visit_results(current_user: User = Depends(_create)) -> dict[str, str]:
    return VISIT_RESULTS


@router.post("/visits", response_model=VisitOut, status_code=201)
async def record_visit(payload: VisitIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_create)):
    case, que = await intake.record_visit(db, organization_id=organization_id, user=current_user,
                                          data=payload.model_dump())
    return {"outcome": que, "case": _to_response(case)}


@router.get("/cases/{case_id}/visits")
async def list_visits(case_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_read)) -> list[dict]:
    case = await intake._get_case(db, organization_id, case_id)
    intake._require_owner(current_user, case)
    return [{"id": str(v.id), "result": v.answers.get("result"), "label": VISIT_RESULTS.get(v.answers.get("result")),
             "notes": v.answers.get("notes"), "at": v.submitted_at.isoformat(), "latitude": v.latitude,
             "longitude": v.longitude} for v in await intake.list_visits(db, case)]


@router.put("/cases/{case_id}/program", response_model=CaseResponse)
async def set_program(case_id: uuid.UUID, payload: ProgramIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_create)):
    return _to_response(await intake.set_program(db, organization_id=organization_id, user=current_user,
                                                 case_id=case_id, program_id=payload.program_id,
                                                 zone_id=payload.zone_id))


@router.get("/cases/{case_id}/form")
async def get_form(case_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_read)) -> dict:
    """El formulario del expediente: definición, respuestas vigentes, lo que
    falta, archivos, términos y la aceptación si ya firmó."""
    case = await intake._get_case(db, organization_id, case_id)
    intake._require_owner(current_user, case)
    estado = await intake.form_state(db, user=current_user, case=case)
    return {"case": _to_response(case).model_dump(mode="json"), **estado}


@router.put("/cases/{case_id}/steps/{step_code}")
async def save_step(case_id: uuid.UUID, step_code: str, payload: StepIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_create)) -> dict:
    case = await intake.save_step(db, organization_id=organization_id, user=current_user, case_id=case_id,
                                  step_code=step_code, answers=payload.answers, latitude=payload.latitude,
                                  longitude=payload.longitude)
    return {"case": _to_response(case).model_dump(mode="json"),
            **await intake.form_state(db, user=current_user, case=case)}


@router.post("/cases/{case_id}/files", status_code=201)
async def upload_file(case_id: uuid.UUID, field_key: str = Form(...), file: UploadFile = File(...),
                      latitude: float | None = Form(None), longitude: float | None = Form(None),
                      captured_at: datetime | None = Form(None), db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_create)) -> dict:
    from app.shared.files.validation import read_limited

    data = await read_limited(file, intake.MAX_FILE_BYTES)
    f = await intake.upload_file(db, organization_id=organization_id, user=current_user, case_id=case_id,
                                 field_key=field_key, filename=file.filename, content_type=file.content_type,
                                 data=data, latitude=latitude, longitude=longitude, captured_at=captured_at)
    return {"id": str(f.id), "field_key": f.field_key, "original_filename": f.original_filename,
            "mime_type": f.mime_type, "watermarked": f.watermarked}


@router.get("/case-files/{file_id}")
async def download_file(file_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)):
    f = await intake.get_file(db, organization_id=organization_id, user=current_user, file_id=file_id)
    return FileResponse(str(absolute_path(f.file_path)), media_type=f.mime_type or "application/octet-stream")


@router.post("/cases/{case_id}/terms-acceptance", response_model=CaseResponse, status_code=201)
async def accept_terms(case_id: uuid.UUID, payload: TermsIn, request: Request, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_create)):
    return _to_response(await intake.accept_terms(
        db, organization_id=organization_id, user=current_user, case_id=case_id,
        customer_name=payload.customer_name, signature=payload.signature, latitude=payload.latitude,
        longitude=payload.longitude, ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))


@router.post("/cases/{case_id}/submit", response_model=CaseResponse)
async def submit(case_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 organization_id: uuid.UUID = Depends(get_organization_id),
                 current_user: User = Depends(_submit)):
    return _to_response(await intake.submit(db, organization_id=organization_id, user=current_user,
                                            case_id=case_id))


@router.get("/case-board")
async def board(include_early_closes: bool = False, mine: bool = False, db: AsyncSession = Depends(get_db),
                organization_id: uuid.UUID = Depends(get_organization_id),
                current_user: User = Depends(_read)) -> list[dict]:
    return await intake.board(db, organization_id=organization_id, user=current_user,
                              include_early_closes=include_early_closes, mine=mine)


@router.get("/cases/{case_id}/terms-acceptance/signature")
async def acceptance_signature(case_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_read)):
    """La imagen de la última firma del cliente, para mostrarla en el expediente."""
    from sqlalchemy import select

    from app.modules.cases.models import CaseTermsAcceptance
    from app.shared.errors import NotFoundError

    case = await intake._get_case(db, organization_id, case_id)
    intake._require_owner(current_user, case)
    aceptacion = (await db.execute(select(CaseTermsAcceptance).where(CaseTermsAcceptance.case_id == case.id)
                                   .order_by(CaseTermsAcceptance.accepted_at.desc()))).scalars().first()
    if aceptacion is None:
        raise NotFoundError("El cliente todavía no ha firmado.", code="signature_not_found")
    return FileResponse(str(absolute_path(aceptacion.signature_path)), media_type="image/png")


# ---------------------------------------------------------------------------
# Documentos del expediente (módulo 3)
# ---------------------------------------------------------------------------

class DocumentReviewIn(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/cases/{case_id}/documents")
async def case_documents(case_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_read)) -> list[dict]:
    from app.modules.cases import documents

    case = await intake._get_case(db, organization_id, case_id)
    intake._require_owner(current_user, case)
    return await documents.list_documents(db, case, current_user)


@router.post("/cases/{case_id}/documents", status_code=201)
async def upload_extra_document(case_id: uuid.UUID, label: str = Form(..., max_length=255),
                                file: UploadFile = File(...), latitude: float | None = Form(None),
                                longitude: float | None = Form(None), db: AsyncSession = Depends(get_db),
                                organization_id: uuid.UUID = Depends(get_organization_id),
                                current_user: User = Depends(_doc_manage)) -> dict:
    from app.modules.cases import documents
    from app.shared.files.validation import read_limited

    data = await read_limited(file, intake.MAX_FILE_BYTES)
    f = await documents.upload_extra(db, organization_id=organization_id, user=current_user, case_id=case_id,
                                     label=label, filename=file.filename, content_type=file.content_type,
                                     data=data, latitude=latitude, longitude=longitude)
    return {"id": str(f.id), "label": f.label, "review_status": f.review_status}


@router.post("/case-files/{file_id}/review")
async def review_document(file_id: uuid.UUID, payload: DocumentReviewIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_doc_review)) -> dict:
    from app.modules.cases import documents

    f = await documents.review(db, organization_id=organization_id, user=current_user, file_id=file_id,
                               status=payload.status, notes=payload.notes)
    return {"id": str(f.id), "review_status": f.review_status, "review_notes": f.review_notes}


@router.get("/documents/review-queue")
async def document_queue(db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_doc_review)) -> list[dict]:
    from app.modules.cases import documents

    return await documents.review_queue(db, organization_id=organization_id)
