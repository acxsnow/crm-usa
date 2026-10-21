"""Diario de obra: la jornada día por día (Fase 4, punto 4 del cuestionario).

Lo que se protege aquí es lo que el cliente quiere ver en las obras que duran
varios días: **qué se hizo cada día y qué se gastó cada día**. Tres reglas
sostienen el archivo:

- El técnico vive en la **jornada**, no en el proyecto: la misma obra tiene uno
  distinto cada día, y una obra con más de una jornada es «de varios días».
- Los gastos del día **se leen** de `expenses` por fecha; no se vuelven a
  capturar, o se contarían dos veces.
- El material que salió de una camioneta descuenta la existencia y no se edita
  desde el diario: el libro de movimientos no se toca.
"""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.warehouse import service as wh
from app.modules.warehouse.models import ProjectDayLogMaterial, WarehouseMovement
from tests.field_helpers import approved_case_with_project, headers_for, jpeg_bytes

HOY = date.today()
AYER = HOY - timedelta(days=1)
API = "/api/v1"


@pytest.fixture
def login(app_client):
    """Inicia sesión solo con los usuarios que la prueba usa (el login tiene
    límite de intentos por minuto). El caché es por prueba."""
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


# ---------------------------------------------------------------------------
# Ayudas: catálogo, camioneta y el camino del diario
# ---------------------------------------------------------------------------

async def _item(app_client, headers, nombre="Tubo cobre 3/8", *, sku="CU-38", costo="5.00") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": "pipe_copper", "unit": "ft", "unit_cost": costo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _camioneta(app_client, headers, *, nombre="Camioneta Tom", tecnico_id=None) -> dict:
    """La ubicación de la que sale el material del día."""
    r = await app_client.post(f"{API}/warehouse/locations", json={
        "name": nombre, "kind": "truck", "technician_user_id": str(tecnico_id) if tecnico_id else None},
        headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _entrada(app_client, headers, item_id, cantidad="100") -> dict:
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "entrada", "quantity": cantidad}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _traslado_a_camioneta(app_client, headers, item_id, location_id, cantidad) -> dict:
    """La bodega carga la camioneta: de ahí sale el material que se usa en obra."""
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "traslado", "quantity": cantidad,
        "to_location_id": str(location_id)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _jornada(app_client, headers, project_id, **campos) -> dict:
    cuerpo = {"log_date": HOY.isoformat(), **campos}
    r = await app_client.post(f"{API}/warehouse/projects/{project_id}/day-logs", json=cuerpo, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _corregir_jornada(app_client, headers, project_id, log_id, **campos) -> object:
    cuerpo = {"log_date": HOY.isoformat(), **campos}
    return await app_client.put(f"{API}/warehouse/projects/{project_id}/day-logs/{log_id}",
                                json=cuerpo, headers=headers)


async def _diario(app_client, headers, project_id) -> list[dict]:
    r = await app_client.get(f"{API}/warehouse/projects/{project_id}/day-logs", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _gasto_aprobado(app_client, tecnico, aprobador, project_id, monto="60.00", fecha=HOY) -> dict:
    """El técnico lo sube y el admin lo aprueba: nadie aprueba su propio gasto."""
    r = await app_client.post(f"{API}/expenses", data={"data": json.dumps({
        "expense_date": fecha.isoformat(), "category": "fuel", "amount": monto, "description": "Gasolina",
        "payment_method": "own_money", "project_id": str(project_id)})},
        files={"receipt": ("recibo.jpg", jpeg_bytes(), "image/jpeg")}, headers=tecnico)
    assert r.status_code == 201, r.text
    gasto = r.json()
    r = await app_client.post(f"{API}/expenses/{gasto['id']}/review", json={"approve": True}, headers=aprobador)
    assert r.status_code == 200, r.text
    return r.json()


async def _segundo_tecnico(db, seeded_org) -> User:
    """Un segundo técnico: la obra de varios días no la lleva siempre el mismo."""
    org = seeded_org["org"]
    user = User(organization_id=org.id, email="tech2@acme-demo.com", email_display="tech2@acme-demo.com",
                full_name="Terry Technician", password_hash=hash_password("SuperSecret123"),
                status=UserStatus.active)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=seeded_org["roles"]["field_technician"].id))
    await db.commit()
    await db.refresh(user)
    return user


def _error(resp) -> str:
    return resp.json()["code"]


# ---------------------------------------------------------------------------
# La jornada
# ---------------------------------------------------------------------------

