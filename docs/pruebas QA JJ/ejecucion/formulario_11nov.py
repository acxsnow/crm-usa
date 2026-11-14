"""Formulario del vendedor con los ajustes del cliente del 11 nov 2026, en
computador y celular: programas GoZero y LADWP, dirección de la visita sin
repetir, «Multifamiliar», 1040/W-2/talones, 50 y 70 A, calefacción y sin
diagnóstico de viabilidad."""
import random

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        esc("FORM-11NOV")
        s = Sesion(nav, "vendedor", **({"vista": vista} if vista else {}))
        boton = s.pg.get_by_role("button", name="INICIAR TURNO")
        if boton.count():
            boton.first.click()
            s.pg.wait_for_timeout(2500)
        pg = s.ir("/sales", 3000)
        # Visita nueva con dirección completa, por la misma API que usa la pantalla.
        calle = f"{random.randint(1000, 9999)} QA Balboa Blvd"
        resp = pg.evaluate("""async (calle) => {
            const tok = (await (await fetch('/api/v1/auth/refresh', {method: 'POST', credentials: 'include'})).json()).access_token;
            const r = await fetch('/api/v1/visits', {method: 'POST', credentials: 'include',
              headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok},
              body: JSON.stringify({result: 'opened', address_street: calle, address_unit: '123', address_city: 'Van Nuys',
                                    address_state: 'CA', address_zip: '91406', latitude: 34.18, longitude: -118.47})});
            return {status: r.status, body: await r.text()}; }""", calle)
        chk(f"[{nombre}] Visita creada", resp["status"] in (200, 201), str(resp)[:200])
        import json as _j
        caso = _j.loads(resp["body"]).get("case", {}) if resp["status"] in (200, 201) else {}
        pg = s.ir(f"/cases/{caso.get('id')}/form", 3500)
        texto = s.texto()
        for prog in ("Eficiencia de Arizona", "TECH Clean California", "LADWP", "GoZero"):
            chk(f"[{nombre}] El vendedor puede elegir {prog}", prog in texto)
        foto(pg, f"{nombre}-1-programas")
        pg.get_by_text("TECH Clean California").first.click()
        pg.wait_for_timeout(3000)
        aviso = pg.locator(".sales-address-known")
        chk(f"[{nombre}] La dirección de la visita sale en una línea, sin repetirla",
            aviso.count() == 1 and "Balboa" in aviso.inner_text() and pg.locator("#f-customer\.address_street").count() == 0,
            aviso.inner_text() if aviso.count() else "sin resumen")
        foto(pg, f"{nombre}-2-cliente", completa=True)
        for paso, revisar in (("Vivienda", lambda t: "Multifamiliar" in t and "Condominio" not in t),
                              ("Elegibilidad", lambda t: all(x in t for x in ("Taxes (1040)", "W-2", "Talones de cheque"))),
                              ("Auditoría técnica", None)):
            pg.locator(".sales-steps button", has_text=paso).click()
            pg.wait_for_timeout(2500)
            t = s.texto()
            if revisar:
                chk(f"[{nombre}] {paso}: lo pedido por el cliente", revisar(t), "")
            else:
                ops = pg.locator("#f-tech\.panel_amperage option").all_inner_texts()
                chk(f"[{nombre}] Amperaje con 50 A y 70 A", {"50 A", "70 A"} <= set(ops), ops)
                chk(f"[{nombre}] Pregunta la calefacción", "Calefacción" in t and "Furnace de gas" in t, "")
                chk(f"[{nombre}] Ya no pregunta el diagnóstico de viabilidad", "Diagnóstico de viabilidad" not in t, "")
            foto(pg, f"{nombre}-3-{paso.split()[0].lower()}", completa=True)
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, ancho)
        s.cerrar()
    nav.close()
guardar("formulario_11nov.json")
