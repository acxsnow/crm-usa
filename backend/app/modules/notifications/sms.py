"""SMS transport abstraction. Masiv uses account credentials supplied by Masiv.

The endpoint and payload stay configurable because Masiv assigns the exact
transactional URL and account contract per customer.
"""
import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


async def send_sms(*, to: str, message: str) -> None:
    if settings.SMS_PROVIDER != "masiv":
        logger.info("sms.send", to=to, provider=settings.SMS_PROVIDER, message_length=len(message))
        return
    if not settings.MASIV_SMS_URL or not settings.MASIV_USERNAME or not settings.MASIV_PASSWORD:
        raise RuntimeError("MASIV_SMS_URL, MASIV_USERNAME and MASIV_PASSWORD are required when SMS_PROVIDER=masiv")

    payload = {"to": to, "message": message, "sender": settings.MASIV_SENDER}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(settings.MASIV_SMS_URL, auth=(settings.MASIV_USERNAME, settings.MASIV_PASSWORD), json=payload)
        response.raise_for_status()
    logger.info("sms.sent", to=to, provider="masiv", message_length=len(message))
