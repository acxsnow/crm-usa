"""Rotación del técnico en la obra (plan bodega-cierre, fase 5).

Lo que el equipo pidió el 24 oct: el personal rota. Con la obra iniciada, el
administrador cambia el técnico con la misma «Orden liberada» y el nuevo sigue
donde el otro terminó. El responsable es el único técnico que llena la obra
(evidencias, checklist, equipos, firmas, diario y pedidos de material). El
anterior la sigue viendo en solo lectura, con lo que hizo él y lo que va
haciendo el nuevo. Los ayudantes de una jornada también la ven, sin llenarla.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus
from tests.field_helpers import approved_case_with_project, checklist_items, headers_for, jpeg_bytes


def _hoy_utc() -> date:
    """El «hoy» del servidor (la organización de prueba está en UTC). Con
    `date.today()` local, después de las 7 p. m. en Bogotá ya es mañana en UTC
    y estas pruebas fallaban por la hora del día."""
    return datetime.now(timezone.utc).date()


API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _tecnico(db, seeded_org, nombre: str) -> User:
    correo = f"{nombre.lower().replace(' ', '.')}@acme-demo.com"
    user = User(organization_id=seeded_org["org"].id, email=correo, email_display=correo, full_name=nombre,
                password_hash=hash_password("SuperSecret123"), status=UserStatus.active)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=seeded_org["roles"]["field_technician"].id))
    await db.commit()
    await db.refresh(user)
    return user


async def _liberar(app_client, headers, project_id, tecnico_id, dia: date):
    r = await app_client.patch(f"{API}/projects/{project_id}/schedule", json={
        "technician_user_id": str(tecnico_id), "scheduled_date": dia.isoformat()}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _jornada(app_client, headers, project_id, dia: date, **extra):
    return await app_client.post(f"{API}/warehouse/projects/{project_id}/day-logs", json={
        "log_date": dia.isoformat(), "work_done": "Avance del día", **extra}, headers=headers)


async def test_el_tecnico_anterior_ve_la_obra_en_solo_lectura(app_client, db, seeded_org, login,
                                                              active_admin_staff_user, active_technician_user):
    oficina = await login(active_admin_staff_user.email)
    tom = await login(active_technician_user.email)
    luis_user = await _tecnico(db, seeded_org, "Luis Nuevo")
    luis = await login(luis_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    hoy = _hoy_utc()

    await _liberar(app_client, oficina, obra.id, active_technician_user.id, hoy)
    # Tom trabaja: registra su día y marca una línea del checklist.
    r = await _jornada(app_client, tom, obra.id, hoy - timedelta(days=1), progress_note="Quedó montada la base")
    assert r.status_code == 201, r.text
    jornada_tom = r.json()
    linea = next(i for i in await checklist_items(db, obra.id) if not i.requires_evidence)
    r = await app_client.patch(f"{API}/checklist-items/{linea.id}", json={"is_complete": True}, headers=tom)
    assert r.status_code == 200, r.text

    # La oficina rota: desde hoy sigue Luis.
    await _liberar(app_client, oficina, obra.id, luis_user.id, hoy)
    historial = (await app_client.get(f"{API}/projects/{obra.id}/assignments", headers=oficina)).json()
    assert [(h["technician_name"], h["current"]) for h in historial] == [("Tom Technician", False),
                                                                         ("Luis Nuevo", True)]

    # Tom la sigue viendo, en solo lectura, y la encuentra en su lista.
    visto = (await app_client.get(f"{API}/projects/{obra.id}", headers=tom)).json()
    assert visto["my_access"] == "read_only"
    assert str(obra.id) in {p["id"] for p in (await app_client.get(f"{API}/projects", headers=tom)).json()}
    assert (await app_client.get(f"{API}/warehouse/projects/{obra.id}/day-logs", headers=tom)).status_code == 200

    # Pero ya no la llena: ni evidencias, ni checklist, ni diario, ni material.
    foto = await app_client.post(f"{API}/projects/{obra.id}/evidence", headers=tom,
                                 files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")},
                                 data={"category": "additional_photo"})
    assert (foto.status_code, foto.json()["code"]) == (403, "project_read_only")
    otra = next(i for i in await checklist_items(db, obra.id) if not i.requires_evidence and i.id != linea.id)
    r = await app_client.patch(f"{API}/checklist-items/{otra.id}", json={"is_complete": True}, headers=tom)
    assert r.status_code == 403
    assert (await _jornada(app_client, tom, obra.id, hoy)).status_code == 403
    assert (await app_client.post(f"{API}/projects/{obra.id}/equipment", json={
        "equipment_type": "heat_pump", "brand": "Goodman", "model": "X", "serial_number": "S"},
        headers=tom)).status_code == 403

    # Luis sigue donde quedó: llena lo suyo, pero no cambia lo de Tom.
    assert (await app_client.get(f"{API}/projects/{obra.id}", headers=luis)).json()["my_access"] == "full"
    assert (await _jornada(app_client, luis, obra.id, hoy)).status_code == 201
    r = await app_client.put(f"{API}/warehouse/projects/{obra.id}/day-logs/{jornada_tom['id']}", json={
        "log_date": jornada_tom["log_date"], "work_done": "Lo cambio yo"}, headers=luis)
    assert (r.status_code, r.json()["code"]) == (403, "day_log_by_other")
    r = await app_client.patch(f"{API}/checklist-items/{linea.id}", json={"is_complete": False}, headers=luis)
    assert (r.status_code, r.json()["code"]) == (403, "checklist_item_by_other")
    # La oficina sí corrige.
    r = await app_client.put(f"{API}/warehouse/projects/{obra.id}/day-logs/{jornada_tom['id']}", json={
        "log_date": jornada_tom["log_date"], "work_done": "Corregido por la oficina",
        "technician_user_id": str(active_technician_user.id)}, headers=oficina)
    assert r.status_code == 200, r.text


async def test_los_ayudantes_ven_la_obra_y_no_la_llenan(app_client, db, seeded_org, login,
                                                         active_admin_staff_user, active_technician_user):
    oficina = await login(active_admin_staff_user.email)
    tom = await login(active_technician_user.email)
    pedro_user = await _tecnico(db, seeded_org, "Pedro Ayudante")
    pedro = await login(pedro_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, active_technician_user.id, _hoy_utc())

    # Antes de ir de ayudante, Pedro no sabe que la obra existe.
    assert (await app_client.get(f"{API}/projects/{obra.id}", headers=pedro)).status_code == 404

    r = await _jornada(app_client, tom, obra.id, _hoy_utc(), helper_user_ids=[str(pedro_user.id)])
    assert r.status_code == 201, r.text
    assert [h["name"] for h in r.json()["helpers"]] == ["Pedro Ayudante"]

    assert (await app_client.get(f"{API}/projects/{obra.id}", headers=pedro)).json()["my_access"] == "read_only"
    assert (await _jornada(app_client, pedro, obra.id, _hoy_utc() + timedelta(days=1))).status_code == 403
    # Un ayudante inventado o de otra organización no entra.
    r = await _jornada(app_client, tom, obra.id, _hoy_utc() + timedelta(days=1), helper_user_ids=[str(uuid.uuid4())])
    assert (r.status_code, r.json()["code"]) == (400, "invalid_technician")


async def test_el_tecnico_registra_solo_su_propia_jornada(app_client, db, seeded_org, login,
                                                          active_admin_staff_user, active_technician_user):
    oficina = await login(active_admin_staff_user.email)
    tom = await login(active_technician_user.email)
    otro = await _tecnico(db, seeded_org, "Otro Técnico")
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, active_technician_user.id, _hoy_utc())

    r = await _jornada(app_client, tom, obra.id, _hoy_utc(), technician_user_id=str(otro.id))
    assert (r.status_code, r.json()["code"]) == (403, "day_log_for_other")
    r = await _jornada(app_client, tom, obra.id, _hoy_utc())
    assert r.json()["technician_user_id"] == str(active_technician_user.id)  # sin elegir, queda a su nombre


async def test_el_calendario_muestra_turnos_y_jornadas(app_client, db, seeded_org, login,
                                                       active_admin_staff_user, active_technician_user):
    oficina = await login(active_admin_staff_user.email)
    tom = await login(active_technician_user.email)
    luis_user = await _tecnico(db, seeded_org, "Luis Nuevo")
    luis = await login(luis_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    hoy = _hoy_utc()
    await _liberar(app_client, oficina, obra.id, active_technician_user.id, hoy)
    await _jornada(app_client, tom, obra.id, hoy - timedelta(days=1), progress_note="Base lista")
    await _liberar(app_client, oficina, obra.id, luis_user.id, hoy)
    await _jornada(app_client, luis, obra.id, hoy, progress_note="Líneas puestas")

    rango = {"date_from": (hoy - timedelta(days=3)).isoformat(), "date_to": (hoy + timedelta(days=3)).isoformat()}
    todo = (await app_client.get(f"{API}/warehouse/calendar", params=rango, headers=oficina)).json()
    assert [(a["technician_name"], a["ended_on"] is None) for a in todo["assignments"]] == [
        ("Tom Technician", False), ("Luis Nuevo", True)]
    assert [d["progress_note"] for d in todo["day_logs"]] == ["Base lista", "Líneas puestas"]

    # El técnico ve solo lo suyo.
    suyo = (await app_client.get(f"{API}/warehouse/calendar", params=rango, headers=tom)).json()
    assert [d["progress_note"] for d in suyo["day_logs"]] == ["Base lista"]
    assert [a["technician_name"] for a in suyo["assignments"]] == ["Tom Technician"]

    largo = {"date_from": hoy.isoformat(), "date_to": (hoy + timedelta(days=90)).isoformat()}
    r = await app_client.get(f"{API}/warehouse/calendar", params=largo, headers=oficina)
    assert (r.status_code, r.json()["code"]) == (400, "calendar_range_too_long")


async def test_rotar_antes_de_la_fecha_no_cruza_los_turnos(app_client, db, seeded_org, login,
                                                          active_admin_staff_user, active_technician_user):
    """D-011: con la obra agendada para dentro de 2 días, rotar hoy dejaba al
    anterior «del 27 al 27» y al nuevo «desde el 25», y la lista salía en
    desorden. Ahora el anterior termina el día del cambio y la lista va en orden."""
    oficina = await login(active_admin_staff_user.email)
    luis_user = await _tecnico(db, seeded_org, "Luis Nuevo")
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    hoy = _hoy_utc()

    await _liberar(app_client, oficina, obra.id, active_technician_user.id, hoy + timedelta(days=2))
    await _liberar(app_client, oficina, obra.id, luis_user.id, hoy)
    historial = (await app_client.get(f"{API}/projects/{obra.id}/assignments", headers=oficina)).json()
    assert [(h["technician_name"], h["started_on"], h["ended_on"], h["current"]) for h in historial] == [
        ("Tom Technician", hoy.isoformat(), hoy.isoformat(), False),
        ("Luis Nuevo", hoy.isoformat(), None, True),
    ]
