"""Prueba de pantalla de los ajustes del cliente del 5 nov 2026 (segunda tanda),
en computador y celular, con los datos de `prep_ajustes_5nov.py` y el
expediente C de `prep_pedidos_5nov.py` (cerrado, para el permiso cerrado).

A. Formulario del vendedor: correo y documento (TECH) opcionales, 50 A y 70 A,
   sin viabilidad eléctrica, sin fotos de furnace/HVAC/pedestal, resultado
   «Completo» o «Pendiente de algo».
C1. Permiso opcional para instalar, con aviso.
C2. Evidencias de la instalación en el acta, con «Papelería firmada».
C3. Obra de cotización sin casillas de checklist; Despacho con celda vacía.
C4. Permiso cerrado en el paso de cobro.
C5. Inspección eléctrica: Administración la agenda y el técnico registra el resultado.
"""
import json
import re
from datetime import date

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, QA, Sesion, chk, esc, foto, guardar, limpiar

DATOS = json.loads((QA / "ejecucion" / "prep_ajustes_5nov_datos.json").read_text(encoding="utf-8"))
HOY = date.today().isoformat()
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c"
    "1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f000001050101010101"
    "0100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107"
    "227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a"
    "636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7"
    "c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9")


def turno(s):
    """Técnicos y vendedores marcan una vez al día: la ventana tapa la app hasta INICIAR TURNO."""
    boton = s.pg.get_by_role("button", name="INICIAR TURNO")
    if boton.count():
        boton.first.click()
        s.pg.wait_for_timeout(2500)


def desborde(s, nombre):
    ancho = s.pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    chk(f"[{nombre}] Sin desborde horizontal", ancho <= 0, str(ancho))


def obligatorio(pg, etiqueta):
    campo = pg.locator("label", has_text=etiqueta).first
    return campo.locator(".form-req").count() > 0


def a_formulario(s, nombre, d):
    esc("AJ-A-FORMULARIO")
    pg = s.ir(f"/cases/{d['case']}/form", 3500)
    turno(s)
    pg = s.ir(f"/cases/{d['case']}/form", 3500)
    chk(f"[{nombre}] Correo electrónico opcional", not obligatorio(pg, "Correo electrónico"))
    chk(f"[{nombre}] Foto del documento opcional en TECH (California)", not obligatorio(pg, "documento de identidad (frente)"))
    foto(pg, f"{nombre}-a1-cliente")
    pg.locator(".sales-steps button", has_text="Auditoría técnica").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    opciones = pg.locator("select").first.locator("option").all_inner_texts()
    chk(f"[{nombre}] El amperaje ofrece 50 A y 70 A", {"50 A", "70 A"} <= set(opciones), opciones)
    chk(f"[{nombre}] Ya no pregunta el diagnóstico de viabilidad", "Diagnóstico de viabilidad" not in texto)
    foto(pg, f"{nombre}-a2-auditoria")
    pg.locator(".sales-steps button", has_text="Documentos").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    chk(f"[{nombre}] Sin fotos de furnace, HVAC ni pedestal",
        not re.search(r"furnace|HVAC existente|pedestal", texto, re.I), "")
    foto(pg, f"{nombre}-a3-documentos")
    pg.locator(".sales-steps button", has_text="Uso interno").click()
    pg.wait_for_timeout(2500)
    texto = s.texto()
    # «No califica» se queda solo si algún expediente ya la eligió (en la base local, los de QA).
    chk(f"[{nombre}] Resultado preliminar: «Completo» o «Pendiente de algo»",
        "Completo" in texto and "Pendiente de algo" in texto and "Preaprobado" not in texto, "")
    foto(pg, f"{nombre}-a4-uso-interno")
    desborde(s, nombre)


