# PAP Ventas — Propuesta UI/UX V1

## Objetivo
Rediseñar visualmente la aplicación PAP CRM / PAP Ventas existente siguiendo la propuesta visual 1 aprobada: interfaz limpia, fondo claro, sidebar oscuro en escritorio, acentos rojos, tarjetas de bordes suaves, jerarquía tipográfica clara y excelente usabilidad móvil. Esta especificación se entrega a un modelo de IA implementador.

## Referencia y alcance
El sistema actual fue documentado mediante un PDF de 56 capturas de pantalla. Mantener TODOS los módulos, vistas, subpestañas, campos, permisos, estados y flujos existentes. Las capturas son la fuente de verdad funcional; esta propuesta define la capa visual. No confundir ejemplos de datos del prototipo con datos reales.

## Principios obligatorios
1. No reescribir ni romper lógica, rutas, APIs, validaciones, permisos, autenticación ni contratos de datos.
2. Respetar la arquitectura y componentes actuales; crear componentes reutilizables donde convenga.
3. Conservar el comportamiento móvil existente donde las tablas se convierten en tarjetas, mejorando únicamente su presentación.
4. No esconder información crítica al transformar tablas en tarjetas: mostrar 2–4 campos clave y detalles secundarios expandibles.
5. Estados completos: cargando (skeleton), vacío con CTA contextual, error recuperable, éxito, deshabilitado, confirmación de acciones destructivas.
6. No introducir dependencias pesadas sin justificación; conservar librería de iconos y gráficas existente si es adecuada.
7. Diseñar primero los patrones compartidos, después migrar módulo por módulo; evitar cambios masivos sin pruebas.

## Identidad visual
- Marca: PAP Ventas, conservando logo existente cuando esté disponible.
- Colores: rojo principal #DC182C; rojo hover #B91325; sidebar #151719; texto principal #17202B; texto secundario #697586; fondo general #F6F7F9; tarjetas #FFFFFF; borde #E7EAF0; éxito #16845B; advertencia #C87A12; información #2563EB.
- Tipografía: Inter o tipografía sans-serif ya instalada. Títulos 24–28 px escritorio / 21–24 px móvil; texto 14–16 px; etiquetas 12–13 px; cifras 24–30 px.
- Espaciado: sistema 4/8/12/16/24/32; tarjetas con radio 12–16 px; botones 10–12 px; sombras muy sutiles.
- Evitar fondos excesivamente decorados, gradientes intensos, tipografías condensadas y exceso de líneas divisorias.
- Estados: chips discretos semánticos, sin usar rojo para todos los estados.

## Layout escritorio
- Sidebar fijo o colapsable de 232–256 px, fondo oscuro, agrupado por áreas existentes: Gestión de campo, Operación comercial, Operación de campo, Bodega, Finanzas, Configuración/Administración.
- Topbar clara de 64–72 px con búsqueda global, notificaciones y perfil.
- Contenido centrado en ancho máximo de 1440 px, padding de 24–32 px; en pantallas anchas usar el espacio disponible, evitando columnas demasiado estrechas.
- Encabezado de página: título, descripción breve, acciones primarias a la derecha.
- Filtros en una franja compacta y plegable cuando sean numerosos.
- Tablas densas pero legibles, encabezado persistente si aplica, acciones agrupadas y paginación visible.

## Layout móvil (prioridad alta)
- Breakpoints orientativos: <= 767 px móvil, 768–1023 tablet, >=1024 escritorio; ajustarlos al sistema actual.
- Sin sidebar permanente. Topbar con menú, título contextual y acciones esenciales; menú completo en drawer.
- Navegación inferior opcional de máximo 5 destinos: Inicio, Clientes, Expedientes, Agenda y Más. El apartado Más abre el menú de todos los módulos. No duplicar rutas ni romper navegación existente.
- Margen lateral 16 px; tarjetas a ancho completo; targets táctiles de al menos 44 px; respetar safe areas.
- KPI en grid de dos columnas (o una si el ancho es insuficiente), sin recortar cantidades monetarias.
- Gráficas con altura 220–280 px, etiquetas abreviadas, leyendas reubicadas y tooltips táctiles; no forzar gráficos complejos horizontalmente.
- Tablas a tarjetas: título + estado arriba; campos más importantes en 2 columnas o filas; acciones al final; detalles adicionales mediante expandir; filtros en bottom sheet o panel plegable; búsqueda siempre accesible.
- Formularios en una columna, campos y botones a ancho completo, teclado apropiado según tipo, validación bajo el campo y botón Guardar accesible sin tapar contenido.
- Modales complejos se convierten en pantallas o sheets de altura apropiada; confirmaciones cortas sí pueden ser diálogos.
- Tablas de cifras financieras: tarjetas con totales destacados y desglose expandible; conservar precisión, moneda y posibilidad de copiar/exportar.

