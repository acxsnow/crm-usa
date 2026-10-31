"""Tablas comunes (31 oct 2026): en cada pantalla del menú de cada rol, en computador
y en celular, comprueba que
- no hay errores de JavaScript,
- toda tabla es la común (`.data-table`), ninguna hecha a mano,
- en el celular las filas son tarjetas (sin encabezado visible) y nada se desborda.
Uso: python tablas_comunes.py [rol …]"""
import json
import sys

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, ESCRITORIO, QA, Sesion

roles = sys.argv[1:] or ["admin", "adm", "vendedor", "tecnico", "conta", "gerencia"]
salida = {}
MEDIR = """() => ({
  tablas: document.querySelectorAll('.app-content table').length,
  aMano: [...document.querySelectorAll('.app-content table:not(.data-table)')].length,
  encabezadoVisible: [...document.querySelectorAll('.app-content table.data-table thead')]
    .some((t) => getComputedStyle(t).display !== 'none'),
  ancho: document.documentElement.scrollWidth,
})"""
with sync_playwright() as p:
    nav = p.chromium.launch()
    for rol in roles:
        fallas = []
        for nombre, vista in (("pc", ESCRITORIO), ("cel", CELULAR)):
            s = Sesion(nav, rol, vista=vista, **({"is_mobile": True, "has_touch": True} if nombre == "cel" else {}))
            if nombre == "cel":
                s.pg.locator(".menu-toggle").first.click()
                s.pg.wait_for_timeout(500)
            rutas = s.pg.evaluate("() => [...new Set([...document.querySelectorAll('.app-sidebar nav a')].map(a => a.getAttribute('href')))]")
            for r in rutas:
                s.errores.clear()
                s.ir(r, 2200)
                m = s.pg.evaluate(MEDIR)
                if s.errores:
                    fallas.append([nombre, r, "error JS", s.errores[:2]])
                if m["aMano"]:
                    fallas.append([nombre, r, "tabla hecha a mano", m["aMano"]])
                if nombre == "cel" and m["encabezadoVisible"]:
                    fallas.append([nombre, r, "encabezado visible en celular", ""])
                if nombre == "cel" and m["ancho"] > 392:
                    fallas.append([nombre, r, "desborda", m["ancho"]])
            s.cerrar()
        salida[rol] = {"pantallas": len(rutas), "fallas": fallas}
        print(rol, len(rutas), fallas or "ok", flush=True)
    nav.close()
(QA / "ejecucion" / "tablas_comunes.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
