"""Documento de identidad por las dos caras y visor de «Ver» (29 oct 2026).

1. Como Administrador (por API, igual que en Configuración de programas): trae
   el campo nuevo del catálogo, crea la versión 2 de Arizona y TECH con el
   frente «(frente)» obligatorio y el reverso opcional, y la publica.
2. Como vendedor en el celular: abre una puerta de Arizona, ve las dos fotos,
   sube el frente y «Ver» la muestra encima de la pantalla.
"""
import io
import random

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

API = "http://api:8000/api/v1"


def cliente(correo):
    limpiar()
    tok = httpx.post(f"{API}/auth/login", json={"email": correo, "password": "ChangeMe123!"}).json()["access_token"]
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {tok}"}, timeout=60)


esc("VEN-004")
adm = cliente("admin@demo-org.com")
adm.post("/programs/install-defaults")
reverso = next(f for f in adm.get("/fields").json() if f["key"] == "customer.id_photo_back")
for prog in adm.get("/programs").json():
    if prog["code"] not in ("AZ_EFFICIENCY", "TECH_CLEAN_CA"):
        continue
    versiones = adm.get(f"/programs/{prog['id']}/versions").json()
    pub = next(v for v in versiones if v["status"] == "published")
    d = adm.get(f"/program-versions/{pub['id']}").json()
    if any(f["key"] == "customer.id_photo_back" for s in d["definition"]["steps"] for f in s["fields"]):
        chk(f"{prog['code']}: la versión publicada ya pide el reverso", True, pub["version"])
        continue
    borrador = next((v for v in versiones if v["status"] == "draft"), None) or adm.post(f"/programs/{prog['id']}/versions").json()
    d = adm.get(f"/program-versions/{borrador['id']}").json()["definition"]
    paso = next(s for s in d["steps"] if s["code"] == "customer")
    frente = next(f for f in paso["fields"] if f["key"] == "customer.id_photo")
    adm.patch(f"/workflow-step-fields/{frente['id']}", json={"label_override": "Foto del documento de identidad (frente)"})
    r = adm.post(f"/workflow-steps/{paso['id']}/fields", json={"field_id": reverso["id"], "requirement": "optional"})
    nuevo = r.json()["id"]
    # Queda justo después del frente.
    orden = [f["key"] for f in adm.get(f"/program-versions/{borrador['id']}").json()["definition"]["steps"][0]["fields"]]
    for _ in range(len(orden) - orden.index("customer.id_photo") - 2):
        adm.post(f"/workflow-step-field/{nuevo}/move".replace("field/", "fields/"), json={"direction": "up"})
    r = adm.post(f"/program-versions/{borrador['id']}/publish")
    chk(f"{prog['code']}: versión {borrador['version']} publicada con frente y reverso", r.status_code == 200, r.text[:200])

v = cliente("vendedor@demo-org.com")
az = next(m for m in v.get("/me/programs").json() if m["program"]["code"] == "AZ_EFFICIENCY")
n = random.randint(1000, 9999)
body = {"result": "opened", "address_street": f"{n} QA Dos Caras Ave", "address_city": "Phoenix", "address_state": "AZ",
        "address_zip": "85001", "latitude": 33.45, "longitude": -112.07, "program_id": az["program"]["id"]}
if az["zones"]:
    body["zone_id"] = az["zones"][0]["id"]
caso = v.post("/visits", json=body).json()["case"]["id"]

img = io.BytesIO()
Image.new("RGB", (900, 560), (40, 90, 160)).save(img, format="JPEG")
with sync_playwright() as p:
    nav = p.chromium.launch()
    s = Sesion(nav, "vendedor", vista=CELULAR, is_mobile=True, has_touch=True)
    s.ir(f"/cases/{caso}/form", 3500)
    t = s.texto()
    chk("El paso Cliente pide el frente y el reverso del documento", "(frente)" in t and "(reverso)" in t, t[-600:])
    entrada = s.pg.locator("input[type=file]").first
    entrada.set_input_files({"name": "id-frente.jpg", "mimeType": "image/jpeg", "buffer": img.getvalue()})
    s.pg.wait_for_timeout(3500)
    s.pg.get_by_role("button", name="Ver").first.click()
    s.pg.wait_for_timeout(2500)
    visor = s.pg.locator(".file-viewer img")
    chk("«Ver» abre la foto encima de la pantalla", visor.count() == 1 and visor.evaluate("i => i.naturalWidth") > 0, "")
    foto(s.pg, "ver-foto-documento")
    s.pg.get_by_role("button", name="Cerrar").click()
    s.pg.wait_for_timeout(500)
    chk("«Cerrar» vuelve al formulario", s.pg.locator(".file-viewer").count() == 0, "")
    foto(s.pg, "dos-caras", completa=True)
    s.cerrar()
    nav.close()
guardar("id_dos_caras.json")
