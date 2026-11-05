"""Pedidos del cliente del 4 nov 2026: cotización con cliente por dirección y
lista de bodega, y permiso «En trámite» en el formulario."""
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

limpiar()
esc("PED-4NOV")
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        s = Sesion(nav, "adm", **({"vista": vista} if vista else {}))
        s.ir("/invoices", 3000)
        s.pg.get_by_role("tab", name="Cotizaciones").click()
        s.pg.wait_for_timeout(1200)
        s.pg.get_by_role("button", name="Nueva cotización").first.click()
        s.pg.wait_for_timeout(800)
        s.pg.locator("#cot-cliente").fill("jos")
        s.pg.wait_for_timeout(1500)
        opciones = s.pg.locator(".customer-search-results button")
        chk(f"[{nombre}] Buscar cliente muestra resultados", opciones.count() > 0)
        foto(s.pg, f"{nombre}-buscar-cliente")
        if opciones.count():
            opciones.first.click()
        listas = s.pg.locator("#cot-lista option")
        chk(f"[{nombre}] Hay listas de bodega para cargar", listas.count() > 1, str(listas.count()))
        if listas.count() > 1:
            s.pg.locator("#cot-lista").select_option(index=1)
            s.pg.get_by_role("button", name="Cargar", exact=True).click()
            s.pg.wait_for_timeout(600)
        chk(f"[{nombre}] Las líneas de la lista quedan «De bodega»", s.pg.locator(".lines-origin.is-ok").count() > 0)
        foto(s.pg, f"{nombre}-cotizacion-con-lista", completa=True)
        ancho = s.pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, str(ancho))
    nav.close()
guardar("pedidos_4nov")
