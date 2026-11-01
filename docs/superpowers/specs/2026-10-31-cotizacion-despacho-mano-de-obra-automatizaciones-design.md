# Cotización por enlace, despacho, mano de obra por horas y campañas automáticas

Fecha: 31 de octubre de 2026. Autor: Mateo Mazo. Cierra lo que faltaba de cuatro filas de `Housecall Pro: qué ya cubrimos y qué no`. La contabilidad para reemplazar QuickBooks queda fuera de este trabajo, por decisión de Mateo.

## Cotización que llega al cliente (`billing/quote_links.py`, `billing/quotes.py`)

- Opciones tipo básica / mejor / premium: `Quote.options` (de 2 a 4) y `QuoteLine.option_key`. Una línea sin opción va en todas; cada opción necesita al menos una línea propia.
- Enlace público `/cotizacion/:token`: se guarda solo el hash del token. Generar otro enlace apaga el anterior, y ajustar la cotización (versión nueva) también.
- El cliente ve, elige, firma y acepta, o rechaza con motivo. Se guardan nombre, firma, IP y `decided_by`. La oficina recibe un aviso (`quote.customer_accepted`, `quote.customer_rejected`).
- Al aceptar, por el enlace o desde la oficina, nace la factura en borrador con las líneas de la opción elegida y, si la cotización no colgaba de una obra, nace la obra por agendar. Nada de esto mueve el expediente.
- Rutas públicas con límite de 60 peticiones por minuto por IP.

## Despacho (`field_ops/board.py`, `GET /dispatch/board`)

- Fila por técnico y columna por día (hasta 31 días), con su turno de la malla y una bandeja de obras sin técnico o sin fecha. Pantalla `/dispatch` con vista de día y de semana.
- Solo lee. Mover una obra usa `PATCH /projects/{id}/schedule`, con sus reglas de siempre. Permiso `dispatch.manage`.

## Mano de obra desde las horas aprobadas (`warehouse/labor.py`)

- Tarifa por hora por técnico (`LaborRate`). Sin tarifa, esa persona no suma por horas: es el caso de quien cobra por trabajo y se anota a mano.
- Las horas salen de las marcas del turno: de «en camino» o «llegué» hasta «salí» (o la siguiente obra, o el fin del turno). El viaje cuenta.
- Solo turnos aprobados. Si lo aprobado es menos que lo marcado, se reparte en proporción. No aplica recargo de horas extras: la tarifa es plana.
- Suma a `labor` en `project_actual_costs`, y de ahí al costo del trabajo y a la rentabilidad.

## Campañas automáticas por evento (`notifications/automations.py`)

- Dos eventos: al cerrar la obra y recordatorio de mantenimiento. Los dos salen N días después de `completed_date`.
- Usan la cola de campañas, con sus reglas: permiso de mercadeo, horario del cliente, STOP y baja. Cada automatización tiene una campaña contenedora en estado `auto`, que no aparece en la lista de campañas.
- Una obra se procesa una sola vez. Solo cuentan las cerradas desde que se activó la automatización. Límite conocido: una persona recibe cada automatización una sola vez por canal, aunque tenga dos obras.
- Celery la corre cada hora (`campaigns.run_automations`). El envío real de SMS depende de las credenciales de Masiv, que siguen en trámite.
