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


class EmailConfigurationError(RuntimeError):
    """La configuración de correo no sirve para enviar."""


def check_smtp_credentials() -> None:
    """Valida la configuración SMTP antes de intentar conectarse.

    `smtplib` codifica usuario y contraseña en ASCII al autenticarse, así que
    una contraseña con tildes o eñes revienta con un `UnicodeEncodeError` que
    no dice nada del problema real. La contraseña de ejemplo del README
    ("la-contraseña-de-aplicación") cae justo en ese caso."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise EmailConfigurationError(
            "SMTP_USERNAME y SMTP_PASSWORD son obligatorios cuando EMAIL_PROVIDER=smtp."
        )
    for nombre, valor in (("SMTP_USERNAME", settings.SMTP_USERNAME), ("SMTP_PASSWORD", settings.SMTP_PASSWORD)):
        try:
            valor.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EmailConfigurationError(
                f"{nombre} tiene caracteres no ASCII (tildes o eñes) y el protocolo "
                "SMTP no los admite al autenticarse. Si copiaste el valor de "
                "ejemplo del README, reemplázalo por la contraseña de aplicación real."
            ) from exc


async def send_email(*, to: str, template: str, context: dict) -> bool:
    """Envía un correo. Devuelve si se logró.

    **No lanza.** Las operaciones que mandan correo (invitar a alguien,
    restablecer una contraseña, pedir una firma) ya guardaron y confirmaron sus
    datos cuando llegan aquí: si un fallo de correo propagara, el endpoint
    respondería error sobre algo que sí ocurrió, y quien lo intentó volvería a
    hacerlo creyendo que no pasó nada.

    El fallo queda registrado con el motivo. Cuando exista la cola del módulo 7,
    este es el punto donde se encola con reintentos."""
    # Los enlaces llevan secretos (restablecer contraseña, invitaciones, firma
    # del cliente). Nunca se escriben en el log.
    sensitive_keys = ("token", "password", "link", "url", "secret")
    safe_context = {k: v for k, v in context.items() if not any(key in k.lower() for key in sensitive_keys)}

    if settings.EMAIL_PROVIDER != "smtp":
        # En modo consola no hay correo real, así que el enlace se registra
        # completo: es la única forma de completar una invitación o un
        # restablecimiento, porque del token solo se guarda el hash. Sin esto,
        # invitar a alguien creaba un usuario que nunca podía entrar.
        # Con un proveedor real el enlace nunca se escribe: quien lea los
        # registros no debe poder entrar con la cuenta de otro.
        logger.info(
            "email.send",
            to=to,
            template=template,
            provider=settings.EMAIL_PROVIDER,
            context=safe_context,
            dev_links={k: v for k, v in context.items() if "link" in k.lower()},
        )
        return True

    try:
        check_smtp_credentials()
        subject, body = _render_template(template, context)
        await asyncio.to_thread(_send_smtp, to, subject, body)
    except Exception as exc:
        logger.warning(
            "email.failed",
            to=to,
            template=template,
            provider="smtp",
            error_type=type(exc).__name__,
            error=str(exc),
            context=safe_context,
        )
        return False

    logger.info("email.sent", to=to, template=template, provider="smtp", context=safe_context)
    return True


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
