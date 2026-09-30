"""Base del cobro: dinero exacto y numeración sin repetidos (módulo 6, D6.8).

Hoy la facturación suma pagos con `float` y numera contando filas. Lo primero
puede fallar por centavos (0.1 + 0.2 != 0.3); lo segundo repite número si dos
facturas se crean a la vez. Estas pruebas fijan el comportamiento correcto.
"""
from decimal import Decimal

import pytest

from app.modules.billing.money import money_sum, to_money
from app.modules.billing.numbering import next_number


def test_money_rounds_half_up_to_cents():
    assert to_money("10.005") == Decimal("10.01")
    assert to_money(4000) == Decimal("4000.00")
    assert to_money(Decimal("7500.4")) == Decimal("7500.40")


def test_money_sum_is_exact():
    # Con float, 0.1 + 0.1 + 0.1 da 0.30000000000000004.
    assert money_sum(["0.1", "0.1", "0.1"]) == Decimal("0.30")
    assert money_sum([]) == Decimal("0.00")


def test_money_rejects_floats():
    """Un float ya trae el error de representación; se exige texto o Decimal."""
    with pytest.raises(TypeError):
        to_money(0.1)


async def test_numbers_are_sequential_per_series_and_year(db, seeded_org):
    org = seeded_org["org"].id
    assert await next_number(db, organization_id=org, series="REB", year=2026) == "REB-2026-0001"
    assert await next_number(db, organization_id=org, series="REB", year=2026) == "REB-2026-0002"
    # Otra serie no comparte el contador.
    assert await next_number(db, organization_id=org, series="FAC", year=2026) == "FAC-2026-0001"
    # Año nuevo reinicia.
    assert await next_number(db, organization_id=org, series="REB", year=2027) == "REB-2027-0001"


async def test_two_organizations_do_not_share_numbering(db, seeded_org, second_org):
    uno = await next_number(db, organization_id=seeded_org["org"].id, series="COT", year=2026)
    otro = await next_number(db, organization_id=second_org["org"].id, series="COT", year=2026)
    assert uno == otro == "COT-2026-0001"


async def test_an_unknown_series_is_rejected(db, seeded_org):
    with pytest.raises(ValueError):
        await next_number(db, organization_id=seeded_org["org"].id, series="XYZ", year=2026)
