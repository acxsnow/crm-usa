# Bandeja «Por revisar» de Administración — Diseño

**Fecha:** 19 de octubre de 2026 · **Pidió:** José Javier

## Problema

El trabajo diario de Administración está repartido en varios lugares:
- «Documentos por revisar» en el menú.
- «Actas por confirmar», recién creada, como otra entrada del menú.
- Las instalaciones cerradas que esperan inspección no aparecen en ninguna lista: «Permisos e inspecciones» muestra las inspecciones registradas, no las que faltan por agendar.
- Los cobros por crear viven en Facturación.

Además, el cobro al programa no se hace solo: lo crea Administración o Contabilidad (`billing.submit`).

## Lo que ya existe

- `GET /documents/review-queue` (`DocumentsQueuePage`).
- `GET /acta-reviews/pending` (`ActaReviewQueuePage`).
- `billing/dashboard.py::_to_create`: la lista «Por cobrar» de Facturación (actas confirmadas sin cobro vivo y expediente sin cerrar).
- `inspections` con `result` (`pending`, `passed`, `failed`) y `scheduled_for`.

## Diseño

- **Una entrada de menú, «Por revisar»** (`/review`), con cuatro pestañas (`?tab=`). Cada pestaña se ve solo con su permiso, y la entrada del menú aparece si se tiene alguno de ellos.

| Pestaña | Permiso | Fuente | Enlace de cada fila |
|---|---|---|---|
| Documentos | `documents.review` | `/documents/review-queue` (existe) | `/cases/{id}/review` |
| Actas por confirmar | `checklists.approve` | `/acta-reviews/pending` (existe) | `/projects/{id}?paso=review` |
| Inspección municipal | `inspections.manage` | **`GET /inspection-queue`** (nuevo) | `/projects/{id}?paso=inspection` |
| Cobros por crear | `billing.submit` | **`GET /billing/to-create`** (nuevo, reusa `_to_create`) | `/projects/{id}?paso=billing` |

- **`GET /inspection-queue`**, paginado en la base. Lista los proyectos cerrados cuya última inspección no está aprobada:
  - estado `unscheduled` (sin inspección), `scheduled` (pendiente, con fecha) o `failed` (falló, hay que reagendar);
  - de la más vieja a la más nueva, por fecha de cierre, con días desde el cierre.
- **`GET /billing/to-create`**: la misma lista «Por cobrar» de Facturación, con la misma consulta, paginada en memoria (`paginate_list`) porque se calcula en Python. La pestaña lleva un enlace a Facturación para radicar y registrar pagos.
- `/documents` y `/acta-reviews` redirigen a su pestaña. Sale la entrada «Actas por confirmar» del menú.
- Facturación y Permisos e inspecciones quedan como están: son las vistas completas.

## Paquetes de Mateo

`field_ops` (cola de inspecciones) y `billing` (ruta `to-create`). Hay que avisarle.
