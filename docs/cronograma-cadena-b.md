# Cronograma — Mateo Mazo (Cadena B)

Fecha: 18 de septiembre de 2026. Propuesto por José Javier; Mateo ajusta las
duraciones según su criterio. Módulos según
`requerimientos-formularios-programas-delta-hvac.md` §18.2 y decisiones en
`decisiones.md`. Misma base de estimación que `cronograma-cadena-a.md`
(una persona full-stack, trabajando con Claude, con pruebas y verificación
de cada cambio). Las fechas ya descuentan los festivos de Colombia: 12 de
octubre, 2 de noviembre, 16 de noviembre, 8 y 25 de diciembre.

La idea: Mateo no espera la Cadena A completa. Recibe dos cosas tempranas de
José (roles y esqueleto del expediente) y trabaja por su cuenta. El módulo 4
es el único que depende del formulario del vendedor, por eso va al final.

## Antes de arrancar (21 – 30 de septiembre)

- Dar OK a D1 (roles del PDF), D2 (`Case` como expediente; `Project.case_id`;
  las tablas de la Cadena B apuntan a `Program`) y a los cambios del `.md`
  §18.2 listados al final. **Fecha límite: viernes 25 de septiembre.**
- Enviar `preguntas-cliente.md` al cliente. La respuesta sobre señal en los
  parques define la opción A o B de la Cadena A; la de contabilidad define
  si hay módulos extra para la Cadena B.
- Recibir de José: roles y códigos de permiso reservados (**25 de
  septiembre**) y el esqueleto (**30 de septiembre**, contrato abajo).
- Mientras tanto: spec del módulo 5 (brainstorming → `docs/superpowers/specs/`)
  y revisar qué de la fase 3 actual (proyecto, checklist, evidencias,
  firmas, monitor de técnicos) se conserva tal cual.

## Contrato del esqueleto — miércoles 30 de septiembre

Lo entrega José. Es un contrato: lo que está aquí no cambia sin avisar.
Idéntico en `cronograma-cadena-a.md`.

- `Program` mínimo: id, organización, código, nombre, activo, marca de
  plantilla del sistema.
- `Case` con: organización, `program_id`, `customer_id` (opcional),
  dirección de la propiedad (calle, unidad o espacio, ciudad, estado, ZIP,
  GPS, dirección normalizada), vendedor, `application_number`,
  `approval_code`, `funder_status_id`, `scheduled_install_date`, **etapa**
  (lista completa: `Sin contacto`, `No interesado`, `No califica`, `Nuevo
  Prospecto`, `Pendiente Aprobación`, `Aprobado`, `Rechazado`, `En espera`,
  `Permiso en Trámite`, `Listo para Instalar`, `Instalado`, `Inspección
  Pendiente`, `En Proceso de Cobro`, `Pagado`, `Cerrado`) y **sub-estado**
  (texto libre por etapa, definido por el dueño de la etapa).
- `case_stage_events`: historial de cada cambio de etapa o sub-estado con
  quién, cuándo y motivo.
- `transition(case, to_stage, actor, reason)` en `cases/service.py` con la
  tabla completa de transiciones permitidas. Mateo registra ahí sus reglas
  de guarda para las etapas desde `Aprobado` en adelante y puede mover un
  case a `Aprobado` desde sus tests sin esperar el módulo 4.
- `Project.case_id` (opcional, con relleno desde `opportunity_id`). Única
  vez que José toca `field_ops`. `Opportunity` queda viva y obsoleta hasta
  que Mateo cambie el disparador de creación del proyecto.
- `shared/events.py` con `emit(nombre, datos)` que por ahora solo registra
  en log. Mateo lo conecta en el módulo 7.
- `storage.py` y `watermark.py` pasan de `field_ops` a `app/shared/files/`.
  **Lo mueve Mateo** esa misma semana (es su código); desde ahí es común.
- Las tablas de Mateo apuntan a `Program`: `ChecklistTemplate.program_id`,
  `InvoiceTemplate.program_id`. José no toca esas tablas.
- Swagger publicado y `docs/contratos-cadena-a.md` iniciado.

## Módulo 5 — Proyecto, checklist técnico, evidencias, permisos e inspección

- Duración: 3 semanas y media.
- Inicio: jueves 1 de octubre de 2026.
- **Entrega: martes 27 de octubre de 2026.**
- Depende de: el esqueleto del 30 de septiembre. Nada más.
- Primera semana, obligatorio antes del **miércoles 7 de octubre**: cambiar
  la creación automática del proyecto para que lea `Case` (etapa
  `Aprobado`) en vez de `Opportunity`, y mover `storage.py` y
  `watermark.py` a `shared/files/`. Con eso José puede retirar
  `Opportunity` en la semana del 16 de octubre sin romperle nada.
