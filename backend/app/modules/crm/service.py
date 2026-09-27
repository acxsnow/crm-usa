"""Reglas de negocio del CRM.

Quedó reducido al retirar el modelo anterior (prospectos, oportunidades,
cotizaciones y etapas de embudo): el expediente los reemplaza y su lógica vive
en `app/modules/cases/service.py`.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.models import FunderStatus


async def get_funder_status_by_code(
    db: AsyncSession, *, organization_id: uuid.UUID, code: str | None
) -> "FunderStatus | None":
    """Busca el estado del programa por su código dentro de la organización.

    `funder_statuses` queda como catálogo de etiquetas: el expediente guarda el
    código plano en `funder_status_code`, sin llave foránea."""
    if not code:
        return None
    return (
        await db.execute(
            select(FunderStatus).where(
                FunderStatus.organization_id == organization_id,
                FunderStatus.code == code,
            )
        )
    ).scalar_one_or_none()
