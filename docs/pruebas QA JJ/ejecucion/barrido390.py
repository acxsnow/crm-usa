"""Recorre todas las pantallas del menú de cada rol a 390 px y anota las que se desbordan.
Uso: python barrido390.py [rol …]"""
import json
import sys

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, QA, Sesion

roles = sys.argv[1:] or ["admin", "adm", "vendedor", "tecnico", "conta", "gerencia"]
salida = {}
with sync_playwright() as p:
    nav = p.chromium.launch()
    for rol in roles:
        s = Sesion(nav, rol, vista=CELULAR)
        rutas = s.pg.evaluate("() => [...document.querySelectorAll('.app-sidebar nav a')].map(a => a.getAttribute('href'))")
        malas = []
        for r in rutas:
            s.ir(r, 2500)
            w = s.pg.evaluate("document.documentElement.scrollWidth")
            if w > 392:
                malas.append([r, w])
        salida[rol] = {"pantallas": len(rutas), "desbordan": malas}
        print(rol, len(rutas), malas, flush=True)
        s.cerrar()
    nav.close()
(QA / "ejecucion" / "barrido390.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
