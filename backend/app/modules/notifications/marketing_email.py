"""Correo de campañas (mercadeo), separado del correo de avisos.

Listo para producción: con `MARKETING_EMAIL_PROVIDER=smtp` y el buzón
(`MARKETING_EMAIL_FROM`, `MARKETING_SMTP_*`) envía. Pensado para Amazon SES
por SMTP, pero sirve cualquier proveedor SMTP.

Cada correo cumple CAN-SPAM: remitente identificable, dirección postal de la
empresa, enlace de baja visible y las cabeceras `List-Unsubscribe` /
`List-Unsubscribe-Post` (baja con un clic en Gmail y Outlook).
"""
import asyncio
import smtplib
from email.message import EmailMessage
from html import escape

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class MarketingEmailConfigurationError(RuntimeError):
    """Falta el buzón de campañas."""


def check_ready() -> None:
    s = get_settings()
    faltan = [n for n in ("MARKETING_EMAIL_FROM", "MARKETING_SMTP_USERNAME", "MARKETING_SMTP_PASSWORD",
                          "MARKETING_POSTAL_ADDRESS") if not getattr(s, n)]
    if faltan:
        raise MarketingEmailConfigurationError(f"Falta configurar: {', '.join(faltan)}.")


def unsubscribe_url(token: str) -> str:
    s = get_settings()
    base = (s.PUBLIC_API_URL or s.FRONTEND_APP_URL).rstrip("/")
    return f"{base}/api/v1/unsubscribe/{token}"


def build_message(*, to: str, subject: str, body: str, unsubscribe_token: str) -> EmailMessage:
    s = get_settings()
    baja = unsubscribe_url(unsubscribe_token)
    pie = (f"\n\n—\n{s.MARKETING_POSTAL_ADDRESS}\n"
           f"Recibes este correo porque aceptaste recibir promociones. Para no recibir más: {baja}")
    m = EmailMessage()
    m["From"] = s.MARKETING_EMAIL_FROM or "no-reply@example.com"
    m["To"] = to
    m["Subject"] = subject
    if s.MARKETING_EMAIL_REPLY_TO:
        m["Reply-To"] = s.MARKETING_EMAIL_REPLY_TO
    m["List-Unsubscribe"] = f"<{baja}>"
    m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    m.set_content(body + pie)
    parrafos = "".join(f"<p>{escape(p)}</p>" for p in body.split("\n") if p.strip())
    m.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;font-size:15px;color:#171514;max-width:560px">{parrafos}
<hr style="border:0;border-top:1px solid #ddd;margin:24px 0 12px">
<p style="font-size:12px;color:#6b6460">{escape(s.MARKETING_POSTAL_ADDRESS)}<br>
Recibes este correo porque aceptaste recibir promociones.
<a href="{escape(baja)}">Darme de baja</a></p></div>""", subtype="html")
    return m


def _smtp_send(message: EmailMessage) -> None:
    s = get_settings()
    with smtplib.SMTP(s.MARKETING_SMTP_HOST, s.MARKETING_SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if s.MARKETING_SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(s.MARKETING_SMTP_USERNAME, s.MARKETING_SMTP_PASSWORD)
        smtp.send_message(message)


async def send_marketing_email(*, to: str, subject: str, body: str, unsubscribe_token: str) -> str:
    """'sent' o 'test' (modo de prueba). Lanza si el proveedor falla."""
    s = get_settings()
    mensaje = build_message(to=to, subject=subject, body=body, unsubscribe_token=unsubscribe_token)
    if s.MARKETING_EMAIL_PROVIDER != "smtp":
        logger.info("marketing_email.test_mode", length=len(body))  # sin asunto ni destinatario: llevan datos personales
        return "test"
    check_ready()
    await asyncio.to_thread(_smtp_send, mensaje)
    logger.info("marketing_email.sent", length=len(body))
    return "sent"
