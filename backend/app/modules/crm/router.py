import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.pagination import paginate, pagination_params
from app.shared.audit import record_audit_event
from app.modules.crm import service as crm_service
from app.modules.cases.models import Case
from app.modules.cases.schemas import CaseResponse
from app.modules.crm.models import Activity, Application, ApplicationDocument, Customer, CustomerContact, CustomerStatus, FunderStatus, ProgramFormField
from app.modules.crm.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    ApplicationCreate,
    ApplicationCustomerSignature,
    ApplicationDocumentResponse,
    ApplicationResponse,
    ApplicationUpdate,
    Customer360Response,
    CustomerContactCreate,
    CustomerContactResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    FunderStatusResponse,
    ProgramFormFieldResponse,
)
from app.modules.users.models import User

router = APIRouter(tags=["crm"])


# --- Customers -----------------------------------------------------------

@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.read")),
    status_filter: CustomerStatus | None = Query(None, alias="status"),
    q: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Customer).where(Customer.organization_id == organization_id).order_by(Customer.legal_name)
    if status_filter:
        stmt = stmt.where(Customer.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Customer.legal_name.ilike(like)) | (Customer.email.ilike(like)) | (Customer.main_phone.ilike(like))
        )
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(
    payload: CustomerCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.create")),
):
    customer = Customer(organization_id=organization_id, **payload.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.read")),
):

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("El cliente no existe.", code="customer_not_found")
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID, payload: CustomerUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.update")),
):

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("El cliente no existe.", code="customer_not_found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=current_user.id,
        action="customer.updated", entity_type="Customer", entity_id=str(customer.id),
        after_data=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    await db.refresh(customer)
    return customer


@router.post("/customers/{customer_id}/contacts", response_model=CustomerContactResponse, status_code=201)
async def add_customer_contact(
    customer_id: uuid.UUID, payload: CustomerContactCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("contacts.manage")),
):

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    if not result.scalar_one_or_none():
        raise NotFoundError("El cliente no existe.", code="customer_not_found")
    contact = CustomerContact(customer_id=customer_id, **payload.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


# --- Program applications ---------------------------------------------------

@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Application).where(Application.organization_id == organization_id).order_by(Application.created_at.desc())
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    if q:
        stmt = stmt.where(Application.program_code.ilike(f"%{q}%"))
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)

@router.get("/program-form-fields", response_model=list[ProgramFormFieldResponse])
async def list_program_form_fields(
    program_code: str, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.create", "cases.read_all")),
):
    result = await db.execute(
        select(ProgramFormField).where(
            ProgramFormField.organization_id == organization_id,
            ProgramFormField.program_code == program_code,
            ProgramFormField.active.is_(True),
        ).order_by(ProgramFormField.sort_order, ProgramFormField.created_at)
    )
    return result.scalars().all()


@router.post("/applications", response_model=ApplicationResponse, status_code=201)
async def create_application(
    payload: ApplicationCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("cases.create")),
):
    if not payload.customer_id:
        raise InvalidInputError(
            "La aplicación debe estar asociada a un cliente.",
            code="application_without_owner",
        )
    application = Application(
        organization_id=organization_id, salesperson_user_id=current_user.id,
        terms_accepted_at=datetime.now(timezone.utc) if payload.terms_accepted else None,
        **payload.model_dump(),
    )
    db.add(application)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id, action="application.created", entity_type="Application", entity_id=str(application.id))
    await db.commit()
    await db.refresh(application)
    return application


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
):
    application = (await db.execute(select(Application).where(Application.id == application_id, Application.organization_id == organization_id))).scalar_one_or_none()
    if not application:
        raise NotFoundError("La aplicación no existe.", code="application_not_found")
    return application


@router.get("/applications/{application_id}/documents", response_model=list[ApplicationDocumentResponse])
async def list_application_documents(
    application_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
):
    exists = (await db.execute(select(Application).where(Application.id == application_id, Application.organization_id == organization_id))).scalar_one_or_none()
    if not exists:
        raise NotFoundError("La aplicación no existe.", code="application_not_found")
    result = await db.execute(select(ApplicationDocument).where(ApplicationDocument.application_id == application_id, ApplicationDocument.organization_id == organization_id).order_by(ApplicationDocument.created_at.desc()))
    return result.scalars().all()


