import csv
import io
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import (
    Activity,
    Customer,
    CustomerContact,
    FunderStatus,
    Lead,
    LeadStatus,
    Opportunity,
    PipelineStage,
    Quote,
    QuoteLineItem,
)
from app.shared.audit import record_audit_event
from app.shared.normalize import normalize_address, normalize_email, normalize_phone


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

async def find_possible_duplicate_leads(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str | None, phone: str | None,
    street: str | None, unit: str | None, city: str | None, zip_code: str | None,
) -> list[tuple[Lead, list[str]]]:
    """Duplicate detection by normalized email/phone/address (spec 7.2). Never
    auto-merges — only flags candidates for the agent to review."""
    email_norm = normalize_email(email)
    phone_norm = normalize_phone(phone)
    address_norm = normalize_address(street, unit, city, zip_code)

    if not any([email_norm, phone_norm, address_norm]):
        return []

    conditions = []
    if email_norm:
        conditions.append(Lead.email_normalized == email_norm)
    if phone_norm:
        conditions.append(Lead.phone_normalized == phone_norm)
    if not conditions:
        conditions = [Lead.id.is_(None)]  # no-op, address-only match handled below

    result = await db.execute(
        select(Lead).where(Lead.organization_id == organization_id, or_(*conditions))
    )
    candidates = result.scalars().all()

    matches: list[tuple[Lead, list[str]]] = []
    for lead in candidates:
        matched_on = []
        if email_norm and lead.email_normalized == email_norm:
            matched_on.append("email")
        if phone_norm and lead.phone_normalized == phone_norm:
            matched_on.append("phone")
        if matched_on:
            matches.append((lead, matched_on))

    # Address-based match (separate pass since it's not indexed the same way).
    if address_norm:
        result = await db.execute(select(Lead).where(Lead.organization_id == organization_id))
        for lead in result.scalars().all():
            lead_addr_norm = normalize_address(lead.address_street, lead.address_unit, lead.address_city, lead.address_zip)
            if lead_addr_norm and lead_addr_norm == address_norm:
                existing = next((m for m in matches if m[0].id == lead.id), None)
                if existing:
                    existing[1].append("address")
                else:
                    matches.append((lead, ["address"]))

    return matches


# Column-mapping keys the importer understands; caller supplies which CSV
# header maps to which key (spec 18 item 7: migration scoped explicitly,
# no hardcoded single spreadsheet format since new batches keep arriving
# in slightly different shapes from different mobile-home-park sheets).
IMPORT_FIELD_KEYS = [
    "full_name", "phone", "email", "address_street", "address_unit",
    "address_city", "address_state", "address_zip", "benefit_type",
    "funder_program", "source", "notes",
]


async def import_leads_from_csv(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID,
    csv_text: str, column_mapping: dict[str, str],
) -> dict:
    """Imports leads from a CSV export of the existing spreadsheets.
    column_mapping maps our field keys (IMPORT_FIELD_KEYS) to the CSV's
    header names, e.g. {"full_name": "NOMBRE", "phone": "TELEFONO"}.
    Never overwrites or auto-merges — duplicates are skipped and reported."""
    reader = csv.DictReader(io.StringIO(csv_text))
    total = 0
    created = 0
    skipped = 0
    errors: list[str] = []
    seen_in_batch: set[tuple[str | None, str | None]] = set()

    for row_num, row in enumerate(reader, start=2):  # header is row 1
        total += 1
        try:
            data = {}
            for field_key, header in column_mapping.items():
                if field_key not in IMPORT_FIELD_KEYS:
                    continue
                value = (row.get(header) or "").strip()
                if value:
                    data[field_key] = value

            if not data.get("full_name"):
                errors.append(f"Row {row_num}: missing name, skipped.")
                skipped += 1
                continue

            email_norm = normalize_email(data.get("email"))
            phone_norm = normalize_phone(data.get("phone"))
            batch_key = (email_norm, phone_norm)
            if batch_key != (None, None) and batch_key in seen_in_batch:
                skipped += 1
                continue

            duplicates = await find_possible_duplicate_leads(
                db, organization_id=organization_id, email=data.get("email"), phone=data.get("phone"),
                street=data.get("address_street"), unit=data.get("address_unit"),
                city=data.get("address_city"), zip_code=data.get("address_zip"),
            )
            if duplicates:
                skipped += 1
                continue

            lead = Lead(
                organization_id=organization_id,
                email_normalized=email_norm,
                phone_normalized=phone_norm,
                **data,
            )
            db.add(lead)
            seen_in_batch.add(batch_key)
            created += 1
        except Exception as exc:  # keep importing the rest of the file
            errors.append(f"Row {row_num}: {exc}")
            skipped += 1

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="leads.imported", entity_type="Lead",
        after_data={"total_rows": total, "created": created, "skipped": skipped},
    )
    await db.commit()
    return {"total_rows": total, "created": created, "skipped_duplicates": skipped, "errors": errors[:50]}


