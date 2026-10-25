"""Cobro en línea (Stripe) y banca conectada (Plaid). Spec 2026-10-25-pagos-tarjeta.

Stripe y Plaid están simulados: `providers.stripe_request` y
`providers.plaid_request` se reemplazan. Las firmas de los webhooks de Stripe se
calculan de verdad con el secreto de prueba.
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.billing.models import InvoicePayment
from app.modules.finance.models import Expense
from app.modules.payments import providers
from app.modules.payments.models import BankConnection, BankTransaction
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"
SECRET = "whsec_prueba"


@pytest.fixture(autouse=True)
def configurado(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(s, "STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(s, "PLAID_CLIENT_ID", "cid")
    monkeypatch.setattr(s, "PLAID_SECRET", "psecret")
    monkeypatch.setattr(s, "FRONTEND_APP_URL", "https://app.example.com")


@pytest.fixture
def stripe(monkeypatch):
    llamadas = []

    async def falso(method, path, data=None, *, idempotency_key=None):
        llamadas.append((method, path, data))
        if path == "/v1/checkout/sessions":
            return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}
        if path.startswith("/v1/payment_intents/"):
            return {"id": path.rsplit("/", 1)[1], "latest_charge": {
                "payment_method_details": {"type": "card", "card": {"brand": "visa", "last4": "4242"}},
                "balance_transaction": {"fee": 4380}}}
        return {}

    monkeypatch.setattr(providers, "stripe_request", falso)
    return llamadas


def _firmado(evento: dict) -> tuple[bytes, dict]:
    cuerpo = json.dumps(evento).encode()
    t = int(time.time())
    firma = hmac.new(SECRET.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return cuerpo, {"Stripe-Signature": f"t={t},v1={firma}", "Content-Type": "application/json"}


async def _factura(app_client, h, monto=1500, email="cliente@example.com") -> dict:
    c = await app_client.post(f"{API}/customers", json={"legal_name": "Dueña de casa", "email": email,
                                                        "main_phone": "+16025550101", "data_consent_accepted": True},
                              headers=h)
    p = await app_client.post(f"{API}/projects", json={"customer_id": c.json()["id"], "title": "Cambio de AC"},
                              headers=h)
    r = await app_client.post(f"{API}/invoices", json={"project_id": p.json()["id"], "amount": monto}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _token(url: str) -> str:
    return url.rsplit("/", 1)[1]


async def _sesion_pagada(app_client, link, invoice_id, org_id, centavos, *, evento_id="evt_1", intent="pi_1",
                         tipo="checkout.session.completed", estado="paid"):
    cuerpo, cab = _firmado({"id": evento_id, "type": tipo, "data": {"object": {
        "id": "cs_test_1", "payment_status": estado, "amount_total": centavos, "payment_intent": intent,
        "metadata": {"organization_id": org_id, "invoice_id": invoice_id, "link_id": link["id"]}}}})
    return await app_client.post(f"{API}/webhooks/stripe", content=cuerpo, headers=cab)


async def test_cobro_con_enlace_de_principio_a_fin(app_client, stripe, seeded_org, active_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h)
    r = await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={"send_email": True}, headers=h)
    assert r.status_code == 201, r.text
    link = r.json()
    assert link["url"].startswith("https://app.example.com/pagar/") and link["sent_to_email"] == "cliente@example.com"
    token = _token(link["url"])

    # El cliente ve su factura y paga.
    vista = (await app_client.get(f"{API}/public/pay/{token}")).json()
    assert (vista["invoice_number"], vista["balance"], vista["amount_requested"]) == (inv["invoice_number"], "1500.00",
                                                                                      "1500.00")
    pago = await app_client.post(f"{API}/public/pay/{token}/checkout")
    assert pago.json()["url"].startswith("https://checkout.stripe.com")
    sesion = next(d for m, p, d in stripe if p == "/v1/checkout/sessions")
    assert sesion["line_items"][0]["price_data"]["unit_amount"] == 150000
    assert sesion["payment_method_types"] == ["card", "us_bank_account"]

    # Stripe avisa: el pago entra solo, con tarjeta y comisión.
    org = str(seeded_org["org"].id)
    r = await _sesion_pagada(app_client, link, inv["id"], org, 150000)
    assert r.status_code == 200 and r.json()["result"] == "ok"
    factura = (await app_client.get(f"{API}/invoices/{inv['id']}", headers=h)).json()
    assert factura["status"] == "paid"
    assert factura["payments"][0]["method"] == "Tarjeta Visa ····4242"
    # Reintento del mismo evento: no duplica.
    r = await _sesion_pagada(app_client, link, inv["id"], org, 150000)
    assert r.json()["result"] == "duplicate"
    assert len((await app_client.get(f"{API}/invoices/{inv['id']}", headers=h)).json()["payments"]) == 1
    # La página ya dice que está pagada y no abre otro pago.
    assert (await app_client.get(f"{API}/public/pay/{token}")).json()["status"] == "paid"
    assert (await app_client.post(f"{API}/public/pay/{token}/checkout")).status_code == 409


async def test_comision_y_reembolso_quedan_registrados(app_client, db, stripe, seeded_org, active_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h)
    link = (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=h)).json()
    org = str(seeded_org["org"].id)
    await _sesion_pagada(app_client, link, inv["id"], org, 150000, intent="pi_9")
    pago = (await db.execute(select(InvoicePayment).where(InvoicePayment.external_id == "pi_9"))).scalar_one()
    assert (pago.provider, pago.fee_amount) == ("stripe", Decimal("43.80"))
    # Reembolso parcial de 200 y luego total.
    for total, evt in ((20000, "evt_r1"), (150000, "evt_r2")):
        cuerpo, cab = _firmado({"id": evt, "type": "charge.refunded", "data": {"object": {
            "id": "ch_1", "payment_intent": "pi_9", "amount_refunded": total, "metadata": {}}}})
        assert (await app_client.post(f"{API}/webhooks/stripe", content=cuerpo, headers=cab)).status_code == 200
    factura = (await app_client.get(f"{API}/invoices/{inv['id']}", headers=h)).json()
    assert float(factura["balance"]) == 1500.0


async def test_anticipo_y_pago_desde_el_banco_en_camino(app_client, stripe, seeded_org, active_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h, monto=8000)
    mal = await app_client.post(f"{API}/invoices/{inv['id']}/payment-links",
                                json={"kind": "deposit", "amount": "9000"}, headers=h)
    assert (mal.status_code, mal.json()["code"]) == (400, "invalid_deposit")
    link = (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links",
                                  json={"kind": "deposit", "amount": "4000"}, headers=h)).json()
    token = _token(link["url"])
    assert (await app_client.get(f"{API}/public/pay/{token}")).json()["amount_requested"] == "4000.00"
    org = str(seeded_org["org"].id)
    # ACH: la sesión termina sin pagar todavía; el pago entra cuando el banco confirma.
    await _sesion_pagada(app_client, link, inv["id"], org, 400000, estado="unpaid", evento_id="evt_a1", intent="pi_ach")
    assert (await app_client.get(f"{API}/public/pay/{token}")).json()["status"] == "processing"
    await _sesion_pagada(app_client, link, inv["id"], org, 400000, tipo="checkout.session.async_payment_succeeded",
                         evento_id="evt_a2", intent="pi_ach")
    factura = (await app_client.get(f"{API}/invoices/{inv['id']}", headers=h)).json()
    assert (factura["status"], float(factura["balance"])) == ("partial", 4000.0)


async def test_firma_invalida_y_enlace_reemplazado(app_client, stripe, seeded_org, active_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h)
    viejo = (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=h)).json()
    nuevo = (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=h)).json()
    assert (await app_client.get(f"{API}/public/pay/{_token(viejo['url'])}")).status_code == 404
    assert (await app_client.get(f"{API}/public/pay/{_token(nuevo['url'])}")).status_code == 200
    assert (await app_client.get(f"{API}/public/pay/inventado")).status_code == 404
    cuerpo = json.dumps({"id": "evt_x", "type": "checkout.session.completed", "data": {"object": {}}}).encode()
    malo = await app_client.post(f"{API}/webhooks/stripe", content=cuerpo,
                                 headers={"Stripe-Signature": f"t={int(time.time())},v1=deadbeef"})
    assert malo.status_code == 400
    assert (await app_client.post(f"{API}/webhooks/stripe", content=cuerpo)).status_code == 400


async def test_permisos_y_otra_organizacion(app_client, db, stripe, seeded_org, active_admin_user,
                                           active_salesperson_user, active_technician_user, second_org_admin_user):
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h)
    vend = await headers_for(app_client, active_salesperson_user.email)
    assert (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=vend)).status_code == 403
    otro = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=otro)).status_code == 404
    # El técnico cobra solo las facturas de las obras que trabaja.
    tec = await headers_for(app_client, active_technician_user.email)
    r = await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=tec)
    assert r.status_code == 404
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    propia = await app_client.post(f"{API}/invoices", json={"project_id": str(obra.id), "amount": 300}, headers=h)
    assert (await app_client.get(f"{API}/payments/projects/{obra.id}/invoices", headers=tec)).json()[0]["balance"] == "300.00"
    r = await app_client.post(f"{API}/invoices/{propia.json()['id']}/payment-links", json={}, headers=tec)
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Banca conectada
# ---------------------------------------------------------------------------

TX = [
    {"transaction_id": "t1", "account_id": "acc_card", "date": "2026-10-20", "amount": 86.40, "name": "HOME DEPOT #4412",
     "merchant_name": "Home Depot", "pending": False, "personal_finance_category": {"primary": "GENERAL_MERCHANDISE"}},
    {"transaction_id": "t2", "account_id": "acc_card", "date": "2026-10-21", "amount": 54.10, "name": "SHELL OIL 5741",
     "merchant_name": "Shell", "pending": False},
    {"transaction_id": "t3", "account_id": "acc_chk", "date": "2026-10-22", "amount": -1456.20, "name": "STRIPE TRANSFER",
     "pending": False},
    {"transaction_id": "t4", "account_id": "acc_card", "date": "2026-10-23", "amount": 12.00, "name": "PENDIENTE",
     "pending": True},
]


@pytest.fixture
def plaid(monkeypatch):
    estado = {"pagina": 0}

    async def falso(path, body):
        if path == "/item/public_token/exchange":
            return {"access_token": "access-sandbox-secreto", "item_id": "item_1"}
        if path == "/accounts/get":
            return {"accounts": [
                {"account_id": "acc_card", "name": "Business Card", "mask": "1234", "type": "credit",
                 "subtype": "credit card", "balances": {"current": 2310.55, "iso_currency_code": "USD"}},
                {"account_id": "acc_chk", "name": "Checking", "mask": "9876", "type": "depository",
                 "subtype": "checking", "balances": {"current": 45210.00, "available": 45000.0}}]
                + ([{"account_id": "acc_loan", "name": "Auto Loan", "mask": "9003", "type": "loan",
                     "subtype": "auto", "balances": {"current": 23211.33}}] if estado.get("prestamo") else [])}
        if path == "/transactions/sync":
            estado["pagina"] += 1
            if estado["pagina"] == 1:
                extra = [{"transaction_id": "t9", "account_id": "acc_loan", "date": "2026-10-20", "amount": 410.0,
                          "name": "LOAN PAYMENT", "pending": False}] if estado.get("prestamo") else []
                return {"added": TX + extra, "modified": [], "removed": [], "next_cursor": "c1", "has_more": False}
            return {"added": [], "modified": [], "removed": [], "next_cursor": "c1", "has_more": False}
        if path == "/link/token/create":
            return {"link_token": "link-sandbox-1"}
        return {}

    monkeypatch.setattr(providers, "plaid_request", falso)
    return estado


async def _conectar(app_client, h):
    r = await app_client.post(f"{API}/bank-feeds/connections", json={
        "public_token": "public-sandbox-1", "institution_name": "Chase"}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def test_conectar_banco_y_revisar_como_quickbooks(app_client, db, plaid, seeded_org, active_accounting_user):
    h = await headers_for(app_client, active_accounting_user.email)
    assert (await app_client.post(f"{API}/bank-feeds/link-token", headers=h)).json()["link_token"] == "link-sandbox-1"
    conexion = await _conectar(app_client, h)
    assert [a["mask"] for a in conexion["accounts"]] == ["1234", "9876"]
    # El token de Plaid queda cifrado, nunca en claro.
    fila = (await db.execute(select(BankConnection))).scalar_one()
    assert "access-sandbox-secreto" not in fila.access_token_encrypted
    assert providers.decrypt(fila.access_token_encrypted) == "access-sandbox-secreto"

    por_revisar = (await app_client.get(f"{API}/bank-feeds/transactions", params={"status": "review"}, headers=h)).json()
    assert len(por_revisar) == 4
    deposito = next(t for t in por_revisar if t["description"] == "STRIPE TRANSFER")
    assert (deposito["received"], deposito["spent"]) == ("1456.20", None)
    pendiente = next(t for t in por_revisar if t["pending"])
    r = await app_client.post(f"{API}/bank-feeds/transactions/{pendiente['id']}/add", json={"category": "other"},
                              headers=h)
    assert r.json()["code"] == "bank_tx_pending"

    # Agregar: gasto de la empresa aprobado y cargado a la obra.
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    home = next(t for t in por_revisar if t["merchant_name"] == "Home Depot")
    r = await app_client.post(f"{API}/bank-feeds/transactions/{home['id']}/add",
                              json={"category": "small_materials", "project_id": str(obra.id)}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "categorized"
    gasto = (await db.execute(select(Expense).where(Expense.id == r.json()["expense_id"]))).scalar_one()
    assert (gasto.status, gasto.payment_method, gasto.amount, gasto.project_id) == (
        "approved", "company_card", Decimal("86.40"), obra.id)
    # Deshacer lo devuelve a revisión y borra el gasto que creó.
    await app_client.post(f"{API}/bank-feeds/transactions/{home['id']}/undo", headers=h)
    assert (await db.execute(select(Expense).where(Expense.id == gasto.id))).scalar_one_or_none() is None
    # Excluir el depósito (transferencia).
    r = await app_client.post(f"{API}/bank-feeds/transactions/{deposito['id']}/exclude",
                              json={"memo": "Depósito de Stripe"}, headers=h)
    assert r.json()["status"] == "excluded"
    conteo = (await app_client.get(f"{API}/bank-feeds/counts", headers=h)).json()
    assert conteo == {"review": 3, "excluded": 1}


async def test_coincidir_con_el_gasto_del_tecnico_y_reglas(app_client, db, plaid, seeded_org, active_accounting_user,
                                                          active_technician_user):
    h = await headers_for(app_client, active_accounting_user.email)
    # El técnico ya había subido el gasto de gasolina (54,10) con su recibo.
    db.add(Expense(organization_id=seeded_org["org"].id, user_id=active_technician_user.id,
                   expense_date=date(2026, 10, 21), category="fuel", amount=Decimal("54.10"),
                   description="Gasolina camioneta", payment_method="own_money", status="submitted"))
    await db.commit()
    # Regla creada antes de conectar: HOME DEPOT → material menor.
    r = await app_client.post(f"{API}/bank-feeds/rules", json={
        "name": "Home Depot", "contains": "home depot", "category": "small_materials"}, headers=h)
    assert r.status_code == 201, r.text
    await _conectar(app_client, h)
    filas = (await app_client.get(f"{API}/bank-feeds/transactions", headers=h)).json()
    home = next(t for t in filas if t["merchant_name"] == "Home Depot")
    assert (home["suggested_category"], home["suggested_by_rule"]) == ("small_materials", True)
    shell = next(t for t in filas if t["merchant_name"] == "Shell")
    cands = (await app_client.get(f"{API}/bank-feeds/transactions/{shell['id']}/candidates", headers=h)).json()
    assert cands[0]["type"] == "expense" and cands[0]["label"] == "Gasto: Gasolina camioneta"
    r = await app_client.post(f"{API}/bank-feeds/transactions/{shell['id']}/match",
                              json={"matched_type": "expense", "matched_id": cands[0]["id"]}, headers=h)
    assert r.json()["status"] == "categorized"
    gasto = (await db.execute(select(Expense).where(Expense.id == cands[0]["id"]))).scalar_one()
    # Lo pagó la tarjeta de la empresa: ya no se le reembolsa al técnico.
    assert gasto.payment_method == "company_card"
    # Aceptar en lote lo que propuso la regla.
    r = await app_client.post(f"{API}/bank-feeds/transactions/accept", json={"ids": [home["id"]]}, headers=h)
    assert r.json()["accepted"] == 1
    assert (await db.execute(select(BankTransaction).where(BankTransaction.review_status == "categorized"))
            ).scalars().all().__len__() == 2


async def test_banca_solo_para_quien_tiene_permiso_y_su_organizacion(app_client, plaid, seeded_org, active_accounting_user,
                                                                   active_technician_user, active_admin_staff_user,
                                                                   second_org_admin_user):
    h = await headers_for(app_client, active_accounting_user.email)
    await _conectar(app_client, h)
    filas = (await app_client.get(f"{API}/bank-feeds/transactions", headers=h)).json()
    for quien in (active_technician_user, active_admin_staff_user):
        x = await headers_for(app_client, quien.email)
        assert (await app_client.get(f"{API}/bank-feeds/transactions", headers=x)).status_code == 403
    otro = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"{API}/bank-feeds/transactions", headers=otro)).json() == []
    assert (await app_client.post(f"{API}/bank-feeds/transactions/{filas[0]['id']}/exclude", json={},
                                  headers=otro)).status_code == 404


async def test_el_formulario_de_stripe_va_codificado_y_anidado(monkeypatch):
    """Regresión: el cliente asíncrono de httpx fallaba con la lista de pares
    («Attempted to send an sync request»). Se prueba la llamada real contra un
    transporte falso, sin red."""
    import httpx

    enviado = {}

    def responder(request: httpx.Request) -> httpx.Response:
        enviado["cuerpo"] = request.content.decode()
        enviado["tipo"] = request.headers["content-type"]
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/x"})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(responder), **kw))
    r = await providers.stripe_request("POST", "/v1/checkout/sessions", {
        "line_items": [{"quantity": 1, "price_data": {"unit_amount": 150000}}], "payment_method_types": ["card"]})
    assert r["id"] == "cs_1" and enviado["tipo"] == "application/x-www-form-urlencoded"
    assert "line_items%5B0%5D%5Bprice_data%5D%5Bunit_amount%5D=150000" in enviado["cuerpo"]
    assert "payment_method_types%5B0%5D=card" in enviado["cuerpo"]


async def test_la_comision_que_llega_despues_se_completa(app_client, db, monkeypatch, seeded_org, active_admin_user):
    """En Stripe real la comisión se asocia unos segundos después del pago y llega
    con `charge.updated` (probado en modo prueba el 25 oct: 250 USD → 7,55)."""
    async def sin_comision(method, path, data=None, *, idempotency_key=None):
        if path.startswith("/v1/payment_intents/"):
            return {"latest_charge": {"payment_method_details": {"type": "card", "card": {"brand": "visa", "last4": "4242"}},
                                      "balance_transaction": None}}
        if path.startswith("/v1/balance_transactions/"):
            return {"fee": 755}
        return {"id": "cs_1", "url": "https://checkout.stripe.com/x"}

    monkeypatch.setattr(providers, "stripe_request", sin_comision)
    h = await headers_for(app_client, active_admin_user.email)
    inv = await _factura(app_client, h, monto=250)
    link = (await app_client.post(f"{API}/invoices/{inv['id']}/payment-links", json={}, headers=h)).json()
    org = str(seeded_org["org"].id)
    await _sesion_pagada(app_client, link, inv["id"], org, 25000, intent="pi_fee", evento_id="evt_f1")
    pago = (await db.execute(select(InvoicePayment).where(InvoicePayment.external_id == "pi_fee"))).scalar_one()
    assert pago.fee_amount is None
    cuerpo, cab = _firmado({"id": "evt_f2", "type": "charge.updated", "data": {"object": {
        "id": "ch_f", "payment_intent": "pi_fee", "balance_transaction": "txn_1", "metadata": {}}}})
    assert (await app_client.post(f"{API}/webhooks/stripe", content=cuerpo, headers=cab)).status_code == 200
    await db.refresh(pago)
    assert pago.fee_amount == Decimal("7.55")


async def test_prestamos_llegan_ocultos_y_se_pueden_mostrar(app_client, plaid, seeded_org, active_accounting_user):
    plaid["prestamo"] = True
    h = await headers_for(app_client, active_accounting_user.email)
    conexion = await _conectar(app_client, h)
    prestamo = next(a for a in conexion["accounts"] if a["mask"] == "9003")
    assert prestamo["active"] is False
    # De la cuenta oculta no llega nada a revisar ni al contador.
    por_revisar = (await app_client.get(f"{API}/bank-feeds/transactions", params={"status": "review"}, headers=h)).json()
    assert "LOAN PAYMENT" not in [t["description"] for t in por_revisar]
    assert (await app_client.get(f"{API}/bank-feeds/counts", headers=h)).json() == {"review": 4}
    r = await app_client.patch(f"{API}/bank-feeds/accounts/{prestamo['id']}", json={"visible": True}, headers=h)
    assert next(a for a in r.json()["accounts"] if a["mask"] == "9003")["active"] is True
    assert (await app_client.get(f"{API}/bank-feeds/counts", headers=h)).json() == {"review": 5}
    # Otra cuenta que no existe (u otra organización): 404.
    r = await app_client.patch(f"{API}/bank-feeds/accounts/{uuid.uuid4()}", json={"visible": False}, headers=h)
    assert r.status_code == 404


async def test_material_menor_de_la_tarjeta_suma_como_material(app_client, db, plaid, seeded_org,
                                                               active_accounting_user):
    from app.modules.finance.profitability import project_costs

    h = await headers_for(app_client, active_accounting_user.email)
    await _conectar(app_client, h)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    filas = (await app_client.get(f"{API}/bank-feeds/transactions", params={"status": "review"}, headers=h)).json()
    home = next(t for t in filas if t["merchant_name"] == "Home Depot")
    shell = next(t for t in filas if t["merchant_name"] == "Shell")
    await app_client.post(f"{API}/bank-feeds/transactions/{home['id']}/add",
                          json={"category": "small_materials", "project_id": str(obra.id)}, headers=h)
    await app_client.post(f"{API}/bank-feeds/transactions/{shell['id']}/add",
                          json={"category": "fuel", "project_id": str(obra.id)}, headers=h)
    costos = (await project_costs(db, seeded_org["org"].id, {obra.id}))[obra.id]
    assert costos["materials"] == Decimal("86.40")
    assert costos["field_expenses"] == Decimal(shell["spent"])
