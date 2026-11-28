"""Varios programas por expediente (28 nov 2026), en computador y celular:
Administración ve los programas, aprueba un adicional con su código y agrega y
quita otro. Corre sobre el piloto local de CompanyCam (base de Docker)."""
import os

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

CASO = os.environ["CASO"]  # un importado «En espera» con TECH, LADWP y Quality Services

limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        esc("VARIOS-PROGRAMAS")
        s = Sesion(nav, "admin", **({"vista": vista} if vista else {}))
        pg = s.ir(f"/cases/{CASO}/review", 7000)
        sec = pg.locator("section.case-programs")
        sec.scroll_into_view_if_needed()
        t = sec.inner_text()
        chk(f"[{nombre}] Se ven los tres programas", all(x in t for x in ("TECH Clean California", "LADWP",
                                                                           "Quality Services")), t[:160])
        chk(f"[{nombre}] Explica que firma y formulario valen para todos", "valen para todos" in t)
        fila = sec.locator("li.case-program-item", has_text="LADWP")
        if "Aprobado" in fila.inner_text():  # la vuelta del celular: se deja pendiente para repetir
            fila.get_by_role("button", name="Rechazar").click()
            fila.get_by_label("Motivo del rechazo").fill("Prueba de pantalla")
            fila.get_by_role("button", name="Rechazar").click()
            pg.wait_for_timeout(1500)
        fila.get_by_role("button", name="Aprobar").click()
        fila.get_by_label("Código de aprobación").fill(f"LA-{nombre}")
        fila.get_by_role("button", name="Aprobar").click()
        pg.wait_for_timeout(2000)
        ft = fila.inner_text()
        chk(f"[{nombre}] LADWP queda aprobado con su código", "Aprobado" in ft and f"LA-{nombre}" in ft, ft)
        chk(f"[{nombre}] El principal no tiene botón de aprobar aparte",
            sec.locator("li.case-program-item", has_text="Principal").get_by_role("button", name="Aprobar").count() == 0)
        sec.get_by_label("Agregar programa").select_option(label="GoZero")
        sec.get_by_role("button", name="Agregar").click()
        pg.wait_for_timeout(2000)
        chk(f"[{nombre}] Se agrega GoZero como adicional", "GoZero" in sec.inner_text())
        sec.screenshot(path=f"/q/evidencias/pantalla/VARIOS-PROGRAMAS/{nombre}-programas.jpg")
        sec.locator("li.case-program-item", has_text="GoZero").get_by_role("button", name="Quitar").click()
        pg.wait_for_timeout(2000)
        chk(f"[{nombre}] Se quita GoZero", "GoZero" not in sec.locator("ul.case-program-list").inner_text())
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, ancho)
        s.cerrar()
    nav.close()
guardar("varios_programas_pantalla.json")
