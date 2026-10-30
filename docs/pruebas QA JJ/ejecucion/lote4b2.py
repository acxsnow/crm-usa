"""Lote 4b2: repite INS-012 y BOD-011 del lote 4b, que fallaron por el script
(campos sin `input[type=text]` y la orden autorizada en «Todas las salidas").
Usa los mismos datos de `prep4b.py`. Ver `ui_comun.py` para correrlo.
"""
import json

from playwright.sync_api import sync_playwright

from ui_comun import QA, Sesion, chk, esc, foto, guardar, seguro

D = json.loads((QA / "ejecucion" / "prep4b.json").read_text())


def paso(pg, clave):
    s = pg.locator(f"#acta-step-{clave}")
    if s.locator(".acta-step-body").count() == 0:
        s.locator(".acta-step-head").click()
        pg.wait_for_timeout(1000)
    return s


def ins012(nav):
    # La salida por autorizar ya se rechazó en el lote 4b; queda el material afuera.
    s = Sesion(nav, "admin")
    s.ir(f"/projects/{D['pid_cancelar']}", 3500)
    paso(s.pg, "release")
    s.pg.get_by_role("button", name="Cancelar la obra…").click()
    s.pg.wait_for_timeout(1500)
    material = s.pg.get_by_label("Qué pasó con ese material")
    chk("Con material afuera pide «Qué pasó con ese material»", material.count() == 1, "")
    if material.count():
        material.fill("QA pantalla: los 2 tubos quedaron cortados en la casa")
    s.pg.get_by_label("Por qué se cancela").fill("QA pantalla: el cliente desistió del programa")
    foto(s.pg, "cancelar-formulario-2", completa=True)
    s.pg.locator("form").filter(has=s.pg.get_by_label("Por qué se cancela")) \
        .get_by_role("button", name="Cancelar la obra", exact=True).click()
    s.pg.wait_for_timeout(3000)
    t = s.texto()
    chk("La obra queda con el aviso «Obra cancelada»", "cancelada" in t.lower(), t[:300])
    foto(s.pg, "obra-cancelada-2", completa=True)
    s.cerrar()


def bod011(nav):
    s = Sesion(nav, "admin")
    s.ir("/warehouse/releases", 3500)
    s.pg.get_by_role("tab", name="Todas las salidas").click()
    s.pg.wait_for_timeout(2500)
    fila = s.pg.locator("tr, article, li").filter(has=s.pg.get_by_role("button", name="Entregar")).first
    chk("En «Todas las salidas» la orden autorizada tiene «Entregar»", fila.count() == 1, "")
    fila.get_by_role("button", name="Entregar").first.click()
    s.pg.wait_for_timeout(1500)
    entrada = s.pg.get_by_label("Serial 1 de", exact=False)
    chk("Al entregar el equipo con serial aparece un campo por unidad", entrada.count() >= 1, "")
    boton = s.pg.locator("form").filter(has=entrada.first).get_by_role("button", name="Entregar")
    chk("Sin el serial, «Entregar» queda deshabilitado", boton.is_disabled(), "")
    foto(s.pg, "entregar-sin-serial")
    entrada.first.fill("sn-ui-001")
    s.pg.wait_for_timeout(300)
    boton.click()
    s.pg.wait_for_timeout(2500)
    t = s.texto()
    chk("Al entregar dice los seriales entregados", "SN-UI-001" in t.upper(), t[:300])
    foto(s.pg, "entregado")
    s.ir("/warehouse/serials", 3000)
    t = s.texto()
    chk("Bodega › Seriales lo muestra «Entregado» con la orden", "SN-UI-001" in t and "ntregado" in t, t[:300])
    foto(s.pg, "seriales")
    s.cerrar()
    s = Sesion(nav, "tecnico")
    s.ir(f"/projects/{D['pid_serial']}", 3500)
    p = paso(s.pg, "equipment")
    sel = s.pg.locator("#equipment-stock-serial")
    chk("En Equipos instalados el técnico ve «Equipo que salió de bodega»", sel.count() == 1, p.inner_text()[:200])
    if sel.count():
        sel.select_option(index=1)
        s.pg.wait_for_timeout(400)
        chk("Al elegirlo se llena el serial", s.pg.locator("#equipment-serial").input_value() == "SN-UI-001",
            s.pg.locator("#equipment-serial").input_value())
    foto(s.pg, "equipos-instalados", completa=True)
    s.cerrar()


with sync_playwright() as p:
    nav = p.chromium.launch()
    for eid, fn in (("INS-012", ins012), ("BOD-011", bod011)):
        seguro(eid, fn, nav)
    nav.close()
guardar("lote4b2.json")
print("ok")
