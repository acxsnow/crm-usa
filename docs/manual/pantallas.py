"""Las pantallas del manual y qué se señala en cada una. Es el punto de entrada:

    docker run --rm --network crm-usa_default -v "<repo>/docs/manual:/m" \
      mcr.microsoft.com/playwright/python:v1.47.0-jammy \
      sh -c "pip install -q playwright==1.47.0 redis && python /m/pantallas.py [clave ...]"

Sin claves, rehace todas. Cada función abre lo que haga falta en la pantalla y
devuelve (puntos, ancla): los puntos son (locator, leyenda, lado del número) y
el ancla, el elemento al que se desplaza la pantalla antes de capturar.
En el celular el número va dentro del recuadro («inside»): los elementos ocupan
todo el ancho y no queda espacio al lado.
"""
import json
import sys

from playwright.sync_api import sync_playwright

from capturas import CELULAR, DEMO, ESCRITORIO, IMG, Sesion, anotar_y_guardar

ANCHO = {"width": 1280, "height": 900}


def alto(h):
    return {"width": 390, "height": h}


def abrir_paso(pg, clave):
    paso = pg.locator(f"#acta-step-{clave}")
    if paso.locator(".acta-step-body").count() == 0:
        paso.locator(".acta-step-head").click()
        pg.wait_for_timeout(800)
    return paso


def login(pg):
    return [
        (pg.locator("input[type=email]"), "Correo con el que lo invitaron.", "left"),
        (pg.locator(".password-field input"), "Contraseña.", "left"),
        (pg.locator(".password-toggle"), "El ojo muestra u oculta la contraseña mientras la escribe.", "right"),
        (pg.locator("button[type=submit]"), "«Sign in» entra a la plataforma.", "left"),
        (pg.get_by_text("Forgot password?"), "«Forgot password?» envía al correo un enlace para crear una contraseña nueva (vale 60 minutos).", "bottom"),
    ], None


def inicio(pg):
    pg.wait_for_timeout(3000)  # las tarjetas cargan después
    return [
        (pg.locator(".app-sidebar"), "Menú: muestra solo lo que su rol puede usar, agrupado por área.", "inside"),
        (pg.locator(".global-search-box"), "Buscador: clientes, expedientes, obras, facturas, artículos y más (ver 4.1).", "right"),
        (pg.locator(".notice-bell"), "Campana: el número son los avisos sin leer; tóquela para verlos.", "bottom"),
        (pg.locator(".user-menu"), "Su nombre y su rol.", "bottom"),
        (pg.locator(".sign-out"), "«Salir» cierra la sesión.", "bottom"),
        (pg.locator(".metric-card").first.locator(".."), "Resumen: expedientes activos, clientes, proyectos en curso y lo cobrado en el mes.", "top"),
        (pg.get_by_text("Actividad reciente").first.locator("xpath=ancestor::*[self::section or self::article][1]"),
         "Actividad reciente: los últimos cambios de etapa de los expedientes y quién los hizo.", "inside"),
    ], None


def campana(pg):
    pg.wait_for_timeout(2500)
    pg.locator(".notice-bell button").first.click()
    pg.wait_for_timeout(3500)
    return [
        (pg.locator(".notice-bell button").first, "La campana abre la lista de avisos.", "left"),
        (pg.locator(".notice-panel"), "Cada aviso lleva directo a lo que hay que hacer y se marca como leído al tocarlo.", "left"),
    ], None


def midia(pg):
    return [
        (pg.locator(".menu-toggle"), "«Menú» abre las opciones de su rol.", "right"),
        (pg.locator(".sales-knock"), "«Tocar una puerta» registra la visita, aunque no abran.", "inside"),
        (pg.get_by_text("Carmen Ruiz").first.locator("xpath=ancestor::a[1]"), "Expedientes por terminar: tóquelo para seguir el formulario.", "inside"),
    ], None


def visita(pg):
    return [
        (pg.locator("select").first, "Programa que se le ofrece al cliente (se puede elegir después).", "inside"),
        (pg.get_by_placeholder("1200 W Sunrise Dr"), "Dirección de la casa, con espacio o unidad, estado, ciudad y ZIP.", "inside"),
        (pg.get_by_text("Abrió y sigue").first.locator("xpath=ancestor::button[1]"), "«Abrió y sigue»: el cliente atiende y se llena su solicitud.", "inside"),
        (pg.get_by_text("No abrió").first.locator("xpath=ancestor::button[1]"), "«No abrió», «No le interesa» o «No califica» guardan la visita y cierran ahí.", "inside"),
    ], None


