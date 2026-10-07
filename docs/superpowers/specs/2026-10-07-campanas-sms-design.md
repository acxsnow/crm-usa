# Campañas de SMS de productos (módulo 7)

Fecha: 7 de octubre de 2026. Cadena B (Mateo). Pedido por el cliente el 7 oct.

- **Productos:** catálogo libre (`/products`): nombre, precio en texto, descripción.
- **Público:** el dueño elige libremente entre los clientes con teléfono (filtros por
  programa, estado, búsqueda o selección a mano).
- **Consentimiento (TCPA):** solo sale a números con permiso de mercadeo registrado
  (`marketing_consents`), con su fuente, fecha y quién lo registró; se registra en la misma
  pantalla con confirmación explícita. Los que no tienen permiso se excluyen al lanzar y se
  cuentan en el resumen.
- **Baja:** todo mensaje termina con «Responde STOP…». El webhook de Masiv
  (`POST /api/v1/webhooks/masiv/inbound?token=MASIV_WEBHOOK_TOKEN`) o el registro manual
  revocan el permiso y sacan el número de lo que esté en cola.
- **Horario:** de 8 a. m. a 9 p. m. en la zona del cliente (AZ → Phoenix; CA y NV → Los
  Ángeles); fuera de eso espera a las 8 a. m.
- **Envío:** tarea `campaigns.send_due` cada minuto; 3 intentos. Prueba a tu propio número.
  Sin `SMS_PROVIDER=masiv` queda en modo de prueba («No enviado»).
- **Permiso:** `notifications.manage`. Migración `0021`. Pruebas: `tests/test_campaigns.py`.

**Pendiente con Masiv:** confirmar el registro 10DLC de la marca y la campaña ante los
operadores de EE. UU. y la URL/formato del webhook de respuestas.
