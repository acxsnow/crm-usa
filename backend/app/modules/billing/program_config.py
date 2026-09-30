"""Configuración de cobro por programa (spec D6.2): tarifas y jurisdicciones con
vigencia, requisitos de radicación y datos de la factura.

Apunta a `Program` (Cadena A) y nunca lo modifica. Mientras José no tenga el
catálogo de programas (módulo 1), aquí solo se leen los programas que existan.
"""
import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import (
    BillingProgramProfile,
    ProgramClaimRequirement,
    ProgramJurisdiction,
    ProgramRebateRate,
)
from app.modules.billing.money import to_money
from app.modules.billing.requirements import AUTO_RULES, default_requirements
from app.modules.cases.models import Program
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

JURISDICTION_KINDS = {"city": "Ciudad", "zip": "Código postal"}


# ---------------------------------------------------------------------------
# Programa y perfil
# ---------------------------------------------------------------------------

async def get_program_or_404(db: AsyncSession, *, organization_id: uuid.UUID, program_id: uuid.UUID) -> Program:
    program = (
        await db.execute(select(Program).where(Program.id == program_id, Program.organization_id == organization_id))
    ).scalar_one_or_none()
    if program is None:
        raise NotFoundError("El programa no existe.", code="program_not_found")
    return program


async def list_programs(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Program]:
    return list(
        (
            await db.execute(select(Program).where(Program.organization_id == organization_id).order_by(Program.name))
        ).scalars().all()
    )


async def ensure_profile(db: AsyncSession, *, organization_id: uuid.UUID, program_id: uuid.UUID) -> BillingProgramProfile:
    """El perfil de cobro del programa; si no existe lo crea con el checklist
    por defecto (spec §5). No hace commit: lo hace quien lo llama."""
    await get_program_or_404(db, organization_id=organization_id, program_id=program_id)
    perfil = (
        await db.execute(
            select(BillingProgramProfile).where(
                BillingProgramProfile.organization_id == organization_id,
                BillingProgramProfile.program_id == program_id,
            )
        )
    ).scalar_one_or_none()
    if perfil is not None:
        return perfil
    perfil = BillingProgramProfile(organization_id=organization_id, program_id=program_id)
    db.add(perfil)
    for req in default_requirements():
        db.add(ProgramClaimRequirement(organization_id=organization_id, program_id=program_id, **req))
    await db.flush()
    return perfil


async def update_profile(db, *, organization_id, user, program_id, changes: dict) -> BillingProgramProfile:
    perfil = await ensure_profile(db, organization_id=organization_id, program_id=program_id)
    if "expected_payment_days" in changes and changes["expected_payment_days"] is not None:
        if not 1 <= changes["expected_payment_days"] <= 365:
            raise InvalidInputError("Los días esperados de pago van de 1 a 365.", code="invalid_payment_days")
    for campo, valor in changes.items():
        setattr(perfil, campo, valor)
    await _audit(db, organization_id, user, "billing.profile_updated", program_id, changes)
    await db.commit()
    await db.refresh(perfil)
    return perfil


# ---------------------------------------------------------------------------
# Tarifas
# ---------------------------------------------------------------------------

async def list_rates(db, *, organization_id, program_id) -> list[ProgramRebateRate]:
    await get_program_or_404(db, organization_id=organization_id, program_id=program_id)
    return list(
        (
            await db.execute(
                select(ProgramRebateRate)
                .where(ProgramRebateRate.organization_id == organization_id, ProgramRebateRate.program_id == program_id)
                .order_by(ProgramRebateRate.valid_from)
            )
        ).scalars().all()
    )


async def add_rate(db, *, organization_id, user, program_id, amount, valid_from: date, valid_to: date | None,
                   notes: str | None = None) -> ProgramRebateRate:
    await ensure_profile(db, organization_id=organization_id, program_id=program_id)
    monto = to_money(amount)
    if monto <= 0:
        raise InvalidInputError("La tarifa debe ser mayor que cero.", code="invalid_rate_amount")
    _check_period(valid_from, valid_to)
    for existente in await list_rates(db, organization_id=organization_id, program_id=program_id):
        if _overlaps(existente.valid_from, existente.valid_to, valid_from, valid_to):
            raise ConflictError(
                f"Ya hay una tarifa vigente entre el {existente.valid_from.isoformat()} y "
                f"{existente.valid_to.isoformat() if existente.valid_to else 'sin fecha de fin'}. "
                "Cierra esa vigencia antes de agregar otra.",
                code="rate_period_overlaps",
            )
    tarifa = ProgramRebateRate(
        organization_id=organization_id, program_id=program_id, amount=monto,
        valid_from=valid_from, valid_to=valid_to, notes=notes,
    )
    db.add(tarifa)
    await db.flush()
    await _audit(db, organization_id, user, "billing.rate_added", program_id,
                 {"amount": str(monto), "valid_from": valid_from.isoformat(),
                  "valid_to": valid_to.isoformat() if valid_to else None})
    await db.commit()
    await db.refresh(tarifa)
    return tarifa


