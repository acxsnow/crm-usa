"""Pantallas de cobro y rentabilidad con la obra del camino feliz de
`qa_cobro_rentabilidad.py` (tarifa TECH, material 1.200, mano de obra 360,
gasolina 40 y pago completo; después el ataque le cargó 500 de gastos a propósito:
costos 2.100 y margen 4.400), en computador y celular."""
import json
import re
import sys

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, chk, esc, foto, guardar, limpiar

cid, pid, claim = json.loads(sys.argv[1])


def plata(texto):
    return {m.replace(",", "") for m in re.findall(r"\$\s?([\d,]+\.\d{2})", texto)}


limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        s = Sesion(nav, "gerencia", **({"vista": vista} if vista else {}))
        esc("COB-P1 Rentabilidad")
        pg = s.ir("/finance-close", 3500)
        pestana = pg.get_by_role("tab", name=re.compile("Rentabilidad"))
        if pestana.count():
            pestana.first.click()
            pg.wait_for_timeout(2500)
        texto = s.texto()
        chk(f"[{nombre}] La rentabilidad abre sin errores", "rentabilidad" in texto.lower() and not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:2])
        foto(pg, f"{nombre}-rentabilidad", completa=True)
        s.cerrar()

        s = Sesion(nav, "adm", **({"vista": vista} if vista else {}))
        esc("COB-P2 Obra - costo del trabajo y cobro")
        pg = s.ir(f"/projects/{pid}?paso=billing", 4000)
        # Los paneles cargan aparte; en el celular tardan más.
        for _ in range(20):
            if "Cargando" not in s.texto():
                break
            pg.wait_for_timeout(1000)
        texto = s.texto()
        montos = plata(texto)
        chk(f"[{nombre}] El paso de cobro muestra el cobro pagado", "Pagado" in texto, "")
        chk(f"[{nombre}] El costo del trabajo muestra 2.100 de costos (igual que la API)", "2100.00" in montos, sorted(montos)[:12])
        chk(f"[{nombre}] El costo del trabajo muestra el margen 4.400 (igual que la API)", "4400.00" in montos, sorted(montos)[:12])
        foto(pg, f"{nombre}-obra-cobro-y-costo", completa=True)
        esc("COB-P3 Detalle del cobro")
        pg = s.ir(f"/invoices/claims/{claim}", 3500)
        texto = s.texto()
        chk(f"[{nombre}] El detalle del cobro dice pagado y su monto", "Pagado" in texto and plata(texto), "")
        foto(pg, f"{nombre}-detalle-cobro", completa=True)
        esc("COB-P4 Tablero de cobros")
        pg = s.ir("/invoices", 3500)
        chk(f"[{nombre}] El tablero de facturación abre sin errores",
            not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:2])
        foto(pg, f"{nombre}-tablero-cobros")
        ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, ancho)
        s.cerrar()
    nav.close()
guardar("cobro_rentabilidad_pantalla.json")
