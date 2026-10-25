"""Visitas fallidas, límite de reagendamiento y cancelación de la obra (D-001).

El camino que faltaba en campo (lo pidió José el 25 oct): el técnico llega y el
cliente no está. Deja escrito qué pasó y la obra vuelve a agendarse; con un
límite que fija cada organización, y al llegar a él decide Administración:
otro intento o cancelar. Cancelar exige motivo y resolver el material.
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.cases.models import Case
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"


def _hoy_utc() -> date:
    # La organización de prueba está en UTC (ver test_technician_rotation).
    return datetime.now(timezone.utc).date()


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _liberar(app_client, headers, project_id, tecnico_id, *, esperado=200):
    r = await app_client.patch(f"{API}/projects/{project_id}/schedule", json={
        "technician_user_id": str(tecnico_id), "scheduled_date": _hoy_utc().isoformat()}, headers=headers)
    assert r.status_code == esperado, r.text
    return r.json()


async def _fallida(app_client, headers, project_id, **extra):
    datos = {"reason_code": "customer_absent", "notes": "Toqué tres veces y nadie abrió", **extra}
    return await app_client.post(f"{API}/projects/{project_id}/failed-visits", json=datos, headers=headers)


@pytest.fixture
async def obra(app_client, db, seeded_org, login, active_admin_staff_user, active_technician_user):
    oficina = await login(active_admin_staff_user.email)
    tecnico = await login(active_technician_user.email)
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, project.id, active_technician_user.id)
    return {"case": case, "project": project, "oficina": oficina, "tecnico": tecnico,
            "tecnico_id": active_technician_user.id}


async def _etapa(db, case_id) -> tuple[str, str | None]:
    # Relee solo el expediente: `expire_all()` expiraría también al usuario que
    # la app comparte con la prueba.
    case = (await db.execute(select(Case).where(Case.id == case_id)
                             .execution_options(populate_existing=True))).scalar_one()
    return case.stage_code, case.substatus_code


# ---------------------------------------------------------------------------
# Visita fallida
# ---------------------------------------------------------------------------

async def test_el_tecnico_registra_la_visita_fallida_y_la_obra_vuelve_a_por_agendar(app_client, db, obra):
    r = await _fallida(app_client, obra["tecnico"], obra["project"].id, latitude=33.45, longitude=-112.07)
    assert r.status_code == 201, r.text
    assert r.json() == {"failed_visits": 1, "limit": 2, "limit_reached": False, "extra_visits_authorized": 0}

    p = (await app_client.get(f"{API}/projects/{obra['project'].id}", headers=obra["oficina"])).json()
    assert (p["scheduled_date"], p["status"], p["failed_visits_count"]) == (None, "planning", 1)
    # Sigue siendo su obra: la oficina solo pone la nueva fecha.
    assert p["primary_technician_user_id"] == str(obra["tecnico_id"])
    # El expediente no cambia de etapa: solo su sub-estado.
    assert await _etapa(db, obra["case"].id) == ("ready_to_install", "visit_failed")

    historial = (await app_client.get(f"{API}/projects/{obra['project'].id}/failed-visits",
                                      headers=obra["tecnico"])).json()
    assert len(historial) == 1
    assert historial[0]["reason_label"] == "El cliente no estaba"
    assert historial[0]["scheduled_date"] == _hoy_utc().isoformat()
    assert historial[0]["technician_name"] == historial[0]["recorded_by_name"] == "Tom Technician"
    assert (historial[0]["latitude"], historial[0]["longitude"]) == (33.45, -112.07)

    # Reagendar vuelve a dejarla agendada.
    await _liberar(app_client, obra["oficina"], obra["project"].id, obra["tecnico_id"])
    assert await _etapa(db, obra["case"].id) == ("ready_to_install", "install_scheduled")


@pytest.mark.parametrize("datos,codigo", [
    ({"notes": ""}, "visit_notes_required"),
    ({"notes": "   no "}, "visit_notes_required"),
    ({"reason_code": "se_me_olvido"}, "unknown_visit_reason"),
])
async def test_la_visita_fallida_exige_motivo_del_catalogo_y_nota(app_client, obra, datos, codigo):
    r = await _fallida(app_client, obra["tecnico"], obra["project"].id, **datos)
    assert (r.status_code, r.json()["code"]) == (400, codigo), r.text


async def test_sin_visita_agendada_no_hay_visita_fallida(app_client, obra):
    assert (await _fallida(app_client, obra["tecnico"], obra["project"].id)).status_code == 201
    r = await _fallida(app_client, obra["tecnico"], obra["project"].id)
    assert (r.status_code, r.json()["code"]) == (409, "no_scheduled_visit")


async def test_solo_el_responsable_o_la_oficina_registran_la_visita_fallida(
        app_client, db, seeded_org, login, obra, active_salesperson_user, second_org_admin_user):
    from tests.test_technician_rotation import _tecnico

    otro = await _tecnico(db, seeded_org, "Otro Tecnico")
    r = await _fallida(app_client, await login(otro.email), obra["project"].id)
    assert r.status_code == 404  # ni sabe que existe
    r = await _fallida(app_client, await login(active_salesperson_user.email), obra["project"].id)
    assert r.status_code == 403  # sin `checklists.complete`
    r = await _fallida(app_client, await login(second_org_admin_user.email), obra["project"].id)
    assert r.status_code == 404  # otra organización
    assert (await _fallida(app_client, obra["oficina"], obra["project"].id)).status_code == 201


# ---------------------------------------------------------------------------
# Límite de reagendamiento
# ---------------------------------------------------------------------------

async def test_al_llegar_al_limite_no_se_agenda_hasta_que_administracion_decida(app_client, obra):
    pid = obra["project"].id
    assert (await _fallida(app_client, obra["tecnico"], pid)).status_code == 201
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"])
    r = await _fallida(app_client, obra["tecnico"], pid)
    assert r.json()["limit_reached"] is True

    r = await app_client.patch(f"{API}/projects/{pid}/schedule", json={
        "technician_user_id": str(obra["tecnico_id"]), "scheduled_date": _hoy_utc().isoformat()},
        headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "visit_limit_reached")

    # El técnico no autoriza intentos; la oficina sí, con motivo.
    r = await app_client.post(f"{API}/projects/{pid}/extra-visit", json={"reason": "El cliente llamó"},
                              headers=obra["tecnico"])
    assert r.status_code == 403
    r = await app_client.post(f"{API}/projects/{pid}/extra-visit", json={"reason": ""}, headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (400, "extra_visit_reason_required")
    r = await app_client.post(f"{API}/projects/{pid}/extra-visit",
                              json={"reason": "El cliente llamó y confirmó que estará"}, headers=obra["oficina"])
    assert r.json() == {"failed_visits": 2, "limit": 3, "limit_reached": False, "extra_visits_authorized": 1}
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"])

    # Otra fallida vuelve a bloquear.
    assert (await _fallida(app_client, obra["tecnico"], pid)).json()["limit_reached"] is True
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"], esperado=409)


async def test_no_se_autoriza_un_intento_extra_antes_del_limite(app_client, obra):
    r = await app_client.post(f"{API}/projects/{obra['project'].id}/extra-visit",
                              json={"reason": "Por si acaso"}, headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "visit_limit_not_reached")


async def test_el_limite_se_configura_por_organizacion(app_client, login, obra, active_admin_user):
    assert (await app_client.get(f"{API}/field-ops/settings", headers=obra["oficina"])).json()[
        "max_failed_visits"] == 2
    for valor in (0, 11):
        r = await app_client.put(f"{API}/field-ops/settings", json={"max_failed_visits": valor},
                                 headers=obra["oficina"])
        assert (r.status_code, r.json()["code"]) == (400, "invalid_visit_limit")
    assert (await app_client.put(f"{API}/field-ops/settings", json={"max_failed_visits": 3},
                                 headers=obra["tecnico"])).status_code == 403
    admin = await login(active_admin_user.email)
    r = await app_client.put(f"{API}/field-ops/settings", json={"max_failed_visits": 1}, headers=admin)
    assert r.json()["max_failed_visits"] == 1

    pid = obra["project"].id
    assert (await _fallida(app_client, obra["tecnico"], pid)).json() == {
        "failed_visits": 1, "limit": 1, "limit_reached": True, "extra_visits_authorized": 0}
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"], esperado=409)
    # Subir el límite aplica de inmediato, sin tocar la obra.
    await app_client.put(f"{API}/field-ops/settings", json={"max_failed_visits": 3}, headers=admin)
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"])


# ---------------------------------------------------------------------------
# Cancelación
# ---------------------------------------------------------------------------

async def _material_entregado(app_client, admin, oficina, tecnico, project_id) -> dict:
    item = (await app_client.post(f"{API}/warehouse/items", json={
        "name": "Tubo cobre 3/8", "sku": "CU-38", "category": "pipe_copper", "unit": "ft", "unit_cost": "3.25"},
        headers=admin)).json()
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "entrada", "quantity": "20"}, headers=admin)
    assert r.status_code == 201, r.text
    orden = (await app_client.post(f"{API}/warehouse/releases", json={
        "project_id": str(project_id), "lines": [{"item_id": item["id"], "quantity": "10"}]},
        headers=tecnico)).json()
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/submit",
                                  headers=tecnico)).status_code == 200
    return {"item": item, "orden": orden}


async def test_cancelar_exige_resolver_salidas_y_material(app_client, db, login, obra, active_admin_user):
    admin = await login(active_admin_user.email)
    pid = obra["project"].id
    m = await _material_entregado(app_client, admin, obra["oficina"], obra["tecnico"], pid)

    # El técnico no cancela; sin motivo tampoco se cancela.
    assert (await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "No quiere"},
                                  headers=obra["tecnico"])).status_code == 403
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "  "}, headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (400, "cancel_reason_required")

    # Con una salida por autorizar no se cancela.
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "Cliente desistió"},
                              headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "open_releases")
    assert "Por autorizar" in r.json()["detail"]

    # Bodega la entrega: ahora hay material afuera sin reintegrar.
    oid = m["orden"]["id"]
    assert (await app_client.post(f"{API}/warehouse/releases/{oid}/approve", headers=obra["oficina"])).status_code == 200
    assert (await app_client.post(f"{API}/warehouse/releases/{oid}/deliver", headers=obra["oficina"])).status_code == 200
    chequeo = (await app_client.get(f"{API}/projects/{pid}/cancellation-check", headers=obra["oficina"])).json()
    assert chequeo["open_releases"] == []
    assert [(x["item_name"], x["quantity"]) for x in chequeo["material_in_field"]] == [("Tubo cobre 3/8", "10.00")]
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "Cliente desistió"},
                              headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "material_pending_return")
    assert "10.00 × Tubo cobre 3/8" in r.json()["detail"]

    # Reintegra 7; los otros 3 se quedaron en la casa y se explica.
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": m["item"]["id"], "movement_type": "devolucion", "quantity": "7", "project_id": str(pid)},
        headers=admin)
    assert r.status_code == 201, r.text
    chequeo = (await app_client.get(f"{API}/projects/{pid}/cancellation-check", headers=obra["oficina"])).json()
    assert [x["quantity"] for x in chequeo["material_in_field"]] == ["3.00"]
    # No se devuelve más de lo que queda afuera (D-008).
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": m["item"]["id"], "movement_type": "devolucion", "quantity": "4", "project_id": str(pid)},
        headers=admin)
    assert (r.status_code, r.json()["code"]) == (400, "return_exceeds_delivered")
    assert "3.00" in r.json()["detail"]
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={
        "reason": "Cliente desistió", "material_note": "Los 3 ft quedaron cortados en la casa"},
        headers=obra["oficina"])
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["cancel_reason"]) == ("cancelled", "Cliente desistió")
    # El expediente se cierra por el cierre administrativo.
    assert (await _etapa(db, obra["case"].id))[0] == "closed"


async def test_la_obra_cancelada_queda_congelada(app_client, obra):
    pid = obra["project"].id
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "Cliente desistió"},
                              headers=obra["oficina"])
    assert r.status_code == 200, r.text
    r = await app_client.post(f"{API}/projects/{pid}/cancel", json={"reason": "Otra vez"}, headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "project_cancelled")
    r = await _fallida(app_client, obra["tecnico"], pid)
    assert (r.status_code, r.json()["code"]) == (409, "project_cancelled")
    await _liberar(app_client, obra["oficina"], pid, obra["tecnico_id"], esperado=409)
    r = await app_client.post(f"{API}/projects/{pid}/equipment", json={
        "equipment_type": "thermostat", "brand": "Honeywell", "model": "T4", "serial_number": "S1"},
        headers=obra["tecnico"])
    assert r.status_code == 409
    r = await app_client.post(f"{API}/warehouse/releases", json={"project_id": str(pid), "lines": []},
                              headers=obra["tecnico"])
    assert r.status_code in (400, 409, 422)
    # El técnico la sigue viendo, con el motivo.
    visto = (await app_client.get(f"{API}/projects/{pid}", headers=obra["tecnico"])).json()
    assert (visto["status"], visto["cancel_reason"]) == ("cancelled", "Cliente desistió")


async def test_una_instalacion_cerrada_no_se_cancela(app_client, db, obra):
    from app.modules.field_ops.models import Project, ProjectStatus

    p = (await db.execute(select(Project).where(Project.id == obra["project"].id))).scalar_one()
    p.status = ProjectStatus.completed
    await db.commit()
    r = await app_client.post(f"{API}/projects/{p.id}/cancel", json={"reason": "Cliente desistió"},
                              headers=obra["oficina"])
    assert (r.status_code, r.json()["code"]) == (409, "installation_closed")


async def test_los_motivos_viajan_en_el_catalogo_de_campo(app_client, obra):
    catalogo = (await app_client.get(f"{API}/field-ops/catalogs", headers=obra["tecnico"])).json()
    assert catalogo["visit_failure_reasons"]["customer_absent"] == "El cliente no estaba"


# ---------------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------------

async def test_la_visita_fallida_avisa_a_la_agenda_y_la_cancelacion_al_tecnico(
        db, seeded_org, active_admin_staff_user, active_technician_user):
    from app.modules.notifications import service as notices
    from app.modules.notifications.models import Notification

    org = seeded_org["org"].id
    _, project = await approved_case_with_project(db, org, technician_id=active_technician_user.id)
    await notices.process_event(db, "installation.visit_failed", {
        "organization_id": str(org), "project_id": str(project.id),
        "recorded_by_user_id": str(active_technician_user.id), "reason": "El cliente no estaba",
        "notes": "Nadie abrió", "scheduled_date": "2026-10-25", "failed_visits": 2, "limit": 2,
        "limit_reached": True})
    aviso = (await db.execute(select(Notification).where(
        Notification.user_id == active_admin_staff_user.id))).scalars().one()
    assert aviso.event == "installation.visit_failed"
    assert "2 de 2" in aviso.body and "autoriza otro intento o cancela" in aviso.body
    assert aviso.link == f"/projects/{project.id}?paso=release"
    # Quien la registró no se avisa a sí mismo.
    assert (await db.execute(select(Notification).where(
        Notification.user_id == active_technician_user.id))).scalars().all() == []

    await notices.process_event(db, "project.cancelled", {
        "organization_id": str(org), "project_id": str(project.id),
        "technician_user_id": str(active_technician_user.id), "reason": "Cliente desistió",
        "cancelled_by_user_id": str(active_admin_staff_user.id)})
    aviso = (await db.execute(select(Notification).where(
        Notification.user_id == active_technician_user.id))).scalars().one()
    assert (aviso.event, aviso.link) == ("project.cancelled", f"/projects/{project.id}")
    assert "Cliente desistió" in aviso.body
