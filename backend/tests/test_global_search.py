"""Buscador global de la barra superior (`GET /search`).

Lo que se cuida: cada grupo aparece solo para quien tiene el permiso de su
pantalla, con el mismo recorte de su listado (el vendedor, sus expedientes; el
técnico, sus obras), nunca con datos de otra organización, y el texto se busca
tal cual (`%` y `_` no son comodines).
"""
import uuid

import pytest

from app.modules.cases import service as case_service
from app.modules.crm.models import Customer
from app.modules.finance.models import Supplier
from app.modules.warehouse.models import WarehouseItem
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _buscar(app_client, headers, q: str) -> dict:
    r = await app_client.get(f"{API}/search", params={"q": q}, headers=headers)
    assert r.status_code == 200, r.text
    return {g["key"]: g for g in r.json()["groups"]}


def _titulos(grupos: dict, clave: str) -> list[str]:
    return [r["title"] for r in grupos.get(clave, {}).get("results", [])]


async def test_busca_en_todo_lo_que_ve_administracion(app_client, db, seeded_org, login, active_admin_staff_user):
    org = seeded_org["org"].id
    case, obra = await approved_case_with_project(db, org)
    db.add(WarehouseItem(organization_id=org, name="Termostato Simpson", sku="AC-9001", brand="Honeywell"))
    await db.commit()
    oficina = await login(active_admin_staff_user.email)

    grupos = await _buscar(app_client, oficina, "simpson")
    assert _titulos(grupos, "customers") == ["Marge Simpson"]
    assert grupos["customers"]["results"][0]["url"].startswith("/customers/")
    # Expediente y obra por el nombre del cliente; artículo por su nombre.
    assert grupos["cases"]["results"][0]["url"] == f"/cases/{case.id}/review"
    assert grupos["projects"]["results"][0]["url"] == f"/projects/{obra.id}"
    assert _titulos(grupos, "items") == ["Termostato Simpson"]
    assert grupos["items"]["results"][0]["url"] == "/warehouse/items?q=AC-9001"
    assert grupos["customers"]["more_url"] == "/customers?q=simpson"

    # También por dirección, número de expediente y código del artículo.
    assert "cases" in await _buscar(app_client, oficina, "evergreen")
    assert "cases" in await _buscar(app_client, oficina, case.case_number)
    assert _titulos(await _buscar(app_client, oficina, "ac-9001"), "items") == ["Termostato Simpson"]


async def test_cada_grupo_solo_con_su_permiso(app_client, db, seeded_org, login, active_technician_user,
                                              active_salesperson_user, active_accounting_user):
    org = seeded_org["org"].id
    await approved_case_with_project(db, org)
    db.add(Supplier(organization_id=org, name="Simpson Supply"))
    await db.commit()

    # El técnico ve clientes (su rol tiene `customers.read`), pero no expedientes
    # ni proveedores, y la obra no es suya.
    tecnico = await _buscar(app_client, await login(active_technician_user.email), "simpson")
    assert set(tecnico) == {"customers"}

    # El vendedor no ve obras ni proveedores, y el expediente no es suyo.
    vendedor = await _buscar(app_client, await login(active_salesperson_user.email), "simpson")
    assert set(vendedor) <= {"customers"}

    # Contabilidad ve proveedores; Administración no los administra.
    conta = await _buscar(app_client, await login(active_accounting_user.email), "simpson")
    assert _titulos(conta, "suppliers") == ["Simpson Supply"]
    assert conta["suppliers"]["results"][0]["url"] == "/payables?tab=suppliers&q=Simpson%20Supply"


async def test_vendedor_solo_sus_expedientes_y_tecnico_solo_sus_obras(app_client, db, seeded_org, login,
                                                                      active_salesperson_user, active_technician_user):
    org = seeded_org["org"].id
    cliente = Customer(organization_id=org, legal_name="Homero Propio")
    db.add(cliente)
    await db.flush()
    propio = await case_service.create_case(
        db, organization_id=org, actor_id=active_salesperson_user.id, stage_code="new_prospect",
        customer_id=cliente.id, address_street="1 Calle Propia", assigned_salesperson_id=active_salesperson_user.id)
    await case_service.create_case(
        db, organization_id=org, actor_id=None, stage_code="new_prospect",
        address_street="2 Calle Propia", assigned_salesperson_id=uuid.uuid4())
    _, mia = await approved_case_with_project(db, org, technician_id=active_technician_user.id)
    await approved_case_with_project(db, org)

    vendedor = await _buscar(app_client, await login(active_salesperson_user.email), "calle propia")
    assert [r["url"] for r in vendedor["cases"]["results"]] == [f"/cases/{propio.id}/form"]

    tecnico = await _buscar(app_client, await login(active_technician_user.email), "evergreen")
    assert [r["url"] for r in tecnico["projects"]["results"]] == [f"/projects/{mia.id}"]


