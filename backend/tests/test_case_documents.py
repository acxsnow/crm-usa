"""Módulo 3: Administración revisa los documentos del expediente."""
import pytest

from app.modules.cases import documents, stages
from app.modules.field_ops import case_hooks
from app.shared import events as domain_events
from tests.field_helpers import headers_for, jpeg_bytes
from tests.test_cases_intake import _abrir, _llenar_todo, _subir, _tech


@pytest.fixture(autouse=True)
def _registries():
    documents._reset_for_tests()
    documents.register()
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    documents._reset_for_tests()
    domain_events.clear_subscribers()


@pytest.fixture
async def enviado(app_client, db, seeded_org, active_salesperson_user, active_admin_staff_user):
    """Un expediente de TECH lleno y enviado a revisión."""
    tech = await _tech(db, seeded_org["org"].id)
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, vendedor, tech.id))["case"]
    await _llenar_todo(app_client, vendedor, caso["id"])
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/submit", headers=vendedor)
    assert r.status_code == 200, r.text
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")
    return {"id": caso["id"], "vendedor": vendedor, "admin": admin}


async def _docs(app_client, e, who="admin"):
    r = await app_client.get(f"/api/v1/cases/{e['id']}/documents", headers=e[who])
    assert r.status_code == 200, r.text
    return r.json()


async def _revisar(app_client, e, file_id, status, notes=None):
    return await app_client.post(f"/api/v1/case-files/{file_id}/review", json={"status": status, "notes": notes},
                                 headers=e["admin"])


async def test_the_case_lists_its_current_documents_with_their_field(app_client, enviado):
    docs = await _docs(app_client, enviado)
    assert len(docs) == 8 and all(d["review_status"] == "pending" for d in docs)
    id_foto = next(d for d in docs if d["field_key"] == "customer.id_photo")
    assert id_foto["label"] and id_foto["step_title"] and id_foto["watermarked"] is True


async def test_a_replaced_photo_leaves_the_list(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, vendedor, tech.id))["case"]
    primera = await _subir(app_client, vendedor, caso["id"], "docs.panel_photo")
    segunda = await _subir(app_client, vendedor, caso["id"], "docs.panel_photo")
    for f in (primera, segunda):
        r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/documents",
                                 json={"answers": {"docs.panel_photo": f}}, headers=vendedor)
        assert r.status_code == 200, r.text
    docs = (await app_client.get(f"/api/v1/cases/{caso['id']}/documents", headers=vendedor)).json()
    assert [d["id"] for d in docs] == [segunda]


async def test_rejecting_requires_a_reason_and_the_salesperson_sees_it(app_client, enviado):
    doc = (await _docs(app_client, enviado))[0]
    r = await _revisar(app_client, enviado, doc["id"], "rejected")
    assert r.status_code == 400 and "por qué" in r.json()["detail"]
    r = await _revisar(app_client, enviado, doc["id"], "rejected", "La foto está borrosa")
    assert r.status_code == 200 and r.json()["review_status"] == "rejected"
    form = (await app_client.get(f"/api/v1/cases/{enviado['id']}/form", headers=enviado["vendedor"])).json()
    visto = next(f for f in form["files"] if f["id"] == doc["id"])
    assert (visto["review_status"], visto["review_notes"]) == ("rejected", "La foto está borrosa")


async def test_the_salesperson_cannot_review(app_client, enviado):
    doc = (await _docs(app_client, enviado, "vendedor"))[0]
    r = await app_client.post(f"/api/v1/case-files/{doc['id']}/review", json={"status": "accepted"},
                              headers=enviado["vendedor"])
    assert r.status_code == 403


async def test_approval_waits_for_every_document(app_client, enviado):
    aprobar = lambda: app_client.post(f"/api/v1/cases/{enviado['id']}/transition",
                                      json={"to_stage": "approved", "approval_code": "TECH-1"},
                                      headers=enviado["admin"])
    docs = await _docs(app_client, enviado)
    r = await aprobar()
    assert r.status_code == 400 and r.json()["code"] == "documents_pending"
    for d in docs[1:]:
        assert (await _revisar(app_client, enviado, d["id"], "accepted")).status_code == 200
    await _revisar(app_client, enviado, docs[0]["id"], "rejected", "Ilegible")
    r = await aprobar()
    assert r.status_code == 400 and r.json()["code"] == "documents_rejected"
    await _revisar(app_client, enviado, docs[0]["id"], "accepted")
    r = await aprobar()
    assert r.status_code == 200 and r.json()["approval_code"] == "TECH-1"


