"""D-004: en los filtros de texto, `%` y `_` se buscan tal cual y no funcionan
como comodines (antes «%» traía todo)."""
from app.shared.text_search import contains_pattern
from tests.field_helpers import headers_for

API = "/api/v1"


def test_el_patron_escapa_comodines_y_quita_el_byte_nulo():
    barra = "\\"
    texto = " 50%_off" + barra + chr(0) + " "
    assert contains_pattern(texto) == "%50" + barra + "%" + barra + "_off" + barra * 2 + "%"


async def test_los_filtros_buscan_porcentaje_y_guion_bajo_tal_cual(app_client, active_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    for nombre in ("Descuento 50% QA", "Cliente Normal QA"):
        r = await app_client.post(f"{API}/customers", json={"legal_name": nombre, "data_consent_accepted": True},
                                  headers=h)
        assert r.status_code == 201, r.text
    for nombre, sku in (("Cinta 50% QA", "A_1"), ("Tubo QA", "AB1")):
        r = await app_client.post(f"{API}/warehouse/items", json={
            "name": nombre, "sku": sku, "category": "pipe_copper", "unit": "ft"}, headers=h)
        assert r.status_code == 201, r.text

    async def nombres(ruta, q, campo):
        r = await app_client.get(f"{API}/{ruta}", params={"q": q}, headers=h)
        assert r.status_code == 200, r.text
        filas = r.json()["items"] if isinstance(r.json(), dict) else r.json()
        return sorted(x[campo] for x in filas)

    assert await nombres("customers", "%", "legal_name") == ["Descuento 50% QA"]
    assert await nombres("customers", "50%", "legal_name") == ["Descuento 50% QA"]
    assert await nombres("warehouse/items", "%", "name") == ["Cinta 50% QA"]
    # «A_1» no encuentra «AB1»: el guion bajo ya no es «cualquier letra».
    assert await nombres("warehouse/items", "A_1", "sku") == ["A_1"]
    assert await nombres("users", "%", "email") == []
    assert await nombres("projects", "_", "id") == []