## Patrones compartidos
**PageHeader**: título, subtítulo, breadcrumbs solo en escritorio, acción primaria.
**KpiCard**: icono opcional, etiqueta, valor, variación contextual y enlace a detalle.
**FilterBar**: búsqueda, selectores, rango de fechas, limpiar, panel móvil.
**DataTable / MobileRecordCard**: misma fuente de datos, diferentes presentaciones responsivas, sin duplicar lógica.
**StatusBadge**: semántica uniforme para pendiente, activo, aprobado, rechazado, vencido, cerrado, en progreso.
**DetailView**: resumen superior, pestañas desplazables, historial/timeline, documentos y acciones.
**FormSection**: grupos con encabezado, campos, ayudas y errores claros.
**EmptyState**: explicación breve y acción relevante si el usuario tiene permisos.
**ConfirmDialog**: impacto de acción, confirmar/cancelar; nunca depender de alertas nativas para operaciones complejas.

## Prototipos funcionales por módulo
Cada renglón define la estructura visual esperada en escritorio y móvil. Las funcionalidades precisas deben leerse del código y de las capturas actuales.

| Módulo / pantalla | Escritorio | Móvil |
|---|---|---|
| Login / recuperación | Pantalla dividida con fotografía arquitectónica sobria y panel de acceso; marca, correo, contraseña, recuperar y SSO si existe | Fondo sobrio, tarjeta centrada o alineada abajo, inputs y botón ancho completo; sin foto que dificulte lectura |
| Inicio / Dashboard | 4 KPI, actividad reciente, acciones rápidas, tareas vencidas; gráficos solo si hay datos reales | KPI 2x2, acciones rápidas verticales, actividad y tareas en tarjetas; sin tabla horizontal |
| Clientes / alta / detalle | Buscador, filtros, tabla, ficha de cliente y CTA nuevo cliente | Buscador fijo en zona superior, clientes en tarjetas con estado, contacto y acciones; formulario de una columna |
| Mi día / tocar una puerta | Formulario guiado por secciones, contexto de ubicación/visita y resultado | Flujo por pasos o secciones apiladas, acciones de llamada/ubicación si existen, CTA inferior |
| Campañas: campañas / contactos propios / resultados / baja | Pestañas, resumen, listas y formulario de campaña | Chips desplazables, tarjetas de campaña con métricas, formulario apilado |
| Expedientes / tablero por etapa / nuevo expediente | Kanban en escritorio con columnas, contadores y tarjetas compactas | Selector de etapa en chips, una lista vertical de tarjetas por etapa; evitar kanban horizontal infinito |
| Por revisar | Pestañas de documentos, asignaciones, inspecciones y cobros; lista priorizada | Tarjetas con urgencia, vencimiento, estado y CTA revisar; pestañas desplazables |
| Proyectos / detalle / ejecución | Listado, filtros, progreso, etapas, técnicos, documentación y costos según vistas existentes | Tarjetas de proyecto con avance, responsable, estado y próximo hito; detalle por pestañas |
| Monitor de técnicos | Filtros, indicadores, tabla de personal y estado | Tarjetas por técnico con estado, actividad y métricas esenciales |
| Agenda de instalaciones | Calendario/lista, selector de fechas y técnicos | Vista agenda por día como predeterminada, calendario compacto opcional, tarjetas de visita |
| Checklists de instalación | Catálogo y editor de checklist con grupos y preguntas | Acordeones por grupo, progreso visible, controles grandes y guardado claro |
| Permisos e inspecciones | Pestañas, filtros y tabla de trámites con vencimientos | Tarjetas con proyecto, tipo, estado y fecha; avisos de vencimiento |
| Existencias de bodega | KPI de inventario, filtros, tabla de existencias y alertas | KPI compactos, búsqueda, tarjetas por artículo con cantidad y estado de stock |
| Artículos de bodega | Catálogo con filtros y datos de artículo | Tarjetas con nombre, categoría, unidad, costo y acciones |
| Listas predefinidas | Listado, filtros, editor de lista y materiales | Tarjetas de listas, detalle editable en secciones |
| Salidas de bodega | Pestañas solicitudes/historial, tabla y nueva salida | Tarjetas de salida con estado, solicitante, fecha y cantidad; formulario por secciones |
| Movimientos de bodega | Filtros por fecha/tipo, historial tabular | Timeline o tarjetas cronológicas con entradas/salidas y saldo cuando aplique |
| Compras sugeridas | Recomendaciones y tabla con acciones | Tarjetas de sugerencia con artículo, faltante, prioridad y CTA |
| Plantillas de costo | Catálogo de plantillas y editor | Tarjetas por plantilla y editor apilado |
| Facturación y cobros: cobros de programa / facturas / cotizaciones / programas | Resumen financiero, pestañas, tablas, detalle de pagos y documentos | Totales en tarjetas, tabs desplazables, cada factura/cotización como tarjeta con monto, vencimiento y estado; detalles expandibles |
| Gastos de campo | Registro, pendientes, histórico, filtros y comprobantes | CTA registrar gasto, tarjetas con monto, categoría, fecha, aprobaciones y adjuntos |
| Proveedores y pagos: facturas / pagos / proveedores / anticipos / ajustes | Pestañas, KPI, tablas, acciones y conciliación | Tarjetas con proveedor, monto, estado y fecha; acciones secundarias en menú |
| Conciliación y rentabilidad | KPI, resumen por proyecto, comparativos y detalles de costos | KPI apilados, rentabilidad y alertas claras; desglose expandible por proyecto |
| Reportes: comercial / operación / finanzas | Filtros globales, KPI, gráficas, tablas y exportación | KPI 2 columnas, gráficas de una en una, filtros plegables, resumen antes del detalle, exportación accesible |
| Configuración de programas / catálogo de campos | Selector de programa, configuración por secciones, editor de campos | Selector superior y acordeones por sección, campos editables apilados |
| Usuarios / roles y permisos | Tabla de usuarios, filtros, ficha; matriz de permisos por rol | Tarjetas de usuario, detalle; permisos agrupados en acordeones con checks grandes |
| Auditoría | Tabla filtrable por fecha, usuario y acción | Tarjetas cronológicas con actor, evento, fecha y detalles expandibles |
| Notificaciones | Pestañas y lista de avisos con prioridad | Feed de notificaciones con estados leída/no leída y acciones claras |

