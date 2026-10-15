# Contador de días en «Pendiente de aprobación» y botón «Revisar ahora»

Fecha: 14 de octubre de 2026. Cadena A (José). Toca un archivo del paquete de
Mateo (`notifications/router.py`, una ruta nueva y aditiva) y la pantalla de
Notificaciones: se le avisa antes de integrar.

Base: PDF `Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf` §3.1 («Seguimiento de
tiempos», referencia 2–3 días hábiles) y la etapa «Pendiente aprobación» de §7
(«con contador de días»); hueco G7 de `docs/validacion-pdf-vs-modulos.md`.

## Problema

El contador existe por dentro pero no se ve:

- El módulo 7 cuenta los días hábiles desde `submitted_at` y avisa a
  Administración al llegar al umbral (`case.approval_overdue`). El umbral se
  edita en Notificaciones → Alertas (`notification_settings.approval_alert_business_days`).
- La revisión corre una vez al día (14:00 UTC, Celery Beat). Cambiar el umbral
  no muestra nada hasta la revisión siguiente: en la revisión manual del 14 de
  octubre se puso 1 día y «no salía nada».
- Ni la tarjeta del tablero ni la cola «Documentos por revisar» muestran cuántos
  días lleva el expediente esperando.

## Decisiones (14 oct, con José)

| Pregunta | Respuesta |
|---|---|
| Quién ve el contador | Todos los que ven el tablero o la cola, también el vendedor con sus propios expedientes |
| Cómo se ve | Gris («2 días hábiles»); desde el umbral, rojo («4 días hábiles · límite 3») |
| Quién usa «Revisar ahora» | Quien ve la pestaña Alertas: Administrador y Administración (`notifications.manage`) |

## Diseño

### 1. Los días los calcula el servidor

Una sola regla, la misma de la alerta, para que la tarjeta y el aviso nunca
digan cosas distintas:

- Solo expedientes en `pending_approval` con `submitted_at`. Para el resto
  `approval_wait` va en `null`.
- `business_days` = `notifications.service.business_days_between(
  local_date(submitted_at, zona_de_la_org), hoy_de_la_org)`. Lunes a viernes,
  sin feriados (igual que la alerta; los feriados siguen siendo pregunta 17 al
  cliente).
- `overdue` = `business_days >= umbral` con el umbral de
  `notifications.service.get_settings_row()`, el mismo `>=` de `daily_alerts`.
- `limit` = el umbral, para que la pantalla escriba «límite 3» sin
  pedir los ajustes (el vendedor no tiene `notifications.manage`).
- La devolución al vendedor no reinicia la cuenta: `submitted_at` no cambia
  (contrato `docs/contratos/case.md`).
- Tampoco la reinicia el reenvío después de un **rechazo**: `transition()` solo
  escribe la fecha hito la primera vez que se entra a la etapa
  (`cases/service.py`, `STAGE_MILESTONE`). Un expediente rechazado, corregido y
  reenviado muestra los días desde el **primer** envío, igual que hoy cuenta la
  alerta. Se deja así a propósito: cambiarlo movería también la alerta y el
  reporte de «días hasta la aprobación». Si el cliente quiere contar desde el
  reenvío, es un cambio aparte.
- «En espera del programa» (`on_hold`) no lleva contador: la alerta tampoco lo
  cuenta, porque la espera es del programa y no de Administración.

Los tres datos viajan juntos en un objeto `approval_wait`
(`{"business_days": 4, "overdue": true, "limit": 3}`, o `null`), calculado por
un solo módulo nuevo `cases/approval_clock.py`:

- `async def wait_context(db, organization_id)` → zona, hoy y umbral de la
  organización (tres consultas por respuesta, no por tarjeta).
- `def approval_wait(case, ctx) -> dict | None`.

Se agrega a tres respuestas, sin cambiar lo que ya traen (campo nuevo):

- `GET /case-board` (`cases/intake.py::board`): cada tarjeta.
- `GET /documents/review-queue` (`cases/documents.py::review_queue`): cada fila.
- `GET /cases/{id}/form` (`cases/intake.py`, la que usan la revisión de
  Administración y el formulario del vendedor): nivel superior.

Zona y «hoy» con `field_ops.clock.org_zone()` / `org_today()`. Se reutilizan
las funciones de Mateo sin cambiarlas (solo se importan).

### 2. La pantalla

- **Tablero** (`CasesBoardPage.tsx`): en las tarjetas de «Pendiente de
  aprobación», una línea `⏱ N días hábiles` en gris; con `overdue`, en
  rojo y `⏱ N días hábiles · límite L`. «1 día hábil» en singular. Con 0 días:
  «Enviado hoy».
- **Cola** (`DocumentsQueuePage.tsx`): el mismo chip junto a «enviado …». La
  cola ya ordena del más antiguo al más nuevo, así que los rojos quedan arriba.
- **Revisión del expediente** (`CaseReviewPage.tsx`): en el encabezado, debajo
  de la fecha de «Enviado» (pedido en la revisión manual del 14 de octubre).
- Un componente pequeño compartido (`features/sales/ApprovalDays.tsx`) pinta el
  chip en los tres lugares.

### 3. «Revisar ahora»

- `POST /notifications/alerts/run` (permiso `notifications.manage`): corre
  `daily_alerts()` para la organización del token y devuelve `{"created": N}`.
  Ruta nueva en `notifications/router.py`; no cambia nada de lo existente.
- No duplica avisos: `daily_alerts` ya usa `dedupe_key` por expediente y por
  día (`approval_overdue:{case}:{fecha}`), y por permiso o factura en los demás.
- Pestaña **Alertas**: botón **Revisar ahora** junto a Guardar. Al terminar:
  «Se crearon N avisos» o «No había nada nuevo para avisar». Cambiar el umbral y
  tocar el botón muestra el efecto en el momento.

## Fuera de alcance

Feriados, umbral por programa, días por cada fase del expediente y contar en
`on_hold`. Requieren respuesta del cliente (pregunta 17).

## Pruebas

- `approval_wait` en board, cola y formulario: un expediente enviado hace 0, 2 y 4 días hábiles con umbral 3 →
  días 0/2/4 y `overdue` falso/falso/verdadero; uno fuera de
  `pending_approval` → `null`. Un fin de semana en medio no cuenta.
- Devolver no cambia los días.
- El vendedor recibe los campos en su propio expediente.
- `POST /notifications/alerts/run`: crea el aviso de un expediente demorado;
  correrlo dos veces el mismo día no duplica; sin `notifications.manage` → 403;
  solo revisa la organización del token.
- Navegador: tarjeta gris y roja, cola con el chip, botón con su mensaje y el
  aviso en la campana.

## Riesgos

- `business_days_between` recorre día por día: con expedientes de meses es un
  bucle corto (días hábiles ≤ ~260 por año) y solo para la página visible del
  tablero. Aceptable.
- Importar de `notifications` desde `cases` crea una dependencia de Cadena A a
  Cadena B. No hay ciclo: `notifications.service` y `field_ops.clock` no
  importan `cases` al cargar, así que los imports van al inicio del archivo.
