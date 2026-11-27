"""Bodega por pantalla (26 nov 2026): recepción de compras con llegada parcial,
traslado a la camioneta, ajuste con motivo, conteo y asociación de la factura
del proveedor, como lo hace la gente: en computador y en celular.

Prepara por API solo lo que el usuario no haría en esta pantalla (los
artículos, la camioneta, el proveedor y su factura); el resto es con clics.
"""
import json
import re
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion, USUARIOS, CLAVE, chk, esc, foto, guardar, limpiar

API = "http://api:8000/api/v1"
RUN = str(int(time.time()))[-6:]


def llamar(metodo, ruta, token=None, datos=None, form=None):
    cab = {"Content-Type": "application/json"}
    cuerpo = None
    if datos is not None:
        cuerpo = json.dumps(datos).encode()
    if form is not None:
        cuerpo = urllib.parse.urlencode(form).encode()
        cab["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        cab["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + ruta, data=cuerpo, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def token(rol):
    limpiar()
    _, d = llamar("POST", "/auth/login", datos={"email": USUARIOS[rol], "password": CLAVE})
    return d["access_token"]


def articulo(pg, n, texto):
    """Elige el artículo `n` (1, 2…) del formulario escribiendo en su buscador."""
    campo = pg.get_by_role("combobox", name=f"Artículo {n}")
    campo.click()
    campo.fill(texto)
    pg.wait_for_timeout(1200)
    pg.get_by_role("listbox").get_by_role("option").first.dispatch_event("mousedown")
    pg.wait_for_timeout(500)


def sin_desborde(pg, nombre):
    ancho = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, ancho)


# --- Preparación --------------------------------------------------------------
t_adm = token("adm")
t_conta = token("conta")
items = {}
for clave, nombre, costo in (("cap", f"QA Capacitor 45/5 {RUN}", "10.00"), ("fil", f"QA Filtro 16x25 {RUN}", "4.00"),
                             ("cel", f"QA Contactor {RUN}", "15.00")):
    st, it = llamar("POST", "/warehouse/items", t_adm, {"name": nombre, "sku": f"QA-{clave}-{RUN}", "category": "parts",
                                                       "unit": "unit", "unit_cost": costo})
    assert st == 201, it
    items[clave] = it
st, cam = llamar("POST", "/warehouse/locations", t_adm, {"name": f"QA Camioneta {RUN}", "kind": "truck"})
assert st == 201, cam
st, prov = llamar("POST", "/payables/suppliers", t_conta, {"name": f"QA Ferguson {RUN}", "kinds": ["equipment"]})
assert st == 201, prov

limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()

    # ======================================================================
    esc("BOD-R1 Recepción con llegada parcial (computador)")
    # ======================================================================
    s = Sesion(nav, "adm")
    pg = s.ir("/warehouse/receipts", 3000)
    chk("[pc] Abre Recepción de compras", "Recepción de compras" in s.texto(), "")
    chk("[pc] El menú de Bodega muestra Recepción de compras y Conteos",
        pg.get_by_role("link", name="Recepción de compras").count() > 0 and pg.get_by_role("link", name="Conteos").count() > 0, "")
    pg.get_by_role("button", name="Nueva recepción").click()
    pg.get_by_role("combobox", name="Proveedor registrado").click()
    pg.get_by_role("combobox", name="Proveedor registrado").fill(f"QA Ferguson {RUN}")
    pg.wait_for_timeout(1200)
    pg.get_by_role("listbox").get_by_role("option").first.dispatch_event("mousedown")
    pg.fill("#rec-doc", f"F-{RUN}")
    pg.fill("#rec-tax", "6")
    pg.fill("#rec-ship", "6")
    articulo(pg, 1, f"QA-cap-{RUN}")
    pg.locator("[id^=rec-ped-]").nth(0).fill("10")
    pg.locator("[id^=rec-lle-]").nth(0).fill("8")
    pg.locator("[id^=rec-cos-]").nth(0).fill("12")
    pg.get_by_role("button", name="+ Agregar artículo").click()
    articulo(pg, 2, f"QA-fil-{RUN}")
    pg.locator("[id^=rec-ped-]").nth(1).fill("5")
    pg.locator("[id^=rec-lle-]").nth(1).fill("5")
    pg.locator("[id^=rec-cos-]").nth(1).fill("0")
    texto = s.texto()
    chk("[pc] El formulario muestra el total con impuesto y envío (120 + 12 = 132)", "132.00" in texto, re.findall(r"Total[^\n]*", texto)[:1])
    foto(pg, "pc-formulario", completa=True)
    pg.get_by_role("button", name="Guardar recepción").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    errores_form = pg.locator(".form-error").all_inner_texts()
    foto(pg, "pc-tras-guardar", completa=True)
    chk("[pc] Guardada: el detalle dice que faltan 2 capacitores", "faltan 2" in texto, errores_form or texto[-300:])
    chk("[pc] El costo con impuesto y envío del capacitor es 13,20", "13.20" in texto, "")
    chk("[pc] Queda «Pendiente por llegar»", "Pendiente por llegar" in texto, "")
    numero = (re.findall(r"REC-\d{4}-\d{4}", texto) or [""])[0]
    foto(pg, "pc-detalle-parcial", completa=True)

    pg.get_by_role("button", name="Todo lo pendiente").click()
    pg.get_by_role("button", name="Registrar llegada").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk("[pc] Llegan los 2: queda completa", "quedó completa" in texto and "Recibida completa" in texto, texto[:200])
    foto(pg, "pc-detalle-completa", completa=True)

    # ======================================================================
    esc("BOD-R2 Traslado a la camioneta y ajuste con motivo (computador)")
    # ======================================================================
    pg = s.ir("/warehouse", 3000)
    if pg.locator(".filter-bar-field input").count() == 0:
        pg.locator(".filter-bar-toggle").click()
    pg.locator(".filter-bar-field input").first.fill(f"QA-cap-{RUN}")
    pg.locator(".filter-bar-field input").first.press("Enter")
    pg.wait_for_timeout(2000)
    texto = s.texto()
    chk("[pc] Existencias: el capacitor tiene 10", re.search(r"10\.00\s*unidades", texto) is not None, texto[:400])
    pg.get_by_role("button", name="Trasladar").first.click()
    pg.wait_for_timeout(800)
    pg.select_option("#mv-destino", label=f"QA Camioneta {RUN}")
    pg.fill("#mv-cant", "3")
    pg.get_by_role("button", name="Trasladar").first.click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk("[pc] Traslado registrado y la camioneta tiene 3", "Traslado registrado" in texto and f"QA Camioneta {RUN}: 3.00" in texto,
        texto[:500])
    pg.get_by_role("button", name="Cerrar").first.click()
    pg.get_by_role("button", name="Ajustar").first.click()
    pg.wait_for_timeout(800)
    pg.fill("#mv-cant", "1")
    pg.get_by_role("button", name="Registrar ajuste").click()
    pg.wait_for_timeout(1200)
    chk("[pc] Sin motivo, el ajuste no se registra", "Elige el motivo" in s.texto(), "")
    pg.select_option("#mv-motivo", label="Dañado o vencido")
    pg.fill("#mv-nota", "Llegó golpeado")
    pg.get_by_role("button", name="Registrar ajuste").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk("[pc] Ajuste registrado: quedan 9 en total", "Ajuste registrado" in texto and re.search(r"9\.00\s*unidades", texto), texto[:400])
    foto(pg, "pc-existencias-despues", completa=True)

    # ======================================================================
    esc("BOD-R3 Conteo mensual (computador)")
    # ======================================================================
    pg = s.ir("/warehouse/counts", 3500)
    pg.fill("#cnt-buscar", f"QA-cap-{RUN}")  # la búsqueda va al servidor (por páginas)
    pg.wait_for_timeout(2500)
    fila = pg.locator("tr", has_text=f"QA Capacitor 45/5 {RUN}")
    chk("[pc] La planilla de la bodega muestra 6 en el sistema (10 − 3 trasladados − 1 dañado)",
        fila.count() == 1 and "6" in fila.locator("td").nth(1).inner_text(), fila.inner_text() if fila.count() else "sin fila")
    pg.get_by_label(f"Contado de QA Capacitor 45/5 {RUN}").fill("7")
    pg.wait_for_timeout(300)
    chk("[pc] La diferencia se ve antes de registrar (+1)", "+1" in fila.inner_text(), fila.inner_text())
    foto(pg, "pc-conteo")
    pg.get_by_role("button", name="Registrar conteo").click()
    pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Confirmar").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk("[pc] Conteo registrado con 1 ajuste", "registrado" in texto and "1 con ajuste" in texto, texto[:300])
    pg = s.ir(f"/warehouse/movements", 3000)
    # Solo los ajustes de hoy: la base de pruebas trae movimientos con fechas futuras.
    if pg.locator(".filter-bar-field select").count() == 0:
        pg.locator(".filter-bar-toggle").click()
    pg.locator(".filter-bar-field select").first.select_option(label="Ajuste")
    desde = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 2 * 86400))
    hasta = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400))
    pg.locator(".filter-bar-field input").nth(0).fill(desde)
    pg.locator(".filter-bar-field input").nth(1).fill(hasta)
    pg.locator(".filter-bar-field input").nth(1).press("Enter")
    pg.wait_for_timeout(2500)
    foto(pg, "pc-movimientos-ajustes", completa=True)
    texto = s.texto()
    chk("[pc] El libro muestra el motivo «Dañado o vencido» y el «Conteo físico»",
        "Dañado o vencido" in texto and "Conteo físico" in texto, "")
    chk("[pc] Sin errores de página", not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:2])
    s.cerrar()

    # ======================================================================
    esc("BOD-R4 Contabilidad asocia la factura del proveedor")
    # ======================================================================
    st, fac = llamar("POST", "/payables/invoices", t_conta, form={"data": json.dumps({
        "supplier_id": prov["id"], "number": f"F-{RUN}", "invoice_date": time.strftime("%Y-%m-%d"), "total": "132.00",
        "category": "materials"})})
    chk("Contabilidad registró la factura en Proveedores", st == 201, fac)
    s = Sesion(nav, "conta")
    pg = s.ir("/warehouse/receipts", 3000)
    pg.get_by_role("tab", name="Sin factura asociada").click()
    pg.wait_for_timeout(3500)
    fila = pg.locator("tr", has_text=numero)
    chk(f"[pc] Contabilidad ve {numero} en «Sin factura asociada»", fila.count() >= 1, numero)
    fila.get_by_role("button").first.click()
    pg.wait_for_timeout(2000)
    pg.locator("select[id^=fac-]").select_option(index=1)
    pg.get_by_role("button", name="Asociar factura").click()
    pg.wait_for_timeout(2000)
    texto = s.texto()
    chk("[pc] Factura asociada", f"Asociada: F-{RUN}" in texto, texto[:300])
    chk("[pc] Contabilidad no ve botones de recibir", pg.get_by_role("button", name="Registrar llegada").count() == 0, "")
    foto(pg, "pc-factura-asociada", completa=True)
    s.cerrar()

    s = Sesion(nav, "tecnico")
    pg = s.ir("/warehouse/receipts", 2500)
    chk("El técnico no entra a Recepción de compras", pg.get_by_role("button", name="Nueva recepción").count() == 0, "")
    s.cerrar()

    # ======================================================================
    esc("BOD-R5 En el celular")
    # ======================================================================
    s = Sesion(nav, "adm", vista=CELULAR)
    pg = s.ir("/warehouse/receipts", 3000)
    pg.get_by_role("button", name="Nueva recepción").click()
    pg.fill("#rec-prov-libre", f"QA Home Depot {RUN}")
    articulo(pg, 1, f"QA-cel-{RUN}")
    pg.locator("[id^=rec-ped-]").nth(0).fill("4")
    pg.locator("[id^=rec-lle-]").nth(0).fill("1")
    sin_desborde(pg, "celular formulario")
    foto(pg, "cel-formulario", completa=True)
    pg.get_by_role("button", name="Guardar recepción").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk("[celular] Recepción guardada con 3 pendientes", "faltan 3" in texto, texto[:300])
    pg.get_by_role("button", name="Cerrar con faltante").click()
    pg.fill("#rec-motivo", "El proveedor solo tenía uno")
    pg.get_by_role("button", name="Confirmar cierre").click()
    pg.wait_for_timeout(2000)
    chk("[celular] Se cierra con faltante", "Cerrada con faltante" in s.texto(), "")
    sin_desborde(pg, "celular recepción")
    foto(pg, "cel-recepcion-cerrada", completa=True)
    for ruta, nombre in (("/warehouse/counts", "conteo"), ("/warehouse", "existencias"), ("/warehouse/movements", "movimientos")):
        pg = s.ir(ruta, 3500)
        sin_desborde(pg, f"celular {nombre}")
        foto(pg, f"cel-{nombre}")
    pg = s.ir("/warehouse/counts", 3500)
    pg.fill("#cnt-buscar", f"QA-cel-{RUN}")
    pg.wait_for_timeout(2500)
    pg.get_by_label(f"Contado de QA Contactor {RUN}").fill("1")
    chk("[celular] El conteo en celular se puede escribir y no muestra diferencia (1 = 1)",
        "0 con diferencia" in s.texto(), "")
    chk("[celular] Sin errores de página", not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:2])
    s.cerrar()
    nav.close()

guardar("bodega_recepcion_pantalla.json")
print("FIN", RUN, numero)
