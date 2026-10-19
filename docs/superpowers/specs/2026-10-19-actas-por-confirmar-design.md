# «Actas por confirmar» y aviso al cerrar la instalación — Diseño

**Fecha:** 19 de octubre de 2026 · **Pidió:** José Javier (recorrido manual como Administrador)

## Problema

Cuando el técnico cierra la instalación, el acta queda «Esperando la revisión de Administración». Pero Administración no tiene cómo enterarse ni dónde verlas:
- El único lugar es el paso 7 dentro de cada proyecto.
- No hay lista de actas pendientes, y el filtro «Completado» de Proyectos no distingue las confirmadas.
- Cerrar no avisa a nadie.

Aparte, el formulario «Crear proyecto» de Proyectos confunde. El proyecto se crea solo al aprobar el expediente; uno creado a mano queda sin expediente, sin programa y sin etapas.

## Lo que ya existe

- El cierre emite `installation.closed`, que nadie escucha.
- El módulo de avisos (`notifications`) tiene catálogo, plantillas editables y la campanita. Los eventos le llegan por `dispatch.EVENTS`.
- «Documentos por revisar» (`/documents`, `DocumentsQueuePage`) es la cola equivalente para los expedientes.
- Confirmar o devolver el acta: `POST /projects/{id}/review/confirm|return` con el permiso `checklists.approve`.

## Diseño

### Aviso al cerrar

- Nuevo aviso `installation.closed` en el catálogo: «Instalación cerrada: {{proyecto}}», para quien tiene `checklists.approve`. El técnico que cerró no lo recibe.
- El enlace es `/projects/{id}?paso=review`: la pantalla abre el paso 7 y baja hasta él.
- `installation.closed` se agrega a `dispatch.EVENTS`.

### Bandeja «Actas por confirmar»

- Entrada propia en el menú, en Operación de campo, con el permiso `checklists.approve`. Es la cola diaria de Administración, igual que «Documentos por revisar».
- `GET /acta-reviews/pending` (paginado en la base) lista los proyectos cerrados cuya última revisión no es «confirmada». Van de la más vieja a la más nueva (fecha de cierre) e incluyen expediente, cliente, técnico, fecha de cierre y días esperando, contados con el «hoy» de la organización.
- Cada fila lleva a `/projects/{id}?paso=review`.

### Quitar «Crear proyecto»

- Sale el formulario de la pantalla Proyectos. La API `POST /projects` se queda: la usan las pruebas, y quitarla es decisión aparte.

## Fuera de alcance

- Un contador en el menú; el aviso y el total de la bandeja cubren eso.

## Paquetes de Mateo

`field_ops` y `notifications`. Hay que avisarle.
