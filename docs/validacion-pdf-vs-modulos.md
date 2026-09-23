# Validación: PDF del cliente vs módulos levantados

**Fuente canónica:** `Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf` (10 páginas, §1–§7).
**Contra:** `requerimientos-formularios-programas-delta-hvac.md` (módulos 1–8, §18).
**Fecha:** 15 de septiembre de 2026. **Autor:** José Javier Miranda.

Leyenda de cobertura: ✅ cubierto por un módulo · 🟡 parcial (el módulo lo toca
pero no cumple lo que pide el PDF) · ❌ ningún módulo lo cubre · ⚙️ ya existe algo
en el código (fases 1–5) que sirve de base.

---

## 1. Resumen ejecutivo

El `.md` de módulos está **muy centrado en el formulario de aplicación y el
expediente** (Cadena A) y en revisión/instalación/invoice (Cadena B). Cubre
bien §2.5–2.6, §3.1 (recepción), §3.3, §5.2–5.5 y §6 (filas de técnicos).

Lo que **no cubre ningún módulo** y el PDF pide de forma explícita:

| # | Área del PDF | Qué falta | Tamaño |
|---|---|---|---|
| G1 | §2.1, §2 app móvil, §7 etapa 1 | **Parques de casas móviles, zonas asignadas y registro de visitas** (incluidas las que no producen aplicación) | Resuelto el 17 sep (D5, D6 en `decisiones.md`): zonas dentro del programa (módulo 1); cada puerta es un `Case` con submissions de visita (módulo 2) |
| G2 | §2.4, §6 filas Ventas | **Auditoría técnica preliminar del vendedor**: amperaje del panel, climatización existente, nº de cuartos, cocina de inducción, water heater, diagnóstico de viabilidad. **No están en el catálogo canónico de campos (§2.5 del .md)** aunque el PDF los marca obligatorios | Campos + reglas en Cadena A |
| G3 | §2.3, §2 app móvil | **Escaneo/foto del documento de identidad (ID)** — no aparece como requisito documental en A.1/A.2 ni en §4.5/§5.5 | Requisito documental en Cadena A |
| G4 | §2.2 | **Verificación de ingresos por declaración de impuestos (taxes)** como vía alterna de elegibilidad — sin campo ni documento | Campo + documento en Cadena A |
| G5 | §3.1, §3 funcionalidades | **Gestor documental con conversión/compresión** a PDF/JPG/PNG y **paquete consolidado** por cliente para radicar en portales | Módulo nuevo o extensión del 3 |
| G6 | §3.2, §3 funcionalidades | **Permisos municipales**: ficha técnica de la mobile home, **autocompletado de formularios oficiales** de la ciudad, radicación y seguimiento | Módulo nuevo (el 5 solo "registra" el permiso) |
| G7 | §3.1, §7 estados | **Contador de días en "Pendiente Aprobación"** (referencia 2–3 días hábiles) y alerta al exceder | Extensión de 4 + 7 |
| G8 | §3 funcionalidades | **Microsoft Forms**: "incrustación o sincronización" | Decisión del cliente |
| G9 | §4.1, §4 funcionalidades | **Gastos de campo** (gasolina, viáticos, materiales) con foto del recibo, ligados al proyecto | Módulo nuevo |
| G10 | §4.4, §4 funcionalidades | **Proveedores y cuentas por pagar (AP)**: registro, facturas de proveedor, vencimientos, programación de pagos | Módulo nuevo |
| G11 | §4.5, §4 funcionalidades, §7 | **Conciliación bancaria, P&L por proyecto, reportes gerenciales** (ingresos, gastos, flujo de caja, tiempos de aprobación, rechazos) y **exportación contable** | Módulo nuevo |
| G12 | §4.3 | **AR**: estado "Rechazado / con errores", flujo de **corrección y refacturación**, ciclo diario de radicación, alertas por tiempo excedido | Extensión del 6 |
| G13 | §5.1 | **Enrutamiento** (ruta/mapa del día) y **preparación de materiales** por orden | Extensión del 5 |
| G14 | §5.5, §3.4 | **Equipos instalados como dato estructurado** (marca, modelo, serial, cantidad) — hoy solo como foto de etiqueta; el cobro al programa lo necesita | Extensión del 5 y 6 |
| G15 | §3.5 | **Inspección**: agendamiento con la ciudad, resultado, y **qué pasa si falla** (re-trabajo, re-inspección) | Extensión del 5 |
| G16 | §3.4, §6 fila Admin | **Expediente de cobro** como paquete con checklist obligatorio (aprobación + código + T&C firmados + evidencias + invoice) y fecha de radicación | Extensión del 6 |
| G17 | §3 Dashboard, §7 | **Un solo estado visible del expediente** (9 estados del PDF) — hoy hay tres juegos distintos: pipeline de Opportunity (código), estados de Application (.md §10) y estados operativos (.md §11) | Decisión interna + cliente |
| G18 | Transversal (§1 roles, §13 del .md) | **Usuarios, roles y permisos administrables.** El PDF no lo menciona pero define 4 áreas + gerencia; el `.md` §18 no le asigna módulo. ⚙️ Existe "Equipo" (invitar con roles, activar/desactivar, límite de 30) y una matriz rol→permiso **fija en código** con 7 roles genéricos de CRM (`commercial_manager`, `project_manager`, `supervisor`, `finance_user`, `field_technician`, `read_only`, `organization_admin`) que **no coinciden con Vendedor / Administración / Técnico / Contabilidad / Gerencia**. Falta: cambiar roles a un usuario existente, editar la matriz desde la UI (el permiso `roles.manage` existe pero no hay endpoint ni pantalla), perfil/cambio de contraseña, asignación vendedor↔zona (G1), jerarquía líder↔vendedor. En `ventas_pap` esto fue la base de todo (matriz Group→Permission administrable) | **Módulo 0 — José Javier** (agregado al `.md` §18.2 el 17 sep 2026) |