## Comportamientos críticos
- No reemplazar datos reales por métricas inventadas. Si no hay datos, presentar estado vacío útil.
- No asumir que todos los roles pueden crear, editar, eliminar, aprobar o exportar.
- No ocultar acciones críticas detrás de hover; en móvil deben poder descubrirse con toque.
- En kanban móvil preservar el conteo por etapa y la transición de estado mediante interacción explícita.
- En módulos financieros mantener valores completos y etiquetas; nunca truncar montos.
- En checklists largos guardar progreso según soporte real de backend; no prometer autoguardado si no existe.
- Mantener accesibilidad: contraste, foco, labels, navegación por teclado, mensajes de error y reduced motion.

## Orden de implementación recomendado
Fase 1: tokens visuales, layout desktop/mobile, sidebar/drawer, topbar, navegación, componentes base.
Fase 2: login, dashboard, clientes, mi día, campañas, expedientes y por revisar.
Fase 3: proyectos, monitor, agenda, checklists, permisos e inspecciones.
Fase 4: bodega completa.
Fase 5: finanzas, conciliación, reportes.
Fase 6: configuración, usuarios, permisos, auditoría, notificaciones y QA final.

## Criterios de aceptación
- Se ven y funcionan las mismas rutas y operaciones que antes del rediseño.
- Vista probada a 360, 390, 430, 768, 1024 y 1440 px.
- Ninguna tabla importante exige desplazamiento horizontal en móvil; se usa tarjeta o patrón específico justificado.
- Los formularios no quedan cortados por teclado ni por barras inferiores.
- Todas las pantallas soportan loading, vacío y error.
- Contraste y foco visibles; no hay acciones inaccesibles sin hover.
- No aparecen datos de demostración en producción.
- Cada fase se revisa visualmente y se prueba antes de pasar a la siguiente.

## PROMPT MAESTRO PARA ENTREGAR AL MODELO DE IA
Actúa como diseñador UI/UX senior y desarrollador frontend experto en React. Vas a aplicar el documento PAP_Ventas_Propuesta_UIUX_V1.md a mi repositorio real de PAP Ventas. Usa las capturas actuales como inventario de pantallas y flujos; NO rediseñes la lógica del producto. Primero inspecciona el proyecto, identifica stack, rutas, componentes compartidos, estilos y puntos de responsive ya implementados. Propón un mapa de componentes y un plan de migración por fases. Luego implementa la primera fase y muéstrame capturas o previews de escritorio (1440 px) y móvil (390 px). No cambies APIs, endpoints, nombres de propiedades, validaciones, permisos ni lógica de negocio. Conserva la conversión actual de tablas a tarjetas móviles y mejora su diseño. Antes de modificar pantallas complejas, verifica todos sus estados y pestañas. Usa componentes reutilizables, estados vacíos y de carga, accesibilidad y responsive real. No inventes información ni ocultes funcionalidades. Al finalizar cada fase, informa archivos modificados, pruebas realizadas, pendientes y solicita validación visual antes de continuar.