def formulario(pg):
    chk = pg.locator("input[type=checkbox]").last
    if chk.count() and not chk.is_checked():
        chk.check()
        pg.wait_for_timeout(800)
    return [
        (pg.get_by_text("Vivienda y hogar").first.locator("xpath=ancestor::*[count(.//button|.//a)>4][1]"),
         "Los pasos del formulario: en verde los completos; se puede ir a cualquiera.", "inside"),
        (pg.get_by_text("Autorizo el uso").first, "Términos del programa que acepta el cliente.", "inside"),
        (pg.locator("label").filter(has=pg.locator("input[type=checkbox]")).last, "El cliente marca que acepta.", "inside"),
        (pg.locator("canvas").first, "El cliente firma con el dedo dentro del recuadro.", "inside"),
        (pg.get_by_role("button", name="Guardar y seguir"), "«Guardar y seguir» guarda el paso; lo que no se guarda no cuenta.", "inside"),
    ], pg.get_by_text("Nombre de quien firma").first


def tablero(pg):
    return [
        (pg.get_by_placeholder("Buscar por expediente, dirección, ciudad o cliente").locator(".."), "Buscar y filtrar por vendedor o programa.", "top"),
        (pg.get_by_text("Pendiente de aprobación").first, "Una columna por etapa del expediente, con cuántos tiene.", "left"),
        (pg.get_by_text("María González").first.locator("xpath=ancestor::a[1]"), "Cada tarjeta es un expediente: tóquela para abrirlo.", "inside"),
        (pg.get_by_text("días hábiles").first, "Días hábiles en «Pendiente de aprobación»: en rojo desde el límite.", "right"),
    ], None


def porrevisar(pg):
    return [
        (pg.locator(".billing-tabs"), "Las cuatro bandejas de Administración; el número rojo son los pendientes de cada una.", "bottom"),
        (pg.get_by_text("María González").first.locator("xpath=ancestor::a[1]"), "Cada fila abre el expediente o el proyecto en el paso que toca.", "left"),
        (pg.get_by_text("días hábiles").first, "Días hábiles esperando: en rojo cuando pasó el límite.", "top"),
        (pg.locator(".billing-chip", has_text="por revisar").first, "Documentos por revisar, rechazados y aceptados.", "top"),
    ], None


def porrevisar_inspeccion(pg):
    return [
        (pg.locator(".billing-tab.is-active"), "Pestaña «Inspección municipal».", "bottom"),
        (pg.get_by_text("Sin agendar").first, "Estado: «Sin agendar», «Agendada» (con fecha) o «Falló: reagendar».", "left"),
        (pg.get_by_text("Luis Herrera").first.locator("xpath=ancestor::a[1]"), "La fila abre el proyecto directo en el paso de inspección.", "left"),
    ], None


def revision(pg):
    return [
        (pg.get_by_role("button", name="✓ Aceptar").first, "«✓ Aceptar» cada documento, o «Rechazar» con una nota.", "left"),
        (pg.locator("ol").filter(has_text="Sometido al programa").first, "Avance con el programa: listo, sometido y en revisión del programa.", "left"),
        (pg.get_by_role("button", name="Aprobar", exact=True), "«Aprobar» con el código del programa: nace el proyecto de instalación.", "left"),
        (pg.get_by_role("button", name="Devolver al vendedor"), "«Devolver al vendedor» con el motivo, para que corrija.", "left"),
        (pg.get_by_role("button", name="Rechazar", exact=True).last, "Poner en espera del programa o rechazar, con motivo.", "left"),
        (pg.get_by_role("heading", name="Historial"), "Historial: cada cambio de etapa con fecha y quién lo hizo.", "left"),
    ], None


