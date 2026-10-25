import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, pagination_params
from app.shared.audit import record_audit_event
from app.modules.crm import privacy
from app.modules.crm import service as crm_service
from app.modules.cases.models import Case
from app.modules.cases.schemas import CaseResponse
from app.modules.crm.models import Activity, Customer, CustomerContact, CustomerStatus, FunderStatus
from app.modules.crm.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    Customer360Response,
    CustomerContactCreate,
    CustomerContactResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    DataConsentNotice,
    FunderStatusResponse,
)
from app.modules.users.models import User

router = APIRouter(tags=["crm"])

# Los datos personales del cliente: tocarlos exige su autorización.
PERSONAL_FIELDS = {"legal_name", "main_phone", "email", "billing_address"}


def _evidence(request: Request) -> tuple[str | None, str | None]:
    """IP y equipo desde donde se autorizó, para la constancia."""
    return (request.client.host if request.client else None, request.headers.get("user-agent"))


# --- Aviso de tratamiento de datos personales -------------------------------

@router.get("/privacy/consent-notice", response_model=DataConsentNotice, tags=["privacy"])
async def consent_notice() -> DataConsentNotice:
    """El aviso que se le muestra al cliente al capturar sus datos.

    Es público: la página de firma del cliente también lo muestra, y ahí no hay
    sesión."""
    return DataConsentNotice(**privacy.notice())


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
    payload: CustomerCreate, request: Request, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.create")),
):
    """Alta de cliente. Sin la autorización de tratamiento de datos no se
    guarda: es el momento en que se capturan sus datos personales."""
    privacy.require_consent(payload.data_consent_accepted)
    datos = payload.model_dump(exclude={"data_consent_accepted"})
    customer = Customer(organization_id=organization_id, **datos)
    db.add(customer)
    await db.flush()
    ip, equipo = _evidence(request)
    await privacy.record_consent(
        db, organization_id=organization_id, source=privacy.SOURCE_CUSTOMER_CREATE,
        customer_id=customer.id, customer_name=customer.legal_name,
        snapshot=privacy.contact_snapshot(name=customer.legal_name, phone=customer.main_phone,
                                          email=customer.email, address=customer.billing_address),
        captured_by_user_id=current_user.id, ip_address=ip, user_agent=equipo,
    )
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=current_user.id,
        action="customer.consent_recorded", entity_type="Customer", entity_id=str(customer.id),
        after_data={"source": privacy.SOURCE_CUSTOMER_CREATE, "version": privacy.DOCUMENT_VERSION},
    )
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
    customer_id: uuid.UUID, payload: CustomerUpdate, request: Request, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.update")),
):

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("El cliente no existe.", code="customer_not_found")
    cambios = payload.model_dump(exclude_unset=True, exclude={"data_consent_accepted"})
    # Cambiar notas o etiquetas no captura datos personales; corregir el nombre,
    # el teléfono, el correo o la dirección sí, y ahí se vuelve a pedir la
    # autorización (queda una constancia nueva, no se pisa la anterior).
    personales = sorted(PERSONAL_FIELDS.intersection(cambios))
    if personales:
        privacy.require_consent(payload.data_consent_accepted)
    for field, value in cambios.items():
        setattr(customer, field, value)
    if personales:
        ip, equipo = _evidence(request)
        await privacy.record_consent(
            db, organization_id=organization_id, source=privacy.SOURCE_CUSTOMER_UPDATE,
            customer_id=customer.id, customer_name=customer.legal_name,
            snapshot=privacy.contact_snapshot(name=customer.legal_name, phone=customer.main_phone,
                                              email=customer.email, address=customer.billing_address),
            captured_by_user_id=current_user.id, ip_address=ip, user_agent=equipo,
        )
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=current_user.id,
        action="customer.updated", entity_type="Customer", entity_id=str(customer.id),
        after_data=cambios,
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
    response: Response, pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("programs.read")),
):
    limit, offset = pagination
    return await paginate(db, select(FunderStatus).where(FunderStatus.organization_id == organization_id)
                          .order_by(FunderStatus.sort_order, FunderStatus.id),
                          limit=limit, offset=offset, response=response)


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


