"""Email sending abstraction (spec 6.3, 11). Dev default logs to stdout;
production should enqueue through the Celery/Taskiq worker and use a
provider with a verified sender domain (e.g. SES)."""
import asyncio
import smtplib
from email.message import EmailMessage
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


async def send_email(*, to: str, template: str, context: dict) -> None:
    """Queue-friendly entrypoint. In dev (EMAIL_PROVIDER=console) this just logs;
    never logs secrets/tokens themselves, only that an email was 'sent'."""
    # Links contain bearer-style secrets (password reset, invitations, and
    # customer signature requests). Never write them to development logs.
    sensitive_keys = ("token", "password", "link", "url", "secret")
    safe_context = {k: v for k, v in context.items() if not any(key in k.lower() for key in sensitive_keys)}
    if settings.EMAIL_PROVIDER == "smtp":
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD are required when EMAIL_PROVIDER=smtp")
        subject, body = _render_template(template, context)
        await asyncio.to_thread(_send_smtp, to, subject, body)
        logger.info("email.sent", to=to, template=template, provider="smtp", context=safe_context)
        return
    logger.info("email.send", to=to, template=template, provider=settings.EMAIL_PROVIDER, context=safe_context)


def _render_template(template: str, context: dict) -> tuple[str, str]:
    """Small transactional-text catalog; replace with branded HTML templates later."""
    if template == "customer_signature_request":
        return (
            "Firma requerida para tu proyecto",
            f"Hola,\n\nEl equipo solicita tu firma para el proyecto: {context.get('project_title', 'tu proyecto')}.\n\nFirma aquí: {context.get('signing_link', '')}\n\nEste enlace vence el {context.get('expires_at', '')}.\n\nSi no esperabas este correo, puedes ignorarlo.",
        )
    if template == "account_invitation":
        return ("Invitación a tu cuenta", f"Has sido invitado a usar la plataforma. Acepta la invitación aquí: {context.get('invite_link', '')}")
    if template == "password_reset_request":
        return ("Restablece tu contraseña", f"Solicitaste restablecer tu contraseña. Continúa aquí: {context.get('reset_link', '')}")
    if template == "password_changed":
        return ("Tu contraseña fue actualizada", "Tu contraseña fue actualizada correctamente. Si no fuiste tú, contacta al administrador.")
    return ("Notificación de PAP.CRM", "Tienes una nueva notificación en PAP.CRM.")


def _send_smtp(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)