def acta_permiso(pg):
    return [
        (pg.locator(".acta-chip").first, "Cada paso del acta muestra su estado: Pendiente, En curso, Completado o Bloqueado.", "left"),
        (pg.get_by_text("Permiso mecánico").first.locator("xpath=ancestor::div[contains(@class,'card') or contains(@class,'permit')][1]"),
         "La tarjeta del permiso: radicado y, cuando responda la ciudad, aprobado.", "left"),
        (pg.get_by_role("button", name="La ciudad lo aprobó"), "«La ciudad lo aprobó»: fechas de aprobación y vencimiento; el expediente pasa a «Listo para instalar».", "bottom"),
        (pg.get_by_role("button", name="La ciudad lo rechazó"), "«La ciudad lo rechazó»: con el motivo; luego se vuelve a radicar.", "right"),
        (pg.get_by_role("button", name="Registrar permiso"), "Registrar otro permiso (eléctrico, mecánico…) o «No requerido».", "left"),
    ], pg.get_by_text("Acta de instalación").first


def orden(pg):
    paso = abrir_paso(pg, "release")
    return [
        (paso.locator("select").first, "Técnico que hará la instalación.", "left"),
        (paso.locator("input[type=date]").first, "Fecha de la instalación.", "bottom"),
        (paso.locator("button.acta-btn.is-primary").first, "Libera la orden: aparece en la Agenda del técnico y le llega un aviso.", "right"),
        (paso.locator(".materials-releases"), "Salidas de bodega de esta obra con su estado; «Pedir material a bodega» abre la salida con la obra puesta.", "left"),
        (paso.locator("table").first, "Materiales de la orden: lo entregado por bodega entra solo; lo demás se anota a mano.", "left"),
        (paso.get_by_role("button", name="Agregar material"), "Agregar lo que no sale de bodega (comprado directo para la obra).", "right"),
    ], paso


def agenda(pg):
    return [
        (pg.get_by_role("tab", name="Pendientes"), "«Pendientes»: lo que falta, con las atrasadas arriba. «Historial»: lo cerrado.", "bottom"),
        (pg.locator("input[type=date]").first, "Hasta qué fecha ver.", "inside"),
        (pg.get_by_role("link", name="CASE-2026-0118").first, "Tocar la orden abre su acta.", "top"),
    ], None


def checklist(pg):
    paso = pg.locator("#acta-step-checklist")
    return [
        (paso.get_by_text("Marca lo que aplica").first.locator(".."), "Condiciones de la casa: agregan o quitan requisitos del checklist.", "inside"),
        (paso.get_by_text("Confirmado el").first, "Línea confirmada, con fecha y hora; «Deshacer» la reabre.", "inside"),
        (paso.locator("label.acta-btn.is-line").first, "«Tomar foto»: la línea exige foto (con GPS y fecha); con la foto queda confirmada.", "inside"),
        (paso.get_by_text("No aplica en esta casa").first, "Si la línea no aplica en esta casa, se marca con su motivo.", "inside"),
    ], paso.get_by_text("Marca lo que aplica").first


def equipos(pg):
    paso = abrir_paso(pg, "equipment")
    # Si una corrida anterior ya guardó la lista, se quita y se vuelve a agregar
    # un equipo para que el paso quede «En curso», con el botón de guardar.
    if paso.get_by_text("Lista guardada").count():
        paso.get_by_role("button", name="Quitar").last.click()
        pg.wait_for_timeout(1500)
    for marca, modelo, serial, tipo in (("Carrier", "25HCE4", "HP-5219E1234", "heat_pump_outdoor"),
                                        ("Carrier", "FV4C", "AH-5219E5678", "air_handler")):
        if paso.locator("tbody").get_by_text(serial).count() == 0:
            pg.select_option("#equipment-type", tipo)
            pg.fill("#equipment-brand", marca)
            pg.fill("#equipment-model", modelo)
            pg.fill("#equipment-serial", serial)
            pg.fill("#equipment-unit", "Casa principal")
            paso.get_by_role("button", name="Agregar equipo").click()
            pg.wait_for_timeout(1500)
    return [
        (paso.locator(".acta-step-summary"), "Mientras la lista no se guarde, el paso sigue «En curso».", "inside"),
        (paso.locator("table").first, "Equipos registrados; «Quitar» borra uno.", "inside"),
        (paso.get_by_role("button", name="Guardar equipos instalados"), "Cuando estén todos, «Guardar equipos instalados» completa el paso.", "inside"),
        (pg.locator("#equipment-brand"), "Para cada equipo: tipo, marca, modelo, serial, cantidad y unidad o espacio.", "inside"),
        (paso.get_by_role("button", name="Agregar equipo"), "«Agregar equipo» lo suma a la lista.", "inside"),
    ], paso


