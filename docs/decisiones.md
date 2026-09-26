# Decisiones de diseño — crm-usa

Una decisión por bloque, con fecha y quién la tomó. Este archivo es la
referencia rápida; el detalle vive en las specs de `docs/superpowers/specs/`.

## D1 — Roles del sistema fieles al PDF

- Fecha: 17 de septiembre de 2026. Tomada por José Javier. Pendiente OK de Mateo.
- Los 7 roles genéricos actuales (`commercial_manager`, `project_manager`,
  `supervisor`, `finance_user`, `field_technician`, `read_only`,
  `organization_admin`) se reemplazan por `organization_admin`, `salesperson`,
  `admin_staff`, `technician`, `accounting`, `management`.
- Impacto en Mateo: `tests/test_rbac_full.py` y cualquier pantalla que
  compare códigos de rol.

## D2 — El expediente es una sola entidad: `Case`

- Fecha: 17 de septiembre de 2026. Tomada por José Javier. Pendiente OK de Mateo.
- `Case` nace en la primera visita a una propiedad y llega hasta el pago.
  Todo se relaciona con él: cliente, submissions por paso, documentos,
  evidencias, firma, T&C, revisión, permiso, proyecto de instalación,
  inspección, invoice, pago. Es "el documento que todos van firmando".
- `Case` reemplaza a `Application` (migración 0007) y a `Opportunity`.
  `Quote` se retira. La pantalla "Pipeline" pasa a ser el Kanban de cases.
- `Project.opportunity_id` pasa a `Project.case_id`; la auto-creación del
  proyecto se dispara desde el estado "Aprobado" del `Case`. Es lo único que
  toca la Cadena B; José hace la migración de datos y avisa antes de tocar
  `field_ops`.
- `Lead` y `Customer` se quedan. `Lead` se funde con `Case` más adelante.
- **Nada muta**: un `Case` nunca se convierte en otra cosa; lo que se
  acumula son submissions, documentos y cambios de estado. Hay cases que
  terminan en "No interesado" y cases que llegan a "Pagado"; son la misma
  tabla.

## D3 — Motor de flujo completo, no formulario plano

- Fecha: 17 de septiembre de 2026. Tomada por José Javier.
- Programa → versión de flujo (inmutable al publicar) → fases (rol
  responsable) → pasos → campos (referencia al catálogo + obligatoriedad +
  condición). Catálogo de campos con `field_key` estable y `binding` a
  columnas tipadas (`customer.*`, `case.*`); lo que no tiene binding vive en
  el JSON de la submission del paso.
- Cada paso completado es una `step_submission` inmutable con rol, usuario,
  fecha y GPS. Una corrección es otra submission; la anterior queda como
  historial.
- Condiciones como reglas JSON simples; transiciones entre fases en código
  con test por regla. Lo configurable es qué es obligatorio, no cómo se valida.
- Plantillas del sistema + copia por organización (mismo patrón que los
  roles), porque el producto se venderá a otras empresas.
- Primera versión implementa una sola fase (Vendedor) con sus pasos; las
  demás fases son configuración cuando llegue su módulo.

## D4 — "Proyecto" vs "Programa"

- Fecha: 17 de septiembre de 2026. Tomada por José Javier.
- **Programa** = lo configurable (Eficiencia de Arizona, TECH Clean): fases,
  pasos, campos, documentos, zonas, asesores asignados, T&C, plantilla de
  invoice. Módulo 1.
- **Proyecto** (`Project`) = la instalación física en una casa (Cadena B).
  Un programa tiene muchos proyectos. No se usa "proyecto" para el programa.

## D5 — Zonas y asesores dentro del programa

- Fecha: 17 de septiembre de 2026. Tomada por José Javier.
- El programa define sus zonas (parques/comunidades de CA, AZ, NV) y la
  asignación asesor ↔ zona. No es un módulo aparte; es configuración del
  programa (módulo 1). El asesor ve en su inicio sus programas y zonas.

## D6 — Las visitas son cases, no una tabla aparte

