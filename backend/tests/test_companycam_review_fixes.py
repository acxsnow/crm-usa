"""Correcciones de la revisión: disco, correos entre organizaciones, reversa
estricta, fallo a mitad de la carga, miniaturas, org en la cola y el guarda
de programa."""
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app.modules.cases import documents, stages
from app.modules.cases import service as case_service
from app.modules.cases.models import Case, CaseFile
from app.modules.crm.models import Customer, DataConsent
from app.modules.imports.companycam import downloads
from app.modules.imports.companycam.loader import Loader
from app.modules.imports.companycam.rollback import rollback_import
from app.modules.imports.models import ImportItem
from app.modules.users.models import User, UserRole, UserStatus
from app.shared.files import storage
from scripts import companycam_download as cli
from tests.companycam_helpers import make_cache, project
from tests.field_helpers import headers_for, jpeg_bytes


async def _load(db, org_id, cache):
    return await Loader(db, org_id, cache, log=lambda *_: None).run()


async def _item(db, org, ref="1"):
    caso, _ = await case_service.import_case(db, organization_id=org, source="companycam", external_ref=ref,
                                             stage_code="on_hold", address_street="1 Main")
    it = ImportItem(organization_id=org, source="companycam", kind="photo", external_id=ref, case_id=caso.id,
                    remote_url="https://img.test/o.jpg", payload={"web_url": "https://img.test/w.jpg"},
                    status="pending")
    db.add(it)
    await db.commit()
    return caso, it


# --- O1 ---------------------------------------------------------------------

def test_cli_se_niega_fuera_de_app_storage(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.get_settings(), "STORAGE_DIR", str(tmp_path))
    assert cli.storage_allowed(False) is False and cli.storage_allowed(True) is True
    org = str(uuid.uuid4())
    assert cli.main(["run", "--org", org]) == 2
    assert cli.main(["purge", "--org", org, "--confirm"]) == 2
    assert "Me niego" in capsys.readouterr().out
    monkeypatch.setattr(cli.get_settings(), "STORAGE_DIR", "/app/storage")
    assert cli.storage_allowed(False) is True


@pytest.mark.asyncio
async def test_disco_casi_lleno_detiene_la_cola(db, seeded_org, monkeypatch):
    org = seeded_org["org"].id
    _, it = await _item(db, org)
    monkeypatch.setattr(downloads, "free_bytes", lambda: 100)
    llamadas = []

    def handler(req):
        llamadas.append(1)
        return httpx.Response(200, content=jpeg_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        r = await downloads.process_batch(db, org, http=http)
    assert r["disk_full"] == 1 and r["remaining"] == 0 and llamadas == []
    await db.refresh(it)
    assert it.status == "pending" and it.attempts == 0 and "Disco casi lleno" in it.last_error


@pytest.mark.asyncio
async def test_presupuesto_de_tiempo_suelta_lo_pendiente(db, seeded_org):
    org = seeded_org["org"].id
    _, it = await _item(db, org)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=jpeg_bytes()))) as http:
        r = await downloads.process_batch(db, org, http=http, budget_seconds=-1)
    assert r.get("downloaded", 0) == 0 and r["remaining"] == 1
    await db.refresh(it)
    assert it.status == "pending" and it.attempts == 0


# --- R6: miniatura ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_foto_guarda_miniatura_aparte_y_se_sirve(app_client, db, seeded_org, active_admin_user):
    org = seeded_org["org"].id
    caso, it = await _item(db, org)

    def handler(req):
        return httpx.Response(200, content=jpeg_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await downloads.process_batch(db, org, http=http)
    await db.refresh(it)
    thumb = it.payload["thumb_path"]
    assert thumb != (await db.get(CaseFile, it.case_file_id)).file_path and storage.absolute_path(thumb).exists()
    h = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.get(f"/api/v1/case-files/{it.case_file_id}/thumbnail", headers=h)
    assert r.status_code == 200 and r.content == storage.read_bytes(thumb)


# --- R4 / R3 / R2 ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_borrado_a_mitad_devuelve_gone(db, seeded_org):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as http:
        assert await downloads.process_item(db, uuid.uuid4(), http, None) == "gone"
    assert await downloads._fail(db, uuid.uuid4(), "x") == "gone"


@pytest.mark.asyncio
async def test_nombre_largo_se_trunca(db, seeded_org):
    org = seeded_org["org"].id
    caso, it = await _item(db, org)
    it.kind, it.remote_url = "document", "https://s3.test/d.pdf"
    it.payload = {"name": "N" * 400 + ".pdf", "content_type": "application/pdf", "project_id": "1"}
    await db.commit()
    from tests.field_helpers import pdf_bytes

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=pdf_bytes()))) as http:
        r = await downloads.process_batch(db, org, http=http)
    assert r["downloaded"] == 1
    f = (await db.execute(select(CaseFile))).scalar_one()
    assert len(f.original_filename) == 255


@pytest.mark.asyncio
async def test_cola_y_purge_respetan_la_organizacion(db, seeded_org, second_org):
    org, otra = seeded_org["org"].id, second_org["org"].id
    _, it = await _item(db, org, "1")
    _, it2 = await _item(db, otra, "2")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=jpeg_bytes()))) as http:
        r = await downloads.process_batch(db, org, http=http)
    assert r["downloaded"] == 1
    await db.refresh(it2)
    assert it2.status == "pending"
    assert await downloads.status(db, otra) == {"photo": {"pending": 1}}
    # purge: borra solo huérfanos de SU organización y tolera subcarpetas
    huerfano = uuid.uuid4()
    for o in (org, otra):
        storage.save_bytes(organization_id=o, subfolder=f"cases/{huerfano}/companycam/sub", filename="a.jpg", data=b"x")
    assert await downloads.purge(db, org) == 1
    assert not (storage.absolute_path(str(org)) / "cases" / str(huerfano)).exists()
    assert (storage.absolute_path(str(otra)) / "cases" / str(huerfano) / "companycam").exists()


