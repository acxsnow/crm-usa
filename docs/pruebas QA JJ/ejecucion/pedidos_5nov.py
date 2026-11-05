"""Prueba de pantalla de los pedidos del cliente del 4 y 5 nov 2026, en
computador y celular, con los datos de `prep_pedidos_5nov.py`.

1. Permiso «En trámite» en lugar de «No requerido».
2. «Radicado» también deja instalar, con el aviso de que falta el aprobado.
3. Cobro con el permiso en cualquier estado; no se cierra sin el aprobado.
4. Cotización con listas y artículos de bodega.
5. Buscar el cliente por dirección.
6. Enlace de la cotización.
7. Administración con los permisos de Contabilidad.
"""
import json
import re
from datetime import date

from playwright.sync_api import sync_playwright

from ui_comun import B, CELULAR, QA, Sesion, chk, esc, foto, guardar, limpiar

DATOS = json.loads((QA / "ejecucion" / "prep_pedidos_5nov_datos.json").read_text(encoding="utf-8"))
HOY = date.today().isoformat()


def etapa(s, case_id):
    s.ir(f"/cases/{case_id}/review", 2500)
    return s.texto()


def desborde(s, nombre):
    ancho = s.pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, str(ancho))


def p1_en_tramite(s, nombre, d):
    esc("PED-1-EN-TRAMITE")
    pg = s.ir(f"/projects/{d['project']}?paso=permit", 3000)
    pg.locator("#permit-status option", has_text="En trámite").wait_for(state="attached", timeout=15000)
    opciones = pg.locator("#permit-status option").all_inner_texts()
    chk(f"[{nombre}] El estado ofrece «En trámite»", "En trámite" in opciones, opciones)
    chk(f"[{nombre}] Ya no ofrece «No requerido»", "No requerido" not in opciones, opciones)
    pg.fill("#permit-jurisdiction", "San Fernando")
    pg.select_option("#permit-status", label="En trámite")
    pg.wait_for_timeout(300)
    chk(f"[{nombre}] «En trámite» no pide fecha de radicado", pg.locator("#permit-filed").count() == 0)
    foto(pg, f"{nombre}-1a-formulario-en-tramite")
    pg.get_by_role("button", name="Registrar permiso").click()
    pg.wait_for_timeout(2500)
    tarjeta = pg.locator(".permit-card").first
    chk(f"[{nombre}] La tarjeta ofrece «Ya se radicó (hoy)»",
        tarjeta.get_by_role("button", name="Ya se radicó (hoy)").count() == 1)
    chk(f"[{nombre}] La tarjeta ofrece «La ciudad lo aprobó»",
        tarjeta.get_by_role("button", name="La ciudad lo aprobó").count() == 1)
    foto(pg, f"{nombre}-1b-tarjeta-en-tramite")
    desborde(s, nombre)
    texto = etapa(s, d["case"])
    chk(f"[{nombre}] El expediente pasó solo a «Listo para instalar»", "Listo para instalar" in texto,
        re.findall(r"Etapa[^\n]*\n?[^\n]*", texto)[:2])
    pg = s.ir("/permits", 2500)
    pg.get_by_label("Filtro").select_option("in_process")
    pg.wait_for_timeout(2000)
    chk(f"[{nombre}] Finanzas › Permisos con filtro «En trámite» muestra la obra", d["number"] in s.texto(), d["number"])
    foto(pg, f"{nombre}-1c-finanzas-permisos-en-tramite")


