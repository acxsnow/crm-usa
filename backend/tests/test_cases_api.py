"""La API del expediente.

Lo que verifica, además de que funcione: que cada ruta exija su permiso, que
todo esté acotado a la organización del usuario, y que el vendedor solo vea los
suyos mientras Administración ve todos. Ese reparto es de la API, no de la
pantalla: esconder una fila en el frontend no impide pedirla por HTTP.
"""
import uuid


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _puerta(**extra):
    payload = {
        "stage_code": "no_contact",
        "address_street": "123 Main St",
        "address_unit": "Spc 14",
        "address_city": "Phoenix",
        "address_state": "AZ",
        "address_zip": "85001",
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

async def test_a_salesperson_opens_a_case_for_a_door(app_client, active_salesperson_user):
    headers = await _login(app_client, "vendedor@acme-demo.com")
    resp = await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)
    assert resp.status_code == 201, resp.text

    cuerpo = resp.json()
    assert cuerpo["stage_code"] == "no_contact"
    assert cuerpo["customer_id"] is None  # nadie abrió: no hay cliente
    assert cuerpo["case_number"].startswith("CASE-")


async def test_the_case_is_assigned_to_whoever_opened_it(app_client, active_salesperson_user):
    headers = await _login(app_client, "vendedor@acme-demo.com")
    creado = (await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)).json()
    assert creado["assigned_salesperson_id"] == str(active_salesperson_user.id)


async def test_a_case_cannot_be_opened_in_the_middle_of_the_flow(app_client, active_salesperson_user):
    headers = await _login(app_client, "vendedor@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/cases", json=_puerta(stage_code="approved"), headers=headers
    )
    assert resp.status_code == 400, resp.text


async def test_a_technician_cannot_open_a_case(app_client, active_technician_user):
    """El técnico instala, no vende: no tiene `cases.create`."""
    headers = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Listar: quién ve qué
# ---------------------------------------------------------------------------

async def test_a_salesperson_only_lists_their_own_cases(
    app_client, active_salesperson_user, active_admin_user
):
    """`cases.read_own` contra `cases.read_all`. El filtro va en la consulta,
    no en la pantalla."""
    del_vendedor = await _login(app_client, "vendedor@acme-demo.com")
    await app_client.post("/api/v1/cases", json=_puerta(), headers=del_vendedor)

    del_admin = await _login(app_client, "admin@acme-demo.com")
    await app_client.post(
        "/api/v1/cases", json=_puerta(address_unit="Spc 99"), headers=del_admin
    )

    mios = (await app_client.get("/api/v1/cases", headers=del_vendedor)).json()
    assert len(mios) == 1
    assert mios[0]["address_unit"] == "Spc 14"

    todos = (await app_client.get("/api/v1/cases", headers=del_admin)).json()
    assert len(todos) == 2


async def test_cases_from_another_organization_are_invisible(
    app_client, active_admin_user, second_org_admin_user
):
    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)

    otros = await _login(app_client, "admin@otra-demo.com")
    assert (await app_client.get("/api/v1/cases", headers=otros)).json() == []


async def test_the_list_is_paginated(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    for i in range(3):
        await app_client.post(
            "/api/v1/cases", json=_puerta(address_unit=f"Spc {i}"), headers=headers
        )

    resp = await app_client.get("/api/v1/cases?limit=2&offset=0", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["X-Total-Count"] == "3"


async def test_the_list_can_be_filtered_by_stage(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)
    await app_client.post(
        "/api/v1/cases",
        json=_puerta(address_unit="Spc 20", stage_code="new_prospect"),
        headers=headers,
    )

    resp = await app_client.get("/api/v1/cases?stage_code=new_prospect", headers=headers)
    assert [c["stage_code"] for c in resp.json()] == ["new_prospect"]


# ---------------------------------------------------------------------------
# Detalle e historial
# ---------------------------------------------------------------------------

async def test_the_detail_includes_the_stage_history(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=headers
        )
    ).json()

    resp = await app_client.get(f"/api/v1/cases/{creado['id']}/events", headers=headers)
    assert resp.status_code == 200
    assert [e["to_stage_code"] for e in resp.json()] == ["new_prospect"]


async def test_a_case_from_another_organization_answers_404_not_403(
    app_client, active_admin_user, second_org_admin_user
):
    """404 y no 403: responder distinto revelaría qué identificadores existen."""
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = (await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)).json()

    otros = await _login(app_client, "admin@otra-demo.com")
    resp = await app_client.get(f"/api/v1/cases/{creado['id']}", headers=otros)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Transiciones