def firmas(pg):
    boton = abrir_paso(pg, "equipment").get_by_role("button", name="Guardar equipos instalados")
    if boton.count():
        boton.click()
        pg.wait_for_timeout(2500)
    paso = abrir_paso(pg, "signatures")
    return [
        (paso.locator("canvas").first, "El técnico firma con el dedo y toca «Firmar».", "inside"),
        (paso.get_by_role("button", name="Enviar enlace por correo"), "Al cliente le llega un enlace al correo para firmar desde su teléfono (vale 72 horas).", "inside"),
        (paso.get_by_role("button", name="Que firme aquí, en este celular"), "Si el cliente no tiene correo ni internet, firma en el celular del técnico.", "inside"),
    ], paso


def firma_cliente(pg):
    paso = abrir_paso(pg, "signatures")
    enlace = paso.get_by_role("button", name="Que firme aquí, en este celular")
    if enlace.count():
        enlace.click()
        pg.wait_for_timeout(800)
        pg.fill("#firma-cliente-nombre", "Roberto Sánchez")
    return [
        (pg.locator("#firma-cliente-nombre"), "El cliente escribe su nombre.", "inside"),
        (paso.locator("canvas").last, "Y firma en el recuadro; luego «Firmar». Una firma no se puede repetir.", "inside"),
        (paso.get_by_role("button", name="Mejor enviarle el enlace"), "Volver a la opción del enlace por correo.", "inside"),
    ], pg.locator("#firma-cliente-nombre")


def cierre(pg):
    paso = abrir_paso(pg, "close")
    return [
        (paso.get_by_text("requisitos cumplidos").first.locator(".."), "Lo que falta para cerrar: líneas del checklist y la lista de equipos guardada.", "inside"),
        (paso.get_by_role("button", name="Cerrar instalación"), "«Cerrar instalación» se habilita con todo cumplido: el acta queda congelada y Administración recibe el aviso.", "inside"),
    ], paso


def confirmacion(pg):
    paso = abrir_paso(pg, "review")
    return [
        (paso.locator(".acta-step-head"), "Paso «Confirmación de Administración», abierto desde el aviso o la bandeja.", "left"),
        (paso.get_by_role("button", name="Confirmar información técnica"), "«Confirmar información técnica»: habilita el cobro.", "left"),
        (paso.get_by_role("button", name="Devolver"), "«Devolver al técnico» con el motivo; el acta se reabre para corregir.", "right"),
    ], paso


def cobro(pg):
    paso = abrir_paso(pg, "billing")
    return [
        (paso.get_by_text("Programa del expediente").first, "Solo aparece el programa del expediente.", "left"),
        (paso.get_by_text("$6,000.00").first, "Tarifa vigente el día de la instalación.", "left"),
        (paso.get_by_role("button", name="Crear cobro"), "«Crear cobro»: el expediente pasa a «En cobro».", "left"),
        (paso.get_by_role("button", name="Vista previa de la factura"), "Ver cómo saldrá la factura antes de crearla.", "right"),
    ], paso


def facturacion(pg):
    return [
        (pg.locator(".billing-tabs"), "Cobros de programas, facturas, cotizaciones del trabajo particular y configuración de cobro de los programas.", "inside"),
        (pg.get_by_text("Por radicar").first.locator("xpath=ancestor::*[count(.//button)>=4][1]"), "El ciclo del cobro: por cobrar, por radicar, radicados, rechazados y pagados.", "left"),
        (pg.get_by_text("Lo que deben los programas").first.locator(".."), "Lo que deben los programas, por antigüedad.", "left"),
        (pg.get_by_text("Patricia Gómez").first.locator("xpath=ancestor::*[self::a or self::li][1]"), "Cada fila abre la instalación o el cobro.", "left"),
    ], None


def gastos(pg):
    return [
        (pg.locator("select").first, "Categoría del gasto: gasolina, viáticos, hotel, material…", "inside"),
        (pg.locator("input[type=file]").first.locator(".."), "Foto del recibo: obligatoria.", "inside"),
        (pg.locator("form button[type=submit]").first, "Queda «por revisar» y a Contabilidad le llega el aviso.", "inside"),
    ], None


def pestanas(texto):
    def fn(pg):
        return [(pg.get_by_role("tab").first.locator(".."), texto, "bottom")], None
    return fn


