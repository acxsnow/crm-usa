"""Forma de pago y horas extras declaradas (respuestas de Don Aldo, 24 oct;
defecto D-019 del QA).

- **Almuerzo:** incluido cuando pagan por día o por hora, no cuando pagan por
  trabajo. Se define por persona (`EmployeePaySetting`); `service.pauses_paid`
  lo aplica en todas las horas.
- **Horas extras:** la persona las declara en horas y el jefe define cuánto
  valen. Nadie aprueba las propias. Lo que calcula `calc.overtime` desde las
  marcas queda solo como referencia para el jefe: no se paga.
"""
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models import EmployeePaySetting, OvertimeDeclaration
from app.modules.attendance.service import LUNCH_INCLUDED, PAY_TYPES, ensure_period_open, now
from app.modules.billing.money import to_money
from app.modules.field_ops import clock
from app.modules.users.models import User, UserStatus
from app.shared.audit import record_audit_event
from app.shared.datetime_utils import as_utc
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError


async def list_pay_settings(db: AsyncSession, organization_id) -> list[dict]:
    tipos = dict((await db.execute(select(EmployeePaySetting.user_id, EmployeePaySetting.pay_type).where(
        EmployeePaySetting.organization_id == organization_id))).all())
    usuarios = (await db.execute(select(User).where(User.organization_id == organization_id,
                                                    User.status == UserStatus.active).order_by(User.full_name))).scalars()
    return [_pay_out(u.id, u.full_name, tipos.get(u.id)) for u in usuarios]


def _pay_out(user_id, name: str, tipo: str | None) -> dict:
    return {"user_id": str(user_id), "name": name, "pay_type": tipo, "pay_type_label": PAY_TYPES.get(tipo),
            "lunch_included": LUNCH_INCLUDED.get(tipo)}


async def set_pay_setting(db: AsyncSession, *, organization_id, actor, user_id, pay_type: str | None) -> dict:
    persona = await db.get(User, user_id)
    if persona is None or persona.organization_id != organization_id:
        raise NotFoundError("La persona no existe.", code="user_not_found")
    fila = (await db.execute(select(EmployeePaySetting).where(EmployeePaySetting.organization_id == organization_id,
                                                              EmployeePaySetting.user_id == user_id))
            ).scalar_one_or_none()
    antes = fila.pay_type if fila else None
    if pay_type is None:
        if fila is not None:
            await db.delete(fila)
    else:
        if fila is None:
            fila = EmployeePaySetting(organization_id=organization_id, user_id=user_id, pay_type=pay_type)
            db.add(fila)
        fila.pay_type, fila.updated_by_user_id = pay_type, actor.id
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.pay_type_set", entity_type="User", entity_id=str(user_id),
                             before_data={"pay_type": antes}, after_data={"pay_type": pay_type})
    await db.commit()
    return _pay_out(user_id, persona.full_name, pay_type)


def stmt(organization_id, *, user_id=None, status=None, date_from=None, date_to=None):
    q = select(OvertimeDeclaration).where(OvertimeDeclaration.organization_id == organization_id)
    if user_id:
        q = q.where(OvertimeDeclaration.user_id == user_id)
    if status:
        q = q.where(OvertimeDeclaration.status == status)
    if date_from:
        q = q.where(OvertimeDeclaration.work_date >= date_from)
    if date_to:
        q = q.where(OvertimeDeclaration.work_date <= date_to)
    return q.order_by(OvertimeDeclaration.work_date.desc(), OvertimeDeclaration.id)


async def rows_out(db: AsyncSession, organization_id, filas: list[OvertimeDeclaration]) -> list[dict]:
    ids = {x for f in filas for x in (f.user_id, f.reviewed_by_user_id) if x}
    nombres = dict((await db.execute(select(User.id, User.full_name).where(
        User.organization_id == organization_id, User.id.in_(ids)))).all()) if ids else {}
    return [{"id": str(f.id), "user_id": str(f.user_id), "user_name": nombres.get(f.user_id, "—"),
             "work_date": f.work_date.isoformat(), "hours": str(f.hours), "notes": f.notes, "status": f.status,
             "value_amount": str(f.value_amount) if f.value_amount is not None else None,
             "review_notes": f.review_notes, "reviewed_by": nombres.get(f.reviewed_by_user_id),
             "reviewed_at": as_utc(f.reviewed_at).isoformat() if f.reviewed_at else None} for f in filas]