def p2_radicado(s, nombre, d):
    esc("PED-2-RADICADO")
    pg = s.ir(f"/projects/{d['project']}?paso=permit", 3000)
    pg.fill("#permit-jurisdiction", "San Fernando")
    pg.select_option("#permit-status", value="submitted")
    pg.fill("#permit-filed", HOY)
    pg.get_by_role("button", name="Registrar permiso").click()
    pg.wait_for_timeout(2500)
    pg = s.ir(f"/projects/{d['project']}", 3000)
    aviso = pg.locator(".permit-missing-banner")
    chk(f"[{nombre}] Sale el aviso «Falta el permiso municipal aprobado»",
        aviso.count() == 1 and "Falta el permiso municipal aprobado" in aviso.inner_text(),
        aviso.inner_text() if aviso.count() else "sin aviso")
    foto(pg, f"{nombre}-2a-aviso-falta-permiso")
    aviso.get_by_role("button", name="Ver el permiso").click()
    pg.wait_for_timeout(1200)
    chk(f"[{nombre}] «Ver el permiso» abre el paso del permiso",
        pg.locator(".permit-card").first.is_visible())
    foto(pg, f"{nombre}-2b-ver-el-permiso")
    texto = etapa(s, d["case"])
    chk(f"[{nombre}] Con «Radicado» el expediente pasó a «Listo para instalar»", "Listo para instalar" in texto)
    pg = s.ir(f"/projects/{d['project']}?paso=permit", 3000)
    pg.locator(".permit-card").first.get_by_role("button", name="La ciudad lo aprobó").click()
    pg.wait_for_timeout(500)
    pg.locator("input[id^=aprobado-]").first.fill(HOY)
    pg.get_by_role("button", name="Guardar aprobación").click()
    pg.wait_for_timeout(2500)
    pg = s.ir(f"/projects/{d['project']}", 3000)
    chk(f"[{nombre}] Con el permiso aprobado el aviso desaparece", pg.locator(".permit-missing-banner").count() == 0)
    foto(pg, f"{nombre}-2c-sin-aviso-aprobado")


def p3_cierre(s, nombre, d):
    esc("PED-3-COBRO-Y-CIERRE")
    texto = etapa(s, d["case"])
    chk(f"[{nombre}] Con el permiso «En trámite» el cobro se radicó y el expediente quedó «Pagado»",
        d["stage"] == "paid" and "Pagado" in texto, d["stage"])
    pg = s.pg
    pg.get_by_role("button", name="Cerrar expediente…").click()
    pg.fill("#close-motivo", "QA: ciclo terminado")
    pg.get_by_role("button", name="Confirmar cierre").click()
    pg.wait_for_timeout(2000)
    error = pg.locator(".review-close .form-error")
    msj = error.inner_text() if error.count() else ""
    chk(f"[{nombre}] Sin el aprobado no deja cerrar y explica por qué",
        "falta el permiso municipal aprobado" in msj, msj or "sin mensaje")
    foto(pg, f"{nombre}-3a-no-cierra-sin-permiso")
    pg = s.ir(f"/projects/{d['project']}?paso=permit", 3000)
    pg.locator(".permit-card").first.get_by_role("button", name="La ciudad lo aprobó").click()
    pg.wait_for_timeout(500)
    pg.locator("input[id^=aprobado-]").first.fill(HOY)
    pg.get_by_role("button", name="Guardar aprobación").click()
    pg.wait_for_timeout(2500)
    etapa(s, d["case"])
    pg.get_by_role("button", name="Cerrar expediente…").click()
    pg.fill("#close-motivo", "QA: ciclo terminado con permiso aprobado")
    pg.get_by_role("button", name="Confirmar cierre").click()
    pg.wait_for_timeout(2500)
    texto = etapa(s, d["case"])
    chk(f"[{nombre}] Con el permiso aprobado el expediente se cierra", "Cerrado" in texto)
    foto(pg, f"{nombre}-3b-cerrado-con-permiso")


