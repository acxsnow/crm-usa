""""Hoy" en la zona horaria de la organización.

El servidor corre en UTC y el trabajo de campo ocurre en Arizona, California y
Colombia. Usar `date.today()` del servidor rechazaba como "fecha pasada" la
instalación de hoy a partir de las 7 p. m. en Bogotá (5 p. m. en Phoenix) y le
ponía al cierre la fecha de mañana. Las fechas de negocio (agenda, cierre,
radicación) se comparan contra el día local de la organización
(`organizations.timezone`).
"""
import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizations.models import Organization

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    """Punto único para leer el reloj; las pruebas lo reemplazan."""
    return datetime.now(timezone.utc)


async def org_zone(db: AsyncSession, organization_id: uuid.UUID):
    """La zona horaria de la organización (UTC si falta o está mal escrita)."""
    nombre = (
        await db.execute(select(Organization.timezone).where(Organization.id == organization_id))
    ).scalar_one_or_none() or "UTC"
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        # Un valor mal escrito en la configuración no debe tumbar la agenda;
        # se registra para corregirlo y se usa UTC.
        logger.warning("organization.invalid_timezone", organization_id=str(organization_id), timezone=nombre)
        return timezone.utc


async def org_today(db: AsyncSession, organization_id: uuid.UUID) -> date:
    return _utcnow().astimezone(await org_zone(db, organization_id)).date()


def local_date(moment: datetime, zone) -> date:
    """El día local de un instante guardado en UTC (`created_at`…). Sin esto,
    un cobro creado a las 6 p. m. en Phoenix cuenta como del día siguiente."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(zone).date()