async def test_la_jornada_se_registra_con_su_tecnico_horas_y_avance(
        app_client, login, db, seeded_org, active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id,
                                                  technician_id=active_technician_user.id)

    jornada = await _jornada(
        app_client, tecnico, project.id, technician_user_id=str(active_technician_user.id), hours="8",
        crew="Ayudante Juan", work_done="Se cambió el evaporador y se probó la carga",
        progress_note="Queda pendiente la línea de retorno", missing_materials="2 codos de 3/8",
        next_day_plan="Terminar el retorno y probar presión", incidents="El cliente no estaba a las 9")
    assert jornada["technician_name"] == "Tom Technician"
    assert jornada["hours"] == "8.00"
    assert jornada["progress_note"] == "Queda pendiente la línea de retorno"
    assert jornada["materials"] == []

    # El diario de la obra lo devuelve, del día más reciente al más viejo.
    diario = await _diario(app_client, tecnico, project.id)
    assert [f["id"] for f in diario] == [jornada["id"]]
    assert diario[0]["next_day_plan"] == "Terminar el retorno y probar presión"


async def test_el_material_de_la_jornada_descuenta_la_camioneta_y_cuesta_a_la_obra(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    org_id = seeded_org["org"].id
    tecnico_id = active_technician_user.id
    _, project = await approved_case_with_project(db, org_id, technician_id=tecnico_id)
    project_id = project.id
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", costo="5.00")
    camioneta = await _camioneta(app_client, admin, tecnico_id=tecnico_id)
    await _entrada(app_client, admin, tubo["id"], "100")
    await _traslado_a_camioneta(app_client, admin, tubo["id"], camioneta["id"], "20")

    jornada = await _jornada(app_client, tecnico, project_id, technician_user_id=str(tecnico_id),
                             hours="9",
                             materials=[
                                 {"item_id": tubo["id"], "quantity": "8", "location_id": camioneta["id"]},
                                 # Comprado directo en la obra: es la anotación del día, no mueve nada.
                                 {"description": "Cinta de aluminio", "quantity": "2"},
                             ])
    usados, anotados = jornada["materials"]
    assert (usados["description"], usados["quantity"], usados["descontada"]) == ("Tubo cobre 3/8", "8.00", True)
    assert usados["location_name"] == "Camioneta Tom"
    assert anotados["descontada"] is False and anotados["movement_id"] is None

    # La camioneta bajó de 20 a 12, y el movimiento quedó a nombre de la obra:
    # ese material es costo del proyecto, no de la bodega.
    db.expire_all()
    assert await wh.stock_quantity(db, org_id, item_id=uuid.UUID(tubo["id"]),
                                   location_id=uuid.UUID(camioneta["id"])) == Decimal("12.00")
    linea = (await db.execute(select(ProjectDayLogMaterial).where(
        ProjectDayLogMaterial.day_log_id == uuid.UUID(jornada["id"])))).scalars().first()
    movimiento = await db.get(WarehouseMovement, linea.movement_id)
    assert (movimiento.movement_type, str(movimiento.quantity), str(movimiento.unit_cost)) == ("salida", "-8.00", "5.00")
    assert movimiento.project_id == project_id

    # Corregir el texto del día no vuelve a descontar la camioneta.
    corregida = await _corregir_jornada(
        app_client, tecnico, project_id, jornada["id"], technician_user_id=str(tecnico_id),
        hours="9", work_done="Se cambió el evaporador",
        materials=[{"id": usados["id"], "item_id": tubo["id"], "quantity": "8", "location_id": camioneta["id"]},
                   {"description": "Cinta de aluminio", "quantity": "2"}])
    assert corregida.status_code == 200, corregida.text
    db.expire_all()
    assert await wh.stock_quantity(db, org_id, item_id=uuid.UUID(tubo["id"]),
                                   location_id=uuid.UUID(camioneta["id"])) == Decimal("12.00")


async def test_los_gastos_del_dia_se_leen_de_los_gastos_de_la_obra(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id,
                                                  technician_id=active_technician_user.id)
    await _jornada(app_client, tecnico, project.id, technician_user_id=str(active_technician_user.id), hours="8")
    # Uno de hoy y otro de ayer: cada día muestra solo lo suyo.
    await _gasto_aprobado(app_client, tecnico, admin, project.id, "60.00", HOY)
    await _gasto_aprobado(app_client, tecnico, admin, project.id, "25.00", AYER)
    # Un gasto por revisar todavía no es plata puesta: no cuenta.
    r = await app_client.post(f"{API}/expenses", data={"data": json.dumps({
        "expense_date": HOY.isoformat(), "category": "small_materials", "amount": "999.00", "description": "Por revisar",
        "payment_method": "own_money", "project_id": str(project.id)})},
        files={"receipt": ("recibo.jpg", jpeg_bytes(), "image/jpeg")}, headers=tecnico)
    assert r.status_code == 201, r.text

    diario = await _diario(app_client, tecnico, project.id)
    assert diario[0]["expenses"] == {"count": 1, "amount": "60.00"}


async def test_dos_jornadas_con_tecnicos_distintos_y_una_sola_por_dia(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    segundo = await _segundo_tecnico(db, seeded_org)
    _, project = await approved_case_with_project(db, seeded_org["org"].id,
                                                  technician_id=active_technician_user.id)
    # La obra va en la agenda: es la que dura varios días.
    project.scheduled_date = HOY
    await db.commit()

    await _jornada(app_client, tecnico, project.id, log_date=AYER.isoformat(),
                   technician_user_id=str(active_technician_user.id), hours="8", progress_note="Día 1")
    await _jornada(app_client, tecnico, project.id, log_date=HOY.isoformat(),
                   technician_user_id=str(segundo.id), hours="6", progress_note="Día 2")

    diario = await _diario(app_client, tecnico, project.id)
    assert [(f["log_date"], f["technician_name"], f["progress_note"]) for f in diario] == [
        (HOY.isoformat(), "Terry Technician", "Día 2"),
        (AYER.isoformat(), "Tom Technician", "Día 1"),
    ]

    # Una jornada por día y obra: el segundo renglón del mismo día se rechaza.
    repetida = await app_client.post(f"{API}/warehouse/projects/{project.id}/day-logs",
                                     json={"log_date": HOY.isoformat(), "hours": "4"}, headers=tecnico)
    assert (repetida.status_code, _error(repetida)) == (400, "day_log_date_taken")

    # Y la Agenda marca la obra como de varios días.
    r = await app_client.get(f"{API}/dispatch/agenda?date_from={HOY.isoformat()}&date_to={HOY.isoformat()}",
                             headers=admin)
    assert r.status_code == 200, r.text
    fila = next(f for f in r.json() if f["project_id"] == str(project.id))
    assert fila["day_count"] == 2


async def test_la_linea_que_ya_movio_existencia_no_se_edita_ni_se_borra(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    org_id = seeded_org["org"].id
    _, project = await approved_case_with_project(db, org_id, technician_id=active_technician_user.id)
    project_id = project.id
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", costo="5.00")
    camioneta = await _camioneta(app_client, admin, tecnico_id=active_technician_user.id)
    await _entrada(app_client, admin, tubo["id"], "100")
    await _traslado_a_camioneta(app_client, admin, tubo["id"], camioneta["id"], "20")

    jornada = await _jornada(app_client, tecnico, project_id, technician_user_id=str(active_technician_user.id),
                             materials=[{"item_id": tubo["id"], "quantity": "8", "location_id": camioneta["id"]}])
    linea_id = jornada["materials"][0]["id"]

    # Quitarla del día dejaría el movimiento de salida sin su origen.
    borrada = await _corregir_jornada(app_client, tecnico, project_id, jornada["id"],
                                      technician_user_id=str(active_technician_user.id), materials=[])
    assert (borrada.status_code, _error(borrada)) == (400, "day_log_line_locked")

    # Corregir la cantidad tampoco: el movimiento ya descontó la existencia.
    cambiada = await _corregir_jornada(
        app_client, tecnico, project_id, jornada["id"], technician_user_id=str(active_technician_user.id),
        materials=[{"id": linea_id, "item_id": tubo["id"], "quantity": "9", "location_id": camioneta["id"]}])
    assert (cambiada.status_code, _error(cambiada)) == (400, "day_log_line_locked")

    db.expire_all()
    assert await wh.stock_quantity(db, org_id, item_id=uuid.UUID(tubo["id"]),
                                   location_id=uuid.UUID(camioneta["id"])) == Decimal("12.00")


async def test_el_diario_de_una_obra_no_se_ve_desde_otra_organizacion(
        app_client, login, db, seeded_org, active_admin_user, second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    await _jornada(app_client, propio, project.id, log_date=HOY.isoformat(), hours="8")

    assert (await app_client.get(f"{API}/warehouse/projects/{project.id}/day-logs", headers=ajeno)).status_code == 404
    r = await app_client.post(f"{API}/warehouse/projects/{project.id}/day-logs",
                              json={"log_date": AYER.isoformat(), "hours": "4"}, headers=ajeno)
    assert r.status_code == 404 and _error(r) == "project_not_found"
