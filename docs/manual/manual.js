// Manual de usuario de PAP.CRM (Delta HVAC): genera docs/Manual_Usuario_CRM_Delta_HVAC.docx.
// Las capturas anotadas y sus leyendas salen de img/ (las hace pantallas.py).
// Uso, desde docs/manual:  docker run --rm -v "<repo>/docs:/d" -w /d/manual node:20-slim \
//                            sh -c "npm install && node manual.js"
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, LevelFormat, BorderStyle, Footer, PageNumber, PageBreak,
  TableOfContents, ImageRun,
} = require("docx");

const IMG = path.join(__dirname, "img");
const CAPTURAS = JSON.parse(fs.readFileSync(path.join(IMG, "capturas.json"), "utf8"));
let figura = 0;

// Ancho y alto en píxeles de un PNG (cabecera IHDR).
function medidas(buf) {
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

// Captura con su título y la lista de lo que señala cada número.
function fig(clave) {
  const dato = CAPTURAS[clave];
  const archivo = path.join(IMG, `${clave}.png`);
  if (!dato || !fs.existsSync(archivo)) return [];
  const buf = fs.readFileSync(archivo);
  const { w, h } = medidas(buf);
  const celular = w < 1000;                       // capturas de 390 px de ancho (×2)
  let ancho = celular ? 290 : 624;                // en puntos de 1/96": 624 = 6,5"
  let alto = Math.round(ancho * h / w);
  const maximo = 790;                             // que quepa en una hoja
  if (alto > maximo) { ancho = Math.round(ancho * maximo / alto); alto = maximo; }
  figura += 1;
  const titulo = new Paragraph({ spacing: { after: 100 }, keepNext: true,
    children: [new TextRun({ text: `Figura ${figura}. ${dato.titulo}`, font: FONT, size: 18, italics: true, color: GRIS })] });
  const leyenda = dato.leyenda.map((texto, i) => new Paragraph({ spacing: { after: 70, line: 270 },
    indent: { left: 360, hanging: 360 },
    children: [new TextRun({ text: `${i + 1}  `, font: FONT, size: 20, bold: true, color: ROJO }),
      new TextRun({ text: texto, font: FONT, size: 20 })] }));
  if (celular) {
    // Celular: imagen a la izquierda y la leyenda al lado; cabe en una hoja.
    const tope = 600;
    let a = 250, b = Math.round(250 * h / w);
    if (b > tope) { a = Math.round(a * tope / b); b = tope; }
    const sinBorde = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
    const bordesNo = { top: sinBorde, bottom: sinBorde, left: sinBorde, right: sinBorde };
    return [
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [4000, 5360], rows: [new TableRow({ cantSplit: true, children: [
        new TableCell({ borders: bordesNo, width: { size: 4000, type: WidthType.DXA },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: buf,
            transformation: { width: a, height: b }, altText: { title: dato.titulo, description: dato.titulo, name: clave } })] })] }),
        new TableCell({ borders: bordesNo, width: { size: 5360, type: WidthType.DXA }, margins: { left: 200, top: 300 },
          children: [titulo, ...leyenda] }),
      ] })] }),
      new Paragraph({ spacing: { after: 120 }, children: [] }),
    ];
  }
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: ancho, height: alto },
        altText: { title: dato.titulo, description: dato.titulo, name: clave } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, keepNext: true,
      children: [new TextRun({ text: `Figura ${figura}. ${dato.titulo}`, font: FONT, size: 18, italics: true, color: GRIS })] }),
    ...dato.leyenda.map((texto, i) => new Paragraph({ spacing: { after: 50, line: 270 }, indent: { left: 360, hanging: 360 },
      keepNext: i < dato.leyenda.length - 1,
      children: [new TextRun({ text: `${i + 1}  `, font: FONT, size: 20, bold: true, color: ROJO }),
        new TextRun({ text: texto, font: FONT, size: 20 })] })),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

const FONT = "Arial";
const ROJO = "B5222D";
const GRIS = "5A5A5A";
const W = 9360;

// **negrita** dentro del texto.
function runs(texto, base = {}) {
  return texto.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((x) =>
    x.startsWith("**") ? new TextRun({ text: x.slice(2, -2), font: FONT, size: 21, bold: true, ...base })
      : new TextRun({ text: x, font: FONT, size: 21, ...base }));
}
const p = (t, after = 110) => new Paragraph({ spacing: { after, line: 285 }, children: runs(t) });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 140 }, keepNext: true,
  children: [new TextRun({ text: t, font: FONT, size: 30, bold: true, color: ROJO })] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 90 }, keepNext: true,
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true })] });
const h3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 140, after: 60 }, keepNext: true,
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, color: "333333" })] });
const li = (t, level = 0) => new Paragraph({ numbering: { reference: "v", level }, spacing: { after: 60, line: 275 }, children: runs(t) });
const n = (t, ref) => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 275 }, children: runs(t) });
const nota = (t) => new Paragraph({ spacing: { before: 100, after: 140 },
  shading: { type: ShadingType.CLEAR, color: "auto", fill: "F7F3EC" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: ROJO, space: 8 } }, children: runs(t, { size: 20 }) });

