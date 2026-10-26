"""Lote 3, fase D: INS-013 (enlace público de firma) y NOT-002 (mensajes en consola).

Antes, desde el equipo: `docker compose logs api worker --since <inicio de 3c> | python enlaces.py`
→ /tmp/links3c.json. PYTHONPATH=/app:/tmp python /tmp/lote3d.py → /tmp/lote3d.json
"""
import json

import httpx

from qa_comun import API, chk, e, esc, guardar

ENLACES = json.load(open("/tmp/links3c.json"))["todos"]
firma = [x["token"] for x in ENLACES if x["template"] == "customer_signature_request"]
reset = [x for x in ENLACES if x["template"] == "password_reset_request"]


def ins013():
    chk(f"Se enviaron {len(firma)} enlaces de firma (el segundo es el reenvío)", len(firma) >= 2, len(firma))
    viejo, nuevo = firma[-2], firma[-1]
    r = httpx.get(f"{API}/public/customer-signature", params={"token": viejo}, timeout=30)
    chk("Al reenviar, el enlace anterior deja de servir", r.status_code in (400, 404, 410), f"{r.status_code} {r.text[:150]}")
    r = httpx.get(f"{API}/public/customer-signature", params={"token": nuevo}, timeout=30)
    chk("El enlace vigente abre el acta", r.status_code == 200 and r.json().get("project_title"), r.status_code)
    alterado = nuevo[:-1] + ("A" if nuevo[-1] != "A" else "B")
    r = httpx.get(f"{API}/public/customer-signature", params={"token": alterado}, timeout=30)
    chk("Token alterado: «El enlace no es válido o ya expiró.»", r.status_code in (400, 404) and "no es válido"
        in r.json().get("detail", ""), f"{r.status_code} {r.text[:150]}")
    r = httpx.post(f"{API}/public/customer-signature", json={"customer_name": "QA", "signature_base64": e.png_signature()},
                   timeout=30)
    chk("Sin token: se rechaza (la pantalla dice «Enlace incompleto»)", r.status_code in (400, 404, 422),
        f"{r.status_code} {r.text[:150]}")
    r = httpx.post(f"{API}/public/customer-signature", json={"token": nuevo, "customer_name": "Cliente QA",
                                                             "signature_base64": e.png_signature()}, timeout=30)
    chk("El cliente firma con el enlace vigente", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    r = httpx.post(f"{API}/public/customer-signature", json={"token": nuevo, "customer_name": "Cliente QA",
                                                             "signature_base64": e.png_signature()}, timeout=30)
    chk("El mismo enlace no sirve para firmar otra vez", r.status_code in (400, 404, 409, 410), f"{r.status_code} {r.text[:150]}")


def not002():
    chk(f"El olvido de clave salió a la consola ({len(reset)} correos)", len(reset) >= 1, len(reset))
    chk(f"El enlace de firma salió a la consola ({len(firma)} correos)", len(firma) >= 1, len(firma))


esc("INS-013")
try:
    ins013()
except Exception as ex:  # noqa: BLE001
    chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
esc("NOT-002")
r = httpx.post(f"{API}/auth/password-reset/request", json={"email": "contabilidad@demo-org.com"}, timeout=30)
chk("Pedir el olvido de clave responde que se envió", r.status_code == 200, r.text[:150])
not002()
guardar("/tmp/lote3d.json")
print("ok")