async def test_a_returned_case_with_rejected_documents_is_resubmitted_after_replacing(app_client, enviado):
    e = enviado
    doc = next(d for d in await _docs(app_client, e) if d["field_key"] == "docs.panel_photo")
    await _revisar(app_client, e, doc["id"], "rejected", "No se ve el amperaje")
    r = await app_client.post(f"/api/v1/cases/{e['id']}/substatus",
                              json={"substatus": "returned", "reason": "Foto del panel"}, headers=e["admin"])
    assert r.status_code == 200, r.text
    r = await app_client.post(f"/api/v1/cases/{e['id']}/submit", headers=e["vendedor"])
    assert r.status_code == 400 and r.json()["code"] == "documents_rejected"
    nueva = await _subir(app_client, e["vendedor"], e["id"], "docs.panel_photo")
    form = (await app_client.get(f"/api/v1/cases/{e['id']}/form", headers=e["vendedor"])).json()
    docs_paso = {k: v for k, v in form["answers"].items() if k.startswith("docs.")}
    r = await app_client.put(f"/api/v1/cases/{e['id']}/steps/documents",
                             json={"answers": {**docs_paso, "docs.panel_photo": nueva}}, headers=e["vendedor"])
    assert r.status_code == 200, r.text
    r = await app_client.post(f"/api/v1/cases/{e['id']}/submit", headers=e["vendedor"])
    assert r.status_code == 200 and r.json()["substatus_code"] == "pending_review"
    panel = next(d for d in await _docs(app_client, e) if d["field_key"] == "docs.panel_photo")
    assert (panel["id"], panel["review_status"]) == (nueva, "pending")


async def test_admin_adds_an_extra_document(app_client, enviado):
    url = f"/api/v1/cases/{enviado['id']}/documents"
    r = await app_client.post(url, data={"label": " "}, files={"file": ("x.pdf", b"%PDF-1.7 x", "application/pdf")},
                              headers=enviado["admin"])
    assert r.status_code == 400
    r = await app_client.post(url, data={"label": "Factura de luz de septiembre"},
                              files={"file": ("luz.pdf", b"%PDF-1.7 x", "application/pdf")}, headers=enviado["admin"])
    assert r.status_code == 201, r.text
    extra = next(d for d in await _docs(app_client, enviado) if d["field_key"] == "__extra__")
    assert (extra["label"], extra["step_title"]) == ("Factura de luz de septiembre", "Documentos adicionales")
    r = await app_client.post(url, data={"label": "Falso"}, files={"file": ("a.pdf", jpeg_bytes()[:10] + b"MZ", "application/pdf")},
                              headers=enviado["admin"])
    assert r.status_code == 400


async def test_the_queue_lists_cases_with_documents_to_review(app_client, enviado):
    cola = (await app_client.get("/api/v1/documents/review-queue", headers=enviado["admin"])).json()
    assert [c["case_id"] for c in cola] == [enviado["id"]] and cola[0]["pending"] == 8
    for d in await _docs(app_client, enviado):
        await _revisar(app_client, enviado, d["id"], "accepted")
    assert (await app_client.get("/api/v1/documents/review-queue", headers=enviado["admin"])).json() == []
    r = await app_client.get("/api/v1/documents/review-queue", headers=enviado["vendedor"])
    assert r.status_code == 403


async def test_sensitive_files_need_permission(app_client, enviado, active_management_user):
    gerencia = await headers_for(app_client, "gerencia@acme-demo.com")
    docs = await _docs(app_client, enviado)
    id_foto = next(d for d in docs if d["field_key"] == "customer.id_photo")
    # Quien revisa la ve; Gerencia (lee todo pero no revisa ni tiene el permiso) no.
    assert (await app_client.get(f"/api/v1/case-files/{id_foto['id']}", headers=enviado["admin"])).status_code == 200
    r = await app_client.get(f"/api/v1/cases/{enviado['id']}/documents", headers=gerencia)
    if r.status_code == 200:
        assert all(d["field_key"] != "customer.id_photo" for d in r.json())
    assert (await app_client.get(f"/api/v1/case-files/{id_foto['id']}", headers=gerencia)).status_code in (403, 404)