async def _get(db: AsyncSession, organization_id, declaration_id) -> OvertimeDeclaration:
    f = await db.get(OvertimeDeclaration, declaration_id)
    if f is None or f.organization_id != organization_id:
        raise NotFoundError("La declaración no existe.", code="overtime_not_found")
    return f


async def declare(db: AsyncSession, *, organization_id, user, work_date: date, hours: Decimal,
                  notes: str | None) -> dict:
    if work_date > await clock.org_today(db, organization_id):
        raise InvalidInputError("No se declaran horas de un día que no ha pasado.", code="overtime_future_date")
    await ensure_period_open(db, organization_id, work_date)
    ya = (await db.execute(select(OvertimeDeclaration.id).where(
        OvertimeDeclaration.organization_id == organization_id, OvertimeDeclaration.user_id == user.id,
        OvertimeDeclaration.work_date == work_date))).first()
    if ya:
        raise ConflictError("Ya declaraste horas extras de ese día. Bórrala si sigue pendiente y decláralas de nuevo.",
                            code="overtime_already_declared")
    f = OvertimeDeclaration(organization_id=organization_id, user_id=user.id, work_date=work_date,
                            hours=to_money(hours), notes=(notes or "").strip() or None, status="pending",
                            created_by_user_id=user.id)
    db.add(f)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="attendance.overtime_declared", entity_type="overtime_declaration",
                             entity_id=str(f.id), after_data={"work_date": work_date.isoformat(), "hours": str(f.hours)})
    await db.commit()
    return (await rows_out(db, organization_id, [f]))[0]


async def delete(db: AsyncSession, *, organization_id, user, declaration_id) -> None:
    f = await _get(db, organization_id, declaration_id)
    if f.user_id != user.id:
        raise NotFoundError("La declaración no existe.", code="overtime_not_found")
    if f.status != "pending":
        raise ConflictError("Solo se borra una declaración pendiente.", code="overtime_already_reviewed")
    await ensure_period_open(db, organization_id, f.work_date)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="attendance.overtime_deleted", entity_type="overtime_declaration",
                             entity_id=str(f.id), before_data={"work_date": f.work_date.isoformat(), "hours": str(f.hours)})
    await db.delete(f)
    await db.commit()


async def review(db: AsyncSession, *, organization_id, actor, declaration_id, approve: bool,
                 value_amount: Decimal | None, notes: str | None) -> dict:
    f = await _get(db, organization_id, declaration_id)
    if f.user_id == actor.id:
        raise ForbiddenError("Nadie aprueba sus propias horas extras.", code="self_review_forbidden")
    if f.status != "pending":
        raise ConflictError("Esa declaración ya se revisó.", code="overtime_already_reviewed")
    await ensure_period_open(db, organization_id, f.work_date)
    if approve and value_amount is None:
        raise InvalidInputError("Escribe cuánto valen esas horas.", code="overtime_value_required")
    motivo = (notes or "").strip() or None
    if not approve and not motivo:
        raise InvalidInputError("Escribe por qué no se aprueban.", code="overtime_reason_required")
    f.status = "approved" if approve else "rejected"
    f.value_amount = to_money(value_amount) if approve else None
    f.review_notes, f.reviewed_by_user_id, f.reviewed_at = motivo, actor.id, now()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=actor.id,
                             action="attendance.overtime_reviewed", entity_type="overtime_declaration",
                             entity_id=str(f.id),
                             after_data={"status": f.status, "value_amount": str(f.value_amount) if approve else None})
    await db.commit()
    return (await rows_out(db, organization_id, [f]))[0]


async def overtime_totals(db: AsyncSession, organization_id, date_from: date, date_to: date, user_id=None) -> dict:
    """{user_id: {declared, approved, value}} del rango; las rechazadas no cuentan."""
    totales: dict = defaultdict(lambda: {"declared": Decimal("0"), "approved": Decimal("0"), "value": Decimal("0")})
    for f in (await db.execute(stmt(organization_id, user_id=user_id, date_from=date_from, date_to=date_to))).scalars():
        if f.status == "rejected":
            continue
        totales[f.user_id]["declared"] += f.hours
        if f.status == "approved":
            totales[f.user_id]["approved"] += f.hours
            totales[f.user_id]["value"] += f.value_amount or Decimal("0")
    return dict(totales)