Conclusión: **la Cadena A y la Cadena B cubren el "core" (aplicación →
revisión → instalación → invoice), pero el PDF describe además toda un área
de Contabilidad (§4) y de Administración operativa (§3.2, §3.5, gestor
documental, permisos) que no tiene dueño ni módulo.** Y dentro de la propia
Cadena A faltan los campos técnicos que el PDF marca obligatorios (G2–G4).

---

## 2. Matriz de cobertura sección por sección

### §2 Vendedores

| Requisito del PDF | Módulo | Estado | Observación |
|---|---|---|---|
| 2.1 Autorización de acceso con el administrador del parque | — | ❌ | No existe entidad "parque"/"comunidad" ni administrador del parque ni registro de autorización. Hoy el código importa CSV "por parque" pero no lo modela |
| 2.1 Recorrido por zonas asignadas (CA/AZ/NV) | — | ❌ | No hay zonas ni asignación vendedor↔zona |
| 2.2 Indagación de beneficios (Medi-Cal, SNAP, WIC, CalFresh) | 1, 2 | ✅ | `eligibility.programs` multi-select con catálogos AZ y TECH |
| 2.2 Verificación de ingresos mediante taxes | — | ❌ | Sin campo de ingresos ni requisito "declaración de impuestos" |
| 2.2 Filtro de compatibilidad con programas (Tech Clean, Arizona, Edison, Go Zero…) | 1 | 🟡 | El .md pide "reglas de elegibilidad" por programa pero no define el motor; el PDF pide "filtro lógico interactivo" que determine compatibilidad. Edison y Go Zero no están definidos como programas |
| 2.3 Nombre, teléfono, dirección, nº de unidad | 1, 2 | ✅ | En catálogo (`customer.*`, `home.unit_number`) |
| 2.3 Verificación física del ID + escaneo con cámara | — | ❌ | No hay requisito documental "ID" en A.1/A.2/§4.5/§5.5 |
| 2.4 Amperaje del panel (obligatorio) | — | ❌ | No está en el catálogo §2.5. Solo existe "foto del panel" como documento |
| 2.4 Climatización previa (Ninguno / mini-split / central) | — | ❌ | No está en el catálogo. Solo "fotos del HVAC existente" |
| 2.4 Número de cuartos (obligatorio) | 1 | ✅ | `home.bedrooms` |
| 2.4 Cocina de inducción Sí/No | — | ❌ | No está. §4.5 tiene triturador/ventilador/extractor/lavaplatos (de otro insumo) pero no inducción |
| 2.4 Water heater Sí/No o tipo/capacidad | — | ❌ | No está |
| 2.4 Diagnóstico de viabilidad eléctrica (adecuada / requiere adecuación) | — | ❌ | No está. `internal.result` es preaprobado/pendiente/no califica, que es elegibilidad, no viabilidad técnica |
| 2.5 Aviso de privacidad + consentimiento firmado | 2 | ✅ | §3.5 del .md. Texto exacto pendiente (§15) |
| 2.6 Estructuración del expediente y envío a administración | 2, 4 | ✅ | Estados Borrador → Pendiente de revisión |
| App: autenticación por vendedor | — | ⚙️✅ | Ya existe (fase 1) |
| App: asignación de zonas + registro geolocalizado de visitas | 2 | 🟡 | .md §9.11 registra "ubicación de la visita" **solo cuando hay aplicación**. El PDF (§7 etapa 1) pide registrar la visita como resultado en sí ("cliente identificado y zona/visita registrada"), incluidas visitas sin venta |
| App: cuestionario dinámico de elegibilidad | 1, 2 | 🟡 | Campos condicionales sí; lógica que concluya "califica para X" no |
| App: captura + escaneo de ID | — | ❌ | Ver 2.3 |
| App: checklist de auditoría técnica y eléctrica | — | ❌ | Ver 2.4 |
| App: adjuntos técnicos (panel, interior) | 3 | ✅ | Categorías de evidencia |
| App: firma digital + T&C | 2 | ✅ | ⚙️ Ya hay firma de cliente por link y presencial |
| App: sincronización cloud inmediata | — | 🟡 | El frontend es PWA. **No se ha definido si el vendedor debe poder trabajar sin señal** en el parque y sincronizar después |

