import json
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.shared.pagination import paginate, pagination_params
from app.modules.crm import service as crm_service
from app.modules.crm.models import Activity, Customer, CustomerContact, FunderStatus, Lead, Opportunity, PipelineStage, Quote
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
    FunderStatusResponse,
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadCreateResult,
    LeadDuplicateWarning,
    LeadResponse,
    LeadUpdate,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityStageChange,
    OpportunityUpdate,
    ImportSummary,
    PipelineStageResponse,
    QuoteCreate,
    QuoteResponse,
)
from app.modules.users.models import User

router = APIRouter(tags=["crm"])


# --- Leads -------------------------------------------------------------

@router.get("/leads", response_model=list[LeadResponse])
async def list_leads(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
    status_filter: str | None = Query(None, alias="status"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Lead).where(Lead.organization_id == organization_id).order_by(Lead.created_at.desc())
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/leads", response_model=LeadCreateResult, status_code=201)
async def create_lead(
    payload: LeadCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
):
    duplicates = await crm_service.find_possible_duplicate_leads(
        db, organization_id=organization_id, email=payload.email, phone=payload.phone,
        street=payload.address_street, unit=payload.address_unit, city=payload.address_city, zip_code=payload.address_zip,
    )
    lead = await crm_service.create_lead(
        db, organization_id=organization_id, actor_id=current_user.id, data=payload.model_dump(),
    )
    return LeadCreateResult(
        lead=lead,
        possible_duplicates=[
            LeadDuplicateWarning(lead_id=d.id, full_name=d.full_name, matched_on=matched) for d, matched in duplicates
        ],
    )


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id))
    lead = result.scalar_one_or_none()
    if not lead:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID, payload: LeadUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
):
    from fastapi import HTTPException

    result = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.post("/leads/{lead_id}/convert", response_model=LeadConvertResponse)
async def convert_lead(
    lead_id: uuid.UUID, payload: LeadConvertRequest, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
):
    customer, contact, opportunity = await crm_service.convert_lead(
        db, organization_id=organization_id, actor_id=current_user.id, lead_id=lead_id,
        opportunity_title=payload.opportunity_title, opportunity_stage_code=payload.opportunity_stage_code,
    )
    return LeadConvertResponse(customer_id=customer.id, contact_id=contact.id, opportunity_id=opportunity.id)


@router.post("/leads/import", response_model=ImportSummary)
async def import_leads(
    file: UploadFile = File(...),
    column_mapping: str = Form(..., description='JSON object, e.g. {"full_name":"NOMBRE","phone":"TELEFONO"}'),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("leads.manage")),
):
    """CSV importer for the existing spreadsheets (spec 18 item 7). Column
    mapping is caller-supplied since the source sheets vary by mobile-home
    park / funder program rather than sharing one fixed layout."""
    from fastapi import HTTPException

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="column_mapping must be valid JSON.")

    raw_bytes = await file.read()
    try:
        csv_text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = raw_bytes.decode("latin-1")

    summary = await crm_service.import_leads_from_csv(
        db, organization_id=organization_id, actor_id=current_user.id, csv_text=csv_text, column_mapping=mapping,
    )
    return ImportSummary(**summary)


# --- Customers -----------------------------------------------------------

@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.read")),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Customer).where(Customer.organization_id == organization_id).order_by(Customer.legal_name)
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
    from fastapi import HTTPException

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID, payload: CustomerUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("customers.update")),
):
    from fastapi import HTTPException

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.post("/customers/{customer_id}/contacts", response_model=CustomerContactResponse, status_code=201)
async def add_customer_contact(
    customer_id: uuid.UUID, payload: CustomerContactCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("contacts.manage")),
):
    from fastapi import HTTPException

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found.")
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
    """Customer 360 view (spec 7.3): opportunities, activities, quotes for this customer."""
    from fastapi import HTTPException

    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    opportunities = (
        await db.execute(select(Opportunity).where(Opportunity.customer_id == customer_id).order_by(Opportunity.created_at.desc()))
    ).scalars().all()
    activities = (
        await db.execute(select(Activity).where(Activity.customer_id == customer_id).order_by(Activity.created_at.desc()))
    ).scalars().all()
    quotes = (
        await db.execute(select(Quote).where(Quote.customer_id == customer_id).order_by(Quote.created_at.desc()))
    ).scalars().all()

    return Customer360Response(customer=customer, opportunities=opportunities, activities=activities, quotes=quotes)


