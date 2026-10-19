"""Firmas del acta como paso propio (spec 2026-10-18-firmas-del-acta): el
técnico solo firma sus órdenes, una firma no se reescribe, la firma en el
celular del técnico queda marcada y el enlace pendiente se ve tras recargar."""
import pytest
from sqlalchemy import select

from app.modules.crm.models import Customer
from app.modules.field_ops import service as field_ops_service
from app.shared.audit_models import AuditEvent
from tests.field_helpers import headers_for, ready_to_install_case
from tests.test_cases_intake import firma_png


@pytest.fixture
def correo(monkeypatch):
    async def fake_send_email(*, to, template, context):
        return True

    monkeypatch.setattr(field_ops_service, "send_email", fake_send_email)


async def _orden(app_client, db, seeded_org, technician=None):
    _, project = await ready_to_install_case(
        db, seeded_org["org"].id, technician_id=technician.id if technician else None)
    return project, await headers_for(app_client, "tech@acme-demo.com")


def _firma(nombre=None):
    return {"signature_base64": firma_png(), **({"customer_name": nombre} if nombre else {})}


async def test_a_technician_cannot_touch_the_acta_of_another_order(app_client, db, seeded_org, active_technician_user, correo):
    project, h = await _orden(app_client, db, seeded_org)  # sin asignar a este técnico
    base = f"/api/v1/projects/{project.id}/attestation"
    assert (await app_client.post(f"{base}/technician-sign", json=_firma(), headers=h)).status_code == 404
    assert (await app_client.post(f"{base}/customer-sign", json=_firma("Marge"), headers=h)).status_code == 404
    assert (await app_client.post(f"{base}/customer-signature-request", headers=h)).status_code == 404
    assert (await app_client.get(base, headers=h)).status_code == 404


async def test_a_signature_is_not_overwritten(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    base = f"/api/v1/projects/{project.id}/attestation"
    assert (await app_client.post(f"{base}/technician-sign", json=_firma(), headers=h)).status_code == 200
    segunda = await app_client.post(f"{base}/technician-sign", json=_firma(), headers=h)
    assert segunda.status_code == 409 and segunda.json()["code"] == "already_signed"

    assert (await app_client.post(f"{base}/customer-sign", json=_firma("Marge Simpson"), headers=h)).status_code == 200
    segunda = await app_client.post(f"{base}/customer-sign", json=_firma("Otra persona"), headers=h)
    assert segunda.status_code == 409 and segunda.json()["code"] == "already_signed"
    acta = (await app_client.get(base, headers=h)).json()
    assert acta["customer_name"] == "Marge Simpson" and acta["is_fully_signed"] is True


async def test_signing_on_the_technician_phone_is_marked_in_the_audit(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    r = await app_client.post(f"/api/v1/projects/{project.id}/attestation/customer-sign",
                              json=_firma("Marge Simpson"), headers=h)
    assert r.status_code == 200, r.text
    evento = (await db.execute(select(AuditEvent).where(AuditEvent.action == "attestation.customer_signed"))).scalar_one()
    assert evento.after_data == {"method": "in_person", "customer_name": "Marge Simpson"}


async def test_the_pending_link_is_part_of_the_acta(app_client, db, seeded_org, active_technician_user, correo):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    cliente = await db.get(Customer, project.customer_id)
    cliente.email = "marge@example.com"
    await db.commit()
    base = f"/api/v1/projects/{project.id}/attestation"

    assert (await app_client.post(f"{base}/customer-signature-request", headers=h)).status_code == 200
    acta = (await app_client.get(base, headers=h)).json()
    assert acta["customer_link_sent_to"] == "marge@example.com"
    assert acta["customer_link_expires_at"]

    # Firmado (aquí en persona), el enlace deja de estar pendiente.
    await app_client.post(f"{base}/customer-sign", json=_firma("Marge Simpson"), headers=h)
    acta = (await app_client.get(base, headers=h)).json()
    assert acta["customer_link_sent_to"] is None