def proveedores(pg):
    return [
        (pg.get_by_role("tab").first.locator(".."), "Facturas, pagos, proveedores y antigüedad. Gerencia y el Administrador ven además «Ajustes».", "inside"),
        (pg.get_by_role("button", name="Exportar facturas (CSV)"), "Exportar facturas y pagos para el contador.", "left"),
        (pg.locator("select").first, "Filtrar por estado: con saldo, por aprobar, pagadas…", "right"),
        (pg.get_by_role("button", name="Registrar factura"), "Registrar una factura de proveedor; cada línea se puede asignar a una instalación.", "left"),
        (pg.locator("td").get_by_text("Por aprobar").first, "Estado: por aprobar, aprobada, pagada en parte o pagada. Debajo dice qué falta.", "right"),
    ], None


def rentabilidad(pg):
    return [
        (pg.get_by_text("Instalación cerrada desde").first.locator(".."), "Filtrar por fecha de cierre y por programa.", "right"),
        (pg.get_by_text("Margen", exact=True).first.locator(".."), "Totales: esperado, cobrado, costos y margen.", "bottom"),
        (pg.get_by_text("Equipos $").first, "Los costos de cada instalación, por tipo: equipos, materiales, contratistas, gastos de campo…", "bottom"),
    ], None


def reportes(pg):
    return [
        (pg.get_by_role("tab").first.locator(".."), "Reportes comercial, de operación y de finanzas.", "inside"),
        (pg.locator("input[type=date]").first.locator(".."), "Rango de fechas del reporte, o atajos de 7, 30 y 90 días o un año.", "top"),
        (pg.get_by_role("button", name="Exportar CSV"), "Exportar el reporte a CSV para Excel.", "left"),
    ], None


def programas(pg):
    return [
        (pg.get_by_text("Eficiencia de Arizona").first.locator("xpath=ancestor::*[self::button or self::a][1]"), "Programas creados; tóquelo para configurarlo.", "right"),
        (pg.get_by_role("button", name="+ Nuevo programa"), "«+ Nuevo programa»: código y nombre.", "right"),
        (pg.get_by_text("Versión 1", exact=True).nth(1), "Formulario por versión: la publicada queda congelada; para cambiar algo se crea una versión nueva.", "left"),
        (pg.get_by_role("button", name="+ Nuevos términos"), "Términos y condiciones por versión e idioma.", "left"),
        (pg.get_by_role("button", name="+ Agregar zona"), "Zonas de venta con sus vendedores.", "left"),
    ], None


def bodega_existencias(pg):
    pg.wait_for_timeout(1500)
    return [
        (pg.get_by_role("button", name="Importar catálogo"), "«Importar catálogo» carga el Excel del catálogo con la cantidad de hoy como conteo inicial.", "left"),
        (pg.locator(".fin-kpis"), "Artículos activos y cuántos están por debajo de su mínimo.", "bottom"),
        (pg.locator(".notices-table").first, "Cada artículo con su categoría, lo que hay en total, el mínimo y lo que vale.", "top"),
    ], None


def bodega_articulo(pg):
    pg.get_by_role("button", name="Nuevo artículo").click()
    pg.wait_for_timeout(800)
    return [
        (pg.locator("#it-sku"), "Código AC Pro (o la referencia del proveedor): evita duplicar el artículo al importar.", "left"),
        (pg.locator("#it-mfg"), "Número del fabricante, tal como aparece en AC Pro (MFG #).", "left"),
        (pg.locator("#it-brand"), "Marca. El buscador encuentra el artículo por nombre, código, fabricante o marca.", "right"),
        (pg.locator("#it-cat"), "Categoría: solo se ofrecen las activas.", "left"),
        (pg.locator("#it-min"), "Mínimo: al llegar aquí la bodega recibe un aviso.", "right"),
    ], pg.locator("#it-name")


def bodega_categorias(pg):
    pg.get_by_role("button", name="Categorías").click()
    pg.wait_for_timeout(1500)
    return [
        (pg.locator("#cat-nueva"), "Escriba el nombre y toque «Agregar» para crear una categoría.", "left"),
        (pg.locator(".category-list li").first, "Cada categoría con cuántos artículos tiene y si está activa.", "left"),
        (pg.locator(".category-actions").first, "«Renombrar» cambia el nombre en todos sus artículos; «Desactivar» la saca de las opciones.", "left"),
    ], pg.locator("#cat-nueva")