### §3 Administración

| Requisito del PDF | Módulo | Estado | Observación |
|---|---|---|---|
| 3.1 Recepción del expediente (datos, ID, T&C, auditoría eléctrica) | 4 | ✅ | Bandeja administrativa |
| 3.1 Migración/centralización de datos | 4 | ✅ | Implícito |
| 3.1 Preparación documental: conversión/organización/optimización a PDF/JPG/PNG | — | ❌ | Módulo 3 tiene vista previa y reemplazo, no conversión ni compresión ni "paquete" |
| 3.1 Radicación en portales oficiales | 4 | ✅ | Manual: estado "Sometida" (confirmado sin integración API) |
| 3.1 Seguimiento de tiempos 2–3 días hábiles | — | ❌ | Sin contador de días ni alerta |
| 3.2 Ficha técnica de la mobile home | — | ❌ | Solo título/decal como documentos. Sin marca, modelo, año, serial/VIN, dimensiones |
| 3.2 Generación/llenado de formularios oficiales de permiso | — | ❌ | "Autocompletado de formas estándar" no está en ningún módulo |
| 3.2 Radicación y seguimiento del permiso con la ciudad | 5 | 🟡 | El .md dice "Registrar permiso municipal" (nº, fecha). Sin seguimiento, vencimiento, ni ciudad/condado |
| 3.3 Liberación de ruta tras aprobación + permiso | 5 | ✅ | "Liberar orden de instalación" |
| 3.4 Recopilación de evidencias post-instalación | 5 | ✅ | Checklist técnico + evidencias |
| 3.4 Consolidación del expediente de pago | 6 | 🟡 | Invoice sí; el "paquete" (aprobación + código + T&C + evidencias + invoice) con checklist obligatorio no está definido |
| 3.4 Radicación de cobro en plataforma del programa | 6 | 🟡 | Sin "fecha de radicación" ni estado "radicado" explícito |
| 3.5 Agendamiento de inspección con ciudad/programa | 5 | 🟡 | "Permisos e inspección" sin detalle: fecha, inspector, resultado, reintento |
| 3.5 Cierre del ciclo con resultado de inspección | 5 | 🟡 | "Registrar resultado de inspección" sí; qué ocurre si falla, no |
| Dashboard Kanban con los 9 estados | 4, 5 | 🟡 | Ver G17: tres juegos de estados distintos; ⚙️ ya hay un kanban de Opportunity con otros nombres |
| Automatización de permisos | — | ❌ | Ver 3.2 |
| Gestor documental + conversor | — | ❌ | Ver 3.1 |
| Microsoft Forms integrados | — | ❌ | No mencionado en el .md |
| Facturación y cierre de cobros (checklist, monto, fecha radicación, estado) | 6 | 🟡 | Falta checklist y fecha de radicación |
| Centro de notificaciones: aprobaciones, vencimiento de permisos, inspecciones | 7 | 🟡 | Módulo 7 existe; "vencimiento de permiso" requiere fecha de vencimiento del permiso, que no está modelada |