# --- Pipeline stages -----------------------------------------------------

@router.get("/pipeline-stages", response_model=list[PipelineStageResponse])
async def list_pipeline_stages(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
):
    result = await db.execute(
        select(PipelineStage).where(PipelineStage.organization_id == organization_id).order_by(PipelineStage.sort_order)
    )
    return result.scalars().all()


# --- Funder statuses -------------------------------------------------------

@router.get("/funder-statuses", response_model=list[FunderStatusResponse])
async def list_funder_statuses(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
):
    result = await db.execute(
        select(FunderStatus).where(FunderStatus.organization_id == organization_id).order_by(FunderStatus.sort_order)
    )
    return result.scalars().all()


# --- Opportunities ---------------------------------------------------------

@router.get("/opportunities", response_model=list[OpportunityResponse])
async def list_opportunities(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Opportunity).where(Opportunity.organization_id == organization_id).order_by(Opportunity.created_at.desc())
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/opportunities", response_model=OpportunityResponse, status_code=201)
async def create_opportunity(
    payload: OpportunityCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
):
    data = payload.model_dump(exclude={"stage_code", "funder_status_code"})
    stage = await crm_service.get_stage_by_code(db, organization_id=organization_id, code=payload.stage_code)
    funder_status = await crm_service.get_funder_status_by_code(
        db, organization_id=organization_id, code=payload.funder_status_code
    )
    opportunity = Opportunity(
        organization_id=organization_id, stage_id=stage.id,
        funder_status_id=funder_status.id if funder_status else None, **data,
    )
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)
    return opportunity


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: uuid.UUID, payload: OpportunityUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
):
    from fastapi import HTTPException

    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.organization_id == organization_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    updates = payload.model_dump(exclude_unset=True)
    if "funder_status_code" in updates:
        code = updates.pop("funder_status_code")
        funder_status = await crm_service.get_funder_status_by_code(db, organization_id=organization_id, code=code)
        opportunity.funder_status_id = funder_status.id if funder_status else None
    for field, value in updates.items():
        setattr(opportunity, field, value)
    await db.commit()
    await db.refresh(opportunity)
    return opportunity


# Stages that automatically spin up field work (confirmed with Mateo, Sept
# 2026): as soon as an Opportunity reaches one of these, a Project is
# created (if one doesn't already exist for it) with the default checklist
# applied, ready to assign a technician.
AUTO_PROJECT_STAGE_CODES = {"approved", "installation"}


@router.post("/opportunities/{opportunity_id}/change-stage", response_model=OpportunityResponse)
async def change_opportunity_stage(
    opportunity_id: uuid.UUID, payload: OpportunityStageChange, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("opportunities.manage")),
):
    opportunity = await crm_service.change_opportunity_stage(
        db, organization_id=organization_id, actor_id=current_user.id, opportunity_id=opportunity_id,
        stage_code=payload.stage_code, loss_reason=payload.loss_reason,
    )

    if payload.stage_code in AUTO_PROJECT_STAGE_CODES:
        from app.modules.field_ops.service import auto_create_project_from_opportunity

        await auto_create_project_from_opportunity(
            db, organization_id=organization_id, actor_id=current_user.id, opportunity=opportunity,
        )

    return opportunity


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
    from fastapi import HTTPException

    result = await db.execute(select(Activity).where(Activity.id == activity_id, Activity.organization_id == organization_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    await db.commit()
    await db.refresh(activity)
    return activity


# --- Quotes ---------------------------------------------------------------

@router.get("/quotes", response_model=list[QuoteResponse])
async def list_quotes(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("quotes.manage")),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(Quote).where(Quote.organization_id == organization_id).order_by(Quote.created_at.desc())
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)


@router.post("/quotes", response_model=QuoteResponse, status_code=201)
async def create_quote(
    payload: QuoteCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("quotes.manage")),
):
    data = payload.model_dump(exclude={"line_items"})
    line_items = [li for li in payload.model_dump()["line_items"]]
    quote = await crm_service.create_quote(
        db, organization_id=organization_id, actor_id=current_user.id, data=data, line_items=line_items,
    )
    return quote