def p4_p5_p6_cotizacion(s, nombre, nav):
    esc("PED-5-BUSCAR-POR-DIRECCION")
    s.ir("/invoices", 3000)
    pg = s.pg
    pg.get_by_role("tab", name="Cotizaciones").click()
    pg.wait_for_timeout(1200)
    pg.get_by_role("button", name="Nueva cotización").first.click()
    pg.wait_for_timeout(800)
    resultados = pg.locator(".customer-search-results button")
    pg.locator("#cot-cliente").fill("Mobile Park")
    pg.wait_for_timeout(1800)
    chk(f"[{nombre}] Por dirección («Mobile Park») aparecen clientes", resultados.count() > 0, resultados.count())
    foto(pg, f"{nombre}-5a-buscar-por-direccion")
    nombre_cliente = resultados.first.locator("strong").inner_text() if resultados.count() else ""
    pg.locator("#cot-cliente").fill(nombre_cliente.split()[0] if nombre_cliente else "QA")
    pg.wait_for_timeout(1800)
    chk(f"[{nombre}] Por nombre también aparece", resultados.count() > 0, nombre_cliente)
    if resultados.count():
        resultados.first.click()
        pg.wait_for_timeout(500)
    chk(f"[{nombre}] El cliente queda elegido con «Cambiar»",
        pg.get_by_role("button", name="Cambiar").count() == 1)

    esc("PED-4-COTIZACION-BODEGA")
    pg.fill("#cot-titulo", f"QA pedidos 5 nov ({nombre})")
    listas = pg.locator("#cot-lista option")
    chk(f"[{nombre}] Hay listas de bodega para cargar", listas.count() > 1, listas.count())
    pg.locator("#cot-lista").select_option(index=1)
    pg.get_by_role("button", name="Cargar", exact=True).click()
    pg.wait_for_timeout(800)
    de_bodega = pg.locator(".lines-origin.is-ok").count()
    chk(f"[{nombre}] Las líneas de la lista quedan «De bodega»", de_bodega > 0, de_bodega)
    pg.fill("#cot-articulo", "fil")
    pg.wait_for_timeout(1800)
    articulos = pg.locator("[aria-label='Artículos de bodega'] button")
    chk(f"[{nombre}] La búsqueda de artículo de bodega da resultados", articulos.count() > 0, articulos.count())
    if articulos.count():
        articulos.first.click()
        pg.wait_for_timeout(600)
    chk(f"[{nombre}] El artículo buscado se agrega «De bodega»", pg.locator(".lines-origin.is-ok").count() == de_bodega + 1)
    filas = pg.locator(".lines-row:not(.lines-head)")

    def nueva_linea(tipo, texto, precio):
        pg.get_by_role("button", name="+ Agregar línea").click()
        fila = filas.last
        fila.get_by_label("Tipo de línea").select_option(tipo)
        fila.get_by_label("Descripción").fill(texto)
        fila.get_by_label("Precio unitario").fill(str(precio))
        return fila

    fila = nueva_linea("material", "Soporte especial QA", 15)
    chk(f"[{nombre}] El material a mano sale «No está en bodega · se valida aparte»",
        "se valida aparte" in fila.inner_text())
    nota = pg.locator(".lines-editor > .lines-check-note")
    chk(f"[{nombre}] Sale la nota de cuántos faltan por validar",
        nota.count() > 0 and "no está en bodega" in nota.first.inner_text(), nota.first.inner_text() if nota.count() else "")
    fila = nueva_linea("labor", "Mano de obra instalación QA", 120)
    chk(f"[{nombre}] La mano de obra no lleva etiqueta de bodega", fila.locator(".lines-origin").count() == 0)
    primera = filas.first
    primera.get_by_label("Descripción").fill(primera.get_by_label("Descripción").input_value() + " (editado)")
    chk(f"[{nombre}] Cambiar la descripción de una línea de bodega la desliga",
        "se valida aparte" in primera.inner_text())
    foto(pg, f"{nombre}-4a-cotizacion-lineas", completa=True)
    desborde(s, nombre)
    pg.get_by_role("button", name="Crear borrador").click()
    pg.wait_for_timeout(3000)
    chk(f"[{nombre}] El aviso no bloquea: el borrador se guarda", "/quotes/" in pg.url or "/cotiz" in pg.url, pg.url)
    pg.get_by_role("button", name="Guardar y dejar lista para enviar").click()
    pg.wait_for_timeout(3000)

    esc("PED-6-ENLACE-COTIZACION")
    pg.get_by_role("button", name="Generar enlace para copiar").click()
    pg.wait_for_timeout(2500)
    campo = pg.get_by_label("Enlace de la cotización")
    enlace = campo.input_value() if campo.count() else ""
    chk(f"[{nombre}] El enlace empieza por https://192.168.59.100:5173/cotizacion/",
        enlace.startswith("https://192.168.59.100:5173/cotizacion/"), enlace)
    foto(pg, f"{nombre}-6a-enlace-generado")
    if enlace:
        # Desde el contenedor de pruebas la IP del computador es este mismo frontend.
        publico = Sesion(nav, vista=CELULAR)
        publico.pg.goto(enlace.replace("https://192.168.59.100:5173", B))
        publico.pg.wait_for_timeout(3500)
        texto = publico.texto()
        chk(f"[{nombre}] El enlace abre la cotización en el celular sin iniciar sesión",
            "QA pedidos 5 nov" in texto and "/login" not in publico.pg.url, texto[:200])
        chk(f"[{nombre}] La cotización pública permite firmar",
            publico.pg.locator("canvas").count() > 0 or "Firm" in texto, texto[-200:])
        foto(publico.pg, f"{nombre}-6b-enlace-en-celular", completa=True)
        publico.cerrar()


