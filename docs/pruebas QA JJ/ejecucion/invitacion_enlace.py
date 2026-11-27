"""Enlace de invitación para copiar y «Generar enlace nuevo» (14 nov 2026), en computador y celular."""
import random

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        esc("USR-ENLACE")
        s = Sesion(nav, "admin", **({"vista": vista} if vista else {}))
        pg = s.ir("/users", 3000)
        correo = f"qa.enlace.{random.randint(10000, 99999)}@demo-org.com"
        pg.locator("form.ui-invite input[type=email]").fill(correo)
        pg.locator("form.ui-invite").get_by_placeholder("Nombre completo").fill("QA Enlace")
        pg.locator("form.ui-invite").get_by_label("Técnico").check()
        pg.get_by_role("button", name="Invitar usuario").click()
        pg.wait_for_timeout(2500)
        campo = pg.get_by_label("Enlace de invitación")
        link1 = campo.input_value() if campo.count() else ""
        chk(f"[{nombre}] Al invitar aparece el enlace para copiar", "/accept-invitation?token=" in link1, link1[:80])
        chk(f"[{nombre}] Tiene el botón «Copiar enlace»", pg.get_by_role("button", name="Copiar enlace").count() == 1)
        foto(pg, f"{nombre}-1-enlace-al-invitar")
        pg.get_by_role("button", name="Cerrar").click()
        fila = pg.locator("tr, .data-card", has_text=correo).first
        fila.get_by_role("button", name="Generar enlace nuevo").click()
        pg.wait_for_timeout(2500)
        link2 = pg.get_by_label("Enlace de invitación").input_value()
        chk(f"[{nombre}] «Generar enlace nuevo» da otro enlace", link2 and link2 != link1, link2[:80])
        foto(pg, f"{nombre}-2-enlace-nuevo")
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, ancho)
        s.cerrar()
    nav.close()
guardar("invitacion_enlace.json")