def bodega_salida(pg):
    pg.get_by_role("button", name="Nueva salida").click()
    pg.wait_for_timeout(800)
    campo = pg.get_by_role("combobox", name="Artículo del renglón 1")
    campo.click()
    campo.fill("pvc")
    pg.locator(".search-picker-option").first.wait_for(timeout=15000)
    return [
        (pg.locator("#rel-lista"), "Aplicar una lista predefinida: trae los renglones del tipo de trabajo para ajustarlos.", "right"),
        (pg.get_by_role("combobox", name="Obra"), "La obra se busca por nombre o dirección; vacía, el material es de uso interno.", "top"),
        (campo, "El artículo se busca escribiendo parte del nombre o la referencia de AC Pro.", "left"),
        (pg.locator(".search-picker-list"), "Se elige de la lista; si salen muchos, se escribe más para afinar.", "left"),
        (pg.get_by_role("button", name="Agregar renglón"), "«Agregar renglón» suma cualquier otro artículo del catálogo.", "left"),
    ], pg.locator("#rel-lista")


def bodega_checklist(pg):
    pg.get_by_role("button", name="Nueva salida").click()
    pg.wait_for_timeout(800)
    pg.locator("#rel-lista").select_option(index=1)
    pg.wait_for_timeout(1500)
    return [
        (pg.locator("#rel-lista"), "La lista trae los renglones del tipo de trabajo, agrupados por sección.", "right"),
        (pg.locator(".release-section-row").first, "Cada sección del trabajo: exterior, eléctrico, líneas, drenaje…", "left"),
        (pg.locator("form .billing-chip.is-required").first, "«Obligatorio»: si se quita, pide el motivo y quien autoriza lo ve.", "right"),
    ], pg.locator("#rel-lista")


def bodega_carga(pg):
    pg.wait_for_timeout(2500)
    fila = pg.locator("tbody tr").filter(has=pg.get_by_role("checkbox", name="Lo llevo")).filter(has_text="Fusible Disconnect").first
    if not fila.locator("details").first.get_attribute("open") is not None:
        fila.locator("summary").first.click()
    pg.wait_for_timeout(600)
    return [
        (fila.locator(".release-load").first, "Cuánto ya va en la camioneta y cuántos obligatorios faltan.", "inside"),
        (fila.get_by_role("checkbox", name="Lo llevo").first.locator(".."), "«Lo llevo»: se marca al subir cada cosa a la camioneta.", "inside"),
        (fila.locator(".billing-chip.is-required").first, "Lo obligatorio va marcado para que no se quede.", "inside"),
    ], fila


def bodega_compras(pg):
    pg.locator("thead th").first.wait_for(timeout=20000)
    return [
        (pg.locator("thead th", has_text="Presupuestado"), "Lo que suman los presupuestos aprobados de las obras abiertas.", "top"),
        (pg.locator("thead th", has_text="Ya entregado"), "Lo que ya salió para esas obras: no se vuelve a comprar.", "top"),
        (pg.locator("thead th", has_text="Por comprar"), "Lo que falta entregar menos lo que hay en bodega.", "top"),
    ], None


def rotacion_solo_lectura(pg):
    pg.locator(".read-only-banner").wait_for(timeout=20000)
    return [
        (pg.locator(".read-only-banner"), "Solo lectura: el responsable de hoy es otro técnico. Se ve todo, no se llena.", "inside"),
    ], pg.locator(".read-only-banner")


def calendario_obras(pg):
    pg.locator(".works-calendar-grid").wait_for(timeout=20000)
    pg.get_by_role("tab", name="Semana").click()
    pg.wait_for_timeout(1500)
    return [
        (pg.locator(".works-calendar-nav"), "Moverse por meses o semanas; «Hoy» vuelve al día de hoy.", "bottom"),
        (pg.locator(".works-calendar-filters"), "Ver el mes o la semana, y solo un técnico.", "bottom"),
        (pg.locator(".works-chip.is-log").first, "Una jornada del diario: la obra, el técnico (y sus ayudantes) y hasta dónde se avanzó.", "left"),
        (pg.locator(".works-chip.is-turn").first, "Punteado: el día en que un técnico toma la obra.", "left"),
    ], None


