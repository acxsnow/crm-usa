"""Enganche del cobro con el expediente (spec D6.5).

Igual que `field_ops/case_hooks.py`: el motor de etapas no sabe que el cobro
existe; aquí se registran las guardas que protegen el camino manual
(`POST /cases/{id}/transition`), para que la etapa diga lo mismo que los
cobros:

- Entrar a "En proceso de cobro" exige al menos un cobro de programa vivo (la
  guarda de campo exige además el acta confirmada).
- Pasar a "Pagado" exige que todos los cobros vivos estén pagados.
"""
from sqlalchemy import select

from app.modules.billing.models import ClaimStatus, RebateClaim
from app.modules.cases import stages
from app.shared.errors import InvalidInputError

_registrado = False


async def _claims_of_case(db, case) -> list[RebateClaim]:
    return list(
        (
            await db.execute(
                select(RebateClaim).where(RebateClaim.case_id == case.id,
                                          RebateClaim.organization_id == case.organization_id)
            )
        ).scalars().all()
    )


async def guard_has_claim(*, db, case, actor_id, reason):
    if not any(c.status != ClaimStatus.withdrawn for c in await _claims_of_case(db, case)):
        raise InvalidInputError(
            "Crea el cobro de al menos un programa antes de pasar a «En proceso de cobro».",
            code="claim_missing",
        )


async def guard_all_claims_paid(*, db, case, actor_id, reason):
    from app.modules.billing.claims import all_paid

    if not all_paid(await _claims_of_case(db, case)):
        raise InvalidInputError(
            "El expediente pasa a «Pagado» cuando todos sus cobros de programa están pagados.",
            code="claims_not_paid",
        )


def register() -> None:
    """Idempotente, como el de campo."""
    global _registrado
    if _registrado:
        return
    for origen in ("installed", "inspection_pending"):
        if stages.is_allowed(origen, "billing_in_progress"):
            stages.register_guard(origen, "billing_in_progress", guard_has_claim)
    stages.register_guard("billing_in_progress", "paid", guard_all_claims_paid)
    _registrado = True


def _reset_for_tests() -> None:
    global _registrado
    _registrado = False