### §4 Contabilidad y facturación

| Requisito del PDF | Módulo | Estado | Observación |
|---|---|---|---|
| 4.1 Viáticos, gasolina, materiales, inventario, asignación por proyecto | — | ❌ | Ningún módulo |
| 4.2 Facturas por programa (códigos de servicio, formatos) | 6 | ✅ | Plantillas GoZero y pedestal |
| 4.2 Facturación a proveedores y clientes particulares | 6 | 🟡 | Módulo 6 está pensado por programa; "particular" no se menciona |
| 4.3 Ciclo diario de cobro / radicación masiva | — | ❌ | |
| 4.3 Tracking Pagado / Pendiente / Rechazado-con errores | 6 | 🟡 | ⚙️ Código tiene Pendiente/Enviada/Pagada/Vencida. Falta **Rechazado** |
| 4.3 Corrección y refacturación rápida | — | ❌ | |
| 4.4 Proveedores, AP, vencimientos, programación de pagos | — | ❌ | Ningún módulo |
| 4.5 Conciliación bancaria | — | ❌ | |
| 4.5 Margen por proyecto (P&L) | — | ❌ | Requiere G9 (gastos) para existir |
| 4.5 Reportes gerenciales (ingresos, gastos, flujo de caja) | — | ❌ | ⚙️ Hay un `GET /finance/dashboard` básico (facturado/pagado/pendiente/vencido) |
| App: gastos de campo con foto del recibo | — | ❌ | |
| Generador de plantillas dinámicas con autocompletado | 6 | ✅ | |
| AR Dashboard con alertas por tiempo | — | 🟡 | ⚙️ Dashboard básico; sin alertas por tiempo ni corrección |
| Centro de AP y proveedores | — | ❌ | |
| P&L por proyecto | — | ❌ | |
| Exportación/sincronización contable | — | ❌ | ⚙️ Solo CSV de invoices |

### §5 Técnicos e instaladores

| Requisito del PDF | Módulo | Estado | Observación |
|---|---|---|---|
| 5.1 Calendario con fecha, dirección, cliente, teléfono, notas | 5 | ✅ | "Asignación y agenda del técnico". ⚙️ Ya hay monitor GTR de técnicos |
| 5.1 Preparación de materiales | — | ❌ | Sin lista de materiales por orden ni inventario |
| 5.2 Distribución espacial (cuartos, cocina, living) | 5 | ✅ | .md §8.1 |
| 5.2 Fachada obligatoria | 5 | ✅ | |
| 5.3 Equipos existentes + placas | 5 | ✅ | |
| 5.3 Protocolo de gas (antes / desconectada) | 5 | ✅ | .md §8.3 |
| 5.4 Conductos y cableado; panel si adecuación | 5 | ✅ | |
| 5.5 Etiquetas int/ext con modelo y serial visibles | 5 | ✅ | Como foto. **Como dato** (modelo/serial escritos) no |
| 5.5 Galería libre | 3, 5 | ✅ | |
| 5.5 Bloqueo de cierre | 5 | ✅ | |
| Dispatch: agenda diaria/semanal + **enrutamiento** | 5 | 🟡 | Agenda sí; ruta/mapa no |
| Smart gatekeeping condicional | 5 | ✅ | |
| N/A con motivo | 5 | ✅ | |
| Subcategorías fotográficas | 3 | ✅ | .md §7.1 es superconjunto |

