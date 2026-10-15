"""Cuántos días hábiles lleva un expediente esperando aprobación.

PDF §3.1 («Seguimiento de tiempos», referencia 2–3 días hábiles) y la etapa
«Pendiente aprobación» de §7 («con contador de días»). La cuenta es la misma
de la alerta diaria del módulo 7 (`notifications.service.daily_alerts`): días
hábiles desde `submitted_at`, en la zona de la organización, contra el umbral
de Notificaciones → Alertas. Así la tarjeta y el aviso nunca dicen cosas
distintas.

`submitted_at` se escribe solo la primera vez que el expediente entra a
«Pendiente de aprobación» (`STAGE_MILESTONE`), así que ni la devolución ni el
reenvío después de un rechazo reinician la cuenta.

Solo lee: el umbral se consulta sin crear la fila de ajustes (los GET del
tablero y la cola no deben escribir).
"""
from dataclasses import dataclass
from datetime import date, tzinfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases.models import Case
from app.modules.field_ops.clock import local_date, org_today, org_zone
from app.modules.notifications.models import NotificationSettings
from app.modules.notifications.service import business_days_between

# El mismo valor por defecto que usa el módulo 7 cuando la organización no ha
# guardado sus ajustes (`notifications.service.get_settings_row`).
DEFAULT_LIMIT = 3


@dataclass(frozen=True)
class WaitContext:
    zone: tzinfo
    today: date
    limit: int


async def wait_context(db: AsyncSession, organization_id) -> WaitContext:
    """Zona, «hoy» y umbral de la organización: una vez por respuesta, no por tarjeta."""
    limite = (await db.execute(select(NotificationSettings.approval_alert_business_days).where(
        NotificationSettings.organization_id == organization_id))).scalar_one_or_none()
    return WaitContext(zone=await org_zone(db, organization_id), today=await org_today(db, organization_id),
                       limit=limite or DEFAULT_LIMIT)


def approval_wait(case: Case, ctx: WaitContext) -> dict | None:
    """`{"business_days", "overdue", "limit"}` del expediente, o `None` si no
    está esperando aprobación («En espera del programa» tampoco cuenta)."""
    if case.stage_code != "pending_approval" or case.submitted_at is None:
        return None
    dias = business_days_between(local_date(case.submitted_at, ctx.zone), ctx.today)
    return {"business_days": dias, "overdue": dias >= ctx.limit, "limit": ctx.limit}
