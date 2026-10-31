"""«Guardar y seguir» en el formulario del vendedor (29 oct): sin obligatorios no
avanza y muestra cuáles faltan; el aviso verde solo sale si se guardó algo."""
import random

import httpx
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

API = "http://api:8000/api/v1"
limpiar()
tok = httpx.post(f"{API}/auth/login", json={"email": "vendedor@demo-org.com", "password": "ChangeMe123!"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
prog = next(m for m in httpx.get(f"{API}/me/programs", headers=h).json() if m["program"]["code"] == "AZ_EFFICIENCY")
n = random.randint(1000, 9999)
body = {"result": "opened", "address_street": f"{n} QA Guardar Paso Rd", "address_unit": "", "address_city": "Phoenix",
        "address_state": "AZ", "address_zip": "85001", "latitude": 33.45, "longitude": -112.07,
        "program_id": prog["program"]["id"], "notes": "QA guardar y seguir"}
if prog["zones"]:
    body["zone_id"] = prog["zones"][0]["id"]
caso = httpx.post(f"{API}/visits", json=body, headers=h).json()["case"]["id"]

esc("VEN-005")
with sync_playwright() as p:
    nav = p.chromium.launch()
    s = Sesion(nav, "vendedor", vista=CELULAR, is_mobile=True, has_touch=True)
    s.ir(f"/cases/{caso}/form", 3500)
    toasts = lambda: s.pg.locator("text=Paso guardado").count() + s.pg.locator("text=Cambios guardados").count()
    s.pg.get_by_role("button", name="Guardar y seguir").click()
    s.pg.wait_for_timeout(2000)
    t = s.texto()
    chk("Sin llenar nada no sale el aviso verde", toasts() == 0, "")
    chk("Muestra los obligatorios que faltan en el paso", "datos obligatorios" in t and "Nombre completo" in t, t[:300])
    chk("Se queda en el paso Cliente", s.pg.locator("text=Seguir sin completarlos").count() == 1, "")
    foto(s.pg, "faltan-obligatorios", completa=True)
    s.pg.get_by_label("Nombre completo").fill("QA Paso Guardado")
    s.pg.get_by_role("button", name="Guardar y seguir").click()
    s.pg.wait_for_timeout(2500)
    chk("Al escribir algo y guardar sale «Paso guardado»", s.pg.locator("text=Paso guardado").count() >= 1, s.texto()[:200])
    s.pg.get_by_role("button", name="Seguir sin completarlos ›").click()
    s.pg.wait_for_timeout(2500)
    chk("«Seguir sin completarlos» pasa al siguiente paso", s.pg.locator("text=Seguir sin completarlos").count() == 0
        and s.pg.get_by_label("Nombre completo").count() == 0, s.texto()[:200])
    foto(s.pg, "siguiente-paso", completa=True)
    s.cerrar()
    nav.close()
guardar("guardar_paso.json")
print("caso", caso)