async def close_rate(db, *, organization_id, user, rate_id, valid_to: date) -> ProgramRebateRate:
    """Cierra la vigencia de una tarifa (para cargar la del año siguiente). El
    monto no se edita: los cobros ya creados congelaron el suyo."""
    tarifa = await _owned(db, ProgramRebateRate, rate_id, organization_id, "La tarifa no existe.", "rate_not_found")
    _check_period(tarifa.valid_from, valid_to)
    tarifa.valid_to = valid_to
    await _audit(db, organization_id, user, "billing.rate_closed", tarifa.program_id, {"valid_to": valid_to.isoformat()})
    await db.commit()
    await db.refresh(tarifa)
    return tarifa


async def rate_for(db, *, organization_id, program_id, on: date) -> ProgramRebateRate | None:
    """La tarifa vigente en `on` (la fecha de la instalación, spec §2)."""
    for tarifa in await list_rates(db, organization_id=organization_id, program_id=program_id):
        if tarifa.covers(on):
            return tarifa
    return None


# ---------------------------------------------------------------------------
# Jurisdicciones
# ---------------------------------------------------------------------------

def normalize_jurisdiction(kind: str, value: str) -> str:
    """Ciudad sin mayúsculas, tildes de más ni espacios dobles; código postal a
    sus 5 dígitos ("91345-1234" → "91345")."""
    texto = (value or "").strip().lower()
    if kind == "zip":
        digitos = re.sub(r"\D", "", texto)[:5]
        if len(digitos) != 5:
            raise InvalidInputError("El código postal debe tener 5 dígitos.", code="invalid_zip")
        return digitos
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        raise InvalidInputError("Escribe el nombre de la ciudad.", code="invalid_city")
    return texto


async def list_jurisdictions(db, *, organization_id, program_id) -> list[ProgramJurisdiction]:
    await get_program_or_404(db, organization_id=organization_id, program_id=program_id)
    return list(
        (
            await db.execute(
                select(ProgramJurisdiction)
                .where(ProgramJurisdiction.organization_id == organization_id,
                       ProgramJurisdiction.program_id == program_id)
                .order_by(ProgramJurisdiction.valid_from, ProgramJurisdiction.label)
            )
        ).scalars().all()
    )


async def add_jurisdiction(db, *, organization_id, user, program_id, kind: str, value: str,
                           valid_from: date, valid_to: date | None) -> ProgramJurisdiction:
    await ensure_profile(db, organization_id=organization_id, program_id=program_id)
    if kind not in JURISDICTION_KINDS:
        raise InvalidInputError("La jurisdicción es por ciudad o por código postal.", code="invalid_jurisdiction_kind")
    _check_period(valid_from, valid_to)
    normal = normalize_jurisdiction(kind, value)
    for existente in await list_jurisdictions(db, organization_id=organization_id, program_id=program_id):
        if existente.kind == kind and existente.value == normal and _overlaps(
            existente.valid_from, existente.valid_to, valid_from, valid_to
        ):
            raise ConflictError(f"«{existente.label}» ya está en la jurisdicción para esas fechas.",
                                code="jurisdiction_duplicated")
    j = ProgramJurisdiction(organization_id=organization_id, program_id=program_id, kind=kind, value=normal,
                            label=value.strip(), valid_from=valid_from, valid_to=valid_to)
    db.add(j)
    await db.flush()
    await _audit(db, organization_id, user, "billing.jurisdiction_added", program_id,
                 {"kind": kind, "value": normal, "valid_from": valid_from.isoformat()})
    await db.commit()
    await db.refresh(j)
    return j


async def delete_jurisdiction(db, *, organization_id, user, jurisdiction_id) -> None:
    j = await _owned(db, ProgramJurisdiction, jurisdiction_id, organization_id,
                     "La jurisdicción no existe.", "jurisdiction_not_found")
    await _audit(db, organization_id, user, "billing.jurisdiction_deleted", j.program_id, {"value": j.value})
    await db.delete(j)
    await db.commit()


