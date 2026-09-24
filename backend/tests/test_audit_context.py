"""La auditoría guarda de dónde vino cada acción.

`audit_events` tiene columnas para `request_id`, `ip_address` y `user_agent`
desde el principio, pero se llenaban solo en una llamada de todo el proyecto.
Sin esos datos, investigar "quién cambió este rol y desde dónde" no es posible.

En vez de pasarlos a mano en cada `record_audit_event` —decenas de sitios, y
el próximo que se escriba se olvidaría— el middleware los deja en el contexto
de la petición y la auditoría los toma de ahí."""
from sqlalchemy import select

from app.shared.audit_models import AuditEvent


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_audit_events_record_the_request_context(app_client, db, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    headers["X-Request-ID"] = "peticion-de-prueba-1"
    headers["User-Agent"] = "NavegadorDePrueba/1.0"

    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "auditado", "name": "Auditado", "permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    event = (
        await db.execute(select(AuditEvent).where(AuditEvent.action == "roles.created"))
    ).scalars().first()
    assert event is not None
    assert event.request_id == "peticion-de-prueba-1"
    assert event.user_agent == "NavegadorDePrueba/1.0"
    assert event.ip_address  # el cliente de pruebas expone una dirección


async def test_audit_context_does_not_leak_between_requests(app_client, db, active_admin_user):
    """Cada evento lleva el identificador de *su* petición, no el de la
    anterior que pasó por el mismo worker."""
    headers = await _login(app_client, "admin@acme-demo.com")

    await app_client.post(
        "/api/v1/roles",
        json={"code": "primero", "name": "Primero", "permissions": ["customers.read"]},
        headers={**headers, "X-Request-ID": "peticion-A"},
    )
    await app_client.post(
        "/api/v1/roles",
        json={"code": "segundo", "name": "Segundo", "permissions": ["customers.read"]},
        headers={**headers, "X-Request-ID": "peticion-B"},
    )

    events = (
        await db.execute(
            select(AuditEvent).where(AuditEvent.action == "roles.created").order_by(AuditEvent.created_at)
        )
    ).scalars().all()
    ids = [e.request_id for e in events]
    assert "peticion-A" in ids
    assert "peticion-B" in ids
    assert len(set(ids)) == len(ids), f"se repitió el identificador entre peticiones: {ids}"


async def test_explicit_values_still_win(app_client, db, active_admin_user):
    """Quien ya pasaba la IP a mano (la invitación de usuarios) sigue mandando:
    el contexto solo rellena lo que falta."""
    from app.modules.users import service as users_service

    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={"email": "nuevo@acme-demo.com", "full_name": "Nuevo Usuario", "role_codes": ["salesperson"]},
        headers={**headers, "X-Request-ID": "peticion-invitacion"},
    )
    assert resp.status_code == 201, resp.text

    event = (
        await db.execute(select(AuditEvent).where(AuditEvent.action == "users.invited"))
    ).scalars().first()
    assert event is not None
    assert event.request_id == "peticion-invitacion"
    assert event.ip_address
