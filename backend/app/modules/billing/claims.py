"""Cobro de rebate: un cobro por programa y por instalación (spec D6.3, D6.5).

Ciclo de un cobro:

    por radicar ──radicar──▶ radicado ──pago──▶ pagado
         ▲                       │
         └──── (corregir) ◀── rechazado        (retirar: libera el programa)

- **Crear** congela la tarifa vigente en la fecha de la instalación y el
  resultado de la jurisdicción, y emite la factura de rebate (serie REB). La
  instalación tiene que tener el acta confirmada por Administración.
- **Radicar** exige todo el checklist del programa cumplido. Cada radicación
  es un intento; los rechazos quedan en el historial y no vencen.
- **Pagar** registra lo que llegó. Si es distinto de la tarifa, la diferencia
  queda visible; no se "completa" sola.

El expediente se mueve por estos hechos (`_sync_case`), con `advance_case()` y
las guardas de `billing/case_hooks.py`: el primer cobro lo lleva a "En proceso
de cobro"; con todos sus cobros pagados pasa a "Pagado". Un cobro nuevo sobre
un expediente ya pagado no lo hace retroceder.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing import program_config
from app.modules.billing.models import (
    REJECTION_CATEGORIES,
    ClaimStatus,
    DocumentStatus,
    Invoice,
    InvoiceKind,
    InvoicePayment,
    RebateClaim,
    RebateClaimAttempt,
    RebateClaimCheck,
)
from app.modules.billing.money import to_money
from app.modules.billing.numbering import next_number
from app.modules.billing.requirements import evaluate_requirements
from app.modules.billing.service import build_lines, collectible_amount
from app.modules.cases.models import Case
from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.case_flow import advance_case, case_for_project, mark_substatus
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import Project, ProjectStatus
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

MIN_REASON_LENGTH = 3


# ---------------------------------------------------------------------------
# Elegibilidad
# ---------------------------------------------------------------------------

def installation_date_of(project: Project) -> date | None:
    """La fecha que decide tarifa y jurisdicción: la del cierre del acta."""
    return project.completed_date


async def eligibility(db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID) -> dict:
    """Qué programas aplican a la dirección de la instalación en su fecha, con
    la tarifa vigente y el cobro que ya exista. Sugiere; no bloquea."""
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    fecha = installation_date_of(project) or await org_today(db, organization_id)
    aplican = await program_config.programs_for_address(
        db, organization_id=organization_id, city=project.address_city, zip_code=project.address_zip, on=fecha
    )
    vivos = {c.program_id: c for c in await _claims_of_project(db, project.id) if c.status != ClaimStatus.withdrawn}
    programas = []
    for programa in await program_config.list_programs(db, organization_id=organization_id):
        if not programa.active:
            continue
        tarifa = await program_config.rate_for(db, organization_id=organization_id, program_id=programa.id, on=fecha)
        jurisdiccion = aplican.get(programa.id)
        cobro = vivos.get(programa.id)
        programas.append({
            "program_id": programa.id, "program_code": programa.code, "program_name": programa.name,
            "applies": jurisdiccion is not None,
            "jurisdiction_label": jurisdiccion.label if jurisdiccion else None,
            "rate": tarifa.amount if tarifa else None,
            "claim_id": cobro.id if cobro else None,
            "claim_status": cobro.status if cobro else None,
        })
    programas.sort(key=lambda p: (not p["applies"], p["program_name"]))
    return {
        "project_id": project.id,
        "installation_date": installation_date_of(project),
        "evaluated_on": fecha,
        "technician_info_confirmed": project.technician_info_confirmed,
        "programs": programas,
    }


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

async def create_claim(
    db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID, program_id: uuid.UUID,
    override_reason: str | None = None,
) -> RebateClaim:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    programa = await program_config.get_program_or_404(db, organization_id=organization_id, program_id=program_id)

    if not project.technician_info_confirmed:
        raise ConflictError(
            "Administración tiene que confirmar la información técnica del acta antes de crear el cobro.",
            code="acta_not_confirmed",
        )
    fecha = installation_date_of(project)
    if fecha is None:
        raise ConflictError("La instalación no tiene fecha de cierre.", code="installation_without_date")

    if any(c.program_id == program_id and c.status != ClaimStatus.withdrawn
           for c in await _claims_of_project(db, project.id)):
        raise ConflictError(
            f"Esta instalación ya tiene un cobro de {programa.name}. Retíralo si hay que empezar de nuevo.",
            code="claim_duplicated",
        )

    tarifa = await program_config.rate_for(db, organization_id=organization_id, program_id=program_id, on=fecha)
    if tarifa is None:
        raise InvalidInputError(
            f"{programa.name} no tiene tarifa vigente el {fecha.isoformat()} (fecha de la instalación). "
            "Cárgala en la configuración del programa.",
            code="rate_missing",
        )

    aplican = await program_config.programs_for_address(
        db, organization_id=organization_id, city=project.address_city, zip_code=project.address_zip, on=fecha
    )
    jurisdiccion = aplican.get(program_id)
    motivo = (override_reason or "").strip() or None
    if jurisdiccion is None and (motivo is None or len(motivo) < MIN_REASON_LENGTH):
        raise InvalidInputError(
            f"La dirección no está en la zona de {programa.name} en la fecha de la instalación. "
            "Si el programa acepta el caso, escribe el motivo.",
            code="program_not_applicable",
        )

    case = await case_for_project(db, project)
    claim = RebateClaim(
        organization_id=organization_id, project_id=project.id, case_id=case.id if case else None,
        program_id=program_id, status=ClaimStatus.preparing, amount=tarifa.amount, rate_id=tarifa.id,
        installation_date=fecha, applies=jurisdiccion is not None,
        jurisdiction_label=jurisdiccion.label if jurisdiccion else None,
        override_reason=motivo if jurisdiccion is None else None, created_by_user_id=user.id,
    )
    try:
        # Savepoint: si falla, se deshace solo el cobro. Un rollback completo
        # expiraría también al usuario de la petición.
        async with db.begin_nested():
            db.add(claim)
            await db.flush()
    except IntegrityError:
        # Otra persona creó el mismo cobro al mismo tiempo (índice único).
        raise ConflictError(
            f"Esta instalación ya tiene un cobro de {programa.name}.", code="claim_duplicated"
        ) from None

    invoice = await _issue_invoice(db, claim=claim, project=project, program_name=programa.name)
    await _audit(db, organization_id, user, "billing.claim_created", claim,
                 {"program": programa.code, "amount": str(claim.amount), "invoice": invoice.invoice_number,
                  "applies": claim.applies, "override_reason": claim.override_reason})
    claim_id = claim.id
    await _sync_case(db, project=project, user=user)
    await db.commit()
    domain_events.emit("claim.created", _payload(claim, organization_id))
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)


def rebate_lines(*, project: Project, amount, program_name: str):
    """Las líneas de la factura de rebate: el trabajo realizado y el rebate del
    programa por el mismo monto (lo que queda a cargo del cliente es 0). La
    usa también la vista previa del PDF."""
    direccion = ", ".join(x for x in (project.address_street, project.address_unit, project.address_city) if x)
    return build_lines([
        {"kind": "service", "description": f"HVAC installation — {direccion or project.title}",
         "quantity": 1, "unit_price": amount},
        {"kind": "rebate", "description": f"{program_name} rebate", "quantity": 1, "unit_price": amount},
    ])


async def _issue_invoice(db, *, claim: RebateClaim, project: Project, program_name: str,
                         replaces: Invoice | None = None) -> Invoice:
    """Factura de rebate emitida: el trabajo realizado y el rebate del programa
    por el mismo monto, así lo que queda a cargo del cliente es 0."""
    hoy = await org_today(db, claim.organization_id)
    perfil = await program_config.ensure_profile(db, organization_id=claim.organization_id,
                                                 program_id=claim.program_id)
    lineas = rebate_lines(project=project, amount=claim.amount, program_name=program_name)
    numero = await next_number(db, organization_id=claim.organization_id, series="REB", year=hoy.year)
    invoice = Invoice(
        organization_id=claim.organization_id, kind=InvoiceKind.rebate, project_id=project.id,
        case_id=claim.case_id, customer_id=project.customer_id, claim_id=claim.id,
        replaces_invoice_id=replaces.id if replaces else None, invoice_number=numero,
        funder_program=program_name, amount=collectible_amount(InvoiceKind.rebate, lineas),
        document_status=DocumentStatus.issued, issue_date=hoy,
        due_date=hoy + timedelta(days=perfil.expected_payment_days), lines=lineas,
    )
    db.add(invoice)
    await db.flush()
    return invoice


# ---------------------------------------------------------------------------
# Consultar
# ---------------------------------------------------------------------------

async def get_claim_or_404(db: AsyncSession, *, organization_id: uuid.UUID, claim_id: uuid.UUID) -> RebateClaim:
    claim = (
        await db.execute(
            select(RebateClaim)
            .where(RebateClaim.id == claim_id, RebateClaim.organization_id == organization_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if claim is None:
        raise NotFoundError("El cobro no existe.", code="claim_not_found")
    return claim


async def list_claims(
    db: AsyncSession, *, organization_id: uuid.UUID, status: str | None = None,
    program_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None,
) -> list[RebateClaim]:
    stmt = (
        select(RebateClaim).where(RebateClaim.organization_id == organization_id)
        .order_by(RebateClaim.created_at.desc())
    )
    if status:
        stmt = stmt.where(RebateClaim.status == status)
    if program_id:
        stmt = stmt.where(RebateClaim.program_id == program_id)
    if project_id:
        stmt = stmt.where(RebateClaim.project_id == project_id)
    return list((await db.execute(stmt)).scalars().all())


async def claim_checklist(db: AsyncSession, *, claim: RebateClaim) -> list[dict]:
    project, case = await _project_and_case(db, claim)
    reqs = await program_config.list_requirements(db, organization_id=claim.organization_id,
                                                  program_id=claim.program_id)
    return await evaluate_requirements(
        db, claim=claim, project=project, case=case, requirements=reqs,
        today=await org_today(db, claim.organization_id),
    )


# ---------------------------------------------------------------------------
# Requisitos manuales
# ---------------------------------------------------------------------------

async def confirm_manual_check(db, *, organization_id, user, claim_id, code: str, note: str | None) -> RebateClaim:
    claim = await _open_claim(db, organization_id, claim_id)
    req = await _manual_requirement(db, claim, code)
    if any(c.code == code for c in claim.checks):
        raise ConflictError(f"«{req.label}» ya está confirmado.", code="check_already_confirmed")
    db.add(RebateClaimCheck(organization_id=organization_id, claim_id=claim.id, code=code,
                            note=(note or "").strip() or None, confirmed_by_user_id=user.id))
    await _audit(db, organization_id, user, "billing.claim_check_confirmed", claim, {"code": code})
    await db.commit()
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


async def remove_manual_check(db, *, organization_id, user, claim_id, code: str) -> RebateClaim:
    claim = await _open_claim(db, organization_id, claim_id)
    check = next((c for c in claim.checks if c.code == code), None)
    if check is None:
        raise NotFoundError("Ese requisito no está confirmado.", code="check_not_found")
    await db.delete(check)
    await _audit(db, organization_id, user, "billing.claim_check_removed", claim, {"code": code})
    await db.commit()
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


async def _manual_requirement(db, claim, code):
    reqs = await program_config.list_requirements(db, organization_id=claim.organization_id,
                                                  program_id=claim.program_id)
    req = next((r for r in reqs if r.code == code and r.active), None)
    if req is None:
        raise NotFoundError("Ese requisito no está en el checklist del programa.", code="requirement_not_found")
    if req.kind != "manual":
        raise InvalidInputError(f"«{req.label}» lo comprueba el sistema; no se confirma a mano.",
                                code="requirement_is_automatic")
    return req


# ---------------------------------------------------------------------------
# Radicar, rechazar, pagar
# ---------------------------------------------------------------------------

async def submit_claim(db, *, organization_id, user, claim_id, portal_reference: str | None,
                       submitted_on: date | None) -> RebateClaim:
    """Radica ante el programa. Regla del cliente: no se envía a cobro sin el
    checklist completo."""
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if claim.status not in (ClaimStatus.preparing, ClaimStatus.rejected):
        raise ConflictError("Solo se radica un cobro por radicar o rechazado.", code="claim_not_submittable")
    pendientes = [r["label"] for r in await claim_checklist(db, claim=claim) if not r["met"]]
    if pendientes:
        raise InvalidInputError("No se puede radicar. Falta: " + "; ".join(pendientes) + ".",
                                code="claim_requirements_missing")
    hoy = await org_today(db, organization_id)
    fecha = submitted_on or hoy
    if fecha > hoy:
        raise InvalidInputError("La fecha de radicación no puede ser futura.", code="invalid_submission_date")
    claim.attempts.append(RebateClaimAttempt(
        organization_id=organization_id, submitted_on=fecha,
        portal_reference=(portal_reference or "").strip() or None, submitted_by_user_id=user.id,
    ))
    claim.status = ClaimStatus.submitted
    invoice = claim.invoice
    if invoice is not None and invoice.sent_at is None:
        from datetime import datetime, timezone

        invoice.sent_at = datetime.now(timezone.utc)
    await _audit(db, organization_id, user, "billing.claim_submitted", claim,
                 {"attempt": len(claim.attempts), "portal_reference": portal_reference})
    await db.flush()
    await _sync_case(db, project=(await _project_and_case(db, claim))[0], user=user)
    await db.commit()
    domain_events.emit("claim.submitted", _payload(claim, organization_id))
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


async def reject_claim(db, *, organization_id, user, claim_id, reason: str, category: str,
                       return_to_technician: bool = False) -> RebateClaim:
    """El programa rechazó el cobro. Queda en corrección sin vencimiento; si el
    motivo es técnico, el acta puede volver al técnico (se reabre el acta, no
    el expediente, spec D6.6)."""
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if claim.status != ClaimStatus.submitted:
        raise ConflictError("Solo se rechaza un cobro radicado.", code="claim_not_submitted")
    motivo = (reason or "").strip()
    if len(motivo) < MIN_REASON_LENGTH:
        raise InvalidInputError("Escribe el motivo del rechazo del programa.", code="rejection_reason_required")
    if category not in REJECTION_CATEGORIES:
        raise InvalidInputError("La categoría del rechazo es documental, técnica u otra.",
                                code="invalid_rejection_category")
    if return_to_technician and category != "technical":
        raise InvalidInputError("Solo un rechazo técnico devuelve el acta al técnico.",
                                code="return_needs_technical_rejection")

    intento = claim.attempts[-1]
    intento.result = "rejected"
    intento.rejection_category = category
    intento.rejection_reason = motivo
    intento.resolved_on = await org_today(db, organization_id)
    intento.resolved_by_user_id = user.id
    claim.status = ClaimStatus.rejected

    project, _ = await _project_and_case(db, claim)
    devuelta = False
    if return_to_technician:
        from app.modules.field_ops.reviews import add_review, reopen_for_correction

        if project.status == ProjectStatus.completed:
            reopen_for_correction(project)
            add_review(db, project=project, action="returned",
                       reason=f"Rechazo de {claim.program.name}: {motivo}", actor_id=user.id)
            devuelta = True
    await _audit(db, organization_id, user, "billing.claim_rejected", claim,
                 {"category": category, "reason": motivo, "returned_to_technician": devuelta})
    await db.flush()
    await _sync_case(db, project=project, user=user)
    await db.commit()
    domain_events.emit("claim.rejected", {**_payload(claim, organization_id), "category": category})
    if devuelta:
        domain_events.emit("project.returned_to_technician",
                           {"project_id": str(project.id), "organization_id": str(organization_id),
                            "reason": motivo})
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


async def record_claim_payment(db, *, organization_id, user, claim_id, amount, paid_on: date,
                               reference: str | None, method: str | None = None) -> RebateClaim:
    """Lo que pagó el programa. Si difiere de la tarifa congelada, la
    diferencia queda registrada (`difference`) y visible."""
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if claim.status != ClaimStatus.submitted:
        raise ConflictError("Solo se registra el pago de un cobro radicado.", code="claim_not_submitted")
    monto = to_money(amount)
    if monto <= 0:
        raise InvalidInputError("El pago debe ser mayor que cero.", code="invalid_payment_amount")
    if paid_on > await org_today(db, organization_id):
        raise InvalidInputError("La fecha del pago no puede ser futura.", code="invalid_payment_date")

    invoice = claim.invoice
    if invoice is not None:
        invoice.payments.append(InvoicePayment(amount=monto, paid_at=paid_on, method=method,
                                               reference=(reference or "").strip() or None))
        from datetime import datetime, timezone

        invoice.paid_at = datetime.now(timezone.utc)
    intento = claim.attempts[-1]
    intento.result = "paid"
    intento.resolved_on = paid_on
    intento.resolved_by_user_id = user.id
    claim.status = ClaimStatus.paid
    claim.paid_on = paid_on
    claim.paid_amount = monto
    claim.payment_reference = (reference or "").strip() or None
    await _audit(db, organization_id, user, "billing.claim_paid", claim,
                 {"amount": str(monto), "difference": str(claim.difference)})
    await db.flush()
    await _sync_case(db, project=(await _project_and_case(db, claim))[0], user=user)
    await db.commit()
    domain_events.emit("claim.paid", {**_payload(claim, organization_id), "amount": str(monto)})
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


# ---------------------------------------------------------------------------
# Retirar y refacturar
# ---------------------------------------------------------------------------

async def withdraw_claim(db, *, organization_id, user, claim_id, reason: str) -> RebateClaim:
    """Retira el cobro con motivo y anula su factura. Libera el programa para
    un cobro nuevo de la misma instalación."""
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if claim.status in (ClaimStatus.paid, ClaimStatus.withdrawn):
        raise ConflictError("Un cobro pagado o ya retirado no se retira.", code="claim_not_withdrawable")
    motivo = (reason or "").strip()
    if len(motivo) < MIN_REASON_LENGTH:
        raise InvalidInputError("Escribe por qué se retira el cobro.", code="withdraw_reason_required")
    invoice = claim.invoice
    if invoice is not None:
        invoice.document_status = DocumentStatus.void
        invoice.void_reason = f"Cobro retirado: {motivo}"
    claim.status = ClaimStatus.withdrawn
    claim.withdrawn_reason = motivo
    await _audit(db, organization_id, user, "billing.claim_withdrawn", claim, {"reason": motivo})
    await db.flush()
    await _sync_case(db, project=(await _project_and_case(db, claim))[0], user=user)
    await db.commit()
    domain_events.emit("claim.withdrawn", _payload(claim, organization_id))
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


async def reissue_invoice(db, *, organization_id, user, claim_id, reason: str) -> RebateClaim:
    """Una factura emitida no se edita: se anula con motivo y se emite otra
    que la reemplaza (con los datos actuales de la instalación)."""
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if not claim.is_open:
        raise ConflictError("Solo se refactura un cobro abierto.", code="claim_not_open")
    motivo = (reason or "").strip()
    if len(motivo) < MIN_REASON_LENGTH:
        raise InvalidInputError("Escribe por qué se refactura.", code="reissue_reason_required")
    anterior = claim.invoice
    if anterior is not None and anterior.payments:
        raise ConflictError("La factura tiene pagos registrados; no se puede reemplazar.",
                            code="invoice_has_payments")
    if anterior is not None:
        anterior.document_status = DocumentStatus.void
        anterior.void_reason = f"Reemplazada: {motivo}"
    project, _ = await _project_and_case(db, claim)
    nueva = await _issue_invoice(db, claim=claim, project=project, program_name=claim.program.name,
                                 replaces=anterior)
    await _audit(db, organization_id, user, "billing.claim_invoice_reissued", claim,
                 {"reason": motivo, "invoice": nueva.invoice_number,
                  "replaces": anterior.invoice_number if anterior else None})
    await db.commit()
    return await get_claim_or_404(db, organization_id=organization_id, claim_id=claim.id)


# ---------------------------------------------------------------------------
# Expediente
# ---------------------------------------------------------------------------

def case_substatus_for(claims: list[RebateClaim]) -> str | None:
    """El sub-estado de "En proceso de cobro" según sus cobros vivos: lo más
    urgente manda (un rechazo, luego lo que falta radicar)."""
    estados = {c.status for c in claims if c.status != ClaimStatus.withdrawn}
    if ClaimStatus.rejected in estados:
        return "rejected_by_program"
    if ClaimStatus.preparing in estados:
        return "invoice_pending"
    if ClaimStatus.submitted in estados:
        return "submitted"
    return None


def all_paid(claims: list[RebateClaim]) -> bool:
    vivos = [c for c in claims if c.status != ClaimStatus.withdrawn]
    return bool(vivos) and all(c.status == ClaimStatus.paid for c in vivos)


async def _sync_case(db, *, project: Project, user) -> None:
    """Lleva el expediente a donde dicen sus cobros. No retrocede: un cobro
    nuevo sobre un expediente pagado lo deja en "Pagado"."""
    case = await case_for_project(db, project)
    if case is None:
        return
    cobros = await _claims_of_project(db, project.id)
    if all_paid(cobros):
        if case.stage_code != "billing_in_progress":
            await advance_case(db, project=project, to_stage="billing_in_progress", user=user,
                               reason="Cobro de programa creado")
        await advance_case(db, project=project, to_stage="paid", user=user,
                           reason="Todos los cobros de programa pagados")
        return
    sub = case_substatus_for(cobros)
    if sub is None:
        return
    await advance_case(db, project=project, to_stage="billing_in_progress", user=user,
                       reason="Cobro de programa creado")
    await mark_substatus(db, project=project, stage="billing_in_progress", substatus=sub, user=user)


# ---------------------------------------------------------------------------

async def _claims_of_project(db, project_id) -> list[RebateClaim]:
    return list(
        (
            await db.execute(
                select(RebateClaim).where(RebateClaim.project_id == project_id)
                .order_by(RebateClaim.created_at)
            )
        ).scalars().all()
    )


async def _project_and_case(db, claim: RebateClaim) -> tuple[Project, Case | None]:
    project = (
        await db.execute(
            select(Project).where(Project.id == claim.project_id, Project.organization_id == claim.organization_id)
        )
    ).scalar_one()
    return project, await case_for_project(db, project)


async def _open_claim(db, organization_id, claim_id) -> RebateClaim:
    claim = await get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    if claim.status not in (ClaimStatus.preparing, ClaimStatus.rejected):
        raise ConflictError("El checklist se edita mientras el cobro está por radicar o rechazado.",
                            code="claim_checklist_locked")
    return claim


def _payload(claim: RebateClaim, organization_id) -> dict:
    return {"claim_id": str(claim.id), "project_id": str(claim.project_id),
            "program_id": str(claim.program_id), "organization_id": str(organization_id)}


async def _audit(db, organization_id, user, action, claim: RebateClaim, data: dict) -> None:
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id, action=action,
        entity_type="RebateClaim", entity_id=str(claim.id), after_data=data,
    )