async def programs_for_address(db, *, organization_id, city: str | None, zip_code: str | None,
                               on: date) -> dict[uuid.UUID, ProgramJurisdiction]:
    """Programas cuya jurisdicción vigente en `on` incluye la dirección: por
    código postal o por ciudad. Devuelve programa → jurisdicción que coincidió
    (para mostrar por qué aplica)."""
    candidatos = []
    if zip_code:
        try:
            candidatos.append(("zip", normalize_jurisdiction("zip", zip_code)))
        except InvalidInputError:
            pass
    if city:
        try:
            candidatos.append(("city", normalize_jurisdiction("city", city)))
        except InvalidInputError:
            pass
    if not candidatos:
        return {}
    filas = (
        await db.execute(select(ProgramJurisdiction).where(ProgramJurisdiction.organization_id == organization_id))
    ).scalars().all()
    aplica: dict[uuid.UUID, ProgramJurisdiction] = {}
    for j in filas:
        if (j.kind, j.value) in candidatos and j.covers(on):
            aplica.setdefault(j.program_id, j)
    return aplica


# ---------------------------------------------------------------------------
# Requisitos
# ---------------------------------------------------------------------------

async def list_requirements(db, *, organization_id, program_id) -> list[ProgramClaimRequirement]:
    await ensure_profile(db, organization_id=organization_id, program_id=program_id)
    return list(
        (
            await db.execute(
                select(ProgramClaimRequirement)
                .where(ProgramClaimRequirement.organization_id == organization_id,
                       ProgramClaimRequirement.program_id == program_id)
                .order_by(ProgramClaimRequirement.sort_order)
            )
        ).scalars().all()
    )


async def add_requirement(db, *, organization_id, user, program_id, label: str, auto_code: str | None) -> ProgramClaimRequirement:
    """Un requisito nuevo: automático (del catálogo) o manual (texto libre,
    como el formulario propio de un programa)."""
    actuales = await list_requirements(db, organization_id=organization_id, program_id=program_id)
    if auto_code:
        if auto_code not in AUTO_RULES:
            raise InvalidInputError(f"La regla automática «{auto_code}» no existe.", code="unknown_auto_rule")
        code, kind, label = auto_code, "auto", (label or AUTO_RULES[auto_code])
    else:
        if len((label or "").strip()) < 3:
            raise InvalidInputError("Escribe el nombre del requisito.", code="requirement_label_required")
        code = "manual_" + re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")[:40]
        kind, label = "manual", label.strip()
    if any(r.code == code for r in actuales):
        raise ConflictError("Ese requisito ya está en el checklist del programa.", code="requirement_duplicated")
    req = ProgramClaimRequirement(organization_id=organization_id, program_id=program_id, code=code, label=label,
                                  kind=kind, sort_order=len(actuales))
    db.add(req)
    await db.flush()
    await _audit(db, organization_id, user, "billing.requirement_added", program_id, {"code": code})
    await db.commit()
    await db.refresh(req)
    return req


async def update_requirement(db, *, organization_id, user, requirement_id, changes: dict) -> ProgramClaimRequirement:
    """Activar/desactivar (TECH sin inspección), renombrar o reordenar."""
    req = await _owned(db, ProgramClaimRequirement, requirement_id, organization_id,
                       "El requisito no existe.", "requirement_not_found")
    for campo in ("label", "active", "sort_order"):
        if campo in changes and changes[campo] is not None:
            setattr(req, campo, changes[campo])
    await _audit(db, organization_id, user, "billing.requirement_updated", req.program_id,
                 {"code": req.code, **{k: v for k, v in changes.items() if v is not None}})
    await db.commit()
    await db.refresh(req)
    return req


# ---------------------------------------------------------------------------

def _check_period(valid_from: date, valid_to: date | None) -> None:
    if valid_to is not None and valid_to < valid_from:
        raise InvalidInputError("La fecha de fin no puede ser anterior a la de inicio.", code="invalid_period")


def _overlaps(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    return (a_to is None or b_from <= a_to) and (b_to is None or a_from <= b_to)


async def _owned(db, model, obj_id, organization_id, message, code):
    obj = (
        await db.execute(select(model).where(model.id == obj_id, model.organization_id == organization_id))
    ).scalar_one_or_none()
    if obj is None:
        raise NotFoundError(message, code=code)
    return obj


async def _audit(db, organization_id, user, action, program_id, data):
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id, action=action,
        entity_type="Program", entity_id=str(program_id),
        after_data={k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()},
    )
