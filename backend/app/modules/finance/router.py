"""Rutas de gastos de campo, proveedores y pagos, conciliación, rentabilidad y reportes."""
import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.finance import expenses as exp
from app.modules.finance import payables as ap
from app.modules.finance import profitability, reconciliation, reports
from app.modules.finance.models import (
    COST_CATEGORIES,
    EXPENSE_CATEGORIES,
    EXPENSE_PAYMENT,
    EXPENSE_STATUSES,
    INVOICE_STATUSES,
    PAYMENT_METHODS,
    SUPPLIER_DOC_KINDS,
    SUPPLIER_KINDS,
    BankStatement,
    BankStatementLine,
    Supplier,
    SupplierDocument,
    SupplierPayment,
)
from app.modules.users.models import User
from app.shared.errors import InvalidInputError, NotFoundError
from app.shared.files.storage import absolute_path
from app.shared.files.validation import read_limited
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["finance"])

_exp_any = require_any_permission("expenses.create_own", "expenses.read_all", "expenses.approve")
_exp_own = require_permission("expenses.create_own")
_exp_all = require_any_permission("expenses.read_all", "expenses.approve")
_exp_approve = require_permission("expenses.approve")
_ap_read = require_any_permission("suppliers.manage", "payables.manage", "payables.approve")
_sup_manage = require_any_permission("suppliers.manage", "payables.approve")
_ap_manage = require_permission("payables.manage")
_ap_approve_any = require_any_permission("payables.approve", "payables.manage")
_ap_approve = require_permission("payables.approve")
_export = require_permission("accounting.export")
_recon = require_permission("reconciliation.manage")
_profit = require_permission("profitability.read")
_reports = require_permission("reports.view")
_reports_export = require_permission("reports.export")


def _file(path: str | None, mime: str | None):
    if not path:
        raise NotFoundError("No hay archivo.", code="file_not_found")
    return FileResponse(str(absolute_path(path)), media_type=mime or "application/octet-stream")


# ===========================================================================
# Gastos de campo
# ===========================================================================

class ExpenseIn(BaseModel):
    expense_date: date
    category: str
    amount: str = Field(max_length=20)
    description: str = Field(min_length=3, max_length=500)
    payment_method: str = "own_money"
    project_id: uuid.UUID | None = None


@router.get("/expenses/catalogs")
async def expense_catalogs(current_user: User = Depends(_exp_any)) -> dict:
    return {"categories": EXPENSE_CATEGORIES, "payment_methods": EXPENSE_PAYMENT, "statuses": EXPENSE_STATUSES}


@router.get("/expenses/mine")
async def my_expenses(response: Response, status: str | None = None, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      pag: tuple[int, int] = Depends(pagination_params),
                      current_user: User = Depends(_exp_own)) -> list[dict]:
    items = await paginate(db, exp.list_stmt(organization_id, user=current_user, mine=True, status=status),
                           limit=pag[0], offset=pag[1], response=response)
    return await exp.out(db, items)


@router.get("/expenses")
async def all_expenses(response: Response, status: str | None = None, user_id: uuid.UUID | None = None,
                       project_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
                       db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_exp_all)) -> list[dict]:
    stmt = exp.list_stmt(organization_id, mine=False, status=status, user_id=user_id, project_id=project_id,
                         date_from=date_from, date_to=date_to)
    return await exp.out(db, await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response))


@router.post("/expenses", status_code=201)
async def create_expense(data: str = Form(...), receipt: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_exp_own)) -> dict:
    datos = ExpenseIn.model_validate_json(data).model_dump()
    contenido = await read_limited(receipt, exp.MAX_RECEIPT_BYTES)
    e = await exp.create(db, organization_id=organization_id, user=current_user, data=datos,
                         receipt=(contenido, receipt.filename, receipt.content_type))
    return (await exp.out(db, [e]))[0]


