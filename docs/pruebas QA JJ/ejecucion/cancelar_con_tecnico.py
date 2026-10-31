"""Cancelar la obra con el técnico en la casa (QA de José, 31 oct 2026): con
«Llegué» marcado hoy, el formulario avisa y no deja cancelar sin «Ya hablé con
el técnico». No se envía: solo se revisa el formulario."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from ui_comun import Sesion, chk, esc, foto, guardar

pid = Path("_presencia.txt").read_text().split()[0]
esc("INS-012")
with sync_playwright() as p:
    nav = p.chromium.launch()
    s = Sesion(nav, "adm")
    s.ir(f"/projects/{pid}", 3500)
    s.pg.locator("#acta-step-release .acta-step-head").click()
    s.pg.wait_for_timeout(1200)
    s.pg.get_by_role("button", name="Cancelar la obra…").click()
    s.pg.wait_for_timeout(2000)
    paso = s.pg.locator("#acta-step-release")
    t = paso.inner_text()
    chk("Avisa que el técnico marcó «Llegué» y sugiere la visita fallida",
        "marcó «Llegué»" in t and "No se pudo hacer la visita" in t, t[:400])
    boton = paso.get_by_role("button", name="Cancelar la obra", exact=True)
    s.pg.get_by_label("Por qué se cancela").fill("QA: el cliente desistió en la puerta")
    chk("Sin la casilla, «Cancelar la obra» queda deshabilitado", boton.is_disabled(), "")
    foto(s.pg, "tecnico-en-la-obra", completa=True)
    s.pg.get_by_label("Ya hablé con el técnico y sabe que no instala.").check()
    chk("Con la casilla marcada se habilita", not boton.is_disabled(), "")
    s.cerrar()
    nav.close()
guardar("cancelar_con_tecnico.json")