# ---------------------------------------------------------------------------

async def test_the_salesperson_sends_the_case_to_review(app_client, active_salesperson_user):
    headers = await _login(app_client, "vendedor@acme-demo.com")
    creado = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=headers
        )
    ).json()

    resp = await app_client.post(
        f"/api/v1/cases/{creado['id']}/transition",
        json={"to_stage": "pending_approval"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage_code"] == "pending_approval"
    assert resp.json()["submitted_at"] is not None


async def test_a_forbidden_transition_is_rejected_with_a_readable_message(
    app_client, active_admin_user
):
    """Con un administrador, que tiene todos los permisos: así lo que responde
    es la validación del mapa de transiciones y no la del permiso."""
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=headers
        )
    ).json()

    resp = await app_client.post(
        f"/api/v1/cases/{creado['id']}/transition", json={"to_stage": "paid"}, headers=headers
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "invalid_transition"
    # El mensaje usa las etiquetas en español, no los códigos internos.
    assert "Nuevo prospecto" in resp.json()["detail"]


async def test_a_technician_cannot_move_a_case(
    app_client, active_technician_user, active_admin_user
):
    """El técnico tiene `checklists.complete`, así que pasa la puerta gruesa de
    la ruta. Lo que lo detiene es el permiso de la etapa concreta."""
    del_admin = await _login(app_client, "admin@acme-demo.com")
    caso = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=del_admin
        )
    ).json()

    headers = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.post(
        f"/api/v1/cases/{caso['id']}/transition",
        json={"to_stage": "pending_approval"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "stage_not_allowed_for_role"


async def test_an_invented_stage_is_a_bad_request_not_a_crash(app_client, active_admin_user):
    """`to_stage` llega del cliente: una etapa inventada tiene que decir que el
    dato es inválido, no reventar contra el mapa de permisos."""
    headers = await _login(app_client, "admin@acme-demo.com")
    caso = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=headers
        )
    ).json()
    resp = await app_client.post(
        f"/api/v1/cases/{caso['id']}/transition",
        json={"to_stage": "etapa_inventada"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "unknown_stage"


async def test_the_stage_catalog_is_exposed_for_the_frontend(app_client, active_salesperson_user):
    """El frontend no debe repetir los códigos de etapa ni sus etiquetas."""
    headers = await _login(app_client, "vendedor@acme-demo.com")
    resp = await app_client.get("/api/v1/cases/stages", headers=headers)
    assert resp.status_code == 200
    catalogo = resp.json()
    assert len(catalogo["stages"]) == 15
    primera = catalogo["stages"][0]
    assert primera["code"] == "no_contact"
    assert primera["label"] == "Sin contacto"
    assert primera["is_initial"] is True


# ---------------------------------------------------------------------------
# SEG-07: separación entre vender y aprobar
# ---------------------------------------------------------------------------

async def test_a_salesperson_cannot_approve_their_own_case(app_client, active_salesperson_user):
    """El hallazgo SEG-07. El vendedor manda a revisión y ahí se detiene: quien
    aprueba es Administración. Si esto se rompe, el vendedor se aprueba sus
    propias ventas y el flujo del cliente deja de significar nada."""
    headers = await _login(app_client, "vendedor@acme-demo.com")
    creado = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=headers
        )
    ).json()

    enviado = await app_client.post(
        f"/api/v1/cases/{creado['id']}/transition",
        json={"to_stage": "pending_approval"},
        headers=headers,
    )
    assert enviado.status_code == 200, enviado.text

    for etapa in ("approved", "rejected", "on_hold"):
        resp = await app_client.post(
            f"/api/v1/cases/{creado['id']}/transition",
            json={"to_stage": etapa},
            headers=headers,
        )
        assert resp.status_code == 403, f"el vendedor pudo pasar a {etapa}: {resp.text}"
        assert resp.json()["code"] == "stage_not_allowed_for_role"


