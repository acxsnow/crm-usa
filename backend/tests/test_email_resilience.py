"""El correo es best-effort: que falle no puede tumbar la operación.

La invitación de un usuario guarda y confirma en base y **después** manda el
correo. Si el envío lanza, el endpoint devolvía 500 aunque el usuario ya
existía: quien invitaba creía que había fallado, volvía a intentar y se
encontraba con "ya existe un usuario con ese correo".

Hasta que exista una cola real (módulo 7), el envío se registra y se sigue."""
import smtplib

import pytest

from app.modules.notifications import email as email_module


async def _login(app_client, email_address, password="SuperSecret123"):
    resp = await app_client.post(
        "/api/v1/auth/login", json={"email": email_address, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_invitation_succeeds_even_if_the_email_fails(
    app_client, active_admin_user, monkeypatch
):
    """El usuario queda creado y el endpoint responde 201, aunque el servidor
    de correo esté caído."""

    def _explode(*args, **kwargs):
        raise smtplib.SMTPAuthenticationError(535, b"credenciales invalidas")

    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "cuenta@ejemplo.com")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "clave")
    monkeypatch.setattr(email_module, "_send_smtp", _explode)

    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={
            "email": "invitado@acme-demo.com",
            "full_name": "Ivan Invitado",
            "role_codes": ["salesperson"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    listado = (await app_client.get("/api/v1/users", headers=headers)).json()
    correos = [u["email"] for u in listado["items"]]
    assert "invitado@acme-demo.com" in correos


async def test_send_email_reports_failure_without_raising(monkeypatch):
    def _explode(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, b"servidor no disponible")

    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "cuenta@ejemplo.com")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "clave")
    monkeypatch.setattr(email_module, "_send_smtp", _explode)

    enviado = await email_module.send_email(
        to="alguien@ejemplo.com", template="account_invitation", context={}
    )
    assert enviado is False


async def test_send_email_reports_success(monkeypatch):
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "console")
    enviado = await email_module.send_email(
        to="alguien@ejemplo.com", template="account_invitation", context={}
    )
    assert enviado is True


async def test_non_ascii_smtp_password_gives_a_clear_message(monkeypatch, caplog):
    """La contraseña de ejemplo del README lleva 'ñ'. `smtplib` la codifica en
    ASCII y revienta con un `UnicodeEncodeError` que no dice nada del problema
    real, así que se detecta antes y se explica."""
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "cuenta@ejemplo.com")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "la-contraseña-de-aplicación")

    with pytest.raises(email_module.EmailConfigurationError) as exc:
        email_module.check_smtp_credentials()
    assert "SMTP_PASSWORD" in str(exc.value)


async def test_ascii_smtp_password_passes_the_check(monkeypatch):
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "cuenta@ejemplo.com")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "abcd efgh ijkl mnop")
    email_module.check_smtp_credentials()  # no lanza


# ---------------------------------------------------------------------------
# Enlaces en desarrollo
# ---------------------------------------------------------------------------

async def test_console_provider_logs_the_link_so_the_flow_can_be_completed(monkeypatch, capsys):
    """En desarrollo no hay correo real, así que el enlace tiene que quedar en
    el log: es la única forma de completar una invitación o un restablecimiento
    de contraseña. Sin esto, invitar a alguien creaba un usuario que nunca
    podía entrar, porque el token solo se guarda como hash."""
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "console")

    enviado = await email_module.send_email(
        to="alguien@ejemplo.com",
        template="account_invitation",
        context={"invite_link": "http://localhost:5173/accept-invitation?token=abc123"},
    )
    assert enviado is True
    salida = capsys.readouterr().out
    assert "abc123" in salida, "el enlace no quedó en el log y no hay forma de usarlo"


async def test_a_real_provider_never_logs_the_link(monkeypatch, capsys):
    """Con un proveedor real el enlace se envía por correo y nunca se escribe:
    quien lea los registros no debe poder entrar con la cuenta de otro."""
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "cuenta@ejemplo.com")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "clave")
    monkeypatch.setattr(email_module, "_send_smtp", lambda *a, **k: None)

    await email_module.send_email(
        to="alguien@ejemplo.com",
        template="account_invitation",
        context={"invite_link": "http://localhost:5173/accept-invitation?token=secreto"},
    )
    assert "secreto" not in capsys.readouterr().out
