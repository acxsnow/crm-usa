"""Carga desde la caché, reversa y reportes."""
import pytest
from sqlalchemy import func, select

from app.modules.cases.models import Case, CaseFile, CaseNote, CaseStageEvent
from app.modules.crm.models import Customer, DataConsent
from app.modules.imports.companycam.loader import ImportAborted, Loader
from app.modules.imports.companycam.rollback import rollback_import
from app.modules.imports.models import ImportItem
from app.modules.users.models import User, UserStatus
from tests.companycam_helpers import make_cache, project


async def _count(db, model):
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _load(db, org_id, cache, **kw):
    run = {k: kw.pop(k) for k in ("only", "limit") if k in kw}
    return await Loader(db, org_id, cache, log=lambda *_: None, **kw).run(**run)


@pytest.mark.asyncio
async def test_carga_tres_proyectos(db, seeded_org, active_salesperson_user, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    r = await _load(db, org.id, cache)
    assert r["cases_created"] == 3 and r["stage_on_hold"] == 1 and r["stage_closed"] == 2
    casos = {c.external_ref: c for c in (await db.execute(select(Case))).scalars().all()}
    assert casos["1001"].stage_code == "on_hold" and casos["1001"].case_number == "CC-1001"
    assert casos["1002"].stage_code == "closed" and "archivado" in casos["1002"].stage_reason
    assert casos["1003"].stage_code == "closed" and "eliminado" in casos["1003"].stage_reason
    assert casos["1001"].address_state == "CA" and casos["1001"].address_unit == "Spc 14"
    # un evento por expediente, todos marcados como importados
    eventos = (await db.execute(select(CaseStageEvent))).scalars().all()
    assert len(eventos) == 3 and all(e.imported for e in eventos)
    # cliente con contacto, marcado de origen y sin constancia de consentimiento
    cli = (await db.execute(select(Customer).where(Customer.external_ref == "contact:c1"))).scalar_one()
    assert cli.source == "companycam" and cli.legal_name == "Marge Simpson" and cli.email == "Marge@Example.com"
    assert await _count(db, DataConsent) == 0
    # notas, fotos y documentos pendientes
    assert r["notes_notepad"] == 3 and r["notes_comment"] == 1 and r["notes_checklist"] == 1
    nota = (await db.execute(select(CaseNote).where(CaseNote.kind == "notepad", CaseNote.case_id == casos["1001"].id))).scalar_one()
    assert nota.body.startswith("Proyecto CompanyCam: Casa Marge · creado por Carla Creadora")
    items = (await db.execute(select(ImportItem).where(ImportItem.kind != "project"))).scalars().all()
    assert len(items) == 3 and all(i.status == "pending" for i in items)
    foto = next(i for i in items if i.external_id == "501")
    assert foto.payload["tags"] == ["Front Side"]
    assert await _count(db, CaseFile) == 0


@pytest.mark.asyncio
async def test_usuario_creador_nuevo_inactivo_y_match_por_correo(db, seeded_org, active_salesperson_user, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    r = await _load(db, org.id, cache)
    assert r["creators_created"] == 1 and r["creators_matched"] == 1
    nuevo = (await db.execute(select(User).where(User.external_ref == "111"))).scalar_one()
    assert nuevo.status == UserStatus.inactive and nuevo.source == "companycam"
    assert nuevo.email == "carla@cc.test" and nuevo.full_name == "Carla Creadora"
    assert [ur.role.code for ur in nuevo.roles] == ["salesperson"] and nuevo.password_hash
    casos = {c.external_ref: c for c in (await db.execute(select(Case))).scalars().all()}
    assert casos["1001"].assigned_salesperson_id == nuevo.id
    assert casos["1003"].assigned_salesperson_id == active_salesperson_user.id  # por correo
    # el límite de usuarios activos no se consume
    from app.modules.users.service import get_active_user_count

    assert await get_active_user_count(db, org.id) == 1


@pytest.mark.asyncio
async def test_creador_sin_correo_usa_correo_sintetico_y_match_por_nombre(db, seeded_org, active_salesperson_user,
                                                                         tmp_path):
    cache = make_cache(tmp_path, with_users=False)
    await _load(db, seeded_org["org"].id, cache)
    por_ref = {u.external_ref: u for u in (await db.execute(select(User).where(User.source == "companycam"))).scalars().all()}
    assert por_ref["111"].email == "cc-111@import.invalid" and por_ref["111"].full_name == "Carla Creadora"
    assert "222" not in por_ref  # «Vic Vendedor» ya existe: se une por nombre exacto
    caso = (await db.execute(select(Case).where(Case.external_ref == "1003"))).scalar_one()
    assert caso.assigned_salesperson_id == active_salesperson_user.id


@pytest.mark.asyncio
async def test_relanzar_no_duplica_ni_pisa(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    caso = (await db.execute(select(Case).where(Case.external_ref == "1001"))).scalar_one()
    caso.address_city = "Editada"
    await db.commit()
    antes = {m: await _count(db, m) for m in (Case, Customer, CaseNote, ImportItem, User, CaseStageEvent)}
    r = await _load(db, org.id, cache)
    assert r["cases_existing"] == 3 and "cases_created" not in r
    assert antes == {m: await _count(db, m) for m in antes}
    await db.refresh(caso)
    assert caso.address_city == "Editada"


@pytest.mark.asyncio
async def test_dry_run_no_deja_filas(db, seeded_org, tmp_path):
    cache = make_cache(tmp_path)
    r = await _load(db, seeded_org["org"].id, cache, dry_run=True)
    assert r["cases_created"] == 3
    for modelo in (Case, Customer, CaseNote, ImportItem, CaseStageEvent):
        assert await _count(db, modelo) == 0
    assert (await db.execute(select(func.count(User.id)).where(User.source == "companycam"))).scalar_one() == 0


@pytest.mark.asyncio
async def test_filtros_only_y_limit(db, seeded_org, tmp_path):
    cache = make_cache(tmp_path)
    r = await _load(db, seeded_org["org"].id, cache, only={"1002"})
    assert r["cases_created"] == 1
    r = await _load(db, seeded_org["org"].id, cache, limit=1)
    assert r["cases_created"] == 1 and await _count(db, Case) == 2


@pytest.mark.asyncio
async def test_aborta_si_la_organizacion_no_existe(db, tmp_path):
    import uuid

    with pytest.raises(ImportAborted):
        await _load(db, uuid.uuid4(), make_cache(tmp_path))


@pytest.mark.asyncio
async def test_aislamiento_entre_organizaciones(db, seeded_org, second_org, tmp_path):
    cache = make_cache(tmp_path)
    await _load(db, seeded_org["org"].id, cache)
    await _load(db, second_org["org"].id, cache)
    por_org = (await db.execute(select(Case.organization_id, func.count()).group_by(Case.organization_id))).all()
    assert dict(por_org) == {seeded_org["org"].id: 3, second_org["org"].id: 3}
    # los usuarios y clientes creados son de cada organización
    u = (await db.execute(select(User).where(User.source == "companycam"))).scalars().all()
    assert {x.organization_id for x in u} == {seeded_org["org"].id, second_org["org"].id}


@pytest.mark.asyncio
async def test_cliente_existente_se_reutiliza_sin_modificarlo(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    existente = Customer(organization_id=org.id, legal_name="Marge S.", email="marge@example.com", notes="No tocar")
    db.add(existente)
    await db.commit()
    await _load(db, org.id, make_cache(tmp_path))
    caso = (await db.execute(select(Case).where(Case.external_ref == "1001"))).scalar_one()
    assert caso.customer_id == existente.id
    await db.refresh(existente)
    assert existente.legal_name == "Marge S." and existente.notes == "No tocar" and existente.source == "app"


@pytest.mark.asyncio
async def test_ambiguo_crea_cliente_nuevo_y_reporta(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    db.add_all([Customer(organization_id=org.id, legal_name="A", email="marge@example.com"),
                Customer(organization_id=org.id, legal_name="B", email="marge@example.com")])
    await db.commit()
    cache = make_cache(tmp_path)
    r = await _load(db, org.id, cache)
    assert r["customers_ambiguous"] == 1 and r["customers_created"] == 3
    assert (cache.reports_dir / "ambiguos-load.csv").exists()


@pytest.mark.asyncio
async def test_rollback_borra_intactos_y_respeta_lo_tocado(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    # alguien trabajó el expediente 1001: se le asigna programa
    from app.modules.programs import service as programs

    await programs.install_defaults(db, organization_id=org.id)
    prog = (await programs.list_programs(db, organization_id=org.id))[0]
    c1 = (await db.execute(select(Case).where(Case.external_ref == "1001"))).scalar_one()
    c1.program_id = prog.id
    await db.commit()
    r = await rollback_import(db, org.id, cache, log=lambda *_: None)
    assert r["cases_deleted"] == 2 and r["cases_blocked"] == 1
    assert await _count(db, Case) == 1
    assert (cache.reports_dir / "rollback_bloqueados.csv").exists()
    # el cliente de 1001 sigue (su expediente quedó); los usuarios con expedientes también
    assert (await db.execute(select(func.count(Customer.id)).where(Customer.source == "companycam"))).scalar_one() == 1
    assert await _count(db, CaseNote) == 3 and (await db.execute(
        select(func.count(ImportItem.id)).where(ImportItem.case_id == c1.id))).scalar_one() == 4
    # el expediente bloqueado conserva su historial
    assert await _count(db, CaseStageEvent) == 1


@pytest.mark.asyncio
async def test_rollback_total_deja_todo_limpio(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    r = await rollback_import(db, org.id, cache, log=lambda *_: None)
    assert r == {"cases_deleted": 3, "cases_blocked": 0, "customers_deleted": 3, "users_deleted": 2}
    for modelo in (Case, CaseNote, ImportItem, CaseStageEvent):
        assert await _count(db, modelo) == 0
    assert (await db.execute(select(func.count(User.id)).where(User.source == "companycam"))).scalar_one() == 0


@pytest.mark.asyncio
async def test_rollback_respeta_archivos_subidos_por_personas(db, seeded_org, active_admin_user, tmp_path):
    org = seeded_org["org"]
    cache = make_cache(tmp_path)
    await _load(db, org.id, cache)
    c = (await db.execute(select(Case).where(Case.external_ref == "1002"))).scalar_one()
    db.add(CaseFile(organization_id=org.id, case_id=c.id, field_key="__extra__", file_path="x", label="Subido",
                    uploaded_by_user_id=active_admin_user.id))
    await db.commit()
    r = await rollback_import(db, org.id, cache, log=lambda *_: None)
    assert r["cases_deleted"] == 2 and r["cases_blocked"] == 1
    assert "archivos subidos" in (cache.reports_dir / "rollback_bloqueados.csv").read_text()