# --- O2 ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correo_existente_en_otra_org_usa_sintetico(db, seeded_org, second_org, tmp_path):
    org, otra = seeded_org["org"], second_org["org"]
    db.add(User(organization_id=otra.id, email="carla@cc.test", email_display="carla@cc.test", full_name="Otra Carla",
                status=UserStatus.active))
    await db.commit()
    cache = make_cache(tmp_path)
    loader = Loader(db, org.id, cache, log=lambda *_: None)
    await loader.run()
    u = (await db.execute(select(User).where(User.organization_id == org.id, User.external_ref == "111"))).scalar_one()
    assert u.email == "cc-111@import.invalid"
    assert loader.created_users[0]["email_conflict"] is True
    assert "carla@cc.test" in (cache.reports_dir / "usuarios_creados-load.csv").read_text()


# --- O3 ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lo_importado_nace_con_updated_igual_a_created(db, seeded_org, tmp_path):
    await _load(db, seeded_org["org"].id, make_cache(tmp_path))
    for c in (await db.execute(select(Case))).scalars().all():
        assert c.updated_at == c.created_at
    for c in (await db.execute(select(Customer))).scalars().all():
        assert c.updated_at == c.created_at


@pytest.mark.asyncio
async def test_reasignar_vendedor_bloquea_la_reversa(db, seeded_org, active_salesperson_user, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    c = (await db.execute(select(Case).where(Case.external_ref == "1002"))).scalar_one()
    c.assigned_salesperson_id = active_salesperson_user.id
    await db.commit()
    r = await rollback_import(db, org.id, cache, log=lambda *_: None)
    assert r["cases_blocked"] == 1 and r["cases_deleted"] == 2
    assert "modificado" in (cache.reports_dir / "rollback_bloqueados.csv").read_text()


@pytest.mark.asyncio
async def test_cliente_con_constancia_o_actividad_bloquea(db, seeded_org, active_admin_user, tmp_path):
    from app.modules.crm.models import Activity, ActivityType

    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    cli = (await db.execute(select(Customer).where(Customer.external_ref == "contact:c1"))).scalar_one()
    db.add(DataConsent(organization_id=org.id, source="customer_update", customer_id=cli.id, document_version="1",
                       document_text="x", accepted_at=datetime.now(timezone.utc)))
    sin_contacto = (await db.execute(select(Customer).where(Customer.external_ref == "project:1002"))).scalar_one()
    db.add(Activity(organization_id=org.id, type=ActivityType.note, subject="n", owner_user_id=active_admin_user.id,
                    customer_id=sin_contacto.id))
    await db.commit()
    r = await rollback_import(db, org.id, cache, log=lambda *_: None)
    assert r["cases_deleted"] == 3 and r["customers_deleted"] == 1
    texto = (cache.reports_dir / "rollback_bloqueados.csv").read_text()
    assert "data_consents" in texto and "activities" in texto


# --- O4 ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallo_a_mitad_no_deja_cuentas_ni_usuarios_de_mas(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    malo = {"id": "2001", "creator_id": "444", "creator_type": "User", "creator_name": "Pepe Malo",
            "created_at": "basura"}
    cache.write_projects([cache.projects()[0], malo, project(2002, creator=("555", "Nuevo Tipo"))])
    for pid in ("2001", "2002"):
        for sub in ("photos", "comments", "documents", "checklists"):
            cache.write_json(cache.project_dir(pid) / f"{sub}.json", [])
    loader = Loader(db, org.id, cache, log=lambda *_: None)
    original = loader._items

    async def items(case, p, data):
        if str(p["id"]) == "2001":
            raise RuntimeError("boom")
        return await original(case, p, data)

    loader._items = items
    r = await loader.run()
    assert r["errors"] == 1 and r["cases_created"] == 2 and r["creators_created"] == 2
    assert [e["project_id"] for e in loader.errors] == ["2001"]
    assert (await db.execute(select(func.count(Case.id)))).scalar_one() == 2
    refs = set((await db.execute(select(User.external_ref).where(User.source == "companycam"))).scalars().all())
    assert refs == {"111", "555"}
    assert sorted(u["external_ref"] for u in loader.created_users) == ["111", "555"]


# --- R7 ---------------------------------------------------------------------------

@pytest.fixture
def _guardas():
    documents._reset_for_tests()
    documents.register()
    yield
    stages.clear_guards()
    stages.clear_effects()
    documents._reset_for_tests()


@pytest.mark.asyncio
async def test_importado_sin_programa_no_sale_de_en_espera(app_client, db, seeded_org, active_admin_user, tmp_path,
                                                           _guardas):
    await _load(db, seeded_org["org"].id, make_cache(tmp_path))
    caso = (await db.execute(select(Case).where(Case.external_ref == "1001"))).scalar_one()
    h = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.post(f"/api/v1/cases/{caso.id}/transition", json={"to_stage": "approved"}, headers=h)
    assert r.status_code == 422 or r.status_code == 400, r.text
    assert r.json()["code"] == "imported_program_required"
    await db.refresh(caso)
    assert caso.stage_code == "on_hold"
