"""Lo que queda del CRM después de retirar el modelo anterior.

Prospectos, oportunidades, cotizaciones y etapas de embudo se retiraron: el
expediente los reemplaza y sus pruebas viven en `test_cases_*.py`. Aquí queda
el cliente, sus contactos, su actividad y su ficha.

La ficha del cliente es la que más importa para el vendedor: cuando vuelve al
parque necesita saber si ya habló con alguien de esa casa, y eso ahora se
responde con los expedientes del cliente, no con oportunidades."""
import uuid


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _cliente(app_client, headers, nombre="Marge Simpson"):
    resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": nombre}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

async def test_create_and_list_customers(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = await _cliente(app_client, headers)
    assert creado["legal_name"] == "Marge Simpson"

    listado = (await app_client.get("/api/v1/customers", headers=headers)).json()
    assert [c["id"] for c in listado] == [creado["id"]]


async def test_a_customer_can_have_contacts(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    cliente = await _cliente(app_client, headers)
    resp = await app_client.post(
        f"/api/v1/customers/{cliente['id']}/contacts",
        json={"full_name": "Homero Simpson", "phone": "555-0100"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["full_name"] == "Homero Simpson"


async def test_customers_from_another_organization_are_invisible(
    app_client, active_admin_user, second_org_admin_user
):
    headers = await _login(app_client, "admin@acme-demo.com")
    await _cliente(app_client, headers)

    otros = await _login(app_client, "admin@otra-demo.com")
    assert (await app_client.get("/api/v1/customers", headers=otros)).json() == []


# ---------------------------------------------------------------------------
# La ficha del cliente
# ---------------------------------------------------------------------------

async def test_the_customer_file_lists_their_cases(app_client, active_admin_user):
    """Antes mostraba oportunidades y cotizaciones. Ahora muestra expedientes,
    que es lo que el vendedor necesita al volver al parque."""
    headers = await _login(app_client, "admin@acme-demo.com")
    cliente = await _cliente(app_client, headers)

    creado = await app_client.post(
        "/api/v1/cases",
        json={
            "stage_code": "new_prospect",
            "customer_id": cliente["id"],
            "address_street": "742 Evergreen Terrace",
            "address_unit": "Spc 14",
        },
        headers=headers,
    )
    assert creado.status_code == 201, creado.text

    ficha = (
        await app_client.get(f"/api/v1/customers/{cliente['id']}/timeline", headers=headers)
    ).json()
    assert ficha["customer"]["id"] == cliente["id"]
    assert len(ficha["cases"]) == 1
    assert ficha["cases"][0]["case_number"] == creado.json()["case_number"]
    # La etiqueta en español viaja con el dato: el frontend no repite el diccionario.
    assert ficha["cases"][0]["stage_label"] == "Nuevo prospecto"
    assert "opportunities" not in ficha
    assert "quotes" not in ficha


async def test_the_file_of_a_customer_without_cases_is_empty_not_an_error(
    app_client, active_admin_user
):
    headers = await _login(app_client, "admin@acme-demo.com")
    cliente = await _cliente(app_client, headers)
    ficha = (
        await app_client.get(f"/api/v1/customers/{cliente['id']}/timeline", headers=headers)
    ).json()
    assert ficha["cases"] == []


async def test_the_file_of_a_customer_that_does_not_exist_answers_404(
    app_client, active_admin_user
):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get(f"/api/v1/customers/{uuid.uuid4()}/timeline", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Lo retirado ya no responde
# ---------------------------------------------------------------------------

async def test_the_endpoints_of_the_old_model_are_gone(app_client, active_admin_user):
    """Cierra COD-01: mientras las rutas existieran, alguien podía seguir
    construyendo sobre el modelo que se retiró."""
    headers = await _login(app_client, "admin@acme-demo.com")
    for ruta in ("/api/v1/leads", "/api/v1/opportunities", "/api/v1/quotes",
                 "/api/v1/pipeline-stages"):
        resp = await app_client.get(ruta, headers=headers)
        assert resp.status_code == 404, f"{ruta} sigue respondiendo {resp.status_code}"
