"""Firma del cliente a distancia (enlace por correo). No tenía pruebas: el QA
del 7 oct encontró que la página pública mandaba el token donde el backend no
lo leía, y que la API respondía «enviado» aunque el correo fallara."""
import pytest

from app.modules.field_ops import service as field_ops_service
from tests.field_helpers import headers_for
from tests.test_cases_intake import firma_png


@pytest.fixture
def correo(monkeypatch):
    enviados = []

    async def fake_send_email(*, to, template, context):
        enviados.append({"to": to, "template": template, **context})
        return True

    monkeypatch.setattr(field_ops_service, "send_email", fake_send_email)
    return enviados


async def _proyecto(app_client, headers, email="cliente@example.com"):
    c = (await app_client.post("/api/v1/customers", json={"legal_name": "Cliente Firma", "email": email}, headers=headers)).json()
    p = await app_client.post("/api/v1/projects", json={"customer_id": c["id"], "title": "Firma a distancia"}, headers=headers)
    assert p.status_code == 201, p.text
    return p.json()["id"]


async def test_the_customer_signs_from_the_email_link_like_the_page_does(app_client, active_admin_user, correo):
    headers = await headers_for(app_client, "admin@acme-demo.com")
    pid = await _proyecto(app_client, headers)
    r = await app_client.post(f"/api/v1/projects/{pid}/attestation/customer-signature-request", headers=headers)
    assert r.status_code == 200, r.text
    token = correo[0]["signing_link"].split("token=")[1]
    detalle = await app_client.get("/api/v1/public/customer-signature", params={"token": token})
    assert detalle.status_code == 200 and detalle.json()["project_title"] == "Firma a distancia"
    # Exactamente como lo manda la página pública: el token va en el cuerpo.
    r = await app_client.post("/api/v1/public/customer-signature",
                              json={"token": token, "customer_name": "Cliente Firma", "signature_base64": firma_png()})
    assert r.status_code == 200, r.text
    assert r.json()["customer_signed_at"]
    # El enlace es de un solo uso.
    assert (await app_client.get("/api/v1/public/customer-signature", params={"token": token})).status_code == 404
    r = await app_client.post("/api/v1/public/customer-signature",
                              json={"token": token, "customer_name": "Otro", "signature_base64": firma_png()})
    assert r.status_code == 404


async def test_a_wrong_token_does_not_sign(app_client):
    r = await app_client.post("/api/v1/public/customer-signature",
                              json={"token": "inventado", "customer_name": "X", "signature_base64": firma_png()})
    assert r.status_code == 404


async def test_if_the_email_fails_the_api_says_so(app_client, active_admin_user, monkeypatch):
    async def cae(**kw):
        return False

    monkeypatch.setattr(field_ops_service, "send_email", cae)
    headers = await headers_for(app_client, "admin@acme-demo.com")
    pid = await _proyecto(app_client, headers)
    r = await app_client.post(f"/api/v1/projects/{pid}/attestation/customer-signature-request", headers=headers)
    assert r.status_code == 502 and r.json()["code"] == "email_not_sent"
