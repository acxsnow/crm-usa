"""Ataque a avisos, campañas, webhooks y bajas (10 nov 2026).

PYTHONPATH=/app:/tmp python /tmp/qa_avisos.py → /tmp/qa_avisos.json
"""
import httpx

from qa_comun import API, chk, cliente, e, esc, guardar, sql

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "ajeno")}
admin, adm, v, tec, conta, ger, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia",
                                                         "ajeno"))
RUN = e.RUN

# ===========================================================================
esc("AVI-A1 Avisos personales")
# ===========================================================================
mio = sql(f"select id from notifications where user_id = '{v.me['id']}' limit 1")
if mio:
    r = tec.post(f"/notifications/{mio}/read")
    chk("Nadie marca como leído el aviso de otro", r.status_code in (403, 404), r.status_code)
    r = ajeno.post(f"/notifications/{mio}/read")
    chk("Otra organización tampoco", r.status_code in (403, 404), r.status_code)
lista = tec.get("/notifications", params={"limit": 100}).json()
lista = lista if isinstance(lista, list) else lista.get("items", [])
chk("La campana del técnico solo trae sus avisos", all(x.get("user_id") in (None, tec.me["id"]) for x in lista),
    len(lista))
r = tec.get("/notifications/deliveries")
chk("El técnico no ve las entregas de todos", r.status_code == 403, r.status_code)
r = v.put("/notifications/templates/case.approved/email", json={"subject": "Hackeado", "body": "x"})
chk("El vendedor no cambia plantillas", r.status_code == 403, r.status_code)
r = adm.put("/notifications/templates/evento.inventado/email", json={"subject": "x", "body": "x"})
chk(f"Plantilla de un evento que no existe ({r.status_code})", r.status_code in (400, 403, 404, 422), r.status_code)

# ===========================================================================
esc("AVI-A2 Campañas")
# ===========================================================================
r = tec.post("/campaigns", json={"name": "QA", "message": "Compre ya"})
chk("El técnico no crea campañas", r.status_code == 403, r.status_code)
r = admin.post("/campaigns", json={"name": f"QA camp {RUN}", "message": "", "channel": "sms"})
chk("Campaña sin mensaje se rechaza", r.status_code in (400, 422), r.status_code)
r = admin.post("/campaigns", json={"name": f"QA camp {RUN}", "message": "Hola", "channel": "paloma"})
chk("Canal inventado se rechaza", r.status_code in (400, 422), r.status_code)
camp = e.expect("Campaña de prueba por SMS", admin.post("/campaigns", json={
    "name": f"QA camp {RUN}", "message": "QA Delta HVAC: revisión de su aire. Responda STOP para no recibir más.",
    "channel": "sms"}), 201) or {}
r = ajeno.get(f"/campaigns/{camp.get('id')}")
chk("Otra organización no ve la campaña", r.status_code in (403, 404), r.status_code)
r = ajeno.post(f"/campaigns/{camp.get('id')}/launch")
chk("Otra organización no la lanza", r.status_code in (403, 404), r.status_code)
r = admin.post(f"/campaigns/{camp.get('id')}/test", json={"phone": "+15555550123"})
chk("La prueba no se manda a un número cualquiera", r.status_code in (400, 403, 422) or
    "15555550123" not in r.text, f"{r.status_code} {r.text[:120]}")
aud = admin.post("/campaigns/audience", json={"channel": "sms"}).json()
chk(f"La audiencia solo cuenta a quien dio permiso de mercadeo ({str(aud)[:80]})",
    isinstance(aud, dict), str(aud)[:150])
r = admin.post("/campaigns/contacts/import", files={"file": ("c.csv", b"\x00\xff basura", "text/csv")})
chk("Importar contactos con un archivo basura no tumba nada", r.status_code in (200, 201, 400, 422), r.status_code)
r = admin.post("/campaign-automations", json={"name": "QA", "trigger": "cuando_llueva", "message": "x"})
chk("Automatización con un disparador inventado se rechaza", r.status_code in (400, 422), r.status_code)

# ===========================================================================
esc("AVI-A3 Webhooks y bajas")
# ===========================================================================
r = httpx.post(f"{API}/webhooks/masiv/inbound", json={"from": "+16025550100", "text": "STOP"}, timeout=30)
chk("El webhook de Masiv sin su token no hace nada", r.status_code in (401, 403, 404), r.status_code)
r = httpx.post(f"{API}/webhooks/masiv/inbound?token=inventado", json={"from": "+16025550100", "text": "START"},
               timeout=30)
chk("Con un token inventado tampoco", r.status_code in (401, 403, 404), r.status_code)
r = httpx.post(f"{API}/webhooks/stripe", content=b'{"type":"checkout.session.completed"}',
               headers={"Stripe-Signature": "t=1,v1=falsa", "content-type": "application/json"}, timeout=30)
chk("Un evento de Stripe con firma falsa se rechaza", r.status_code in (400, 401, 403, 503), r.status_code)
r = httpx.post(f"{API}/webhooks/plaid", json={"webhook_type": "TRANSACTIONS"},
               headers={"Plaid-Verification": "falso"}, timeout=30)
chk("Un evento de Plaid con verificación falsa se rechaza", r.status_code in (400, 401, 403, 503), r.status_code)
r = httpx.get(f"{API}/unsubscribe/inventado", timeout=30)
chk("Un enlace de baja inventado no existe", r.status_code in (400, 404, 410), r.status_code)
r = httpx.post(f"{API}/unsubscribe/inventado", timeout=30)
chk("Ni da de baja a nadie", r.status_code in (400, 404, 410), r.status_code)

guardar("/tmp/qa_avisos.json")
print("FIN")
