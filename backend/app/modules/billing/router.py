import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
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
    InvoiceIssue,
    InvoiceLinesReplace,
    InvoicePaymentCreate,
    InvoicePreview,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceVoid,
    invoice_response,
)
from app.modules.field_ops.clock import org_today
from app.shared.errors import NotFoundError
from app.shared.files.storage import absolute_path, save_bytes
from app.modules.users.models import User

router = APIRouter(tags=["billing"])


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    response: Response,
    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
    status_filter: str | None = Query(None, alias="status"),
    project_id: uuid.UUID | None = None,
    kind: str | None = Query(None, description="rebate o particular"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    # El estado de pago se calcula (no es una columna), así que el filtro y la
    # paginación van en Python, sobre el resultado ya filtrado: X-Total-Count
    # cuenta lo filtrado, no el total crudo.
    invoices, hoy = await billing_service.list_invoices(
        db, organization_id=organization_id, status_filter=status_filter, project_id=project_id, kind=kind,
    )
    limit, offset = pagination
    response.headers["X-Total-Count"] = str(len(invoices))
    return [invoice_response(i, hoy) for i in invoices[offset : offset + limit]]


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    payload: InvoiceCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.create")),
):
    invoice = await billing_service.create_invoice(
        db, organization_id=organization_id, actor_id=current_user.id, data=payload.model_dump(),
    )
    return invoice_response(invoice, await org_today(db, organization_id))


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}.pdf"'})


@router.post("/invoices/preview")
async def preview_invoice_pdf(
    payload: InvoicePreview, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
):
    """El PDF de la factura que se emitiría. No guarda nada ni consume número."""
    from app.modules.billing.pdf import invoice_document, preview_invoice, render_invoice_pdf

    invoice, program, project = await preview_invoice(
        db, organization_id=organization_id, user=current_user, data=payload.model_dump(),
    )
    documento = await invoice_document(db, invoice, program=program, project=project)
    # Sin commit: lo que se haya sembrado al leer (perfil del programa) se
    # descarta al cerrar la sesión.
    return _pdf(render_invoice_pdf(documento), "preview")


@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
):
    from app.modules.billing.pdf import invoice_document, render_invoice_pdf

    invoice = await billing_service.get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    documento = await invoice_document(db, invoice)
    return _pdf(render_invoice_pdf(documento), invoice.invoice_number)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.read")),
):
    invoice = await billing_service.get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    return invoice_response(invoice, await org_today(db, organization_id))


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    invoice = await billing_service.get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    await db.commit()
    invoice = await billing_service.get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    return invoice_response(invoice, await org_today(db, organization_id))


@router.put("/invoices/{invoice_id}/lines", response_model=InvoiceResponse)
async def replace_invoice_lines(
    invoice_id: uuid.UUID, payload: InvoiceLinesReplace, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    """Ajusta las líneas de un borrador antes de emitirlo."""
    invoice = await billing_service.replace_draft_lines(
        db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id,
        lines=[l.model_dump() for l in payload.lines],
    )
    return invoice_response(invoice, await org_today(db, organization_id))


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: uuid.UUID, payload: InvoiceIssue, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.create")),
):
    invoice = await billing_service.issue_invoice(
        db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id,
        due_date=payload.due_date,
    )
    return invoice_response(invoice, await org_today(db, organization_id))


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice(
    invoice_id: uuid.UUID, payload: InvoiceVoid, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    """Anula una factura con motivo. Una emitida no se edita: se anula y se
    emite otra."""
    invoice = await billing_service.void_invoice(
        db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id, reason=payload.reason,
    )
    return invoice_response(invoice, await org_today(db, organization_id))


@router.post("/invoices/{invoice_id}/mark-sent", response_model=InvoiceResponse)
async def mark_invoice_sent(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    invoice = await billing_service.mark_sent(db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id)
    return invoice_response(invoice, await org_today(db, organization_id))


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceResponse, status_code=201)
async def record_invoice_payment(
    invoice_id: uuid.UUID, payload: InvoicePaymentCreate, db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.record_payment")),
):
    invoice = await billing_service.record_payment(
        db, organization_id=organization_id, actor_id=current_user.id, invoice_id=invoice_id, data=payload.model_dump(),
    )
    return invoice_response(invoice, await org_today(db, organization_id))


@router.post("/invoices/{invoice_id}/attachments", response_model=InvoiceAttachmentResponse, status_code=201)
async def upload_invoice_attachment(
    invoice_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("invoices.update")),
):
    invoice = await billing_service.get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)

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
        raise NotFoundError("El adjunto no existe.", code="attachment_not_found")
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
    invoices, hoy = await billing_service.list_invoices(db, organization_id=organization_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["invoice_number", "kind", "project_id", "funder_program", "amount", "paid_amount", "balance",
                     "status", "issue_date", "due_date"])
    for inv in invoices:
        writer.writerow([
            inv.invoice_number, inv.kind, str(inv.project_id or ""), _csv_safe(inv.funder_program or ""), inv.amount,
            inv.paid_amount, inv.balance, inv.payment_status_on(hoy), inv.issue_date or "", inv.due_date or "",
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
