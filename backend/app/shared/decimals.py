"""Números que llegan de afuera (formularios, Excel, la API) convertidos a
`Decimal` con dos decimales.

Antes cada módulo hacía `Decimal(str(valor))` por su cuenta: un «abc», «NaN»,
«1,5» o un número que no cabe en la columna terminaban en un 500 (ataque del
24 oct, `docs/qa/ataque-bodega-rotacion-2026-10-24.md`). Aquí cualquier cosa
que no sea un número finito y razonable responde 400 con un mensaje que la
persona entiende.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.shared.errors import InvalidInputError

CENT = Decimal("0.01")
# Lo que cabe en las columnas: cantidades Numeric(10, 2) y dinero Numeric(12, 2).
MAX_QUANTITY = Decimal("99999999.99")
MAX_MONEY = Decimal("9999999999.99")


def parse_decimal(value, *, limit: Decimal, places: Decimal = CENT) -> Decimal:
    """`value` como Decimal redondeado a `places`; 400 `invalid_number` si no es
    un número finito o pasa de `limit` (en valor absoluto)."""
    try:
        numero = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise InvalidInputError(f"«{value}» no es un número válido.", code="invalid_number") from None
    if not numero.is_finite() or abs(numero) > limit:
        raise InvalidInputError(f"«{value}» no es un número válido o es demasiado grande.",
                                code="invalid_number")
    return numero.quantize(places, rounding=ROUND_HALF_UP)


def to_quantity(value) -> Decimal:
    """Una cantidad de bodega (columna Numeric(10, 2)). Vacío es cero."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal("0.00")
    return parse_decimal(value, limit=MAX_QUANTITY)
