import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Invoice, InvoicePayment, InvoiceStatus
from app.modules.field_ops.models import Project
from app.shared.audit import record_audit_event

# Attachment scope (Phase 5 hardening — the upload endpoint had no MIME/size
# limits when it shipped in Phase 4; unrestricted upload is an OWASP Top 10
# item). Payment/submission proof documents are photos, scans, or PDFs.
ALLOWED_ATTACHMENT_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
    "application/pdf",
}
MAX_ATTACHMENT_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_ATTACHMENTS_PER_INVOICE = 20


def validate_attachment(*, content_type: str | None, size_bytes: int, existing_count: int) -> None:
    if content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only photos, scans, or PDF documents are accepted as invoice attachments.",
        )
    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment exceeds the 15MB size limit.")
    if existing_count >= MAX_ATTACHMENTS_PER_INVOICE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invoice already has the maximum number of attachments.")


async def next_invoice_number(db: AsyncSession, *, organization_id: uuid.UUID) -> str:
    result = await db.execute(select(Invoice).where(Invoice.organization_id == organization_id))
    count = len(result.scalars().all())
    return f"FAC-{count + 1:04d}"


async def create_invoice(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, data: dict) -> Invoice:
    project_result = await db.execute(
        select(Project).where(Project.id == data["project_id"], Project.organization_id == organization_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    invoice_number = await next_invoice_number(db, organization_id=organization_id)
    invoice = Invoice(
        organization_id=organization_id, customer_id=project.customer_id, invoice_number=invoice_number,
        status=InvoiceStatus.pending, **data,
    )
    db.add(invoice)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.created", entity_type="Invoice",
        after_data={"invoice_number": invoice_number, "amount": float(data["amount"])},
    )
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def _get_invoice_or_404(db: AsyncSession, *, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return invoice


def _refresh_overdue_status(invoice: Invoice) -> None:
    """Applies the "overdue" transition. Two callers keep this in sync: the
    read path below (get_invoice/list_invoices — so it's never stale for
    someone looking at the API right now) and the Celery beat sweep
    (sweep_overdue_invoices — so it's also caught even if nobody opens the
    Invoices page that day, per spec 17 phase 4)."""
    if invoice.status in (InvoiceStatus.pending, InvoiceStatus.sent):
        if invoice.due_date and invoice.due_date < date.today() and invoice.balance > 0:
            invoice.status = InvoiceStatus.overdue


async def get_invoice(db: AsyncSession, *, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = await _get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    before = invoice.status
    _refresh_overdue_status(invoice)
    if invoice.status != before:
        await db.commit()
        await db.refresh(invoice)
    return invoice


async def list_invoices(
    db: AsyncSession, *, organization_id: uuid.UUID, status_filter: str | None = None, project_id: uuid.UUID | None = None,
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.organization_id == organization_id).order_by(Invoice.created_at.desc())
    if project_id:
        stmt = stmt.where(Invoice.project_id == project_id)
    result = await db.execute(stmt)
    invoices = result.scalars().all()
    changed = False
    for invoice in invoices:
        before = invoice.status
        _refresh_overdue_status(invoice)
        changed = changed or invoice.status != before
    if changed:
        await db.commit()
    if status_filter:
        invoices = [i for i in invoices if i.status.value == status_filter]
    return invoices


async def mark_sent(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = await _get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.status != InvoiceStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a pending invoice can be marked as sent.")
    invoice.status = InvoiceStatus.sent
    invoice.sent_at = datetime.now(timezone.utc)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.sent", entity_type="Invoice", entity_id=str(invoice.id),
    )
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def record_payment(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID, data: dict,
) -> Invoice:
    invoice = await _get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.status == InvoiceStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot record a payment on a cancelled invoice.")

    payment = InvoicePayment(invoice_id=invoice.id, **data)
    db.add(payment)
    await db.flush()

    if invoice.balance - float(data["amount"]) <= 0:
        invoice.status = InvoiceStatus.paid
        invoice.paid_at = datetime.now(timezone.utc)
    elif invoice.status == InvoiceStatus.pending:
        invoice.status = InvoiceStatus.sent  # a partial payment implies the invoice reached the funder

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.payment_recorded", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"amount": float(data["amount"])},
    )
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def finance_dashboard(db: AsyncSession, *, organization_id: uuid.UUID) -> dict:
    from datetime import timedelta

    invoices = await list_invoices(db, organization_id=organization_id)
    total_invoiced = round(sum(float(i.amount) for i in invoices), 2)
    total_paid = round(sum(i.paid_amount for i in invoices), 2)
    total_outstanding = round(sum(i.balance for i in invoices if i.status != InvoiceStatus.cancelled), 2)
    overdue = [i for i in invoices if i.status == InvoiceStatus.overdue]
    total_overdue = round(sum(i.balance for i in overdue), 2)
    soon_cutoff = date.today() + timedelta(days=7)
    due_soon = [
        i for i in invoices
        if i.status in (InvoiceStatus.pending, InvoiceStatus.sent) and i.due_date and date.today() <= i.due_date <= soon_cutoff
    ]

    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "invoice_count": len(invoices),
        "overdue_count": len(overdue),
        "due_soon_count": len(due_soon),
    }


async def sweep_overdue_invoices(db: AsyncSession) -> int:
    """Runs the same overdue check as _refresh_overdue_status, but across
    every organization's pending/sent invoices in one pass — this is what
    the Celery beat task (app/workers/tasks.py) calls daily, so an invoice
    surfaces as overdue in reports/dashboards even if nobody happens to
    open the Invoices page that day. Not organization-scoped by design:
    it's a maintenance sweep, not a request made on any one org's behalf,
    and it only ever flips a status flag — it never reads or returns
    invoice content across tenants. Returns how many invoices were flipped
    to overdue, purely for the task's log line."""
    stmt = select(Invoice).where(Invoice.status.in_([InvoiceStatus.pending, InvoiceStatus.sent]))
    result = await db.execute(stmt)
    invoices = result.scalars().all()
    changed = 0
    for invoice in invoices:
        before = invoice.status
        _refresh_overdue_status(invoice)
        if invoice.status != before:
            changed += 1
    if changed:
        await db.commit()
    return changed
