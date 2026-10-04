# Módulo 1 — Programas, catálogo de campos y flujo del vendedor

Fecha: 4 de octubre de 2026. Cadena A, desarrollado por Mateo mientras José
Javier no puede trabajar (acordado con él el 4 de octubre). Base: el alcance
que José dejó escrito en `cronograma-cadena-a.md` (módulo 1),
`requerimientos-formularios-programas-delta-hvac.md` §2–§5 y §18.2, y
`decisiones.md` D2–D7. Entrega planeada: **22 de octubre de 2026**.

## 1. Punto de partida (verificado en el código el 4 de octubre)

- Hecho por José y en `main`: `Program` mínimo (código, nombre, activo,
  plantilla del sistema), `ProgramVersion` y `ProgramZone` vacías en
  `cases/models.py`; los permisos `programs.*`, `fields.*`, `workflows.*` y
  `zones.*` ya existen y están repartidos por rol.
- No existe: paquete `programs`, API, pantallas, catálogo de campos, flujo,
  carga de Arizona y TECH.
- Vive todavía el formulario del modelo anterior (`Application`,
  `ProgramFormField`, `/applications`). Se retira al terminar el módulo 2,
  como José dejó escrito.

## 2. Decisiones

### D1.1 — Los modelos nuevos viven en `programs`; `Program` se queda donde está

`Program`, `ProgramVersion` y `ProgramZone` siguen en `cases/models.py`
(el cobro y campo ya los importan de ahí) y solo ganan columnas. Las tablas
nuevas van en `app/modules/programs/`. Mover la clase rompería importaciones
de las dos cadenas sin ganar nada.

### D1.2 — Catálogo de campos independiente del formulario (§2.4)

`field_definitions`: cada pregunta existe una vez por organización con su
`key` estable (`customer.full_name`), uno de los 18 tipos (§2.3), opciones
normalizadas (§2.6), validación (formato, mínimo/máximo, longitud, opción
excluyente), `binding` (columna real `customer.*` / `case.*` o nulo = vive en
los datos del paso), y las marcas `internal` (§3.6) y `sensitive` (§17.3).
Una clave no se renombra ni se borra: se desactiva.

### D1.3 — Flujo versionado: versión → fases → pasos → campos (D3)

`ProgramVersion` gana estado (`draft` / `published` / `archived`), quién y
cuándo publicó, y la versión de T&C que usa. Debajo: `workflow_phases` (rol
responsable), `workflow_steps` y `workflow_step_fields` (campo del catálogo,
`required` / `optional` / `conditional`, condición, etiqueta y ayuda propias,
orden). Una versión publicada **no se edita**: cambiar algo es crear una
versión nueva, que copia la última. Solo una publicada por programa; publicar
otra archiva la anterior. Los expedientes guardan la suya (`program_version_id`).

### D1.4 — Condiciones como JSON simple, sin lenguaje de expresiones

`{"field": "home.gas_type", "eq": "natural_gas"}`, `{"field": ..., "in": [..]}`,
`{"field": ..., "not_empty": true}`. Al publicar se valida que el campo
referido exista en la versión. Un solo motor (`programs/engine.py`) evalúa
visibilidad, obligatoriedad y validaciones: lo usan la vista previa (aquí) y
la pantalla del vendedor (módulo 2), así que los dos dicen lo mismo.

### D1.5 — Identidad del programa frente al cliente (§17.1)

`Program` gana funder, nombre que ve el cliente, logo, texto de autorización y
entidad que factura. Los T&C viven en `program_terms` por versión e idioma
(es/en); una versión de T&C publicada no se edita.

### D1.6 — Zonas de venta separadas de las zonas de cobro

`ProgramZone` (de José) son **zonas de venta**: parques y comunidades donde se
asignan vendedores (D5). Las jurisdicciones del módulo 6 son **dónde paga el
programa** (ciudad o código postal con vigencia). Son conceptos distintos y se
quedan separados; en pantalla se llaman "Zonas de venta" y "Dónde paga".
`zone_assignments` une vendedor ↔ zona.

### D1.7 — Plantillas del sistema en código, copia por organización

Como los roles: el catálogo canónico y los flujos de Arizona y TECH viven en
`programs/templates.py`; `install_defaults(org)` los copia a la organización
(idempotente). Lo usan el seed y un botón del administrador. Así cada empresa
nueva arranca con los dos programas y los ajusta.

### D1.8 — Pendientes de José con la Cadena B, ahora resueltos aquí

- Transiciones `approved → ready_to_install` (permiso de la orden,
  `dispatch.manage`) e `installed → billing_in_progress`.
- La transición a `approved` acepta `approval_code` y `application_number`;
  sin código, el cobro no se puede radicar (requisito del módulo 6).

## 3. API

| Ruta | Permiso |
|---|---|
| `GET/POST /programs`, `GET/PATCH /programs/{id}` | `programs.read` / `programs.manage` |
| `GET/POST /programs/{id}/terms`, `POST /program-terms/{id}/publish` | `programs.read` / `programs.manage` |
| `GET/POST /fields`, `PATCH /fields/{id}` | `programs.read` / `fields.manage` |
| `GET/POST /programs/{id}/versions`, `GET /program-versions/{id}` | `programs.read` / `workflows.manage` |
| Fases, pasos y campos del paso (crear, editar, mover, quitar) | `workflows.manage` |
| `POST /program-versions/{id}/publish`, `/archive` | `workflows.publish` |
| `POST /program-versions/{id}/preview` | `programs.read` |
| `GET/POST /programs/{id}/zones`, `PATCH /zones/{id}`, `PUT /zones/{id}/salespeople` | `programs.read` / `zones.manage` |
| `GET /me/programs` (programas y zonas del vendedor) | autenticado |
| `POST /programs/install-defaults` | `programs.manage` |

## 4. Pantallas

"Configuración de programas" (hoy deshabilitada en el menú): lista de
programas → hoja del programa (identidad, T&C, versiones, zonas de venta) →
editor de la versión (fases, pasos y campos con subir/bajar, condiciones) con
**vista previa** al lado. Catálogo de campos aparte. Mismo lenguaje visual del
acta y del cobro.

## 5. Fuera de este módulo

Pantalla del vendedor, visitas, envío y firma (módulo 2); documentos del
expediente (módulo 3); retiro de `Application`/`ProgramFormField` (al cerrar
el módulo 2); arrastrar para ordenar (decisión de José: subir/bajar basta).

## 6. Pruebas

Catálogo (clave única, tipos válidos, opciones, desactivar), motor (visibilidad
condicional, obligatorios, formatos, excluyente, internos), versión (borrador
editable, publicada inmutable, nueva versión copia, publicar archiva la
anterior, condición a un campo inexistente bloquea publicar), T&C por idioma,
zonas y asignación, `/me/programs`, plantillas idempotentes con Arizona y TECH
completos, permisos por ruta y aislamiento por organización, y las dos
transiciones nuevas.
