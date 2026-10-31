"""Salidas de bodega y técnico de la obra (QA de José, 31 oct 2026): sin técnico
no se pide material, y quien pidió una salida la anula con motivo."""
import httpx
from playwright.sync_api import sync_playwright

from ui_comun import Sesion, chk, esc, foto, guardar, limpiar

API = "http://api:8000/api/v1"
limpiar()
tok = httpx.post(f"{API}/auth/login", json={"email": "administracion@demo-org.com", "password": "ChangeMe123!"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
obras = httpx.get(f"{API}/projects", headers=h, params={"limit": 100}).json()
obras = obras["items"] if isinstance(obras, dict) else obras
sin_tecnico = next((o for o in obras if not o.get("primary_technician_user_id") and o.get("status") in ("planning", "scheduled")), None)
# Una salida de prueba propia (no se toca SAL-2026-0004 de José).
con_tecnico = next(o for o in obras if o.get("primary_technician_user_id") and o.get("status") in ("planning", "scheduled"))
items = httpx.get(f"{API}/warehouse/items", headers=h, params={"limit": 1}).json()
items = items["items"] if isinstance(items, dict) else items
prueba = httpx.post(f"{API}/warehouse/releases", headers=h, json={
    "lines": [{"item_id": items[0]["id"], "quantity": "1"}], "project_id": con_tecnico["id"],
    "note": "QA anular"}).json()
numero = httpx.post(f"{API}/warehouse/releases/{prueba['id']}/submit", headers=h).json()["number"]

esc("BOD-005")
with sync_playwright() as p:
    nav = p.chromium.launch()
    s = Sesion(nav, "adm")
    if sin_tecnico:
        s.ir(f"/projects/{sin_tecnico['id']}", 3500)
        # El panel de materiales vive dentro del paso «Orden liberada».
        s.pg.locator("#acta-step-release .acta-step-head").click()
        s.pg.wait_for_timeout(1500)
        t = s.pg.locator("#acta-step-release").inner_text()
        chk("Obra sin técnico: no muestra «Pedir material a bodega» y avisa qué hacer primero",
            "Pedir material a bodega" not in t and "Primero asigna el técnico" in t, t[:300])
        foto(s.pg, "obra-sin-tecnico", completa=True)
    else:
        chk("Hay una obra sin técnico para probar el aviso", False, "ninguna obra sin técnico en la base")
    s.ir("/warehouse/releases", 3500)
    s.pg.get_by_role("tab", name="Todas las salidas").click()
    s.pg.wait_for_timeout(2500)
    fila = s.pg.locator("tr").filter(has_text=numero)
    chk(f"{numero} tiene el botón «Anular»", fila.get_by_role("button", name="Anular").count() == 1, fila.inner_text()[:200])
    fila.get_by_role("button", name="Anular").click()
    s.pg.wait_for_timeout(800)
    s.pg.get_by_label("Motivo").fill("QA: la pedí antes de asignar el técnico")
    foto(s.pg, "anular-motivo")
    s.pg.get_by_role("button", name="Anular la salida").click()
    s.pg.wait_for_timeout(2500)
    t = s.pg.locator("tr").filter(has_text=numero).inner_text()
    chk("Queda «Anulada» con el motivo", "Anulada" in t and "QA: la pedí antes" in t, t[:200])
    foto(s.pg, "anulada")
    s.cerrar()
    nav.close()
guardar("salida_tecnico.json")
