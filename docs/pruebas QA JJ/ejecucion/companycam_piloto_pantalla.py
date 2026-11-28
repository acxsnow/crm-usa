"""Piloto local de la migración de CompanyCam (28 nov 2026): expediente con
varios programas y venta en proceso como prospecto, en computador y celular."""
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

MULTI = "d11c2ab8-cdd3-45a9-ab3f-4e6d20520fe1"     # CC-115093657: TECH, LADWP y Quality Services
PROSPECTO = "930fc435-920e-47f3-a188-371278b1ab24"  # CC-114837213: venta de «Vendedores 4»


def al_fondo(pg):
    for _ in range(6):
        pg.mouse.wheel(0, 2500)
        pg.wait_for_timeout(500)


limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        esc("CC-PILOTO")
        s = Sesion(nav, "admin", **({"vista": vista} if vista else {}))
        pg = s.ir(f"/cases/{MULTI}/review", 7000)
        seccion = pg.locator("section.imp-program")
        seccion.scroll_into_view_if_needed()
        t = seccion.inner_text() if seccion.count() else ""
        chk(f"[{nombre}] El importado muestra «Programas» con los tres", all(x in t for x in (
            "Programas", "TECH Clean California", "LADWP", "Quality Services")), t[:200])
        chk(f"[{nombre}] Marca el principal y los adicionales", "Principal" in t and "Adicional" in t)
        seccion.screenshot(path=f"/q/evidencias/pantalla/CC-PILOTO/{nombre}-1-varios-programas.jpg")
        al_fondo(pg)
        chk(f"[{nombre}] Trae las etiquetas de CompanyCam como nota",
            pg.get_by_text("Etiquetas en CompanyCam").count() > 0)
        foto(pg, f"{nombre}-1b-notas")
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal (varios programas)", ancho <= 0, ancho)
        pg = s.ir(f"/cases/{PROSPECTO}/review", 5000)
        t = s.texto()
        chk(f"[{nombre}] La venta en proceso es «Nuevo prospecto»", "Nuevo prospecto" in t, t[:200])
        chk(f"[{nombre}] Dice que falta programa y formulario", "por asignar programa" in t)
        foto(pg, f"{nombre}-2-prospecto")
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal (prospecto)", ancho <= 0, ancho)
        s.cerrar()
    nav.close()
guardar("companycam_piloto_pantalla.json")
