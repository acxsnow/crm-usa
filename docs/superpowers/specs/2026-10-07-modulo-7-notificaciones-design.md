# Módulo 7: notificaciones

Fecha: 7 de octubre de 2026. Cadena B (Mateo). Aprobado en conversación el 7 oct.

- **Cola real:** `shared/events.emit()` → `notifications/dispatch.py` encola en Celery
  (`notifications.process_event`). El worker crea el aviso en la app (`notifications`)
  y un envío pendiente por canal (`notification_deliveries`). `notifications.deliver_pending`
  (cada minuto) envía con hasta 5 intentos espaciados (2, 4, 8, 16 min); luego queda «Falló»
  y se puede reenviar. `NOTIFICATIONS_DISPATCH=off` lo apaga (pruebas).
- **Quién recibe qué:** `catalog.py` y `service._resolve()`. Enviado a revisión → `cases.review`;
  devuelto, aprobado, rechazado, en espera → vendedor; instalación agendada y acta devuelta →
  técnico; cobro rechazado o pagado → `billing.submit`.
- **Alertas diarias** (14:00 UTC): expediente con más de N días hábiles en aprobación
  (N=3 por defecto) y permiso que vence en ≤7 días. Una sola vez por día/permiso (`dedupe_key`).
- **Plantillas:** texto por aviso y canal con variables `{{...}}`, editables y restaurables.
  El aviso en la app no se apaga.
- **Canales:** en la app siempre; correo por defecto; SMS si la persona lo activa con su celular.
  SMS en modo de prueba («No enviado») mientras `SMS_PROVIDER` no sea `masiv`. SMS al cliente
  final apagado hasta registrar su consentimiento.
- **Permisos:** avisos propios con `notifications.read_own` o `notifications.manage`;
  historial, plantillas y alertas con `notifications.manage`.
- Migración `0020`. Pruebas: `tests/test_notifications.py`.

**Para José:** `DashboardLayout.tsx` cambió una línea: el botón fijo de la campana ahora es
`<NotificationBell />`.