async def test_admin_staff_can_approve(app_client, active_admin_staff_user, active_salesperson_user):
    """El contrapeso: quien sí tiene el permiso pasa.

    Lleva cliente porque aprobar dispara la creación del proyecto de
    instalación, y `Project.customer_id` es obligatorio."""
    del_vendedor = await _login(app_client, "vendedor@acme-demo.com")
    cliente = (
        await app_client.post(
            "/api/v1/customers", json={"legal_name": "Marge Simpson"}, headers=del_vendedor
        )
    ).json()
    creado = (
        await app_client.post(
            "/api/v1/cases",
            json=_puerta(stage_code="new_prospect", customer_id=cliente["id"]),
            headers=del_vendedor,
        )
    ).json()
    await app_client.post(
        f"/api/v1/cases/{creado['id']}/transition",
        json={"to_stage": "pending_approval"},
        headers=del_vendedor,
    )

    de_admin = await _login(app_client, "admin-staff@acme-demo.com")
    resp = await app_client.post(
        f"/api/v1/cases/{creado['id']}/transition",
        json={"to_stage": "approved"},
        headers=de_admin,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage_code"] == "approved"


async def test_a_salesperson_cannot_move_someone_elses_case(
    app_client, active_salesperson_user, active_admin_user
):
    """La otra mitad de SEG-07: el cambio de etapa no comprobaba el dueño,
    aunque la consulta sí. Responde 404, no 403: confirmar que existe ya sería
    revelar de más."""
    del_admin = await _login(app_client, "admin@acme-demo.com")
    ajeno = (
        await app_client.post(
            "/api/v1/cases", json=_puerta(stage_code="new_prospect"), headers=del_admin
        )
    ).json()

    del_vendedor = await _login(app_client, "vendedor@acme-demo.com")
    resp = await app_client.post(
        f"/api/v1/cases/{ajeno['id']}/transition",
        json={"to_stage": "pending_approval"},
        headers=del_vendedor,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Actividad reciente (Inicio, QA-REG-03)
# ---------------------------------------------------------------------------

async def test_recent_activity_comes_from_the_stage_history_newest_first(app_client, active_admin_user):
    """El panel del Inicio estaba escrito a mano; ahora sale del historial."""
    headers = await _login(app_client, "admin@acme-demo.com")
    caso = (await app_client.post("/api/v1/cases", json=_puerta(), headers=headers)).json()
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/transition",
                              json={"to_stage": "new_prospect"}, headers=headers)
    assert r.status_code == 200, r.text

    actividad = (await app_client.get("/api/v1/cases/activity", headers=headers)).json()
    assert [a["to_stage_code"] for a in actividad] == ["new_prospect", "no_contact"]
    primero = actividad[0]
    assert primero["case_number"] == caso["case_number"]
    assert primero["label"] == "Nuevo prospecto"
    assert primero["address"] == "123 Main St, Spc 14"
    assert primero["customer_name"] is None  # nadie ha dado sus datos todavía
    assert primero["actor_name"]


async def test_administration_sees_the_activity_of_every_salesperson(
    app_client, active_salesperson_user, active_admin_staff_user
):
    vendedor = await _login(app_client, "vendedor@acme-demo.com")
    await app_client.post("/api/v1/cases", json=_puerta(), headers=vendedor)
    administracion = await _login(app_client, "admin-staff@acme-demo.com")
    actividad = (await app_client.get("/api/v1/cases/activity", headers=administracion)).json()
    assert len(actividad) == 1
    assert actividad[0]["actor_name"] == active_salesperson_user.full_name


async def test_activity_hides_other_salespeople_and_other_organizations(
    app_client, db, seeded_org, active_salesperson_user, active_admin_user, second_org_admin_user
):
    from tests.conftest import _make_role_user

    await _make_role_user(db, seeded_org, role_code="salesperson", email="vendedor2@acme-demo.com", full_name="Otro")
    otro = await _login(app_client, "vendedor2@acme-demo.com")
    await app_client.post("/api/v1/cases", json=_puerta(address_unit="Spc 77"), headers=otro)

    vendedor = await _login(app_client, "vendedor@acme-demo.com")
    assert (await app_client.get("/api/v1/cases/activity", headers=vendedor)).json() == []
    admin = await _login(app_client, "admin@acme-demo.com")
    assert len((await app_client.get("/api/v1/cases/activity", headers=admin)).json()) == 1
    ajeno = await _login(app_client, "admin@otra-demo.com")
    assert (await app_client.get("/api/v1/cases/activity", headers=ajeno)).json() == []


async def test_a_technician_has_no_case_activity(app_client, active_technician_user):
    headers = await _login(app_client, "tech@acme-demo.com")
    assert (await app_client.get("/api/v1/cases/activity", headers=headers)).status_code == 403