@router.post("/applications/{application_id}/documents", response_model=ApplicationDocumentResponse, status_code=201)
async def upload_application_document(
    application_id: uuid.UUID, file: UploadFile = File(...), field_key: str = Form(...),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("documents.manage")),
):
    from app.shared.files.storage import save_bytes
    application = (await db.execute(select(Application).where(Application.id == application_id, Application.organization_id == organization_id))).scalar_one_or_none()
    if not application:
        raise NotFoundError("La aplicación no existe.", code="application_not_found")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise InvalidInputError("El archivo no puede superar 15 MB.", code="file_too_large")
    relative_path = save_bytes(organization_id=organization_id, subfolder=f"applications/{application_id}", filename=file.filename or "document", data=data)
    document = ApplicationDocument(application_id=application_id, organization_id=organization_id, field_key=field_key, file_path=relative_path, original_filename=file.filename, mime_type=file.content_type, size_bytes=len(data), uploaded_by_user_id=current_user.id)
    db.add(document)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id, action="application.document_uploaded", entity_type="Application", entity_id=str(application_id), after_data={"field_key": field_key, "filename": file.filename})
    await db.commit()
    await db.refresh(document)
    return document


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: uuid.UUID, payload: ApplicationUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.review", "cases.approve")),
):
    application = (await db.execute(select(Application).where(Application.id == application_id, Application.organization_id == organization_id))).scalar_one_or_none()
    if not application:
        raise NotFoundError("La aplicación no existe.", code="application_not_found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("terms_accepted") is True and not application.terms_accepted:
        application.terms_accepted_at = datetime.now(timezone.utc)
    for field, value in changes.items():
        setattr(application, field, value)
    if application.status in {"ready_to_submit", "submitted"}:
        application.submitted_at = application.submitted_at or datetime.now(timezone.utc)
    if application.status in {"approved", "rejected", "correction_requested"}:
        application.reviewed_by_user_id = current_user.id
        application.reviewed_at = datetime.now(timezone.utc)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id, action="application.updated", entity_type="Application", entity_id=str(application.id), after_data=changes)
    await db.commit()
    await db.refresh(application)
    return application


@router.post("/applications/{application_id}/customer-sign", response_model=ApplicationResponse)
async def sign_application_with_customer(
    application_id: uuid.UUID, payload: ApplicationCustomerSignature, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(require_permission("cases.submit")),
):
    from app.modules.field_ops.pdf import decode_signature_png
    from app.shared.files.storage import save_bytes
    application = (await db.execute(select(Application).where(Application.id == application_id, Application.organization_id == organization_id))).scalar_one_or_none()
    if not application:
        raise NotFoundError("La aplicación no existe.", code="application_not_found")
    if not application.terms_accepted:
        raise InvalidInputError(
            "El cliente debe aceptar los Términos y Condiciones antes de firmar.",
            code="terms_not_accepted",
        )
    answers = dict(application.answers or {})
    answers["customer_name"] = payload.customer_name.strip()
    application.answers = answers
    application.customer_signature_path = save_bytes(organization_id=organization_id, subfolder=f"applications/{application.id}", filename="customer_signature.png", data=decode_signature_png(payload.signature_base64))
    now = datetime.now(timezone.utc)
    application.customer_signed_at = now
    application.salesperson_user_id = current_user.id
    application.salesperson_signed_at = now
    application.status = "pending_review"
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id, action="application.signed", entity_type="Application", entity_id=str(application.id))
    await db.commit()
    await db.refresh(application)
    return application


@router.get("/customers/{customer_id}/timeline", response_model=Customer360Response)
async def customer_timeline(
    customer_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.read")),
):
    """Ficha del cliente con todos sus expedientes y su actividad.

    Antes mostraba oportunidades y cotizaciones; el expediente las reemplaza.
    Es la vista que usa el vendedor cuando vuelve al parque y necesita saber si
    ya habló con alguien de esa casa."""

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("El cliente no existe.", code="customer_not_found")

    cases = (
        await db.execute(
            select(Case)
            .where(Case.customer_id == customer_id, Case.organization_id == organization_id)
            .order_by(Case.created_at.desc())
        )
    ).scalars().all()
    activities = (
        await db.execute(select(Activity).where(Activity.customer_id == customer_id).order_by(Activity.created_at.desc()))
    ).scalars().all()

    return Customer360Response(
        customer=customer,
        cases=[CaseResponse.model_validate(c, from_attributes=True) for c in cases],
        activities=activities,
    )


# --- Funder statuses -------------------------------------------------------

@router.get("/funder-statuses", response_model=list[FunderStatusResponse])
async def list_funder_statuses(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("programs.read")),
):
    result = await db.execute(
        select(FunderStatus).where(FunderStatus.organization_id == organization_id).order_by(FunderStatus.sort_order)
    )
    return result.scalars().all()


# --- Activities -----------------------------------------------------------

@router.get("/activities", response_model=list[ActivityResponse])
async def list_activities(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("activities.manage")),
    owner_user_id: uuid.UUID | None = None,
    overdue_only: bool = False,
    pagination: tuple[int, int] = Depends(pagination_params),
):
    from datetime import datetime, timezone

    stmt = select(Activity).where(Activity.organization_id == organization_id)
    if owner_user_id:
        stmt = stmt.where(Activity.owner_user_id == owner_user_id)
    if overdue_only:
        stmt = stmt.where(Activity.due_date < datetime.now(timezone.utc), Activity.completed_at.is_(None))
    stmt = stmt.order_by(Activity.due_date.asc().nulls_last())
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/activities", response_model=ActivityResponse, status_code=201)
async def create_activity(
    payload: ActivityCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("activities.manage")),
):
    activity = Activity(organization_id=organization_id, **payload.model_dump())
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.patch("/activities/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: uuid.UUID, payload: ActivityUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("activities.manage")),
):

    result = await db.execute(select(Activity).where(Activity.id == activity_id, Activity.organization_id == organization_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise NotFoundError("La actividad no existe.", code="activity_not_found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    await db.commit()
    await db.refresh(activity)
    return activity


