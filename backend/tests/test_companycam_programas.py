"""Migración de CompanyCam con lo que pidió el cliente el 28 nov 2026: el
programa sale de las etiquetas del proyecto (pueden ser varios), las ventas en
proceso de las cuentas «Vendedores» entran como prospecto y una cuenta se le
pasa a un usuario real."""
import pytest
from sqlalchemy import select

from app.modules.cases import service as case_service
from app.modules.cases.models import Case, CaseNote, CaseProgram, Program
from app.modules.imports.companycam import mapping as m
from app.modules.imports.companycam.cache import ExportCache
from app.modules.imports.companycam.loader import ImportAborted, Loader
from app.modules.programs import service as programs
from tests.companycam_helpers import project


def _labels(*nombres):
    return [{"id": str(i), "display_value": n, "value": n.lower(), "tag_type": "project"}
            for i, n in enumerate(nombres)]


def _cache(tmp_path, proyectos: dict) -> ExportCache:
    """proyectos: {proyecto: etiquetas}"""
    cache = ExportCache(tmp_path / "export")
    cache.write_projects(list(proyectos))
    cache.write_json(cache.root / "users.json", [])
    cache.write_json(cache.root / "tags.json", [])
    cache.write_json(cache.root / "tag_photos.json", {})
    for p, etiquetas in proyectos.items():
        d = cache.project_dir(p["id"])
        for sub in ("photos", "comments", "documents", "checklists"):
            cache.write_json(d / f"{sub}.json", [])
        cache.write_json(d / "labels.json", etiquetas)
    return cache


class _P(dict):
    __hash__ = object.__hash__


def _p(pid, **kw):
    return _P(project(pid, street=f"{pid} Main St", **kw))


async def _load(db, org_id, cache, **kw):
    return await Loader(db, org_id, cache, log=lambda *_: None, **kw).run()


def test_programas_por_etiqueta_con_el_principal_primero():
    assert m.programs_from_labels(_labels("GO ZERO SUBMITED", "TECH PROGRAM", "ONTARIO")) == ["TECH_CLEAN_CA",
                                                                                               "GOZERO"]
    assert m.programs_from_labels(_labels("HEERA PROGRAM", "Needs Go Zero Application")) == ["HEERA", "GOZERO"]
    assert m.programs_from_labels(_labels("LADWP")) == ["LADWP"]
    assert m.programs_from_labels(_labels("PEDESTALES")) == ["PEDESTALES"]
    assert m.programs_from_labels(_labels("Quality Services")) == ["QUALITY_SERVICES"]
    assert m.programs_from_labels(_labels("PROYECTO COMPLETO", "WARREN PARK")) == []


def test_venta_de_vendedores_es_prospecto_y_lo_archivado_se_cierra():
    assert m.map_stage(project(1, creator=("9", "Vendedores  4")))[0] == "new_prospect"
    assert m.map_stage(project(1, creator=("9", "Vendedores 1")))[0] == "new_prospect"
    assert m.map_stage(project(1, creator=("9", "Vendedores  4"), archived=True))[0] == "closed"
    assert m.map_stage(project(1, creator=("9", "Mariana Y Myriam")))[0] == "on_hold"


@pytest.mark.asyncio
async def test_carga_programas_y_prospectos(db, seeded_org, active_salesperson_user, tmp_path):
    org = seeded_org["org"]
    await programs.install_defaults(db, organization_id=org.id)
    await db.commit()
    tech_gz = _p(2001, archived=True)
    heera = _p(2002, archived=True)
    venta = _p(2003, creator=("444", "Vendedores  4"))
    otra = _p(2004, creator=("555", "Vendedores 1"))
    sin = _p(2005, creator=("666", "Ashley McDonald"))
    cache = _cache(tmp_path, {tech_gz: _labels("TECH PROGRAM", "GO ZERO SUBMITED", "ONTARIO"),
                              heera: _labels("HEERA PROGRAM"), venta: [], otra: [], sin: _labels("PEDESTALES")})
    r = await _load(db, org.id, cache, creator_emails={"Vendedores 4": active_salesperson_user.email})
    assert r["cases_created"] == 5 and r["stage_new_prospect"] == 2 and r["cases_multi_program"] == 1
    assert r["creators_reassigned"] == 1
    codigos = {p.id: p.code for p in (await db.execute(select(Program))).scalars()}
    casos = {c.external_ref: c for c in (await db.execute(select(Case))).scalars()}

    async def programas(ref):
        filas = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == casos[ref].id))).scalars().all()
        return {codigos[f.program_id]: f.is_primary for f in filas}

    assert codigos[casos["2001"].program_id] == "TECH_CLEAN_CA" and casos["2001"].program_version_id
    assert await programas("2001") == {"TECH_CLEAN_CA": True, "GOZERO": False}
    assert await programas("2002") == {"HEERA": True}
    assert await programas("2005") == {"PEDESTALES": True} and casos["2005"].stage_code == "on_hold"
    # La venta de «Vendedores 4» es de la vendedora real, como prospecto y sin programa.
    assert casos["2003"].stage_code == "new_prospect" and casos["2003"].program_id is None
    assert casos["2003"].assigned_salesperson_id == active_salesperson_user.id
    assert casos["2004"].stage_code == "new_prospect"
    assert casos["2004"].assigned_salesperson_id != active_salesperson_user.id
    # Las etiquetas quedan como nota.
    nota = (await db.execute(select(CaseNote).where(CaseNote.case_id == casos["2001"].id,
                                                    CaseNote.kind == "labels"))).scalar_one()
    assert "TECH PROGRAM" in nota.body and "ONTARIO" in nota.body


@pytest.mark.asyncio
async def test_usuario_destino_que_no_existe_aborta(db, seeded_org, tmp_path):
    org = seeded_org["org"]
    await programs.install_defaults(db, organization_id=org.id)
    await db.commit()
    cache = _cache(tmp_path, {_p(2010, creator=("444", "Vendedores  4")): []})
    with pytest.raises(ImportAborted):
        await _load(db, org.id, cache, creator_emails={"Vendedores 4": "nadie@ejemplo.com"})
    assert (await db.execute(select(Case))).first() is None


@pytest.mark.asyncio
async def test_cambiar_el_principal_conserva_los_adicionales(db, seeded_org):
    org = seeded_org["org"]
    await programs.install_defaults(db, organization_id=org.id)
    caso, _ = await case_service.import_case(db, organization_id=org.id, source="companycam", external_ref="77",
                                             stage_code="on_hold")
    ids = {p.code: p.id for p in (await db.execute(select(Program))).scalars()}
    await case_service.set_case_programs(db, caso, primary_id=ids["TECH_CLEAN_CA"], additional_ids=[ids["GOZERO"]])
    await case_service.set_case_programs(db, caso, primary_id=ids["HEERA"],
                                         additional_ids=[ids["GOZERO"]])
    filas = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == caso.id))).scalars().all()
    assert {f.program_id: f.is_primary for f in filas} == {ids["HEERA"]: True, ids["GOZERO"]: False}
    assert caso.program_id == ids["HEERA"]