@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: uuid.UUID, payload: ExpenseIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_exp_own)) -> dict:
    e = await exp.update(db, organization_id=organization_id, user=current_user, expense_id=expense_id,
                         data=payload.model_dump())
    return (await exp.out(db, [e]))[0]


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_exp_own)):
    await exp.delete(db, organization_id=organization_id, user=current_user, expense_id=expense_id)
    return Response(status_code=204)


class ReviewIn(BaseModel):
    approve: bool
    notes: str | None = Field(default=None, max_length=1000)


@router.post("/expenses/{expense_id}/review")
async def review_expense(expense_id: uuid.UUID, payload: ReviewIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_exp_approve)) -> dict:
    e = await exp.review(db, organization_id=organization_id, user=current_user, expense_id=expense_id,
                         approve=payload.approve, notes=payload.notes)
    return (await exp.out(db, [e]))[0]


class ReimburseIn(BaseModel):
    paid_on: date
    reference: str | None = Field(default=None, max_length=120)


@router.post("/expenses/{expense_id}/reimburse")
async def reimburse_expense(expense_id: uuid.UUID, payload: ReimburseIn, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(require_any_permission("payables.manage", "expenses.approve"))) -> dict:
    e = await exp.reimburse(db, organization_id=organization_id, user=current_user, expense_id=expense_id,
                            paid_on=payload.paid_on, reference=payload.reference)
    return (await exp.out(db, [e]))[0]


@router.get("/expenses/{expense_id}/receipt")
async def expense_receipt(expense_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_exp_any)):
    e = await exp.get_expense(db, organization_id, expense_id)
    if not exp.can_see(current_user, e):
        raise NotFoundError("El gasto no existe.", code="expense_not_found")
    return _file(e.receipt_path, e.receipt_mime)


# ===========================================================================
# Proveedores y cuentas por pagar
# ===========================================================================

@router.get("/payables/catalogs")
async def payables_catalogs(current_user: User = Depends(_ap_read)) -> dict:
    return {"supplier_kinds": SUPPLIER_KINDS, "payment_methods": PAYMENT_METHODS, "cost_categories": COST_CATEGORIES,
            "document_kinds": SUPPLIER_DOC_KINDS, "invoice_statuses": INVOICE_STATUSES}


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=40)
    kinds: list[str] = []
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    states: list[str] = []
    payment_terms_days: int = 30
    payment_method: str | None = None
    bank_details: str | None = Field(default=None, max_length=2000)
    license_number: str | None = Field(default=None, max_length=80)
    license_expires_on: date | None = None
    insurance_expires_on: date | None = None
    w9_on_file: bool = False
    notes: str | None = Field(default=None, max_length=4000)
    active: bool = True


@router.get("/payables/suppliers")
async def list_suppliers(response: Response, q: str | None = None, active: bool | None = None,
                         db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                         pag: tuple[int, int] = Depends(pagination_params),
                         current_user: User = Depends(_ap_read)) -> list[dict]:
    stmt = select(Supplier).where(Supplier.organization_id == organization_id)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(Supplier.name.ilike(patron), Supplier.legal_name.ilike(patron),
                              Supplier.contact_name.ilike(patron)))
    if active is not None:
        stmt = stmt.where(Supplier.active.is_(active))
    items = await paginate(db, stmt.order_by(Supplier.name), limit=pag[0], offset=pag[1], response=response)
    saldos = await ap.supplier_balances(db, organization_id)
    return [ap.supplier_out(s, current_user, saldos.get(s.id, ap.ZERO)) for s in items]


@router.post("/payables/suppliers", status_code=201)
async def create_supplier(payload: SupplierIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_sup_manage)) -> dict:
    s = await ap.save_supplier(db, organization_id=organization_id, user=current_user, data=payload.model_dump())
    return ap.supplier_out(s, current_user)


