import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.shared.pagination import paginate, pagination_params
from app.modules.billing import service as billing_service
from app.modules.billing.models import Invoice, InvoiceAttachment
from app.modules.billing.schemas import (
    FinanceDashboardResponse,
    InvoiceAttachmentResponse,
    InvoiceCreate,
    InvoicePaymentCreate,
    InvoiceResponse,
    InvoiceUpdate,
)
from app.modules.field_ops.storage import absolute_path, save_bytes
from app.modules.users.models import User

router = APIRouter(tags=["billing"])


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
    status_filter: str | None = Query(None, alias="status"),
    project_id: uuid.UUID | None = None,
    pagination: tuple[int, int] = Depends(pagination_params),
):
    # list_invoices applies the lazy overdue-status refresh and the status
    # filter in Python (status is computed, not a plain column, so it can't
    # be pushed into SQL) — page in Python too, over the already-filtered
    # result, so X-Total-Count reflects the filtered count, not the raw one.
    invoices = await billing_service.list_invoices(db, organization_id=organization_id, status_filter=status_filter, project_id=project_id)
    limit, offset = pagination
    response.headers["X-Total-Count"] = str(len(invoices))
    return invoices[offset : offset + limit]


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    payload: InvoiceCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.create")),
):
    return await billing_service.create_invoice(
        db, organization_id=organization_id, actor_id=current_user.id, data=payload.model_dump(),
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
):
    return await billing_service.get_invoice(db, organization_id=organization_id, invoice_id=invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/mark-sent", response_model=InvoiceResponse)
async def mark_invoice_sent(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    return await billing_service.mark_sent(db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id)


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceResponse, status_code=201)
async def record_invoice_payment(
    invoice_id: uuid.UUID, payload: InvoicePaymentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.record_payment")),
):
    return await billing_service.record_payment(
        db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id, data=payload.model_dump(),
    )


@router.post("/invoices/{invoice_id}/attachments", response_model=InvoiceAttachmentResponse, status_code=201)
async def upload_invoice_attachment(
    invoice_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    raw_bytes = await file.read()
    billing_service.validate_attachment(
        content_type=file.content_type, size_bytes=len(raw_bytes), existing_count=len(invoice.attachments)
    )
    relative_path = save_bytes(
        organization_id=organization_id, subfolder=f"invoices/{invoice_id}/attachments",
        filename=file.filename or "attachment", data=raw_bytes,
    )
    attachment = InvoiceAttachment(
        invoice_id=invoice_id, file_path=relative_path, original_filename=file.filename,
        mime_type=file.content_type, size_bytes=len(raw_bytes), uploaded_by_user_id=current_user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/invoice-attachments/{attachment_id}/file")
async def download_invoice_attachment(
    attachment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
):
    result = await db.execute(
        select(InvoiceAttachment).join(Invoice, Invoice.id == InvoiceAttachment.invoice_id).where(
            InvoiceAttachment.id == attachment_id, Invoice.organization_id == organization_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return FileResponse(str(absolute_path(attachment.file_path)), media_type=attachment.mime_type or "application/octet-stream")


def _csv_safe(value: str) -> str:
    """Prefixes a cell that starts with =, +, -, or @ with a leading tab
    (invisible in Excel/Sheets but breaks formula evaluation) — CSV/Excel
    formula injection, OWASP/CWE-1236. funder_program is free text an org
    admin can set, so it's untrusted enough to guard even though it's
    internal data, not raw user upload."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "\t" + value
    return value


@router.get("/invoices-export.csv")
async def export_invoices_csv(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.export")),
):
    invoices = await billing_service.list_invoices(db, organization_id=organization_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["invoice_number", "project_id", "funder_program", "amount", "paid_amount", "balance", "status", "issue_date", "due_date"])
    for inv in invoices:
        writer.writerow([
            inv.invoice_number, str(inv.project_id), _csv_safe(inv.funder_program or ""), inv.amount, inv.paid_amount,
            inv.balance, inv.status.value, inv.issue_date or "", inv.due_date or "",
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@router.get("/finance/dashboard", response_model=FinanceDashboardResponse)
async def get_finance_dashboard(
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dashboards.finance")),
):
    return await billing_service.finance_dashboard(db, organization_id=organization_id)