- Fecha: 17 de septiembre de 2026. Tomada por José Javier.
- Cada puerta tocada crea o reutiliza un `Case` identificado por la
  propiedad (parque, unidad/espacio, dirección normalizada, GPS). El cliente
  es opcional hasta que alguien abra y dé sus datos.
- Cada toque es una submission del paso "Visita" del mismo case (GPS, hora,
  resultado). Varias visitas a la misma puerta = un case, varias submissions.
- Estados de cierre temprano, previos a "Nuevo Prospecto": `Sin contacto`,
  `No interesado`, `No califica`. Se pueden reabrir si la puerta luego
  responde. Los 9 estados del PDF no cambian.
- Listas y Kanban filtran por defecto los cierres tempranos; el reporte de
  productividad del asesor (puertas, apertura, venta por zona) sale de ellos.

## D7 — Preguntas al cliente

- Fecha: 17 de septiembre de 2026. Pendiente: Mateo las envía.
- Preguntas 8, 9, 10, 11, 13, 14, 15, 16 de `validacion-pdf-vs-modulos.md`
  §3.B (campos técnicos, ID, ingresos, motor de elegibilidad, trabajo sin
  señal, T&C e idioma, identidad frente al cliente, datos sensibles).
- Mientras llegan, se construye con valores provisionales como
  configuración, no como código.

## D8 — Contrato del esqueleto y reglas de paralelo

- Fecha: 18 de septiembre de 2026. Tomada por José Javier. Pendiente OK de Mateo.
- El 30 de septiembre José entrega un esqueleto (definido igual en
  `cronograma-cadena-a.md` y `cronograma-cadena-b.md`): `Program` mínimo,
  `Case` con la lista completa de etapas y sub-estado, `case_stage_events`,
  `transition()` con la tabla completa de transiciones, `Project.case_id`,
  `shared/events.py` y `storage`/`watermark` movidos a `shared/files/`.
- Las tablas de la Cadena B apuntan a `Program` (`ChecklistTemplate.program_id`,
  `InvoiceTemplate.program_id`), no al revés.
- `Opportunity` sigue viva y obsoleta hasta que Mateo cambie el disparador
  de creación del proyecto (antes del 7 de octubre); José la retira en la
  semana del 13 de octubre.
- Paquetes: José `users`, `auth`, `organizations`, `crm`, `programs`,
  `cases`, `documents`; Mateo `field_ops`, `billing`, `notifications`.
  Comunes: `shared/files/`, `shared/events.py`. Archivos compartidos solo
  se editan agregando líneas. Integración a `main` cada viernes.
- Orden de la Cadena B: 5 → 6 → 7 → 4. Requiere cambiar §18.2 del `.md`.

## D9 — Los módulos (grupos de permisos) viven en base de datos y se editan desde pantalla

- Fecha: 22 de septiembre de 2026. Tomada por José Javier.
- Un **módulo** es un grupo de permisos y es la unidad de navegación: el menú
  y las rutas preguntan "¿el usuario tiene algún permiso de este módulo?".
- La relación permiso ↔ módulo es de **muchos a muchos**: el módulo tiene la
  lista de permisos, no al revés. Un mismo permiso puede estar en varios
  módulos (`dashboards.finance` en Facturación y en Reportes;
  `programs.read` en Configuración y en Expedientes).
- Se guardan en dos tablas nuevas, `permission_modules` y
  `permission_module_items`, con el mismo patrón que los roles: el código
  (`DEFAULT_MODULES` en `app/shared/permissions.py`) define los valores
  iniciales y el seed crea la plantilla del sistema más una copia por
  organización; la tabla es el estado vivo y editable.
- Los 15 módulos del PDF se marcan `is_system`: se pueden renombrar,
  reordenar y cambiarles los permisos, pero **no borrar**. Cada uno tiene
  "restaurar valores por defecto".
- Riesgo aceptado: si alguien deja un módulo sin permisos, su ítem del menú
  desaparece aunque la pantalla siga existiendo. Lo mitiga `is_system` +
  restaurar valores por defecto.
- Alternativa descartada: dejarlos solo en código (más simple y sin
  migraciones, pero no editable por el administrador).