@router.get("/payables/suppliers/{supplier_id}")
async def get_supplier(supplier_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_ap_read)) -> dict:
    s = await ap.get_supplier(db, organization_id, supplier_id)
    docs = (await db.execute(select(SupplierDocument).where(SupplierDocument.supplier_id == s.id)
                             .order_by(SupplierDocument.created_at.desc()))).scalars().all()
    saldos = await ap.supplier_balances(db, organization_id)
    return {**ap.supplier_out(s, current_user, saldos.get(s.id, ap.ZERO)), "documents": [
        {"id": str(d.id), "kind": d.kind, "kind_label": SUPPLIER_DOC_KINDS.get(d.kind), "filename": d.original_filename,
         "expires_on": d.expires_on.isoformat() if d.expires_on else None,
         "uploaded_at": d.created_at.isoformat() if d.created_at else None} for d in docs]}


@router.put("/payables/suppliers/{supplier_id}")
async def update_supplier(supplier_id: uuid.UUID, payload: SupplierIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_sup_manage)) -> dict:
    datos = payload.model_dump()
    if datos.get("bank_details") == "•••":
        datos.pop("bank_details")  # quien no ve el dato no lo borra al guardar
    s = await ap.save_supplier(db, organization_id=organization_id, user=current_user, data=datos,
                               supplier_id=supplier_id)
    return ap.supplier_out(s, current_user)


class ImportIn(BaseModel):
    text: str = Field(min_length=5, max_length=2_000_000)


@router.post("/payables/suppliers/import")
async def import_suppliers(payload: ImportIn, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_sup_manage)) -> dict:
    return await ap.import_suppliers_csv(db, organization_id=organization_id, user=current_user, text=payload.text)


@router.post("/payables/suppliers/{supplier_id}/documents", status_code=201)
async def upload_supplier_document(supplier_id: uuid.UUID, kind: str = Form(...), expires_on: date | None = Form(None),
                                   file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                                   organization_id: uuid.UUID = Depends(get_organization_id),
                                   current_user: User = Depends(_sup_manage)) -> dict:
    data = await read_limited(file, ap.MAX_FILE_BYTES)
    d = await ap.add_supplier_document(db, organization_id=organization_id, user=current_user, supplier_id=supplier_id,
                                       kind=kind, expires_on=expires_on, data=data, filename=file.filename,
                                       mime=file.content_type)
    return {"id": str(d.id), "kind": d.kind}


@router.get("/payables/supplier-documents/{document_id}/file")
async def supplier_document_file(document_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                 organization_id: uuid.UUID = Depends(get_organization_id),
                                 current_user: User = Depends(_ap_read)):
    d = await db.get(SupplierDocument, document_id)
    if d is None or d.organization_id != organization_id:
        raise NotFoundError("El documento no existe.", code="document_not_found")
    return _file(d.file_path, d.mime_type)


class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    category: str = "materials"
    quantity: str = "1"
    unit_cost: str
    project_id: uuid.UUID | None = None


class InvoiceIn(BaseModel):
    supplier_id: uuid.UUID
    number: str = Field(min_length=1, max_length=80)
    invoice_date: date
    due_date: date | None = None
    lines: list[LineIn] = Field(default=[], max_length=200)
    total: str | None = None
    description: str | None = Field(default=None, max_length=255)
    category: str | None = None
    project_id: uuid.UUID | None = None
    tax: str | None = None
    shipping: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    paid_now: bool = False
    paid_method: str | None = None
    paid_reference: str | None = Field(default=None, max_length=120)


@router.get("/payables/invoices")
async def list_invoices(response: Response, status: str | None = None, supplier_id: uuid.UUID | None = None,
                        overdue: bool = False, due_within_days: int | None = Query(None, ge=0, le=365),
                        project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pag: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_ap_read)) -> list[dict]:
    from datetime import timedelta

    hoy = await ap._today(db, organization_id)
    stmt = ap.invoices_stmt(organization_id, status=status, supplier_id=supplier_id, overdue=overdue, today=hoy,
                            due_before=hoy + timedelta(days=due_within_days) if due_within_days is not None else None,
                            project_id=project_id)
    items = await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response)
    return await ap.invoice_out(db, items, organization_id)