RUTAS_ADM = [("Contabilidad", "/accounting"), ("Facturación y cobros", "/invoices"), ("Gastos de campo", "/expenses"),
             ("Proveedores y pagos", "/payables"), ("Banca", "/banking"), ("Conciliación y rentabilidad", "/finance-close"),
             ("Nómina", "/payroll"), ("Configuración de programas", "/programs")]


def p7_administracion(s, nombre):
    esc("PED-7-ADMIN-CONTABILIDAD")
    s.ir("/", 2500)
    for etiqueta, ruta in RUTAS_ADM:
        pg = s.ir(ruta, 2500)
        chk(f"[{nombre}] Administración abre «{etiqueta}»", pg.url.rstrip("/").endswith(ruta), pg.url)
    foto(s.ir("/accounting", 3000), f"{nombre}-7a-contabilidad-administracion")
    if nombre == "pc":
        menu = s.ir("/", 2500).get_by_label("Navegación principal").inner_text()
        faltan = [e for e, _ in RUTAS_ADM if e not in menu]
        chk("[pc] Todas salen en el menú de Administración", not faltan, faltan)


def p7_gerencia(nav):
    g = Sesion(nav, "gerencia")
    pg = g.ir("/programs", 2500)
    chk("[pc] Gerencia no entra a «Configuración de programas»", not pg.url.rstrip("/").endswith("/programs"), pg.url)
    g.cerrar()


limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        d = DATOS[nombre]
        s = Sesion(nav, "adm", **({"vista": vista} if vista else {}))
        for fn, args in ((p1_en_tramite, (s, nombre, d["A"])), (p2_radicado, (s, nombre, d["B"])),
                         (p3_cierre, (s, nombre, d["C"])), (p4_p5_p6_cotizacion, (s, nombre, nav)),
                         (p7_administracion, (s, nombre))):
            try:
                fn(*args)
            except Exception as ex:  # noqa: BLE001
                chk(f"[{nombre}] {fn.__name__} terminó sin error inesperado", False, repr(ex)[:300])
                foto(s.pg, f"{nombre}-error-{fn.__name__}")
        chk(f"[{nombre}] Sin errores de JavaScript", not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:3])
        s.cerrar()
    p7_gerencia(nav)
    nav.close()
guardar("pedidos_5nov.json")
