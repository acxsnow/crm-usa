# Campañas de productos por SMS y correo (módulo 7)

Fecha: 7 de octubre de 2026. Cadena B (Mateo). Pedido por el cliente el 7 oct.

- **Productos:** catálogo libre (`/products`): nombre, precio en texto, descripción.
- **Público:** el dueño elige libremente entre clientes del sistema y **contactos propios**
  (`marketing_contacts`), que se cargan pegando una lista o subiendo un CSV (nombre,
  teléfono y/o correo por línea). Filtros por programa, estado, búsqueda o selección a mano.
- **Canales:** SMS, correo o ambos. El correo lleva asunto.
- **Permiso (ley de EE. UU.):** solo sale a números con permiso de SMS (`marketing_consents`,
  TCPA) y a correos con permiso de correo (`email_marketing_consents`, CAN-SPAM), con fuente,
  fecha y quién lo registró. Al cargar contactos propios se registra su permiso con la fuente
  indicada y confirmación explícita.
- **Bajas:** cada SMS termina con «Responde STOP…»; el webhook de Masiv
  (`/api/v1/webhooks/masiv/inbound?token=MASIV_WEBHOOK_TOKEN`) registra STOP y START. Cada
  correo lleva la dirección postal, el enlace `/api/v1/unsubscribe/{token}` (público) y las
  cabeceras `List-Unsubscribe` (baja con un clic). Ninguna baja se deshace desde la oficina.
- **Horario de SMS:** de 8 a. m. a 9 p. m. en la zona del cliente (AZ → Phoenix; CA y NV →
  Los Ángeles). El correo sale de inmediato.
- **Envío:** tarea `campaigns.send_due` cada minuto; 3 intentos. Pruebas: SMS solo al celular
  propio registrado; correo solo al correo propio.
- **Proveedores (listos, solo falta configurar; ver `backend/.env.example`):**
  - SMS: Masiv (masivapp) con `SMS_PROVIDER=masiv`, `MASIV_USERNAME`, `MASIV_PASSWORD`.
    Masiv debe confirmar el registro 10DLC para EE. UU.
  - Correo: buzón nuevo `promociones@<dominio de Delta HVAC>` en Amazon SES (dominio verificado
    con DKIM/SPF/DMARC y fuera del sandbox), con `MARKETING_EMAIL_PROVIDER=smtp`,
    `MARKETING_EMAIL_FROM`, `MARKETING_SMTP_USERNAME/PASSWORD` y `MARKETING_POSTAL_ADDRESS`.
    Separado del Gmail de avisos (`EMAIL_*`).
- **Permiso de la app:** `notifications.manage`. Migraciones `0021` y `0022`.
  Pruebas: `tests/test_campaigns.py`.