@router.post("/payables/invoices", status_code=201)
async def create_invoice(data: str = Form(...), file: UploadFile | None = File(None), db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_ap_manage)) -> dict:
    datos = InvoiceIn.model_validate_json(data).model_dump()
    adjunto = None
    if file is not None and file.filename:
        adjunto = (await read_limited(file, ap.MAX_FILE_BYTES), file.filename, file.content_type)
    inv = await ap.create_invoice(db, organization_id=organization_id, user=current_user, data=datos, file=adjunto)
    return (await ap.invoice_out(db, [inv], organization_id))[0]


@router.get("/payables/invoices/{invoice_id}")
async def get_invoice(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_ap_read)) -> dict:
    inv = await ap.get_invoice(db, organization_id, invoice_id)
    return (await ap.invoice_out(db, [inv], organization_id))[0]


class NotesIn(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


@router.post("/payables/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: uuid.UUID, payload: NotesIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_ap_approve_any)) -> dict:
    inv = await ap.approve_invoice(db, organization_id=organization_id, user=current_user, invoice_id=invoice_id,
                                   notes=payload.notes)
    return (await ap.invoice_out(db, [inv], organization_id))[0]


class ScheduleIn(BaseModel):
    scheduled_payment_date: date | None


@router.post("/payables/invoices/{invoice_id}/schedule")
async def schedule_invoice(invoice_id: uuid.UUID, payload: ScheduleIn, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_ap_approve)) -> dict:
    inv = await ap.schedule_invoice(db, organization_id=organization_id, user=current_user, invoice_id=invoice_id,
                                    scheduled=payload.scheduled_payment_date)
    return (await ap.invoice_out(db, [inv], organization_id))[0]


class VoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/payables/invoices/{invoice_id}/void")
async def void_invoice(invoice_id: uuid.UUID, payload: VoidIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_ap_approve_any)) -> dict:
    inv = await ap.void_invoice(db, organization_id=organization_id, user=current_user, invoice_id=invoice_id,
                                reason=payload.reason)
    return (await ap.invoice_out(db, [inv], organization_id))[0]


@router.get("/payables/invoices/{invoice_id}/file")
async def invoice_file(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_ap_read)):
    inv = await ap.get_invoice(db, organization_id, invoice_id)
    return _file(inv.file_path, inv.file_mime)


class AllocationIn(BaseModel):
    invoice_id: uuid.UUID
    amount: str


class PaymentIn(BaseModel):
    supplier_id: uuid.UUID
    paid_on: date
    amount: str
    method: str
    reference: str | None = Field(default=None, max_length=120)
    bank_account: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    allocations: list[AllocationIn] = Field(min_length=1, max_length=100)


def _payment_out(p: SupplierPayment, nombres: dict) -> dict:
    from app.modules.billing.money import to_money

    return {"id": str(p.id), "supplier_id": str(p.supplier_id), "supplier_name": nombres.get(p.supplier_id),
            "paid_on": p.paid_on.isoformat(), "amount": str(to_money(p.amount)), "method": p.method,
            "method_label": PAYMENT_METHODS.get(p.method), "reference": p.reference, "bank_account": p.bank_account,
            "notes": p.notes, "has_file": bool(p.file_path),
            "allocations": [{"invoice_id": str(a.invoice_id), "amount": str(to_money(a.amount))} for a in p.allocations]}


@router.get("/payables/payments")
async def list_payments(response: Response, supplier_id: uuid.UUID | None = None, date_from: date | None = None,
                        date_to: date | None = None, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pag: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_ap_read)) -> list[dict]:
    stmt = select(SupplierPayment).where(SupplierPayment.organization_id == organization_id)
    if supplier_id:
        stmt = stmt.where(SupplierPayment.supplier_id == supplier_id)
    if date_from:
        stmt = stmt.where(SupplierPayment.paid_on >= date_from)
    if date_to:
        stmt = stmt.where(SupplierPayment.paid_on <= date_to)
    items = await paginate(db, stmt.order_by(SupplierPayment.paid_on.desc(), SupplierPayment.created_at.desc()),
                           limit=pag[0], offset=pag[1], response=response)
    nombres = {s.id: s.name for s in (await db.execute(select(Supplier).where(
        Supplier.id.in_({p.supplier_id for p in items})))).scalars().all()} if items else {}
    return [_payment_out(p, nombres) for p in items]