### §6 Matriz de validación

| Fila | Estado |
|---|---|
| Ventas: amperaje, climatización, inducción, water heater | ❌ ver G2 |
| Ventas: nº de cuartos | ✅ |
| Técnicos: todas las filas | ✅ |
| Administración: no enviar a cobro sin checklist | 🟡 ver G16 |
| Regla general: nada obligatorio incompleto avanza de etapa | 🟡 Cubierta en aplicación (2) y cierre técnico (5); no en permiso, inspección ni cobro |

### §7 Flujo integral y resultado esperado

| Etapa / resultado | Estado |
|---|---|
| Etapas 1–2 (prospecto, elegibilidad) | 🟡 visita/zona ❌, elegibilidad ✅ |
| Etapas 3–5 (validación técnica, expediente, aprobación) | 🟡 técnica ❌, expediente ✅, aprobación ✅ |
| Etapa 6 (permiso) | 🟡 |
| Etapas 7–8 (dispatch, instalación) | ✅ |
| Etapa 9 (inspección) | 🟡 |
| Etapa 10 (cobro) | 🟡 |
| Etapas 11–12 (pago conciliado, rentabilidad) | ❌ |
| "Medir costos, ingresos, tiempos de aprobación, rechazos y rentabilidad" | ❌ sin módulo de reportes/KPIs |

---

## 3. Preguntas para el cliente (Mateo / Delta HVAC)

Agrupadas por área. Cada una dice por qué importa para no preguntar en el aire.

### A. Alcance: ¿qué entra en esta entrega?

1. **Contabilidad (§4 completo)**: gastos de campo, proveedores/AP, conciliación, P&L, reportes. ¿Entra en esta fase o es una fase posterior? Hoy no tiene módulo ni responsable. Sin esto, la etapa 12 del flujo (rentabilidad) no existe.
2. **Permisos municipales (§3.2)**: ¿el sistema debe **generar/llenar** los formularios de la ciudad o solo **registrar** que se tramitó un permiso (número, fecha, estado)? Si genera: ¿qué ciudades/condados, qué formularios exactos (PDF rellenables) y qué datos de la mobile home piden?
3. **Gestor documental (§3.1)**: ¿necesitan que el CRM **convierta/comprima** archivos (foto → PDF, tamaño máximo por portal) y arme un **paquete descargable** por cliente para subir al portal del programa? ¿Qué formatos y límites exige cada portal?
4. **Microsoft Forms**: ¿siguen usándolo hoy? ¿El CRM lo **reemplaza** o debe **incrustar/sincronizar** formularios existentes? (Recomendación: reemplazar; sincronizar duplica fuente de verdad.)
5. **Enrutamiento (§5.1)**: ¿basta una agenda diaria por técnico o quieren mapa con orden de visitas optimizado? ¿Integración con Google Maps/Waze?
6. **Nevada**: aparece en el alcance geográfico pero no hay ningún programa de NV definido. ¿Cuál es y tienen su formulario?
7. **Programas adicionales**: Edison, Go Zero, LADWP, HEEHRA, CARE se mencionan en distintos documentos. ¿Cuáles deben estar configurados al arranque y tienen formulario/insumo de cada uno? (Hoy solo hay insumo para Arizona y TECH Clean.)

### B. Vendedor y formulario (Cadena A — bloquea el módulo 1)

