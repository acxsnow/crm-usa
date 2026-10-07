"""Envío de SMS por Masiv (masivapp).

Listo para producción: con `SMS_PROVIDER=masiv`, `MASIV_USERNAME` y
`MASIV_PASSWORD` envía. La API de Masiv recibe autenticación básica y un JSON
con `to` (número con código de país, sin «+»: 1 + 10 dígitos en EE. UU.) y
`text`. Los mensajes de más de 160 caracteres van como mensaje largo.

Si la cuenta de Masiv asignada usa otra URL, se cambia en `MASIV_SMS_URL`
sin tocar código.
"""
import httpx
import structlog

from app.core.config import get_settings
from app.shared.normalize import normalize_phone

logger = structlog.get_logger(__name__)


class SmsConfigurationError(RuntimeError):
    """Falta configuración de Masiv."""


def to_masiv_number(phone: str) -> str:
    """'(818) 555-0101', '+18185550101' → '18185550101'."""
    digitos = normalize_phone(phone) or ""
    if len(digitos) != 10:
        raise ValueError(f"Número de EE. UU. inválido: termina en {digitos[-4:]}")
    return f"1{digitos}"


def masiv_payload(*, to: str, message: str, custom: str | None = None) -> dict:
    return {
        "to": to_masiv_number(to),
        "text": message,
        "customdata": (custom or "")[:50],
        "isPremium": False,
        "isFlash": False,
        "isLongmessage": len(message) > 160,
        "isRandomRoute": False,
    }


async def send_sms(*, to: str, message: str, custom: str | None = None) -> str | None:
    """Envía un SMS. Devuelve el id de Masiv si lo da. Lanza si falla: la cola
    que llama lleva los reintentos."""
    settings = get_settings()
    if settings.SMS_PROVIDER != "masiv":
        logger.info("sms.send", provider=settings.SMS_PROVIDER, phone_tail=(normalize_phone(to) or "")[-4:],
                    message_length=len(message))
        return None
    if not settings.MASIV_SMS_URL or not settings.MASIV_USERNAME or not settings.MASIV_PASSWORD:
        raise SmsConfigurationError("Con SMS_PROVIDER=masiv faltan MASIV_USERNAME y/o MASIV_PASSWORD.")
    async with httpx.AsyncClient(timeout=settings.MASIV_TIMEOUT_SECONDS) as client:
        response = await client.post(settings.MASIV_SMS_URL, auth=(settings.MASIV_USERNAME, settings.MASIV_PASSWORD),
                                     json=masiv_payload(to=to, message=message, custom=custom))
    if response.status_code >= 400:
        raise RuntimeError(f"Masiv respondió {response.status_code}: {response.text[:200]}")
    try:
        datos = response.json()
    except ValueError:
        datos = {}
    message_id = datos.get("messageId") or datos.get("messageid")
    logger.info("sms.sent", provider="masiv", phone_tail=(normalize_phone(to) or "")[-4:], message_id=message_id)
    return message_id