async def test_nada_de_otra_organizacion(app_client, db, seeded_org, second_org, login, active_admin_staff_user):
    db.add(Customer(organization_id=second_org["org"].id, legal_name="Bart Ajeno"))
    db.add(WarehouseItem(organization_id=second_org["org"].id, name="Bart Ajeno filtro"))
    await db.commit()
    assert await _buscar(app_client, await login(active_admin_staff_user.email), "ajeno") == {}


async def test_comodines_y_textos_cortos(app_client, db, seeded_org, login, active_admin_staff_user):
    org = seeded_org["org"].id
    db.add_all([Customer(organization_id=org, legal_name="Ventas 100% seguras"),
                Customer(organization_id=org, legal_name="Ventas 1000 seguras"),
                Customer(organization_id=org, legal_name="Casa_Azul"),
                Customer(organization_id=org, legal_name="CasaXAzul")])
    await db.commit()
    oficina = await login(active_admin_staff_user.email)

    assert _titulos(await _buscar(app_client, oficina, "100%"), "customers") == ["Ventas 100% seguras"]
    assert _titulos(await _buscar(app_client, oficina, "casa_"), "customers") == ["Casa_Azul"]
    # Una letra no busca (sería medio catálogo); los espacios de más no cuentan.
    r = await app_client.get(f"{API}/search", params={"q": "  v  "}, headers=oficina)
    assert r.json() == {"q": "v", "groups": []}
    assert (await app_client.get(f"{API}/search", params={"q": "x" * 101}, headers=oficina)).status_code == 422


async def test_pocos_por_grupo(app_client, db, seeded_org, login, active_admin_staff_user):
    org = seeded_org["org"].id
    db.add_all([Customer(organization_id=org, legal_name=f"Flanders {i:02d}") for i in range(12)])
    await db.commit()
    grupos = await _buscar(app_client, await login(active_admin_staff_user.email), "flanders")
    assert _titulos(grupos, "customers") == [f"Flanders {i:02d}" for i in range(5)]


async def test_sin_permisos_no_entra(app_client, login, active_roleless_user):
    r = await app_client.get(f"{API}/search", params={"q": "algo"}, headers=await login(active_roleless_user.email))
    assert r.status_code == 403
    assert (await app_client.get(f"{API}/search", params={"q": "algo"})).status_code == 401


async def test_facturas_filtra_por_numero_o_cliente(app_client, db, seeded_org, login, active_accounting_user):
    """El «Ver todos» de Facturas abre la lista filtrada con el mismo texto."""
    from datetime import date
    from decimal import Decimal

    from app.modules.billing.models import Invoice

    org = seeded_org["org"].id
    lisa = Customer(organization_id=org, legal_name="Lisa Factura")
    otro = Customer(organization_id=org, legal_name="Nelson Otro")
    db.add_all([lisa, otro])
    await db.flush()
    db.add_all([Invoice(organization_id=org, customer_id=lisa.id, invoice_number="FAC-2026-0042",
                        amount=Decimal("10"), issue_date=date.today()),
                Invoice(organization_id=org, customer_id=otro.id, invoice_number="FAC-2026-0099",
                        amount=Decimal("10"), issue_date=date.today())])
    await db.commit()
    conta = await login(active_accounting_user.email)

    por_cliente = (await app_client.get(f"{API}/invoices", params={"q": "lisa"}, headers=conta)).json()
    assert [i["invoice_number"] for i in por_cliente] == ["FAC-2026-0042"]
    por_numero = (await app_client.get(f"{API}/invoices", params={"q": "0099"}, headers=conta)).json()
    assert [i["invoice_number"] for i in por_numero] == ["FAC-2026-0099"]

    grupos = await _buscar(app_client, conta, "lisa")
    assert grupos["invoices"]["results"][0]["url"] == "/invoices?tab=invoices&q=FAC-2026-0042"