8. **Auditoría técnica preliminar (§2.4)**: el PDF la marca obligatoria (amperaje del panel, climatización existente, cuartos, cocina de inducción, water heater, viabilidad). Las plantillas de Arizona y TECH Clean que enviaron **no tienen esos campos**. ¿Se agregan como sección común a todos los programas? ¿Valores exactos? (amperaje: lista 100/125/150/200 A o número libre; water heater: Sí/No o tipo gas/eléctrico + capacidad; viabilidad: adecuada / requiere adecuación / no viable.)
9. **ID del cliente (§2.3)**: ¿se guarda foto/escaneo del ID en el expediente o solo se verifica físicamente y se marca "verificado"? Si se guarda: ¿es dato sensible con acceso restringido? ¿Se envía al programa?
10. **Ingresos por taxes (§2.2)**: cuando el cliente no tiene beneficio, ¿se captura el ingreso anual y se adjunta la declaración? ¿Umbrales por programa/tamaño del hogar para decidir elegibilidad?
11. **Motor de elegibilidad**: ¿el sistema debe **decidir** "califica para TECH Clean / Arizona" a partir de las respuestas, o el vendedor elige el programa y el sistema solo valida? Si decide: necesitamos las reglas por programa (beneficios que califican, ingresos, tipo de vivienda, estado).
12. **Visitas y zonas (§2.1)**: ¿quieren registrar cada puerta tocada (resultado: no contestó, no interesado, no califica, aplicación creada) para medir productividad del vendedor? ¿Asignación de vendedor a parque/zona? ¿Registro de la autorización del administrador del parque (nombre, fecha, contacto)?
13. **Trabajo sin señal**: ¿los vendedores tienen cobertura en los parques? ¿Necesitan capturar sin conexión y sincronizar después? (Cambia la arquitectura del frontend.)
14. **T&C y autorización**: ¿en inglés, español o bilingüe? ¿Quién entrega el texto legal definitivo y su versión por programa? ¿Se genera un PDF firmado que se entrega al cliente?
15. **Identidad frente al cliente (.md §17.1)**: Desert Alliance Properties LLC vs Delta HVAC Service Inc. ¿Qué nombre/logo aparece en el formulario de Arizona, en el T&C y en el invoice?
16. **Datos sensibles (.md §17.3)**: discapacidad, condición médica, beneficios, ingresos, ID. ¿Quién puede verlos? ¿Se ocultan en reportes/exportaciones?

### C. Administración

17. **Contador de días**: la referencia es 2–3 días hábiles. ¿Se alerta a partir de qué día? ¿Días hábiles de qué calendario (feriados de CA/AZ)? ¿A quién se notifica?
18. **Estados del expediente**: el PDF define 9 estados del Kanban. ¿Es el único estado que el cliente quiere ver? Internamente la aplicación tiene 9 sub-estados (borrador → sometida → aprobada/rechazada) y el proyecto otros 12. ¿Confirmamos que el Kanban del PDF es la vista "gerencial" y los otros son detalle?
19. **Inspección (§3.5)**: ¿quién la agenda (ciudad, programa, ambos)? ¿Qué datos: fecha, inspector, resultado, observaciones? Si **falla**, ¿vuelve a "Listo para instalar" (re-trabajo) o hay un estado "Corrección técnica"? ¿Se cobra parcial mientras tanto?
20. **Permiso: vencimiento**: el PDF pide alertas por "vencimiento de permisos". ¿Los permisos tienen fecha de expiración? ¿Cuál es el plazo típico?
21. **Expediente de cobro (§3.4)**: ¿cuál es el checklist exacto por programa para poder radicar (aprobación, código, T&C firmado, fotos X/Y/Z, invoice, formulario del programa)? ¿Difiere entre Arizona y TECH Clean?

### D. Técnicos

22. **Equipos instalados como dato**: además de la foto de la etiqueta, ¿el programa exige registrar marca, modelo, serial, BTU/tonelaje y cantidad por unidad? (TECH Clean normalmente sí, para el rebate.) ¿Debe ir en el invoice?
23. **Preparación de materiales (§5.1)**: ¿lista de materiales por orden (nº de mini-splits, cableado, breakers)? ¿Control de inventario/stock, o solo un checklist "llevo todo"?
24. **Roles reales**: el PDF habla de Vendedor, Administración, Técnico, Contabilidad y Gerencia. El sistema hoy tiene admin, gerente comercial, project manager, supervisor, finanzas, técnico, solo lectura. ¿Qué personas ocupan qué rol y hay alguien que haga dos (p. ej. Mateo administración + contabilidad)?

