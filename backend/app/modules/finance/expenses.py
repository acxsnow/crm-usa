"""Gastos de campo: el técnico o vendedor registra, Contabilidad revisa."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.billing.money import ZERO, to_money
from app.modules.finance.models import EXPENSE_CATEGORIES, EXPENSE_PAYMENT, Expense, FinanceSettings
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

RECEIPT_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def settings_of(db: AsyncSession, organization_id) -> FinanceSettings:
    fila = (await db.execute(select(FinanceSettings).where(
        FinanceSettings.organization_id == organization_id))).scalar_one_or_none()
    if fila is None:
        fila = FinanceSettings(organization_id=organization_id, two_approval_threshold=Decimal("10000"),
                               due_alert_days=5, document_alert_days=30, max_expense_amount=Decimal("5000"))
        db.add(fila)
        await db.flush()
    return fila


async def get_expense(db, organization_id, expense_id) -> Expense:
    e = await db.get(Expense, expense_id)
    if e is None or e.organization_id != organization_id:
        raise NotFoundError("El gasto no existe.", code="expense_not_found")
    return e


def can_see(user, e: Expense) -> bool:
    return e.user_id == user.id or "expenses.read_all" in get_effective_permissions(user)


async def _check_project(db, organization_id, user, project_id) -> None:
    if project_id is None:
        return
    from app.modules.field_ops.access import get_visible_project

    # Solo un proyecto que la persona ve (el técnico, los suyos): 404 si no.
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)


async def validate_fields(db, organization_id, *, amount, category, payment_method, expense_date) -> Decimal:
    if category not in EXPENSE_CATEGORIES:
        raise InvalidInputError("Categoría de gasto desconocida.", code="invalid_expense_category")
    if payment_method not in EXPENSE_PAYMENT:
        raise InvalidInputError("Forma de pago desconocida.", code="invalid_expense_payment")
    monto = to_money(amount)
    tope = to_money((await settings_of(db, organization_id)).max_expense_amount)
    if monto <= ZERO:
        raise InvalidInputError("El monto debe ser mayor que cero.", code="invalid_amount")
    if monto > tope:
        raise InvalidInputError(f"Un gasto no puede pasar de {tope} USD; si es mayor, es una compra a proveedor.",
                                code="expense_over_limit")
    from app.modules.field_ops.clock import org_today

    if expense_date > await org_today(db, organization_id):
        raise InvalidInputError("La fecha del gasto no puede ser futura.", code="expense_future_date")
    return monto


async def create(db: AsyncSession, *, organization_id, user, data: dict, receipt: tuple | None) -> Expense:
    from app.shared.files.storage import save_bytes
    from app.shared.files.validation import check_type

    monto = await validate_fields(db, organization_id, amount=data["amount"], category=data["category"],
                                  payment_method=data["payment_method"], expense_date=data["expense_date"])
    await _check_project(db, organization_id, user, data.get("project_id"))
    if receipt is None:
        raise InvalidInputError("Sube la foto o el PDF del recibo.", code="receipt_required")
    contenido, nombre, mime = receipt
    mime = check_type(contenido, mime, RECEIPT_MIME)
    e = Expense(organization_id=organization_id, user_id=user.id, project_id=data.get("project_id"),
                expense_date=data["expense_date"], category=data["category"], amount=monto,
                description=data["description"].strip(), payment_method=data["payment_method"], status="submitted")
    db.add(e)
    await db.flush()
    e.receipt_path = save_bytes(organization_id=organization_id, subfolder=f"expenses/{e.id}",
                                filename=nombre or "recibo", data=contenido)
    e.receipt_mime = mime
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="expenses.created",
                             entity_type="expense", entity_id=str(e.id),
                             after_data={"amount": str(monto), "category": e.category})
    await db.commit()
    await db.refresh(e)
    domain_events.emit("expense.submitted", {"expense_id": str(e.id), "organization_id": str(organization_id)})
    return e


async def update(db, *, organization_id, user, expense_id, data: dict) -> Expense:
    e = await get_expense(db, organization_id, expense_id)
    if e.user_id != user.id:
        raise NotFoundError("El gasto no existe.", code="expense_not_found")
    if e.status != "submitted":
        raise ConflictError("Solo se corrige un gasto que todavía no se ha revisado.", code="expense_locked")
    e.amount = await validate_fields(db, organization_id, amount=data["amount"], category=data["category"],
                                     payment_method=data["payment_method"], expense_date=data["expense_date"])
    await _check_project(db, organization_id, user, data.get("project_id"))
    e.category, e.payment_method, e.expense_date = data["category"], data["payment_method"], data["expense_date"]
    e.description, e.project_id = data["description"].strip(), data.get("project_id")
    await db.commit()
    await db.refresh(e)
    return e


async def delete(db, *, organization_id, user, expense_id) -> None:
    e = await get_expense(db, organization_id, expense_id)
    if e.user_id != user.id:
        raise NotFoundError("El gasto no existe.", code="expense_not_found")
    if e.status != "submitted":
        raise ConflictError("Un gasto revisado no se borra.", code="expense_locked")
    await db.delete(e)
    await db.commit()


async def review(db, *, organization_id, user, expense_id, approve: bool, notes: str | None) -> Expense:
    e = await get_expense(db, organization_id, expense_id)
    if e.user_id == user.id:
        raise ForbiddenError("Nadie aprueba sus propios gastos.", code="own_expense")
    if e.status != "submitted":
        raise ConflictError("Ese gasto ya se revisó.", code="expense_already_reviewed")
    nota = (notes or "").strip() or None
    if not approve and not nota:
        raise InvalidInputError("Explica por qué se rechaza: quien lo registró lo verá.", code="review_notes_required")
    e.status = "approved" if approve else "rejected"
    e.reviewed_by_user_id, e.reviewed_at, e.review_notes = user.id, _now(), nota
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action=f"expenses.{e.status}", entity_type="expense", entity_id=str(e.id),
                             after_data={"notes": nota})
    await db.commit()
    await db.refresh(e)
    domain_events.emit("expense.reviewed", {"expense_id": str(e.id), "organization_id": str(organization_id),
                                            "status": e.status})
    return e


async def reimburse(db, *, organization_id, user, expense_id, paid_on: date, reference: str | None) -> Expense:
    e = await get_expense(db, organization_id, expense_id)
    if e.status != "approved":
        raise ConflictError("Solo se reembolsa un gasto aprobado.", code="expense_not_approved")
    if e.payment_method != "own_money":
        raise ConflictError("Ese gasto se pagó con la tarjeta de la empresa: no hay nada que reembolsar.",
                            code="expense_company_card")
    e.status, e.reimbursed_at, e.reimbursement_reference = "reimbursed", paid_on, (reference or "").strip() or None
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="expenses.reimbursed",
                             entity_type="expense", entity_id=str(e.id), after_data={"paid_on": paid_on.isoformat()})
    await db.commit()
    await db.refresh(e)
    return e


def list_stmt(organization_id, *, user=None, mine: bool, status=None, user_id=None, project_id=None,
              date_from=None, date_to=None):
    stmt = select(Expense).where(Expense.organization_id == organization_id)
    if mine:
        stmt = stmt.where(Expense.user_id == user.id)
    elif user_id:
        stmt = stmt.where(Expense.user_id == user_id)
    if status:
        stmt = stmt.where(Expense.status == status)
    if project_id:
        stmt = stmt.where(Expense.project_id == project_id)
    if date_from:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.expense_date <= date_to)
    return stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())


async def names(db, ids) -> dict:
    from app.modules.users.models import User

    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()}


async def out(db, items: list[Expense]) -> list[dict]:
    from app.modules.field_ops.models import Project

    personas = await names(db, {e.user_id for e in items} | {e.reviewed_by_user_id for e in items})
    pids = {e.project_id for e in items if e.project_id}
    proyectos = {p.id: p.title for p in (await db.execute(select(Project).where(Project.id.in_(pids)))).scalars().all()} \
        if pids else {}
    return [{
        "id": str(e.id), "user_id": str(e.user_id), "user_name": personas.get(e.user_id),
        "project_id": str(e.project_id) if e.project_id else None, "project_title": proyectos.get(e.project_id),
        "expense_date": e.expense_date.isoformat(), "category": e.category,
        "category_label": EXPENSE_CATEGORIES.get(e.category, e.category), "amount": str(to_money(e.amount)),
        "description": e.description, "payment_method": e.payment_method,
        "payment_label": EXPENSE_PAYMENT.get(e.payment_method), "status": e.status,
        "has_receipt": bool(e.receipt_path), "reviewed_by": personas.get(e.reviewed_by_user_id),
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None, "review_notes": e.review_notes,
        "reimbursed_at": e.reimbursed_at.isoformat() if e.reimbursed_at else None,
        "reimbursement_reference": e.reimbursement_reference,
    } for e in items]


def parse_uuid(v) -> uuid.UUID | None:
    if v in (None, ""):
        return None
    try:
        return uuid.UUID(str(v))
    except ValueError:
        raise InvalidInputError("Identificador inválido.", code="invalid_id") from None