- Incluye:
  - Proyecto colgado del expediente; se crea solo cuando el expediente
    llega a "Aprobado".
  - Transiciones del expediente desde "Aprobado" hasta "Inspección
    pendiente" con sus sub-estados (permiso en trámite, listo para
    instalar, instalación programada, instalado, inspección aprobada),
    registradas en `transition()` con prueba por transición.
  - Checklist técnico configurable por programa y tipo de instalación
    (hoy hay una plantilla fija): categorías, ítems obligatorios,
    condicionales, "No aplica" con motivo, bloqueo de cierre.
    `ChecklistTemplate.program_id`.
  - Evidencias por categoría (las 15 del `.md` §7.1) asociadas a un ítem
    del checklist, usando `shared/files/` (marca de GPS y fecha ya existe).
  - Equipos instalados como dato: marca, modelo, serial, cantidad por
    unidad (lo pide el cobro al programa, no solo la foto de la etiqueta).
  - Permiso municipal: número, ciudad o condado, fecha de radicación,
    aprobación, vencimiento, estado. Solo registro; el autollenado de
    formularios es un módulo aparte si el cliente lo confirma.
  - Inspección: agendamiento, fecha, inspector, resultado, observaciones,
    y qué pasa si falla (vuelve a "Listo para instalar" o estado de
    corrección, según responda el cliente).
  - Agenda y asignación de técnicos (el monitor GTR actual se conserva) y
    lista de materiales por orden (PDF §5.1).
  - Eventos emitidos con `shared/events.py`: proyecto creado, orden
    liberada, instalación cerrada, inspección registrada.
  - Permisos por acción, auditoría, pruebas.

## Módulo 6 — Invoices, pagos y plantillas por programa

- Duración: 2 semanas y media.
- Inicio: miércoles 28 de octubre de 2026.
- **Entrega: viernes 13 de noviembre de 2026.**
- Depende de: `Project` (módulo 5) y `Program` (código).
- Incluye:
  - Invoice con líneas de servicio, materiales, mano de obra, permisos,
    subtotal, rebate, total, pagos y balance; equipos instalados del
    módulo 5 como líneas.
  - Plantillas por programa (`InvoiceTemplate.program_id`):
    GoZero/HousecallPro y pedestal/Charge Ready como mínimo; campos
    visibles y fórmulas por plantilla; editor y vista previa.
  - Expediente de cobro: checklist obligatorio por programa (aprobación,
    código, T&C firmado, evidencias, invoice), fecha de radicación, estado
    "radicado". No se puede radicar con el checklist incompleto.
  - Etapas del expediente "En proceso de cobro" → "Pagado" → "Cerrado" en
    `transition()`.
  - Estados de cobro: pendiente, radicado, pagado, **rechazado con
    motivo**, y corrección o refacturación con referencia al invoice
    anterior.
  - Dashboard de cobros con alerta por tiempo excedido.
  - Eventos: invoice radicado, pago recibido, rechazo.
  - Permisos, auditoría, pruebas.

## Módulo 7 — Notificaciones, correo y SMS Masiv

- Duración: 1.5 semanas.
- Inicio: martes 17 de noviembre de 2026 (el 16 es festivo).
- **Entrega: jueves 26 de noviembre de 2026.**
- Depende de: `shared/events.py` y los eventos de los módulos 5 y 6. Los
  de la Cadena A (enviado a revisión, devuelto) ya se emiten desde el
  módulo 2 de José; se conectan aquí.
- Incluye:
  - Conectar `emit()` a un despachador real; centro visual de
    notificaciones.
  - Contador de días en "Pendiente aprobación" con alerta al exceder la
    referencia (2–3 días hábiles; el umbral lo responde el cliente).
  - Alertas de vencimiento de permiso e inspección.
  - Plantillas de correo y SMS; adaptador de correo real (hoy hay SMTP con
    un error de codificación con la "ñ" que hay que corregir) y adaptador
    Masiv configurable; modo de prueba sin envío; historial y reenvío.
  - Pruebas.

## Módulo 4 — Revisión administrativa y sometimiento

- Duración: 1.5 semanas.
- Depende de: handoff de la Cadena A (respuestas del vendedor, documentos,
  T&C, firma). La pantalla se puede adelantar contra el Swagger del módulo
  2 de José desde la primera semana de noviembre.
- Opción A (Cadena A entregada el 24 de noviembre):
  - Inicio: viernes 27 de noviembre de 2026.
  - **Entrega: miércoles 9 de diciembre de 2026.**
- Opción B (Cadena A entregada el 3 de diciembre; entre el 27 de noviembre
  y el 3 de diciembre Mateo adelanta la pantalla contra el Swagger):
  - Inicio: viernes 4 de diciembre de 2026.
  - **Entrega: miércoles 16 de diciembre de 2026.**