def c1_c2_obra(s, nombre, d):
    esc("AJ-C1-C2-PERMISO-Y-EVIDENCIAS")
    pg = s.ir(f"/projects/{d['project']}", 3500)
    aviso = pg.locator(".permit-missing-banner")
    chk(f"[{nombre}] Sin permiso registrado sale el aviso", aviso.count() == 1 and "sin registrar" in aviso.inner_text())
    chk(f"[{nombre}] El permiso dice que no frena la instalación", "no frena la instalación" in s.texto())
    chk(f"[{nombre}] La orden liberada es el paso en curso, no el permiso",
        "Sin técnico ni fecha" in s.texto() and pg.locator("#acta-step-release, [data-step='release']").count() >= 0)
    foto(pg, f"{nombre}-c1-obra-sin-permiso")
    pg.get_by_text("Evidencias de la instalación").first.click()
    pg.wait_for_timeout(1200)
    opciones = pg.locator("#evidencia-categoria option").all_inner_texts()
    chk(f"[{nombre}] El acta tiene «Evidencias de la instalación» con «Papelería firmada»",
        "Papelería firmada a mano (utilidades)" in opciones and "Equipos viejos" in opciones, opciones[:4])
    chk(f"[{nombre}] Los anexos ya no repiten las evidencias",
        pg.locator(".acta-annex #anexo-evidencias").count() == 0)
    foto(pg, f"{nombre}-c2-evidencias-en-el-acta")
    desborde(s, nombre)


def c3_cotizacion(s, nombre, d):
    esc("AJ-C3-OBRA-DE-COTIZACION")
    pg = s.ir(f"/projects/{d['project']}?paso=checklist", 3500)
    chk(f"[{nombre}] La obra de cotización dice que no tiene checklist", "Este trabajo no tiene checklist" in s.texto())
    chk(f"[{nombre}] Sin casillas de condiciones cuando no hay checklist", "Se retira equipo de gas" not in s.texto())
    chk(f"[{nombre}] Sin aviso de permiso (no es de un expediente)", pg.locator(".permit-missing-banner").count() == 0)
    foto(pg, f"{nombre}-c3-obra-cotizacion")


def c3_despacho(s, nombre):
    esc("AJ-C3-DESPACHO")
    pg = s.ir("/dispatch", 3500)
    if nombre == "celular":
        # En el celular el tablero va en tarjetas sin celdas vacías: se agenda tocando la obra.
        return
    pg.locator(".dispatch-grid tbody td").first.click(force=True)
    pg.wait_for_timeout(800)
    dialogo = pg.locator("[aria-labelledby='dispatch-pick-title']")
    chk(f"[{nombre}] Tocar una celda vacía abre qué obra va ahí", dialogo.count() == 1)
    chk(f"[{nombre}] El diálogo lista las obras sin agendar", dialogo.locator(".dispatch-job").count() > 0,
        dialogo.inner_text()[:150] if dialogo.count() else "")
    foto(pg, f"{nombre}-c3-despacho-celda")
    if dialogo.count():
        dialogo.get_by_role("button", name="Cerrar").click(force=True)


def c4_permiso_cerrado(s, nombre, d):
    esc("AJ-C4-PERMISO-CERRADO")
    pg = s.ir(f"/projects/{d['project']}?paso=billing", 3500)
    caja = pg.locator(".closed-permit")
    caja.wait_for(timeout=15000)
    chk(f"[{nombre}] El cobro pide subir el permiso cerrado sin frenarlo",
        caja.count() == 1 and "Falta subir el permiso cerrado" in caja.inner_text(), caja.inner_text() if caja.count() else "")
    foto(pg, f"{nombre}-c4a-falta-permiso-cerrado")
    caja.locator("input[type=file]").set_input_files({"name": "permiso.jpg", "mimeType": "image/jpeg", "buffer": JPEG})
    pg.wait_for_timeout(3000)
    chk(f"[{nombre}] Subido, queda «✓ Permiso cerrado subido»", "Permiso cerrado subido" in caja.inner_text(),
        caja.inner_text())
    foto(pg, f"{nombre}-c4b-permiso-cerrado-subido")


