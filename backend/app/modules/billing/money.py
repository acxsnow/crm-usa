"""Dinero exacto (spec D6.8).

Todo monto del módulo de cobro pasa por aquí: `Decimal` con dos decimales y
redondeo comercial (0,005 sube). Los `float` se rechazan a propósito: `0.1`
como float ya es `0.1000000000000000055…`, y sumar pagos así termina en
diferencias de centavos que Contabilidad no puede explicar.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    if isinstance(value, float):
        raise TypeError("Los montos no se manejan como float: usa texto o Decimal.")
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def money_sum(values: Iterable) -> Decimal:
    total = ZERO
    for value in values:
        total += to_money(value)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