- Incluye:
  - Bandeja administrativa con sub-estados (pendiente de revisión,
    devuelta, lista para someter, sometida, en revisión del programa).
  - Vista completa del expediente: respuestas por paso, documentos,
    fotos y videos con GPS y fecha, T&C y firma.
  - Aprobar internamente, devolver con motivo obligatorio, marcar lista
    para someter, registrar sometimiento, aprobación o rechazo del
    programa, código de aprobación. Transiciones `Pendiente Aprobación` →
    `Aprobado` / `Rechazado` / `En espera` en `transition()`.
  - Validación de expediente completo antes de someter.
  - Historial de revisión, permisos, auditoría, pruebas.

## Handoff Cadena B → José (para el módulo 8)

- **Opción A: jueves 10 de diciembre de 2026.**
- **Opción B: jueves 17 de diciembre de 2026.**
- Se entrega: migraciones aplicadas, `docs/contratos-cadena-b.md`
  completo, estados definitivos, permisos por rol, datos de prueba, eventos
  y respuestas de error, ambiente integrado.

## Módulos sin dueño (si el cliente confirma alcance)

Se planifican cuando el cliente responda; no tienen fecha:

- Permisos municipales con autollenado de formularios de la ciudad.
- Gestor documental: conversión, compresión y paquete por cliente para los
  portales.
- Contabilidad: gastos de campo, proveedores y cuentas por pagar,
  conciliación, P&L por proyecto, reportes gerenciales, exportación
  contable.
- Reportes gerenciales básicos (tiempos por etapa, tasa de rechazo,
  productividad por zona): con `case_stage_events` los datos ya quedan
  guardados desde el 30 de septiembre.

## Reglas para trabajar en paralelo con José

- Paquetes de Mateo: `field_ops`, `billing`, `notifications`. Paquetes de
  José: `users`, `auth`, `organizations`, `crm`, `programs`, `cases`,
  `documents`. Nadie edita el del otro; si necesita algo, lo pide.
- Archivos compartidos (`alembic/env.py`, `tests/conftest.py`,
  `api/v1/router.py`, `shared/permissions.py`, `app/router.tsx`,
  `DashboardLayout.tsx`): solo se agregan líneas, nunca se reordenan ni se
  borran las del otro.
- `Case` es de José; Mateo registra sus transiciones en `transition()` sin
  tocar el modelo.
- `shared/files/` y `shared/events.py` son comunes: cambios de común
  acuerdo.
- Integración a `main` todos los viernes con `pytest` verde y `tsc` +
  `vite build` limpios. Quien integra segundo renumera su migración de
  Alembic encima de la del otro.
- `docs/contratos-cadena-b.md` (Mateo) y `docs/contratos-cadena-a.md`
  (José) siempre al día, más Swagger.
- Revisión conjunta corta cada viernes sobre `main`.

## Cambios al `.md` §18.2 que requieren el OK de Mateo

- Orden de la Cadena B: 5 → 6 → 7 → 4.
- Quitar "entregar la cadena completa antes de integrar" en ambas cadenas;
  reemplazar por integración por contrato, semanal.
- Módulo 5: checklist configurable por programa, equipos instalados como
  dato, permiso con vencimiento, inspección con resultado y reintento,
  lista de materiales por orden.
- Módulo 6: expediente de cobro con checklist y fecha de radicación,
  rechazado con motivo y refacturación, dashboard de cobros con alerta.
- Módulo 7: contador de días en "Pendiente Aprobación", alertas de
  vencimiento de permiso e inspección.
- Sección nueva "Contrato del esqueleto — 30 de septiembre".

## Vista conjunta — fechas clave

- 25 sep: roles (José). OK de Mateo a D1, D2 y cambios del `.md`.
- 30 sep: esqueleto (José). Mateo mueve `storage`/`watermark` a común.
- 1 oct: Mateo arranca el módulo 5.
- 7 oct: creación del proyecto ya lee `Case` (Mateo).
- 22 oct: módulo 1 (José); `Opportunity`, `Quote` y Pipeline retirados.
- 27 oct: módulo 5 (Mateo).
- 13 nov: módulo 2 opción A (José) y módulo 6 (Mateo).
- 23 nov: módulo 3 opción A (José).
- 24 nov: handoff Cadena A opción A.
- 25 nov: módulo 2 opción B (José).
- 26 nov: módulo 7 (Mateo). (Thanksgiving en EE. UU.: el cliente no
  responde esa semana.)
- 2 dic: módulo 3 opción B (José).
- 3 dic: handoff Cadena A opción B.
- 9 dic / 16 dic: módulo 4 (Mateo), según opción.
- 10 dic / 17 dic: handoff Cadena B.
- Módulo 8 (José, 2 semanas): **23 de diciembre de 2026 (opción A)** o
  **8 de enero de 2027 (opción B, sin contar la semana del 24 de diciembre
  al 1 de enero)** — sistema completo probado de punta a punta para
  Arizona y TECH Clean.