@router.post("/payables/payments", status_code=201)
async def record_payment(data: str = Form(...), file: UploadFile | None = File(None), db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_ap_manage)) -> dict:
    datos = PaymentIn.model_validate_json(data).model_dump()
    adjunto = None
    if file is not None and file.filename:
        adjunto = (await read_limited(file, ap.MAX_FILE_BYTES), file.filename, file.content_type)
    p = await ap.record_payment(db, organization_id=organization_id, user=current_user, data=datos, file=adjunto)
    s = await ap.get_supplier(db, organization_id, p.supplier_id)
    return _payment_out(p, {s.id: s.name})


@router.get("/payables/payments/{payment_id}/file")
async def payment_file(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_ap_read)):
    p = await db.get(SupplierPayment, payment_id)
    if p is None or p.organization_id != organization_id:
        raise NotFoundError("El pago no existe.", code="payment_not_found")
    return _file(p.file_path, p.file_mime)


@router.get("/payables/aging")
async def payables_aging(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_ap_read)) -> dict:
    return await ap.aging(db, organization_id=organization_id)


@router.get("/payables/export.csv")
async def payables_export(kind: str = Query("invoices", pattern="^(invoices|payments)$"), date_from: date | None = None,
                          date_to: date | None = None, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_export)):
    texto = await ap.export_csv(db, organization_id=organization_id, kind=kind, date_from=date_from, date_to=date_to)
    return Response(content=texto, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="proveedores-{kind}.csv"'})


class FinanceSettingsIn(BaseModel):
    two_approval_threshold: str
    due_alert_days: int = Field(ge=1, le=60)
    document_alert_days: int = Field(ge=1, le=120)
    max_expense_amount: str


def _settings_out(s) -> dict:
    from app.modules.billing.money import to_money

    return {"two_approval_threshold": str(to_money(s.two_approval_threshold)), "due_alert_days": s.due_alert_days,
            "document_alert_days": s.document_alert_days, "max_expense_amount": str(to_money(s.max_expense_amount))}


@router.get("/finance/settings")
async def get_finance_settings(db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_ap_read)) -> dict:
    s = await exp.settings_of(db, organization_id)
    await db.commit()
    return _settings_out(s)


@router.put("/finance/settings")
async def put_finance_settings(payload: FinanceSettingsIn, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_ap_approve)) -> dict:
    from app.modules.billing.money import to_money
    from app.shared.audit import record_audit_event

    s = await exp.settings_of(db, organization_id)
    umbral, tope = to_money(payload.two_approval_threshold), to_money(payload.max_expense_amount)
    if umbral <= 0 or tope <= 0:
        raise InvalidInputError("Los montos deben ser mayores que cero.", code="invalid_amount")
    s.two_approval_threshold, s.max_expense_amount = umbral, tope
    s.due_alert_days, s.document_alert_days = payload.due_alert_days, payload.document_alert_days
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id,
                             action="finance.settings_updated", entity_type="finance_settings",
                             after_data=_settings_out(s))
    await db.commit()
    return _settings_out(s)


# ===========================================================================
# Rentabilidad
# ===========================================================================

@router.get("/finance/profitability")
async def profitability_report(date_from: date | None = None, date_to: date | None = None,
                               program_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None,
                               db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_profit)) -> dict:
    return await profitability.report(db, organization_id=organization_id, date_from=date_from, date_to=date_to,
                                      program_id=program_id, project_id=project_id)


# ===========================================================================
# Conciliación bancaria
# ===========================================================================

@router.post("/reconciliation/statements", status_code=201)
async def import_statement(account_label: str = Form("Cuenta principal", max_length=120), file: UploadFile = File(...),
                           db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_recon)) -> dict:
    data = await read_limited(file, 5 * 1024 * 1024)
    try:
        texto = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = data.decode("latin-1")
    return await reconciliation.import_statement(db, organization_id=organization_id, user=current_user,
                                                 account_label=account_label, filename=file.filename, text=texto)


