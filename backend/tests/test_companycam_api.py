"""Lo importado visto desde la API: programa editable, archivos, notas, tablero,
cola de revisión, clientes y reportes."""
import httpx
import pytest
from sqlalchemy import select

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case, CaseFile, CaseStageEvent
from app.modules.crm.models import Customer
from app.modules.imports.companycam import downloads
from app.modules.imports.companycam.loader import Loader
from app.modules.programs import service as programs
from tests.companycam_helpers import make_cache
from tests.field_helpers import headers_for, jpeg_bytes


@pytest.fixture(autouse=True)
def _clean():
    yield
    stages.clear_guards()
    stages.clear_effects()


async def _cargar(db, org_id, tmp_path):
    await Loader(db, org_id, make_cache(tmp_path), log=lambda *_: None).run()
    return {c.external_ref: c for c in (await db.execute(select(Case))).scalars().all()}


async def _descargar(db, org):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=jpeg_bytes()))) as http:
        await downloads.process_batch(db, org, http=http)


async def _programa(db, org_id):
    await programs.install_defaults(db, organization_id=org_id)
    return next(p for p in await programs.list_programs(db, organization_id=org_id) if p.code == "TECH_CLEAN_CA")


@pytest.mark.asyncio
async def test_administracion_elige_programa_de_un_importado(app_client, db, seeded_org, active_admin_staff_user,
                                                            tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    prog = await _programa(db, seeded_org["org"].id)
    h = await headers_for(app_client, "admin-staff@acme-demo.com")
    r = await app_client.put(f"/api/v1/cases/{casos['1001'].id}/imported-program",
                             json={"program_id": str(prog.id)}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["program_id"] == str(prog.id) and r.json()["stage_code"] == "on_hold"
    assert r.json()["source"] == "companycam" and r.json()["external_ref"] == "1001"
    # también sirve en uno archivado (closed)
    r = await app_client.put(f"/api/v1/cases/{casos['1002'].id}/imported-program",
                             json={"program_id": str(prog.id)}, headers=h)
    assert r.status_code == 200
    from app.shared.audit_models import AuditEvent

    acciones = (await db.execute(select(AuditEvent.action).where(AuditEvent.entity_id == str(casos["1001"].id)))).scalars().all()
    assert "cases.program_selected" in acciones


@pytest.mark.asyncio
async def test_vendedor_no_elige_programa_importado(app_client, db, seeded_org, active_salesperson_user, tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    prog = await _programa(db, seeded_org["org"].id)
    h = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.put(f"/api/v1/cases/{casos['1001'].id}/imported-program",
                             json={"program_id": str(prog.id)}, headers=h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_expediente_normal_en_espera_sigue_bloqueado(app_client, db, seeded_org, active_admin_staff_user,
                                                          active_admin_user):
    org = seeded_org["org"].id
    prog = await _programa(db, org)
    normal = await case_service.create_case(db, organization_id=org, actor_id=None, stage_code="new_prospect",
                                            address_street="5 Native St")
    normal = await case_service.transition(db, case=normal, to_stage="pending_approval", actor_id=None,
                                           actor_permissions=stages.SYSTEM_ACTOR)
    normal = await case_service.transition(db, case=normal, to_stage="on_hold", actor_id=None,
                                           actor_permissions=stages.SYSTEM_ACTOR)
    h = await headers_for(app_client, "admin-staff@acme-demo.com")
    r = await app_client.put(f"/api/v1/cases/{normal.id}/imported-program", json={"program_id": str(prog.id)},
                             headers=h)
    assert r.status_code == 409 and r.json()["code"] == "program_locked"
    admin = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.put(f"/api/v1/cases/{normal.id}/program", json={"program_id": str(prog.id)}, headers=admin)
    assert r.status_code == 409 and r.json()["code"] == "program_locked"


@pytest.mark.asyncio
async def test_programa_de_otra_organizacion_da_404(app_client, db, seeded_org, second_org_admin_user, tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    prog = await _programa(db, seeded_org["org"].id)
    h = await headers_for(app_client, "admin@otra-demo.com")
    r = await app_client.put(f"/api/v1/cases/{casos['1001'].id}/imported-program",
                             json={"program_id": str(prog.id)}, headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_imported_files_y_notes_paginados(app_client, db, seeded_org, active_admin_user, tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    await _descargar(db, seeded_org["org"].id)
    h = await headers_for(app_client, "admin@acme-demo.com")
    cid = casos["1001"].id
    r = await app_client.get(f"/api/v1/cases/{cid}/imported-files?limit=2", headers=h)
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "2"
    fotos = r.json()
    assert {f["kind"] for f in fotos} == {"photo"} and all(f["author_name"] == "Carla Creadora" for f in fotos)
    assert any(f["tags"] == ["Front Side"] for f in fotos) and fotos[0]["latitude"] == 34.2
    # el binario sale por la ruta existente
    b = await app_client.get(f"/api/v1/case-files/{fotos[0]['id']}", headers=h)
    assert b.status_code == 200 and b.content[:3] == b"\xff\xd8\xff"
    n = await app_client.get(f"/api/v1/cases/{cid}/notes", headers=h)
    assert n.headers["X-Total-Count"] == "3"
    assert {x["kind"] for x in n.json()} == {"notepad", "comment", "checklist"}
    assert n.json()[0]["body"].startswith("Proyecto CompanyCam")
    # paginado de verdad
    p2 = await app_client.get(f"/api/v1/cases/{cid}/imported-files?limit=1&offset=1", headers=h)
    assert len(p2.json()) == 1 and p2.json()[0]["id"] != r.json()[0]["id"]


@pytest.mark.asyncio
async def test_archivos_importados_otra_org_y_ajeno(app_client, db, seeded_org, second_org_admin_user,
                                                    active_salesperson_user, tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    cid = casos["1001"].id
    otra = await headers_for(app_client, "admin@otra-demo.com")
    assert (await app_client.get(f"/api/v1/cases/{cid}/imported-files", headers=otra)).status_code == 404
    assert (await app_client.get(f"/api/v1/cases/{cid}/notes", headers=otra)).status_code == 404
    vend = await headers_for(app_client, "vendedor@acme-demo.com")  # no es su expediente
    r = await app_client.get(f"/api/v1/cases/{cid}/notes", headers=vend)
    assert r.status_code in (200, 404)
    ajeno = casos["1002"]  # asignado al usuario creado, no al vendedor
    assert (await app_client.get(f"/api/v1/cases/{ajeno.id}/notes", headers=vend)).status_code == 404


@pytest.mark.asyncio
async def test_importados_no_entran_a_la_cola_de_revision(app_client, db, seeded_org, active_admin_staff_user,
                                                          tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    await _descargar(db, seeded_org["org"].id)
    # aunque quedaran como pendientes, la cola los ignora
    for f in (await db.execute(select(CaseFile))).scalars().all():
        f.review_status = "pending"
    await db.commit()
    h = await headers_for(app_client, "admin-staff@acme-demo.com")
    r = await app_client.get("/api/v1/documents/review-queue", headers=h)
    assert r.status_code == 200 and r.json() == []


@pytest.mark.asyncio
async def test_tablero_filtra_por_origen(app_client, db, seeded_org, active_admin_user, tmp_path):
    org = seeded_org["org"].id
    await _cargar(db, org, tmp_path)
    await case_service.create_case(db, organization_id=org, actor_id=None, stage_code="new_prospect",
                                   address_street="Nativa 1")
    h = await headers_for(app_client, "admin@acme-demo.com")

    async def numeros(q=""):
        cols = (await app_client.get(f"/api/v1/case-board{q}", headers=h)).json()
        return sorted(c["case_number"] for col in cols for c in col["cases"])

    todos = await numeros()
    assert len(todos) == 4
    assert await numeros("?source=companycam") == ["CC-1001", "CC-1002", "CC-1003"]
    assert len(await numeros("?source=app")) == 1
    cols = (await app_client.get("/api/v1/case-board?source=companycam", headers=h)).json()
    assert any(c["source"] == "companycam" for col in cols for c in col["cases"])


@pytest.mark.asyncio
async def test_cliente_importado_expone_origen_y_sin_consentimiento(app_client, db, seeded_org, active_admin_user,
                                                                    tmp_path):
    await _cargar(db, seeded_org["org"].id, tmp_path)
    cli = (await db.execute(select(Customer).where(Customer.source == "companycam"))).scalars().first()
    h = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.get(f"/api/v1/customers/{cli.id}", headers=h)
    assert r.status_code == 200 and r.json()["source"] == "companycam" and r.json()["has_consent"] is False
    lista = (await app_client.get("/api/v1/customers", headers=h)).json()
    assert all(c["has_consent"] is False and c["source"] == "companycam" for c in lista)
    t = (await app_client.get(f"/api/v1/customers/{cli.id}/timeline", headers=h)).json()
    assert t["customer"]["has_consent"] is False and t["cases"][0]["source"] == "companycam"


@pytest.mark.asyncio
async def test_reportes_no_cambian_con_lo_importado(app_client, db, seeded_org, active_admin_user, tmp_path):
    org = seeded_org["org"].id
    h = await headers_for(app_client, "admin@acme-demo.com")
    await case_service.create_case(db, organization_id=org, actor_id=None, stage_code="new_prospect",
                                   address_street="Nativa 1")
    antes = (await app_client.get("/api/v1/reports/commercial", headers=h)).json()
    ops_antes = (await app_client.get("/api/v1/reports/operations", headers=h)).json()
    await _cargar(db, org, tmp_path)
    despues = (await app_client.get("/api/v1/reports/commercial", headers=h)).json()
    assert antes["kpis"] == despues["kpis"]
    etapas = next(s for s in despues["sections"] if s["title"].startswith("Expedientes por etapa"))
    previas = next(s for s in antes["sections"] if s["title"].startswith("Expedientes por etapa"))
    assert etapas["rows"][:-1] == previas["rows"] and etapas["rows"][-1] == ["Importados de CompanyCam", 3]
    assert (await app_client.get("/api/v1/reports/operations", headers=h)).json() == ops_antes
    from sqlalchemy import func

    assert (await db.execute(select(func.count(CaseStageEvent.id)).where(CaseStageEvent.imported.is_(True)))).scalar_one() == 3


@pytest.mark.asyncio
async def test_una_visita_no_se_une_a_un_importado(app_client, db, seeded_org, active_salesperson_user, tmp_path):
    casos = await _cargar(db, seeded_org["org"].id, tmp_path)
    h = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.post("/api/v1/visits", json={"result": "opened", "address_street": "7722 Cleon Ave",
                                                     "address_unit": "Spc 14", "address_city": "Los Angeles",
                                                     "address_zip": "91352"}, headers=h)
    assert r.status_code == 201 and r.json()["outcome"] == "created"
    assert r.json()["case"]["id"] != str(casos["1001"].id)
