"""Numeración de documentos por serie, año y organización (spec D6.8).

Reemplaza a la numeración anterior, que contaba filas: si dos facturas se
creaban a la vez, las dos leían el mismo conteo y salían con el mismo número.
Aquí cada (organización, serie, año) tiene su contador en una fila que se
bloquea al asignar (`SELECT … FOR UPDATE` en Postgres), así que dos
asignaciones simultáneas se turnan. La restricción única de la tabla cubre la
primera asignación del año, cuando la fila todavía no existe.

No hace commit: el número se confirma junto con el documento que lo usa. Si la
creación del documento falla, el número tampoco se consume.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import DocumentSequence

# Serie → qué numera. Una serie desconocida es un error de programación, no
# un dato del usuario.
SERIES = {
    "REB": "Factura de rebate (cobro a un programa)",
    "FAC": "Factura de trabajo particular",
    "COT": "Cotización de trabajo particular",
}


async def next_number(db: AsyncSession, *, organization_id: uuid.UUID, series: str, year: int) -> str:
    if series not in SERIES:
        raise ValueError(f"Serie de numeración desconocida: {series}")
    fila = (
        await db.execute(
            select(DocumentSequence)
            .where(
                DocumentSequence.organization_id == organization_id,
                DocumentSequence.series == series,
                DocumentSequence.year == year,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if fila is None:
        fila = DocumentSequence(organization_id=organization_id, series=series, year=year, last_number=0)
        db.add(fila)
    fila.last_number += 1
    await db.flush()
    return f"{series}-{year}-{fila.last_number:04d}"