async def create_lead(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, data: dict) -> Lead:
    lead = Lead(
        organization_id=organization_id,
        email_normalized=normalize_email(data.get("email")),
        phone_normalized=normalize_phone(data.get("phone")),
        **data,
    )
    db.add(lead)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="leads.created", entity_type="Lead", after_data={"full_name": data.get("full_name")},
    )
    await db.commit()
    await db.refresh(lead)
    return lead


async def convert_lead(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, lead_id: uuid.UUID,
    opportunity_title: str | None, opportunity_stage_code: str,
) -> tuple[Customer, CustomerContact, Opportunity]:
    result = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    if lead.status == LeadStatus.converted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lead has already been converted.")

    customer = Customer(
        organization_id=organization_id,
        legal_name=lead.company_name or lead.full_name,
        main_phone=lead.phone,
        email=lead.email,
        billing_address=lead.address_street,
    )
    db.add(customer)
    await db.flush()

    contact = CustomerContact(
        customer_id=customer.id, full_name=lead.full_name, email=lead.email, phone=lead.phone, is_primary=True,
    )
    db.add(contact)

    stage_result = await db.execute(
        select(PipelineStage).where(PipelineStage.organization_id == organization_id, PipelineStage.code == opportunity_stage_code)
    )
    stage = stage_result.scalar_one_or_none()
    if not stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown pipeline stage: {opportunity_stage_code}")

    await db.flush()
    opportunity = Opportunity(
        organization_id=organization_id,
        customer_id=customer.id,
        primary_contact_id=contact.id,
        title=opportunity_title or f"{lead.full_name} — {lead.benefit_type or 'oportunidad'}",
        stage_id=stage.id,
        owner_user_id=lead.assigned_owner_user_id,
        benefit_type=lead.benefit_type,
        funder_program=lead.funder_program,
        address_street=lead.address_street,
        address_unit=lead.address_unit,
        address_city=lead.address_city,
        address_state=lead.address_state,
        address_zip=lead.address_zip,
    )
    db.add(opportunity)
    await db.flush()

    lead.status = LeadStatus.converted
    lead.converted_customer_id = customer.id
    lead.converted_opportunity_id = opportunity.id

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="leads.converted", entity_type="Lead", entity_id=str(lead.id),
        after_data={"customer_id": str(customer.id), "opportunity_id": str(opportunity.id)},
    )
    await db.commit()
    await db.refresh(customer)
    await db.refresh(contact)
    await db.refresh(opportunity)
    return customer, contact, opportunity


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

async def get_stage_by_code(db: AsyncSession, *, organization_id: uuid.UUID, code: str) -> PipelineStage:
    result = await db.execute(
        select(PipelineStage).where(PipelineStage.organization_id == organization_id, PipelineStage.code == code)
    )
    stage = result.scalar_one_or_none()
    if not stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown pipeline stage: {code}")
    return stage


async def get_funder_status_by_code(db: AsyncSession, *, organization_id: uuid.UUID, code: str | None) -> "FunderStatus | None":
    if not code:
        return None
    result = await db.execute(
        select(FunderStatus).where(FunderStatus.organization_id == organization_id, FunderStatus.code == code)
    )
    funder_status = result.scalar_one_or_none()
    if not funder_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown funder status: {code}")
    return funder_status


async def change_opportunity_stage(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, opportunity_id: uuid.UUID,
    stage_code: str, loss_reason: str | None,
) -> Opportunity:
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.organization_id == organization_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found.")

    new_stage = await get_stage_by_code(db, organization_id=organization_id, code=stage_code)
    if new_stage.is_lost and not loss_reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="loss_reason is required when moving to a lost stage.")

    before_stage_id = str(opportunity.stage_id)
    opportunity.stage_id = new_stage.id
    if loss_reason:
        opportunity.loss_reason = loss_reason

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="opportunities.stage_changed", entity_type="Opportunity", entity_id=str(opportunity.id),
        before_data={"stage_id": before_stage_id}, after_data={"stage_id": str(new_stage.id), "stage_code": stage_code},
    )
    await db.commit()
    await db.refresh(opportunity)
    return opportunity


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

async def next_quote_number(db: AsyncSession, *, organization_id: uuid.UUID) -> str:
    result = await db.execute(select(Quote).where(Quote.organization_id == organization_id))
    count = len(result.scalars().all())
    return f"COT-{count + 1:04d}"


def _compute_line_total(item) -> float:
    return round(float(item.quantity) * float(item.unit_price) - float(item.discount) + float(item.tax_value), 2)


async def create_quote(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, data: dict, line_items: list[dict]) -> Quote:
    quote_number = await next_quote_number(db, organization_id=organization_id)
    quote = Quote(organization_id=organization_id, quote_number=quote_number, **data)
    db.add(quote)
    await db.flush()

    total = 0.0
    for idx, item_data in enumerate(line_items):
        item = QuoteLineItem(quote_id=quote.id, sort_order=idx, **item_data)
        item.line_total = _compute_line_total(item)
        total += item.line_total
        db.add(item)
    quote.total_amount = round(total, 2)

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="quotes.created", entity_type="Quote", entity_id=str(quote.id),
        after_data={"quote_number": quote_number, "total_amount": quote.total_amount},
    )
    await db.commit()
    await db.refresh(quote)
    return quote