def c5_agendar(s, nombre, d):
    esc("AJ-C5-INSPECCION-ELECTRICA")
    pg = s.ir(f"/cases/{d['case']}/review", 3500)
    tarjeta = pg.locator(".electrical-card")
    chk(f"[{nombre}] La revisión del expediente trae «Inspección eléctrica»", tarjeta.count() == 1)
    tarjeta.locator("#ei-tecnico").select_option(label="Tito Técnico")
    tarjeta.locator("#ei-fecha").fill(HOY)
    tarjeta.get_by_role("button", name="Agendar inspección eléctrica").click()
    pg.wait_for_timeout(2500)
    chk(f"[{nombre}] Queda agendada con Tito", "Agendada" in tarjeta.inner_text() and "Tito" in tarjeta.inner_text(),
        tarjeta.inner_text()[:200])
    foto(pg, f"{nombre}-c5a-agendada")


def c5_resultado(nav, nombre, vista, d):
    t = Sesion(nav, "tecnico", **({"vista": vista} if vista else {}))
    pg = t.ir("/electrical-inspections", 3500)
    turno(t)
    pg = t.ir("/electrical-inspections", 3500)
    item = pg.locator(".electrical-item", has_text=d["number"])
    chk(f"[{nombre}] El técnico ve su inspección por hacer", item.count() == 1)
    item.get_by_role("button", name="Registrar resultado").click()
    pg.wait_for_timeout(600)
    item.get_by_label("Adecuada").check()
    item.locator("select").select_option("70")
    item.locator("input[type=number]").fill("2.5")
    item.locator("fieldset", has_text="calentador").get_by_label("Sí").check()
    item.locator("fieldset", has_text="inducción").get_by_label("No").check()
    foto(pg, f"{nombre}-c5b-resultado-tecnico", completa=True)
    item.get_by_role("button", name="Guardar resultado").click()
    pg.wait_for_timeout(2500)
    pg.get_by_label("Estado").select_option("done")
    pg.wait_for_timeout(2000)
    hecho = pg.locator(".electrical-item", has_text=d["number"])
    chk(f"[{nombre}] Queda «Hecha» con el resultado", hecho.count() == 1 and "2.5" in hecho.inner_text()
        and "Adecuada" in hecho.inner_text(), hecho.inner_text()[:200] if hecho.count() else "")
    desborde(t, nombre)
    t.cerrar()


def c5_ver(s, nombre, d):
    pg = s.ir(f"/cases/{d['case']}/review", 3500)
    tarjeta = pg.locator(".electrical-card")
    chk(f"[{nombre}] Administración ve el resultado en el expediente",
        "Adecuada" in tarjeta.inner_text() and "70 A" in tarjeta.inner_text(), tarjeta.inner_text()[:200])
    foto(pg, f"{nombre}-c5c-resultado-en-expediente", completa=True)


limpiar()
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nombre, vista in (("pc", None), ("celular", CELULAR)):
        d = DATOS[nombre]
        extra = {"vista": vista} if vista else {}
        vend = Sesion(nav, "vendedor", **extra)
        try:
            a_formulario(vend, nombre, d["V"])
        except Exception as ex:  # noqa: BLE001
            chk(f"[{nombre}] a_formulario terminó sin error inesperado", False, repr(ex)[:300])
        vend.cerrar()
        s = Sesion(nav, "adm", **extra)
        for fn, args in ((c1_c2_obra, (s, nombre, d["E"])), (c3_cotizacion, (s, nombre, d["Q"])),
                         (c3_despacho, (s, nombre)), (c4_permiso_cerrado, (s, nombre, d["P"])),
                         (c5_agendar, (s, nombre, d["E"])), (c5_resultado, (nav, nombre, vista, d["E"])),
                         (c5_ver, (s, nombre, d["E"]))):
            try:
                fn(*args)
            except Exception as ex:  # noqa: BLE001
                chk(f"[{nombre}] {fn.__name__} terminó sin error inesperado", False, repr(ex)[:300])
                foto(s.pg, f"{nombre}-error-{fn.__name__}")
        chk(f"[{nombre}] Sin errores de JavaScript", not [x for x in s.errores if "ServiceWorker" not in x], s.errores[:3])
        s.cerrar()
    nav.close()
guardar("ajustes_5nov.json")
