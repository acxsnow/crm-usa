"""Varios programas por expediente (cliente, 28 nov 2026).

Una misma instalación puede ir a varios programas (TECH y GoZero, HEERA y
GoZero). Lo acordado:

- El formulario se llena **una vez**, el del programa principal
  (`Case.program_id`). Como los campos son un catálogo único de la
  organización, las respuestas sirven para todos; si un adicional pide algo que
  no se capturó, aquí se dice qué le falta (`missing`).
- **Una sola firma** vale para todos: la constancia guarda los programas
  (`CaseTermsAcceptance.program_codes`).
- **Cada programa se aprueba o se rechaza por separado**, con su código. El
  principal sigue el flujo del expediente (aprobar o rechazar el expediente);
  cada adicional se decide con `decide()`. El rechazo de un adicional no frena
  la obra: ese programa no se cobra.
- **Un cobro por programa aprobado** (`billing/claims.py`); el expediente pasa a
  «Pagado» cuando están pagos todos sus cobros.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.cases.models import Case, CaseProgram, Program
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

# Antes de enviar a revisión no hay nada que decidir.
_SIN_DECISION = {"no_contact", "not_interested", "not_eligible", "new_prospect"}
# Con el expediente terminado ya no se cambian sus programas.
_CERRADAS = {"paid", "closed", "rejected"}


async def rows(db, case: Case) -> list[tuple[CaseProgram, Program]]:
    return list((await db.execute(
        select(CaseProgram, Program).join(Program, Program.id == CaseProgram.program_id)
        .where(CaseProgram.case_id == case.id, CaseProgram.organization_id == case.organization_id)
        .order_by(CaseProgram.is_primary.desc(), Program.name))).all())


async def _missing(db, case: Case, program: Program, respuestas: dict) -> list[str]:
    """Lo que el formulario publicado de ese programa pide y el expediente no
    tiene respondido (con las respuestas del formulario principal)."""
    from app.modules.programs import engine
    from app.modules.programs import service as programs

    version = await programs.published_version(db, organization_id=case.organization_id, program_id=program.id)
    if version is None:
        return []
    definicion = await programs.version_definition(db, version)
    return [m["label"] for m in engine.evaluate(definicion, respuestas)["missing"]]


async def describe(db, case: Case) -> list[dict]:
    """Los programas del expediente con su decisión y lo que le falta a cada
    adicional; el principal primero."""
    from app.modules.cases.intake import current_answers

    filas = await rows(db, case)
    respuestas = None
    del_principal: set[str] = set()
    out = []
    for cp, p in filas:
        faltan: list[str] = []
        if not cp.is_primary and case.program_version_id:
            if respuestas is None:
                from app.modules.cases.intake import _definition
                from app.modules.programs import engine

                respuestas, _ = await current_answers(db, case)
                del_principal = {m["label"] for m in engine.evaluate(await _definition(db, case),
                                                                     respuestas)["missing"]}
            # Solo lo que ese programa pide además del formulario principal: lo
            # que le falta al principal ya se ve (y se exige) en el formulario.
            faltan = [m for m in await _missing(db, case, p, respuestas) if m not in del_principal]
        out.append({"program_id": str(p.id), "code": p.code, "name": p.name, "is_primary": cp.is_primary,
                    "source": cp.source, "status": cp.status, "approval_code": cp.approval_code,
                    "application_number": cp.application_number, "decision_reason": cp.decision_reason,
                    "decided_at": cp.decided_at.isoformat() if cp.decided_at else None, "missing": faltan})
    return out


async def program_codes(db, case: Case) -> list[str]:
    return [p.code for _, p in await rows(db, case)]


async def set_additional(db, *, user, case: Case, program_ids: list[uuid.UUID]) -> None:
    """Deja los programas adicionales del expediente en `program_ids`. No toca
    el principal. Un adicional con cobro vivo no se quita."""
    if case.stage_code in _CERRADAS:
        raise ConflictError("El expediente ya terminó: sus programas no cambian.", code="case_programs_locked")
    if case.program_id is None:
        raise ConflictError("Elige primero el programa principal.", code="program_required")
    pedidos = list(dict.fromkeys(pid for pid in program_ids if pid != case.program_id))
    for pid in pedidos:
        prog = await db.get(Program, pid)
        if prog is None or prog.organization_id != case.organization_id:
            raise NotFoundError("Ese programa no existe.", code="program_not_found")
        if not prog.active:
            raise InvalidInputError(f"{prog.name} no está activo.", code="program_inactive")
    actuales = {cp.program_id: cp for cp, _ in await rows(db, case) if not cp.is_primary}
    quitar = [cp for pid, cp in actuales.items() if pid not in pedidos]
    if quitar:
        from app.modules.billing.models import ClaimStatus, RebateClaim
        from app.modules.field_ops.models import Project

        proyectos = select(Project.id).where(Project.case_id == case.id)
        con_cobro = set((await db.execute(select(RebateClaim.program_id).where(
            RebateClaim.project_id.in_(proyectos), RebateClaim.status != ClaimStatus.withdrawn))).scalars())
        for cp in quitar:
            if cp.program_id in con_cobro:
                prog = await db.get(Program, cp.program_id)
                raise ConflictError(f"{prog.name} ya tiene un cobro: no se quita.", code="program_has_claim")
    from app.modules.cases.service import set_case_programs

    antes = sorted(str(p) for p in actuales)
    await set_case_programs(db, case, primary_id=case.program_id, additional_ids=pedidos)
    await record_audit_event(db, organization_id=case.organization_id, actor_user_id=user.id,
                             action="cases.programs_changed", entity_type="case", entity_id=str(case.id),
                             before_data={"additional": antes},
                             after_data={"additional": sorted(str(p) for p in pedidos)})
    await db.commit()


async def decide(db, *, user, case: Case, program_id: uuid.UUID, decision: str, approval_code: str | None = None,
                 application_number: str | None = None, reason: str | None = None) -> None:
    """Aprobación o rechazo de un programa ADICIONAL. El principal se decide
    aprobando o rechazando el expediente."""
    if decision not in ("approved", "rejected", "pending"):
        raise InvalidInputError("La decisión es aprobado, rechazado o pendiente.", code="invalid_decision")
    if case.stage_code in _SIN_DECISION:
        raise ConflictError("El expediente todavía no se ha enviado a revisión.", code="case_not_submitted")
    cp = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == case.id,
                                                     CaseProgram.program_id == program_id))).scalar_one_or_none()
    if cp is None:
        raise NotFoundError("Ese programa no es de este expediente.", code="program_not_in_case")
    if cp.is_primary:
        raise ConflictError("El programa principal se aprueba o se rechaza con el expediente.",
                            code="primary_program_follows_case")
    if decision == "rejected" and not (reason or "").strip():
        raise InvalidInputError("Escribe el motivo.", code="reason_required")
    if decision != "approved":
        from app.modules.billing.models import ClaimStatus, RebateClaim
        from app.modules.field_ops.models import Project

        proyectos = select(Project.id).where(Project.case_id == case.id)
        if (await db.execute(select(RebateClaim.id).where(
                RebateClaim.project_id.in_(proyectos), RebateClaim.program_id == program_id,
                RebateClaim.status != ClaimStatus.withdrawn))).first():
            raise ConflictError("Ese programa ya tiene un cobro: retíralo antes de cambiar su decisión.",
                                code="program_has_claim")
    antes = {"status": cp.status, "approval_code": cp.approval_code}
    cp.status = decision
    cp.approval_code = (approval_code or "").strip() or None if decision == "approved" else None
    cp.application_number = (application_number or "").strip() or cp.application_number
    cp.decision_reason = (reason or "").strip() or None
    cp.decided_at = datetime.now(timezone.utc) if decision != "pending" else None
    cp.decided_by_user_id = user.id if decision != "pending" else None
    await record_audit_event(db, organization_id=case.organization_id, actor_user_id=user.id,
                             action="cases.program_decided", entity_type="case", entity_id=str(case.id),
                             before_data=antes, after_data={"program_id": str(program_id), "status": decision,
                                                            "approval_code": cp.approval_code,
                                                            "reason": cp.decision_reason})
    await db.commit()


async def sync_primary(db, case: Case, *, user_id: uuid.UUID | None) -> None:
    """El principal copia la decisión del expediente: aprobado al aprobarlo,
    rechazado al rechazarlo. No hace `commit`."""
    if case.program_id is None:
        return
    cp = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == case.id,
                                                     CaseProgram.program_id == case.program_id))
          ).scalar_one_or_none()
    if cp is None:
        return
    if case.stage_code == "approved":
        cp.status, cp.approval_code = "approved", case.approval_code
        cp.application_number = case.application_number
    elif case.stage_code == "rejected":
        cp.status, cp.decision_reason = "rejected", case.stage_reason
    else:
        return
    cp.decided_at, cp.decided_by_user_id = datetime.now(timezone.utc), user_id


async def billable_program_ids(db, case: Case) -> set[uuid.UUID]:
    """Los programas a los que se les puede cobrar: el principal y los
    adicionales aprobados."""
    out = set()
    for cp, _ in await rows(db, case):
        if cp.is_primary or cp.status == "approved":
            out.add(cp.program_id)
    if case.program_id:
        out.add(case.program_id)
    return out