const borde = { style: BorderStyle.SINGLE, size: 4, color: "D5D0C8" };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };
function tabla(cab, filas, anchos) {
  const celda = (texto, w, esCab) => new TableCell({
    borders: bordes, width: { size: w, type: WidthType.DXA },
    shading: esCab ? { type: ShadingType.CLEAR, color: "auto", fill: "F2EEE8" } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: [new Paragraph({ children: esCab ? [new TextRun({ text: texto, font: FONT, size: 19, bold: true })] : runs(texto, { size: 19 }) })],
  });
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: anchos, rows: [
    new TableRow({ tableHeader: true, children: cab.map((c, i) => celda(c, anchos[i], true)) }),
    ...filas.map((f) => new TableRow({ children: f.map((c, i) => celda(c, anchos[i], false)) })),
  ] });
}
const esp = () => new Paragraph({ spacing: { after: 80 }, children: [] });

// Listas numeradas independientes (cada una reinicia en 1).
const LISTAS = ["l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9", "l10", "l11", "l12", "l13", "l14", "l15"];

const c = [];
const add = (...xs) => c.push(...xs);

// --- Portada --------------------------------------------------------------------
add(
  new Paragraph({ spacing: { before: 1800, after: 120 }, children: [new TextRun({ text: "PAP.CRM · Delta HVAC", font: FONT, size: 28, color: ROJO, bold: true })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Manual de usuario", font: FONT, size: 56, bold: true })] }),
  new Paragraph({ spacing: { after: 400 }, children: [new TextRun({ text: "Venta puerta a puerta, revisión, instalación, cobro y finanzas", font: FONT, size: 26, color: GRIS })] }),
  p("**Versión:** 24 de octubre de 2026 · ambiente de pruebas"),
  p("Este manual describe la aplicación tal como funciona hoy. Si una pantalla no se ve como aquí se describe, repórtelo (sección 14)."),
  p("Las capturas son de la aplicación real con datos de demostración. Los números rojos señalan cada parte de la pantalla; debajo de cada imagen dice qué es cada número."),
  new Paragraph({ children: [new PageBreak()] }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
);

// --- 1 ---------------------------------------------------------------------------
add(
  h1("1. Cómo usar este manual"),
  p("La plataforma lleva cada venta desde que el vendedor toca la puerta hasta que el programa paga la instalación. Todo gira alrededor del **expediente**: nace en la puerta y pasa de rol en rol (vendedor, Administración, técnico, Contabilidad) hasta quedar pagado y cerrado."),
  p("Las secciones 2 a 4 son para todos. Después hay una sección por rol: lea la suya. La sección 12 explica la bodega y la 13 es una guía para probar la plataforma de punta a punta."),
);

// --- 2 ---------------------------------------------------------------------------
add(
  h1("2. Entrar a la plataforma"),
  h2("2.1 Ingreso"),
  n("Abra el navegador en la dirección de la plataforma (en pruebas: http://localhost:5173, o la IP del computador desde un celular en la misma red).", "l1"),
  n("Escriba su correo y su contraseña. El **ojo** al lado de la contraseña la muestra u oculta.", "l1"),
  ...fig("login"),
  n("Toque **Sign in**. La pantalla de ingreso, la de invitación y la de restablecer contraseña están en inglés a propósito; el resto de la aplicación está en español.", "l1"),
  h2("2.2 Olvidé mi contraseña"),
  p("En el ingreso, **Forgot password?** envía un enlace al correo. Sirve una sola vez y vence en 60 minutos. Se pueden pedir hasta 3 por hora."),
  h2("2.3 Invitación"),
  p("Los usuarios nuevos los invita el Administrador desde **Equipo**. Llega un correo con un enlace para crear la contraseña, válido por 72 horas."),
  h2("2.4 Sesión y seguridad"),
  li("La sesión dura hasta 14 días en el mismo navegador. Al salir con **Salir** se cierra."),
  li("Después de varios intentos fallidos el ingreso se bloquea por 15 minutos, aunque la contraseña esté bien."),
  li("Si se pierde la señal, la aplicación no lo saca: espera a que vuelva."),
  h2("2.5 Usuarios de prueba"),
  p("Todos con la contraseña **ChangeMe123!** (cambiarla antes de usar datos reales):"),
  tabla(["Rol", "Usuario"], [
    ["Administrador", "admin@demo-org.com"], ["Vendedor", "vendedor@demo-org.com"],
    ["Administración", "administracion@demo-org.com"], ["Técnico", "tecnico@demo-org.com"],
    ["Contabilidad", "contabilidad@demo-org.com"], ["Gerencia", "gerencia@demo-org.com"],
  ], [3000, 6360]),
  esp(),
  p("Para tener dos roles abiertos a la vez use una ventana de incógnito: en la misma ventana, entrar con otro usuario cierra la sesión anterior."),
);

// --- 3 ---------------------------------------------------------------------------
add(
  h1("3. Roles y menú"),
  p("Cada persona ve **solo lo que su rol le permite**. Si alguien no ve una opción del menú, es porque su rol no la incluye, no es un error. Si escribe a mano la dirección de una pantalla sin permiso (o una que no existe), la aplicación lo lleva al Inicio."),
  tabla(["Rol", "Qué hace"], [
    ["Vendedor", "Toca puertas, llena el formulario del programa con el cliente, toma la firma y envía el expediente a revisión. Ve solo sus expedientes."],
    ["Administración", "Revisa documentos y decide los expedientes; registra permisos, asigna técnico y fecha, confirma el acta, agenda la inspección y crea los cobros. Trabaja desde «Por revisar». Lleva la bodega: catálogo, conteos, autoriza y entrega las salidas, y arma el presupuesto de la obra."],
    ["Técnico", "Ve su agenda y las órdenes asignadas a él; llena el acta de instalación, registra equipos, toma las firmas y cierra la instalación. Registra sus gastos de campo, pide material a la bodega y llena el diario de la obra."],
    ["Contabilidad", "Configura tarifas y zonas de cobro, radica cobros, registra pagos del programa, factura el trabajo particular, revisa gastos, lleva proveedores y pagos, concilia y ve la rentabilidad."],
    ["Gerencia", "Consulta la operación, aprueba facturas de proveedor y ajustes, ve reportes, rentabilidad y el monitor de técnicos."],
    ["Administrador", "Todo lo anterior, más equipo, roles y permisos, auditoría y configuración de programas."],
  ], [2000, 7360]),
  esp(),
  h2("3.1 El menú"),
  tabla(["Sección", "Entrada", "Para qué"], [
    ["—", "Inicio", "Resumen del día y actividad reciente"],
    ["Operación comercial", "Clientes", "Directorio de clientes y su ficha"],
    ["", "Mi día", "Vendedor: programas, zonas y pendientes; botón «+ Tocar una puerta»"],
    ["", "Campañas", "Campañas de SMS y correo a clientes con permiso"],
    ["", "Expedientes", "Tablero de expedientes por etapa"],
    ["", "Por revisar", "Bandeja de Administración: Documentos, Actas por confirmar, Inspección municipal y Cobros por crear"],
    ["Operación de campo", "Proyectos", "Una instalación por expediente aprobado"],
    ["", "Monitor de técnicos", "Si cada técnico está conectado y cuántas órdenes tiene"],
    ["", "Agenda", "Instalaciones pendientes e historial"],
    ["", "Checklists de instalación", "Plantillas del checklist por programa"],
    ["", "Permisos e inspecciones", "Vista general de permisos municipales e inspecciones"],
    ["Bodega", "Existencias", "Qué hay en la bodega y en las camionetas; importar el catálogo"],
    ["", "Artículos · Listas", "El catálogo de materiales y las listas predefinidas por tipo de trabajo"],
    ["", "Salidas", "Órdenes de salida: se piden, se autorizan y se entregan"],
    ["", "Movimientos · Compras sugeridas", "Libro de entradas y salidas; lo que hay que comprar según los presupuestos"],
    ["", "Plantillas de costo", "Cómo se reparte el precio de cada tipo de trabajo para el estimado"],
    ["Finanzas", "Facturación y cobros", "Cobros a los programas, facturas, cotizaciones y configuración de cobro"],
    ["", "Gastos de campo", "Gastos con recibo, revisión y reembolso"],
    ["", "Proveedores y pagos", "Proveedores, facturas de proveedor, aprobaciones y pagos"],
    ["", "Conciliación y rentabilidad", "Conciliación bancaria y margen por proyecto"],
    ["Administración", "Reportes", "Comercial, operación y finanzas"],
    ["", "Configuración de programas", "Programas, formularios, términos y zonas de venta"],
    ["", "Equipo · Roles y permisos · Auditoría", "Usuarios, permisos por rol e historial de acciones"],
    ["", "Notificaciones", "Mis avisos, preferencias, plantillas y alertas"],
  ], [2100, 2600, 4660]),
);

// --- 4 ---------------------------------------------------------------------------
add(
  h1("4. Lo que es igual en toda la plataforma"),
  ...fig("inicio"),
  li("**Avisos de guardado:** cada vez que algo se guarda aparece abajo un aviso corto (por ejemplo «Cambios guardados.» o «Equipos instalados guardados.»). Se cierra solo o al tocarlo. Los errores, en cambio, se muestran en rojo dentro del mismo formulario."),
  li("**La campana:** arriba a la derecha, con el número de avisos sin leer. Al tocar un aviso lo lleva directo a lo que tiene que hacer. Todos los avisos están en **Notificaciones**."),
  ...fig("campana"),
  li("**Listas por páginas:** las listas largas se muestran de a 20 o 30, con botones de página abajo. Los botones solo aparecen cuando hay más de una página."),
  li("**En el celular:** el menú se abre con **Menú**, y las tablas se muestran como una tarjeta por fila para leerlas sin desplazarse de lado."),
  li("**Fotos:** cada foto que se sube queda marcada con la fecha, la hora y la ubicación GPS. Si el navegador no tiene permiso de ubicación, la foto queda marcada «sin GPS». Solo se aceptan fotos, videos y PDF reales, hasta 10 MB."),
  li("**Fechas y días:** los contadores de días usan la fecha y la zona horaria de la empresa."),
);

// --- 5 ---------------------------------------------------------------------------
add(
  h1("5. El recorrido de un expediente"),
  tabla(["Etapa", "Quién lo mueve", "Cómo"], [
    ["Sin contacto · No interesado · No califica", "Vendedor", "Resultado de la visita en la puerta"],
    ["Nuevo prospecto", "Vendedor", "El cliente abrió; se llena el formulario"],
    ["Pendiente de aprobación", "Vendedor", "«Enviar a revisión»; corre el contador de días hábiles"],
    ["Aprobado", "Administración", "«Aprobar» con el código del programa; nace el proyecto de instalación"],
    ["Permiso en trámite", "Administración", "Registra el permiso municipal"],
    ["Listo para instalar", "Automático", "Cuando la ciudad aprueba el permiso"],
    ["Instalado", "Técnico", "«Cerrar instalación» en el acta"],
    ["Inspección pendiente", "Administración", "Agenda y registra la inspección municipal"],
    ["En cobro", "Administración o Contabilidad", "«Crear cobro» al programa"],
    ["Pagado", "Contabilidad", "«Registrar pago» del programa"],
    ["Cerrado", "Administración", "«Cerrar expediente…» con motivo"],
  ], [2900, 2300, 4160]),
  esp(),
  p("El expediente avanza solo con lo que se registra en cada paso: nadie lo «mueve» a mano. Cada cambio de etapa queda en su **Historial** con fecha y quién lo hizo."),
);

// --- 6 ---------------------------------------------------------------------------
add(
  h1("6. Configurar un programa (Administrador o Administración, y Contabilidad)"),
  p("Se hace una vez por programa (Eficiencia de Arizona y TECH Clean California ya vienen cargados)."),
  h2("6.1 El programa y su formulario"),
  p("Menú **Configuración de programas**:"),
  ...fig("programas"),
  n("**+ Nuevo programa:** código y nombre. El código no se puede cambiar después; lo demás sí. En «Identidad frente al cliente» van el nombre que ve el cliente, quién financia y quién factura.", "l2"),
  n("**Términos y condiciones:** «+ Nuevos términos», texto e idioma, y **Publicar**. Publicados no se editan: se crea una versión nueva.", "l2"),
  n("**Formulario:** «+ Nueva versión», luego los pasos (Cliente, Vivienda, Auditoría técnica, Documentos, Autorización…) y en cada paso los campos del catálogo, como obligatorios, opcionales o condicionales (por ejemplo, «Título de la casa móvil» solo si la vivienda es casa móvil). La vista previa de la derecha muestra el formulario como lo verá el vendedor. **Publicar versión** la congela.", "l2"),
  n("**Zonas de venta:** «+ Agregar zona» y asignar vendedores. Sin zona, el vendedor ve todos los programas publicados.", "l2"),
  h2("6.2 La configuración de cobro (Contabilidad)"),
  p("Menú **Facturación y cobros** → pestaña **Programas**: la **tarifa** por instalación con su vigencia, las **zonas de cobro** (ciudad o código postal), los **requisitos** del checklist para radicar (por ejemplo, si exige inspección) y el **emisor** de la factura."),
  nota("Sin tarifa vigente el día de la instalación no se puede crear el cobro. Configúrela antes de vender en ese programa."),
  h2("6.3 Checklist de instalación"),
  p("Menú **Checklists de instalación**: la lista de lo que el técnico debe confirmar en cada instalación, por programa (fachada, pedestal, equipos viejos, panel, gas, etiquetas, prueba de funcionamiento…). Los cambios aplican a las instalaciones siguientes."),
);

// --- 7 ---------------------------------------------------------------------------
add(
  h1("7. Vendedor"),
  h2("7.1 Mi día"),
  p("Primera pantalla del vendedor: sus programas y zonas, los expedientes devueltos para corregir y lo pendiente."),
  ...fig("midia"),
  h2("7.2 Tocar una puerta"),
  ...fig("visita"),
  n("**+ Tocar una puerta:** dirección, unidad (por ejemplo «Spc 14»), programa y resultado de la visita.", "l3"),
  n("Si no abrió, no está interesado o no califica, el expediente se cierra ahí sin pedir datos del cliente.", "l3"),
  n("Si la misma casa ya tiene expediente (aunque la dirección se escriba distinto), se reabre ese mismo; no se crea otro.", "l3"),
  h2("7.3 El formulario con el cliente"),
  li("Se llena paso por paso con **Guardar y seguir**. Lo que no se guarda no cuenta."),
  li("Los campos aparecen o desaparecen según las respuestas (por ejemplo, título y decal solo para casa móvil). Los números no aceptan letras ni valores por encima del máximo."),
  li("Las fotos (identificación, panel, furnace…) se toman con la cámara o se suben del celular, con GPS y fecha."),
  h2("7.4 Términos y firma"),
  ...fig("formulario"),
  p("En el último paso el cliente lee los términos, escribe su nombre y firma con el dedo. La firma queda guardada con la fecha, la ubicación y la versión de los términos. Antes de enviar se puede repetir."),
  h2("7.5 Enviar a revisión"),
  p("**Enviar a revisión** pasa el expediente a «Pendiente de aprobación» y ya no se puede editar. Si falta algo obligatorio, no deja enviar y dice qué falta."),
  p("Si Administración lo **devuelve**, llega un aviso con el motivo; el expediente aparece en Mi día para corregir y volver a enviar. Un expediente rechazado también se puede corregir y reenviar."),
);

// --- 8 ---------------------------------------------------------------------------
add(
  h1("8. Administración"),
  h2("8.1 La bandeja «Por revisar»"),
  p("Es el punto de partida del día. Tiene cuatro pestañas, cada una con el número de pendientes; cada fila abre el expediente o el proyecto **directo en el paso que toca**:"),
  tabla(["Pestaña", "Qué muestra"], [
    ["Documentos", "Expedientes enviados con documentos por revisar o rechazados, los que más llevan esperando primero, con el contador de días hábiles"],
    ["Actas por confirmar", "Instalaciones cerradas por el técnico que esperan su confirmación, la más vieja primero, con los días esperando"],
    ["Inspección municipal", "Instalaciones cerradas sin inspección aprobada: «Sin agendar», «Agendada» (con fecha) o «Falló: reagendar»"],
    ["Cobros por crear", "Actas confirmadas que todavía no tienen cobro al programa"],
  ], [2600, 6760]),
  ...fig("porrevisar"),
  h2("8.2 Revisar y decidir el expediente"),
  ...fig("tablero"),
  li("**Expedientes** muestra el tablero por etapa. En «Pendiente de aprobación» cada tarjeta lleva **⏱ N días hábiles** desde el envío: gris a tiempo, rojo desde el límite. Devolver no reinicia la cuenta."),
  li("En la revisión: **✓ Aceptar** cada documento o rechazarlo con una nota; **+ Agregar documento** si falta uno."),
  ...fig("revision"),
  li("**Devolver al vendedor** con un motivo, si hay que corregir."),
  li("Avance con el programa: «Listo para el programa» → «Sometido al programa» → «En revisión del programa»."),
  li("**Aprobar** con el código de aprobación del programa. Al aprobar **nace el proyecto de instalación** («Instalación · CASE-…»). También: poner en espera del programa, rechazar con motivo o **Cerrar expediente…** con motivo."),
  nota("El proyecto no se crea a mano: siempre nace al aprobar el expediente."),
  h2("8.3 Permiso municipal"),
  ...fig("acta_permiso"),
  p("En el proyecto, paso **Permiso municipal**: **Registrar el permiso** (ciudad o condado, número, tipo y fecha de radicado). Queda como una tarjeta con sus pasos. Cuando la ciudad responda: **La ciudad lo aprobó** (fechas de aprobación y vencimiento) o **La ciudad lo rechazó** (motivo, y luego volver a radicar). También existe «No requerido» con motivo."),
  p("Al aprobarse el permiso, el expediente pasa solo a «Listo para instalar». Si la empresa activa la opción de instalar con el permiso **solo radicado**, pasa a «Listo para instalar» desde el radicado; el cobro siempre pide el permiso aprobado."),
  h2("8.4 Liberar la orden"),
  ...fig("orden"),
  p("Paso **Orden liberada**: elegir el técnico y la fecha. La orden aparece en la Agenda del técnico y le llega un aviso. En **Materiales de la orden** se anota lo que lleva la instalación (tabla con descripción, cantidad y unidad)."),
  h2("8.5 Confirmar el acta"),
  ...fig("confirmacion"),
  p("Cuando el técnico cierra la instalación llega un aviso a la campana y el acta aparece en **Por revisar › Actas por confirmar**. En el paso **Confirmación de Administración** se revisa lo registrado (checklist, fotos, equipos, firmas) y se toca **Confirmar información técnica**, o **Devolver** con el motivo para que el técnico corrija. Sin esta confirmación no se puede cobrar."),
  h2("8.6 Inspección municipal"),
  ...fig("porrevisar_inspeccion"),
  p("Desde **Por revisar › Inspección municipal**, paso **Inspección** del proyecto: **Agendar inspección** (pide el permiso radicado) y registrar el resultado. Si falla, con observaciones: el expediente vuelve a «Listo para instalar» para el re-trabajo y se reagenda. Para aprobarla hay que subir el permiso firmado por el inspector. Si el programa no exige inspección, del acta confirmada se pasa directo a cobro."),
  h2("8.7 Crear el cobro"),
  ...fig("cobro"),
  p("Desde **Por revisar › Cobros por crear**, paso **Cobro al programa** del proyecto: aparece **solo el programa del expediente**, con la tarifa vigente el día de la instalación. **Crear cobro** pasa el expediente a «En cobro». Una instalación se cobra a un solo programa. El resto (radicar, rechazos, pago) se sigue en Facturación y cobros (sección 10)."),
  h2("8.8 Alertas y campañas"),
  li("**Notificaciones › Alertas:** los días hábiles en «Pendiente de aprobación» antes de avisar (por defecto 3) y los días antes de que venza un permiso. Las alertas salen una vez al día o con **Revisar ahora**, sin repetirse."),
  li("**Campañas:** mensajes por SMS o correo a clientes que dieron permiso de mercadeo, solo de 8 a. m. a 9 p. m. en la hora del cliente; quien responde STOP deja de recibir."),
);

// --- 9 ---------------------------------------------------------------------------
add(
  h1("9. Técnico"),
  p("El técnico trabaja desde el celular y ve **solo las órdenes asignadas a él**."),
  h2("9.1 Agenda"),
  ...fig("agenda"),
  li("**Pendientes:** arriba las **Atrasadas** (en rojo, con los días de atraso), luego **Hoy** y los días siguientes hasta la fecha de «Ver hasta»."),
  li("**Historial:** lo cerrado o cancelado, por fechas y por páginas."),
  li("Tocar el nombre de la orden abre su acta."),
  h2("9.2 El acta de instalación, paso a paso"),
  p("El acta abre el paso en curso y, al completarlo, abre el siguiente. Cada paso muestra su estado: Pendiente, En curso, Completado o Bloqueado."),
  n("**Permiso municipal** y **Orden liberada:** los registra Administración; el técnico los consulta.", "l4"),
  n("**Checklist técnico:** primero las condiciones de la casa (por ejemplo, «se retira furnace a gas»), que agregan o quitan requisitos. Luego cada línea con su foto; las que no aplican se marcan «No aplica» con motivo. Cada confirmación se puede deshacer.", "l4"),
  ...fig("checklist"),
  n("**Equipos instalados:** tipo, marca, modelo, serial, cantidad y unidad o espacio de cada equipo, con **Agregar equipo**. Cuando estén todos, **Guardar equipos instalados**: recién ahí el paso queda completo. Si después se agrega o quita uno, hay que guardar la lista de nuevo.", "l4"),
  ...fig("equipos"),
  n("**Firmas del acta:** al guardar los equipos la pantalla baja sola a este paso. El técnico firma en el recuadro. El cliente firma de una de dos formas: **Enviar enlace por correo** (le llega un enlace que vence en 72 horas; con **Consultar si ya firmó** se ve si ya lo hizo, sin recargar) o, si no tiene correo ni internet, **Que firme aquí, en este celular**: escribe su nombre y firma en el teléfono del técnico. Una firma no se puede repetir. Con las dos firmas se puede **Descargar acta firmada (PDF)**.", "l4"),
  ...fig("firmas"),
  ...fig("firma_cliente"),
  n("**Cierre de la instalación:** muestra lo que falta (líneas del checklist, la lista de equipos guardada). Cuando todo está, **Cerrar instalación**: el acta queda congelada, el expediente pasa a «Instalado» y Administración recibe el aviso.", "l4"),
  ...fig("cierre"),
  nota("Las firmas todavía no son obligatorias para cerrar (decisión pendiente). Si Administración devuelve el acta, llega un aviso con el motivo y el acta se reabre para corregir."),
  h2("9.3 Anexos"),
  p("Debajo del acta: **Evidencias** (todas las fotos del proyecto y la opción de subir fotos adicionales) y **Tareas internas** (pendientes del equipo para esa orden)."),
  h2("9.4 Gastos de campo"),
  ...fig("gastos"),
  p("Menú **Gastos de campo**: categoría, monto, fecha, forma de pago, **foto del recibo** (obligatoria) y, si aplica, la instalación. Queda «por revisar» y Contabilidad recibe el aviso. Mientras está pendiente se puede editar o borrar."),
);

// --- 10 ---------------------------------------------------------------------------
add(
  h1("10. Contabilidad"),
  h2("10.1 Cobros a los programas"),
  ...fig("facturacion"),
  li("**Por revisar › Cobros por crear** muestra las actas listas para cobrar."),
  li("**Facturación y cobros › Cobros de programas** sigue el ciclo completo: Por cobrar, Por radicar, Radicados, Rechazados y Pagados, con la antigüedad."),
  li("En el cobro: marcar los requisitos del checklist, **Radicar ante el programa** y **Ver PDF** de la factura. No deja radicar con requisitos pendientes."),
  li("Si el programa lo rechaza: **Registrar rechazo** con el motivo, **Refacturar** y radicar de nuevo."),
  li("**Registrar pago** con monto, fecha y referencia; si el monto es distinto, muestra la diferencia. El expediente pasa a «Pagado». Solo Contabilidad registra el pago."),
  h2("10.2 Trabajo particular"),
  p("**Facturación y cobros › Cotizaciones:** cotización con versiones → se envía → el cliente acepta → factura en borrador → se emite → pagos parciales hasta saldarla. No mueve ningún expediente."),
  h2("10.3 Gastos de campo"),
  p("Aprobar o rechazar con motivo los gastos de técnicos y vendedores, y **marcar reembolsado** cuando se pague. Nadie aprueba sus propios gastos. Los gastos aprobados con instalación suman a su costo."),
  h2("10.4 Proveedores y pagos"),
  ...fig("proveedores"),
  li("**Proveedores:** datos, condiciones de pago y documentos (W-9, licencia, seguro, contrato) con vencimiento; importación por CSV."),
  li("**Facturas:** número, fechas, líneas (cada línea se puede asignar a una instalación), impuestos, envío y archivo. Queda «por aprobar»."),
  li("**Aprobación:** Gerencia aprueba y programa el pago. Desde 10.000 USD hacen falta dos aprobaciones de personas distintas."),
  li("**Pagos:** se registra el pago hecho por fuera (la plataforma no paga) y se reparte entre facturas aprobadas; admite pagos parciales."),
  li("**Antigüedad** y **exportar CSV** para el contador."),
  h2("10.5 Conciliación y rentabilidad"),
  ...fig("rentabilidad"),
  li("**Conciliación:** importar el extracto del banco en CSV; lo que tiene un solo candidato se concilia solo; lo demás se concilia a mano o se marca como «otro»."),
  li("**Rentabilidad:** por instalación, lo esperado, lo cobrado, los costos (facturas de proveedor asignadas y gastos aprobados) y el margen. La comisión del vendedor todavía no entra."),
);

// --- 11 ---------------------------------------------------------------------------
add(
  h1("11. Gerencia y Administrador"),
  h2("11.1 Gerencia"),
  ...fig("reportes"),
  li("Consulta expedientes, proyectos, facturación, el **Monitor de técnicos** y los **Reportes** (comercial, operación y finanzas, con rango de fechas y exportación a CSV)."),
  li("Aprueba y programa el pago de facturas de proveedor y los ajustes de finanzas (umbral de doble aprobación, días de aviso, tope de gastos)."),
  li("Los datos sensibles (programa de beneficio, foto de identificación, datos bancarios) se le muestran ocultos."),
  h2("11.2 Administrador"),
  ...fig("equipo"),
  li("**Equipo:** invitar usuarios con su rol, editar nombre y rol, activar y desactivar (no se borran)."),
  li("**Roles y permisos:** qué puede hacer cada rol; se pueden crear roles nuevos."),
  li("**Auditoría:** quién hizo qué y cuándo (ingresos, cambios de etapa, firmas, aprobaciones…). Solo lectura."),
  li("Además ve y hace todo lo de los demás roles."),
);

// --- 12 ---------------------------------------------------------------------------
add(
  h1("12. Bodega"),
  p("La bodega lleva el material desde que entra hasta que se usa en una obra. Hay **una bodega** y **una camioneta por técnico**: el material que sobra de una obra larga se puede quedar en la camioneta. La administra **Administración** (el supervisor); el **técnico** pide material y llena el diario; **Contabilidad** y **Gerencia** consultan existencias."),
  h2("12.1 Existencias y catálogo"),
  ...fig("bodega_existencias"),
  li("**Importar catálogo:** se sube el Excel con la hoja «Catálogo». Los artículos nuevos entran con la cantidad de hoy como conteo inicial; los que ya existen se reconocen por su referencia y solo se actualizan sus datos. Subir el mismo archivo dos veces no suma la existencia dos veces. Además de las columnas del cuestionario, reconoce **Código AC Pro**, **Número del fabricante** y **Marca**. Si una fila trae una categoría que no existe, se crea y el resultado de la carga lo avisa."),
  li("**Artículos:** nombre, código AC Pro (o la referencia del proveedor), número del fabricante, marca, categoría, unidad, costo, proveedor, mínimo y si lleva serial. Un artículo no se borra: se desactiva y deja de ofrecerse para pedir."),
  ...fig("bodega_articulo"),
  li("**Categorías:** en **Artículos › Categorías** se agregan, se renombran y se desactivan. Renombrar cambia el nombre en todos sus artículos. Desactivar la saca de las opciones para artículos nuevos; los que ya la tienen la conservan. No se borran, y «Otro» queda siempre activa. Arrancan con las del cuestionario más las del catálogo de AC Pro: termostatos, filtros, ventilación (B-Vent), PVC y drenaje, hierro negro y gas, repuestos, químicos y limpieza, y cintas y sellantes."),
  ...fig("bodega_categorias"),
  li("**Mínimo:** cuando la existencia llega al mínimo, el artículo sale «Bajo mínimo» y quien administra la bodega recibe un aviso."),
  li("**Movimientos:** entradas (compras), traslados de la bodega a una camioneta, devoluciones y ajustes de conteo. El libro no se edita: un error se corrige con el movimiento contrario. El material solo sale de la bodega con una orden de salida."),
  li("**Conteo físico:** se registra lo contado y la diferencia queda como ajuste en el libro."),
  h2("12.2 Listas predefinidas"),
  p("Menú **Listas**: lo que siempre lleva un tipo de trabajo (por ejemplo, la instalación de un aire), con cantidad sugerida, medida o calibre, sección y si es obligatorio. Al aplicarla a una salida o a un presupuesto, cada uno recibe **su propia copia**: cambiar la lista después no cambia lo ya pedido."),
  h2("12.3 Órdenes de salida"),
  ...fig("bodega_salida"),
  n("**Armar:** el técnico (o Administración) toca **Nueva salida**, aplica una lista si quiere, ajusta cantidades y calibres, agrega lo que haga falta con **Agregar renglón** y elige la obra. Queda como borrador.", "l12"),
  n("**Buscar un artículo:** en el renglón se escribe parte del nombre, el código de AC Pro, el número del fabricante o la marca, y se toca el artículo en la lista. Se muestran los primeros 20 que coinciden; si no aparece, escriba más. Lo mismo sirve para buscar la obra.", "l12"),
  n("**Mandar a autorizar:** la orden recibe su número (SAL-2026-0001) y quien autoriza recibe un aviso.", "l12"),
  n("**Autorizar o rechazar:** lo hace otra persona, nunca quien la pidió. Para rechazar hay que escribir el motivo.", "l12"),
  n("**Entregar:** Bodega entrega lo autorizado. Si no hay existencia suficiente, entrega lo que hay y la orden queda con el faltante escrito. Lo entregado se descuenta de la bodega y se carga como material de la obra.", "l12"),
  h2("12.4 Presupuesto de la obra y compras sugeridas"),
  li("En la ficha del proyecto, **Costo del trabajo**: el supervisor arma el presupuesto (a mano, desde una lista o desde una plantilla de costo) y lo aprueba. Al final se compara lo presupuestado con lo real: lo que salió de bodega, las compras cargadas a la obra y los gastos de campo."),
  li("**Compras sugeridas** suma el material de los presupuestos aprobados de las obras abiertas y le resta lo que hay en bodega: lo que falta es lo que conviene comprar por adelantado."),
  h2("12.5 Diario de obra"),
  ...fig("bodega_diario"),
  p("Para trabajos de varios días: en la ficha del proyecto, **Registrar la jornada** guarda un día con el técnico de ese día, cuadrilla, horas, qué se hizo, hasta dónde se avanzó, qué material faltó, qué llevar al día siguiente y novedades. El material del día se busca en el catálogo igual que en la salida: si se elige de qué camioneta salió, se descuenta de ella; si se deja sin ubicación, solo queda anotado. Los gastos de campo aprobados de ese día aparecen solos en la jornada."),
);

// --- 13 ---------------------------------------------------------------------------
add(
  h1("13. Guía de pruebas sugerida"),
  h2("Prueba 1 — Un expediente de punta a punta"),
  n("Vendedor: tocar una puerta con el código postal de una zona de cobro, llenar el formulario con fotos, firmar y enviar a revisión.", "l5"),
  n("Administración: en Por revisar › Documentos, aceptar los documentos y aprobar con un código. Verificar que nació el proyecto.", "l5"),
  n("Administración: registrar el permiso y aprobarlo; asignar técnico y fecha.", "l5"),
  n("Técnico (en el celular): desde la Agenda, llenar el checklist con fotos, agregar y guardar los equipos, firmar el técnico y el cliente (probar las dos formas) y cerrar.", "l5"),
  n("Administración: confirmar el acta desde Por revisar › Actas por confirmar; agendar y aprobar la inspección; crear el cobro desde Cobros por crear.", "l5"),
  n("Contabilidad: radicar, registrar un rechazo y refacturar, radicar otra vez y registrar el pago. Administración: cerrar el expediente y revisar su Historial.", "l5"),
  h2("Prueba 2 — Lo que no se debe poder hacer"),
  li("El vendedor no ve expedientes de otros ni puede aprobar los suyos."),
  li("El técnico solo ve sus órdenes; no ve expedientes ni la bandeja Por revisar; no firma ni descarga el acta de otra orden."),
  li("No se puede cerrar la instalación sin las fotos obligatorias ni sin guardar los equipos."),
  li("No se puede crear el cobro sin el acta confirmada, ni a un programa distinto al del expediente."),
  li("Gerencia no puede guardar cambios fuera de sus aprobaciones."),
  h2("Prueba 3 — Celular y señal"),
  li("Recorrer el acta en un teléfono con una mano: menús, tablas como tarjetas, cámara y firma."),
  li("Quitar la señal a mitad de un paso: debe avisar y no perder lo escrito."),
);

// --- 14 ---------------------------------------------------------------------------
add(
  h1("14. Cómo reportar un problema"),
  li("Usuario y rol con el que pasó."),
  li("Qué esperaba y qué pasó, y si bloquea el trabajo o es solo visual."),
  li("Los pasos exactos para repetirlo: pantalla, expediente o proyecto y datos usados."),
  li("Captura o video corto, navegador, dispositivo y fecha y hora."),
);

// --- 15 ---------------------------------------------------------------------------
add(
  h1("15. Lo que todavía no hace"),
  li("Órdenes de compra a proveedores y precios por proveedor. En bodega, todavía no: la lista como checklist del técnico al cargar la camioneta y el calendario para planear cada día de una obra (en desarrollo)."),
  li("Pagar desde la plataforma (solo registra pagos hechos por fuera), sincronizar con QuickBooks y los 1099."),
  li("Llenar automáticamente los formularios municipales y sincronizar con Microsoft Forms."),
  li("Trabajar sin conexión; la comisión del vendedor en la rentabilidad."),
  li("SMS reales hasta activar el proveedor (hoy en modo de prueba). Las fotos y documentos se guardan en el servidor de pruebas."),
);

const doc = new Document({
  features: { updateFields: true },
  styles: { default: { document: { run: { font: FONT, size: 21 } } } },
  numbering: { config: [
    { reference: "v", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 260 } } } },
    ] },
    ...LISTAS.map((ref) => ({ reference: ref, levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 320 } } } },
    ] })),
  ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1300, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: "Manual de usuario · PAP.CRM Delta HVAC · página ", font: FONT, size: 16, color: GRIS }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: GRIS }),
    ] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const salida = process.env.SALIDA || path.join(__dirname, "..", "Manual_Usuario_CRM_Delta_HVAC.docx");
  fs.writeFileSync(salida, buf);
  console.log("ok", salida, figura, "figuras");
});
