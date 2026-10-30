"""Comprueba a 390 px que la página no se corre de lado (ni forzando el scroll)."""
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion

RUTAS = {"admin": ["/", "/projects", "/warehouse/releases", "/finance-close", "/payables", "/users", "/audit-log"],
         "tecnico": ["/", "/my-schedule", "/my-shift"], "vendedor": ["/", "/cases", "/customers"]}
with sync_playwright() as p:
    nav = p.chromium.launch()
    malas = []
    for rol, rutas in RUTAS.items():
        s = Sesion(nav, rol, vista=CELULAR, has_touch=True, is_mobile=True)
        for r in rutas:
            s.ir(r, 2500)
            x = s.pg.evaluate("() => { window.scrollTo(300, window.scrollY); return window.scrollX; }")
            if x:
                malas.append((rol, r, x))
        s.cerrar()
    nav.close()
print("se corren de lado:", malas or "ninguna", "de", sum(map(len, RUTAS.values())))