def bodega_diario(pg):
    pg.get_by_role("button", name="Registrar la jornada").first.click()
    pg.wait_for_timeout(800)
    campo = pg.get_by_role("combobox", name="Artículo del material 1")
    campo.click()
    campo.fill("tape")
    pg.locator(".search-picker-option").first.wait_for(timeout=15000)
    return [
        (pg.locator("#diario-trabajo"), "Qué se hizo ese día; abajo, el avance, lo que faltó y qué llevar mañana.", "inside"),
        (campo, "El material del día se busca en el catálogo escribiendo su nombre o referencia.", "inside"),
        (pg.locator(".search-picker-list"), "Se toca el artículo para elegirlo.", "inside"),
    ], pg.get_by_role("heading", name="Material del día")


def equipo(pg):
    return [
        (pg.locator("form").first, "Invitar a una persona por correo, con su rol.", "bottom"),
        (pg.locator("table").first, "El equipo, con rol y estado; se activa o desactiva, no se borra.", "top"),
    ], None


def buscador(pg):
    pg.wait_for_timeout(1500)
    caja = pg.locator(".global-search-box input")
    caja.click()
    caja.fill("Cliente")
    pg.wait_for_timeout(2500)
    grupo = pg.locator(".global-search-group").first
    return [
        (caja, "Escriba al menos 2 letras: nombre, dirección, número de expediente, factura o salida, código de artículo…", "right"),
        (grupo.locator("header span"), "Los resultados van por grupo, y solo de lo que su rol puede ver.", "left"),
        (grupo.locator(".global-search-option").first, "Tocar un resultado lo abre. Con el teclado: flechas y Enter.", "left"),
        (grupo.get_by_text("Ver todos"), "«Ver todos» abre la lista completa ya filtrada con el mismo texto.", "right"),
    ], None


def buscador_celular(pg):
    pg.wait_for_timeout(1500)
    lupa = pg.locator(".global-search-trigger")
    caja_lupa = lupa.bounding_box()
    lupa.click()
    pg.wait_for_timeout(500)
    pg.locator(".global-search-box input").fill("Cliente")
    pg.wait_for_timeout(2500)
    return [
        (pg.locator(".global-search-option").first, "La lupa junto a la campana abre el buscador a pantalla completa; tocar un resultado lo abre.", "inside"),
        (pg.locator(".global-search-close"), "«Cerrar» vuelve a la pantalla en que estaba.", "bottom"),
    ] if caja_lupa else [], None