### E. Contabilidad (si entra en alcance)

25. **Gastos**: ¿categorías (gasolina, viáticos, materiales, peajes, otros)? ¿Quién los registra (técnico desde el móvil / contabilidad)? ¿Aprobación antes de contar en el P&L?
26. **Proveedores/AP**: ¿facturas de proveedor con vencimiento y programación de pago? ¿Pagos parciales?
27. **Conciliación bancaria**: ¿importar extracto bancario (CSV/OFX) y cruzar contra invoices, o registrar manualmente "pago recibido el día X por $Y"?
28. **Exportación contable**: ¿QuickBooks, Xero, Excel? ¿Formato exacto?
29. **AR — rechazos**: cuando el programa devuelve una aplicación/factura por error, ¿qué información viene (motivo, código)? ¿Se reabre el mismo invoice o se emite uno nuevo con referencia al anterior?
30. **Facturación a particulares**: ¿existen trabajos fuera de programa (cliente paga directo)? ¿Con impuestos? ¿Qué plantilla?

---

## 4. Decisiones internas (José + Mateo, no son del cliente)

- **Relación Application ↔ Lead ↔ Opportunity ↔ Project.** El código actual
  tiene `Lead → Customer + Opportunity → Project` (una Opportunity por
  propiedad/espacio, con `funder_program`, `application_number`,
  `approval_code`, `funder_status`). El `.md` introduce `Application` (ya hay
  un modelo inicial, migración 0007) pero no dice si **reemplaza** a
  Opportunity, la **complementa** o si `Application` se cuelga de la
  Opportunity. Hay que decidirlo antes del módulo 1, porque afecta a G17 (un
  solo estado visible) y al handoff a Cadena B.
- **Qué juego de estados manda** (G17): propuesta — `Application.status` para
  la Cadena A (9 estados del .md §10), `Project.status` para la Cadena B, y
  una función derivada `expediente_stage` que mapea ambos a los 9 estados
  del PDF para el Kanban.
- **Dónde viven los campos técnicos de §2.4**: como `field_key` del catálogo
  (`technical.panel_amperage`, `technical.existing_hvac`,
  `technical.induction_stove`, `technical.water_heater`,
  `technical.viability`) en una sección común "Auditoría técnica preliminar",
  activada en todos los programas. Es Cadena A. Requiere confirmación del
  cliente (pregunta 8) pero se puede construir ya con valores provisionales.
- **Requisitos documentales comunes** que faltan en A.1/A.2: `document.id_front`,
  `document.id_back` (pregunta 9), `document.tax_return` (pregunta 10).
- **Dueño de los módulos nuevos** (G1, G5, G6, G9, G10, G11): no están en la
  división §18.2. Hay que repartirlos cuando el cliente confirme alcance.

---

## 5. Impacto inmediato en la Cadena A (lo que sí depende de mí)

Aunque el cliente no haya respondido, el módulo 1 debe nacer preparado para:

1. **Sección "Auditoría técnica preliminar"** en el catálogo canónico con los
   5 campos de §2.4 (valores provisionales, ajustables por admin).
2. **Requisitos documentales** `ID` y `declaración de impuestos` en el
   catálogo de documentos, desactivados por defecto hasta confirmar.
3. **Campo `visit.geolocation` / `visit.recorded_at`** ya contemplado en §9.11;
   dejar el modelo de aplicación listo para colgarse de una futura entidad
   `Visit` (G1) sin migración destructiva.
4. **Reglas de elegibilidad** como estructura de datos por programa
   (`eligibility_rules` JSON) aunque el motor inicial solo valide, no decida.
5. **Estados de Application** exactamente los 9 del `.md` §10 + un campo
   derivado para el Kanban del PDF (G17).
6. **T&C versionado** con idioma (`en`/`es`) desde el inicio (pregunta 14).

Nada de esto contradice el `.md`; lo extiende donde el PDF es más exigente.