@router.get("/reconciliation/statements")
async def list_statements(response: Response, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          pag: tuple[int, int] = Depends(pagination_params),
                          current_user: User = Depends(_recon)) -> list[dict]:
    stmt = select(BankStatement).where(BankStatement.organization_id == organization_id).order_by(
        BankStatement.created_at.desc())
    items = await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response)
    return [{"id": str(s.id), "account_label": s.account_label, "filename": s.original_filename,
             "period_start": s.period_start.isoformat() if s.period_start else None,
             "period_end": s.period_end.isoformat() if s.period_end else None,
             "imported_at": s.created_at.isoformat() if s.created_at else None} for s in items]


@router.get("/reconciliation/lines")
async def list_lines(response: Response, status: str | None = None, statement_id: uuid.UUID | None = None,
                     db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_recon)) -> list[dict]:
    stmt = select(BankStatementLine).where(BankStatementLine.organization_id == organization_id)
    if status:
        stmt = stmt.where(BankStatementLine.status == status)
    if statement_id:
        stmt = stmt.where(BankStatementLine.statement_id == statement_id)
    items = await paginate(db, stmt.order_by(BankStatementLine.line_date.desc(), BankStatementLine.id),
                           limit=pag[0], offset=pag[1], response=response)
    return [reconciliation.line_out(l) for l in items]


@router.get("/reconciliation/summary")
async def reconciliation_summary(db: AsyncSession = Depends(get_db),
                                 organization_id: uuid.UUID = Depends(get_organization_id),
                                 current_user: User = Depends(_recon)) -> dict:
    return await reconciliation.summary(db, organization_id)


@router.get("/reconciliation/lines/{line_id}/candidates")
async def line_candidates(line_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_recon)) -> dict:
    l = await reconciliation.get_line(db, organization_id, line_id)
    return {"items": await reconciliation.candidates(db, organization_id, l)}


class MatchIn(BaseModel):
    matched_type: str = Field(pattern="^(invoice_payment|supplier_payment|expense)$")
    matched_id: uuid.UUID


@router.post("/reconciliation/lines/{line_id}/match")
async def match_line(line_id: uuid.UUID, payload: MatchIn, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_recon)) -> dict:
    return reconciliation.line_out(await reconciliation.match_line(
        db, organization_id=organization_id, user=current_user, line_id=line_id, matched_type=payload.matched_type,
        matched_id=payload.matched_id))


class IgnoreIn(BaseModel):
    notes: str = Field(min_length=1, max_length=500)


@router.post("/reconciliation/lines/{line_id}/ignore")
async def ignore_line(line_id: uuid.UUID, payload: IgnoreIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_recon)) -> dict:
    return reconciliation.line_out(await reconciliation.ignore_line(
        db, organization_id=organization_id, user=current_user, line_id=line_id, notes=payload.notes))


@router.post("/reconciliation/lines/{line_id}/unmatch")
async def unmatch_line(line_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_recon)) -> dict:
    return reconciliation.line_out(await reconciliation.unmatch_line(
        db, organization_id=organization_id, user=current_user, line_id=line_id))


# ===========================================================================
# Reportes
# ===========================================================================

@router.get("/reports/{kind}")
async def get_report(kind: str, date_from: date | None = None, date_to: date | None = None,
                     db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_reports)) -> dict:
    if kind not in reports.REPORTS:
        raise NotFoundError("Ese reporte no existe.", code="report_not_found")
    return await reports.REPORTS[kind](db, organization_id=organization_id, date_from=date_from, date_to=date_to)


@router.get("/reports/{kind}/csv")
async def export_report(kind: str, date_from: date | None = None, date_to: date | None = None,
                        db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_reports_export)):
    if kind not in reports.REPORTS:
        raise NotFoundError("Ese reporte no existe.", code="report_not_found")
    rep = await reports.REPORTS[kind](db, organization_id=organization_id, date_from=date_from, date_to=date_to)
    return Response(content=reports.to_csv(rep), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="reporte-{kind}.csv"'})