PANTALLAS = [
    ("login", None, ESCRITORIO, "/login", "Ingreso", login),
    ("inicio", "admin", ESCRITORIO, "/", "Inicio", inicio),
    ("campana", "admin", ESCRITORIO, "/", "La campana de avisos", campana),
    ("midia", "vendedor", CELULAR, "/sales", "Mi día (vendedor, en el celular)", midia),
    ("visita", "vendedor", alto(1330), "/sales/visit", "Tocar una puerta", visita),
    ("formulario", "vendedor", alto(1200), f"/cases/{DEMO['formulario']}/form", "Formulario: términos y firma del cliente", formulario),
    ("tablero", "adm", ESCRITORIO, "/cases", "Expedientes: tablero por etapa", tablero),
    ("porrevisar", "adm", {"width": 1280, "height": 1300}, "/review", "Por revisar › Documentos", porrevisar),
    ("porrevisar_inspeccion", "adm", {"width": 1280, "height": 1300}, "/review?tab=inspecciones", "Por revisar › Inspección municipal", porrevisar_inspeccion),
    ("revision", "adm", ANCHO, f"/cases/{DEMO['revision']}/review", "Revisión del expediente", revision),
    ("acta_permiso", "adm", {"width": 1280, "height": 1150}, f"/projects/{DEMO['permiso']['project']}", "Acta de instalación: permiso municipal", acta_permiso),
    ("orden", "adm", {"width": 1280, "height": 1150}, f"/projects/{DEMO['permiso']['project']}", "Orden liberada: técnico, fecha y materiales", orden),
    ("agenda", "tecnico", CELULAR, "/my-schedule", "Agenda del técnico", agenda),
    ("checklist", "tecnico", alto(1500), f"/projects/{DEMO['tecnico']['project']}", "Checklist técnico", checklist),
    ("equipos", "tecnico", alto(1400), f"/projects/{DEMO['tecnico']['project']}", "Equipos instalados", equipos),
    ("firmas", "tecnico", alto(1300), f"/projects/{DEMO['tecnico']['project']}", "Firmas del acta", firmas),
    ("firma_cliente", "tecnico", alto(1300), f"/projects/{DEMO['tecnico']['project']}", "Firma del cliente en el celular del técnico", firma_cliente),
    ("cierre", "tecnico", alto(1750), f"/projects/{DEMO['tecnico']['project']}", "Cierre de la instalación", cierre),
    ("confirmacion", "adm", ANCHO, f"/projects/{DEMO['acta']['project']}?paso=review", "Confirmación de Administración", confirmacion),
    ("cobro", "adm", ANCHO, f"/projects/{DEMO['cobro']['project']}?paso=billing", "Cobro al programa", cobro),
    ("facturacion", "conta", {"width": 1280, "height": 1600}, "/invoices", "Facturación y cobros", facturacion),
    ("gastos", "tecnico", alto(1300), "/expenses", "Gastos de campo", gastos),
    ("proveedores", "conta", ESCRITORIO, "/payables", "Proveedores y pagos", proveedores),
    ("rentabilidad", "gerencia", ESCRITORIO, "/finance-close", "Rentabilidad por instalación", rentabilidad),
    ("reportes", "gerencia", ESCRITORIO, "/reports", "Reportes", reportes),
    ("bodega_existencias", "adm", ESCRITORIO, "/warehouse", "Bodega: existencias", bodega_existencias),
    ("bodega_articulo", "adm", {"width": 1280, "height": 1000}, "/warehouse/items", "Bodega: un artículo con su código AC Pro, fabricante y marca", bodega_articulo),
    ("bodega_categorias", "adm", {"width": 1280, "height": 1000}, "/warehouse/items", "Bodega: categorías del catálogo", bodega_categorias),
    ("bodega_salida", "adm", {"width": 1280, "height": 1000}, "/warehouse/releases", "Bodega: nueva salida con el buscador de artículos", bodega_salida),
    ("bodega_checklist", "tecnico", alto(1600), "/warehouse/releases", "Salida armada desde una lista (celular del técnico)", bodega_checklist),
    ("bodega_carga", "tecnico", alto(1500), "/warehouse/releases", "«Lo llevo»: la checklist al cargar la camioneta", bodega_carga),
    ("bodega_compras", "adm", ESCRITORIO, "/warehouse/purchasing", "Compras sugeridas", bodega_compras),
    ("rotacion_solo_lectura", "tecnico", alto(1100), f"/projects/{DEMO['tecnico']['project']}", "Obra en solo lectura para el técnico anterior", rotacion_solo_lectura),
    ("calendario_obras", "adm", {"width": 1280, "height": 1100}, "/works-calendar", "Calendario de obras", calendario_obras),
    ("bodega_diario", "tecnico", alto(1500), f"/projects/{DEMO['tecnico']['project']}", "Diario de obra: material del día (celular)", bodega_diario),
    ("programas", "admin", {"width": 1280, "height": 1350}, "/programs", "Configuración de programas", programas),
    ("equipo", "admin", ESCRITORIO, "/users", "Equipo", equipo),
    ("buscador", "adm", {"width": 1280, "height": 900}, "/", "Buscador global", buscador),
    ("buscador_celular", "adm", CELULAR, "/", "Buscador global en el celular", buscador_celular),
]


def main(claves):
    IMG.mkdir(exist_ok=True)
    ruta_json = IMG / "capturas.json"
    datos = json.loads(ruta_json.read_text()) if ruta_json.exists() else {}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--host-resolver-rules=MAP localhost frontend"])
        sesiones = {}
        for clave, rol, vista, ruta, titulo, fn in PANTALLAS:
            if claves and clave not in claves:
                continue
            k = (rol, vista["width"], vista["height"])
            if k not in sesiones:
                sesiones[k] = Sesion(b, rol, vista)
            s = sesiones[k]
            s.ir(ruta, 3000)
            try:
                puntos, ancla = fn(s.pg)
                leyenda = anotar_y_guardar(s.pg, clave, puntos, ancla)
                datos[clave] = {"titulo": titulo, "leyenda": leyenda}
            except Exception as e:
                print(f"  ✗ {clave}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
