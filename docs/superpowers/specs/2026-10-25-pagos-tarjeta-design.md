# Pagos con tarjeta y gastos de tarjeta · Diseño

Fecha: 25 oct 2026 · Autor: Mateo Mazo · Estado: **propuesta, pendiente de aprobación**

## Por qué

El cliente quiere dejar Housecall Pro y QuickBooks. Las dos cosas que hoy le dan esos sistemas y aquí no existen:

1. **Cobrar al dueño de casa con tarjeta o con un enlace de pago** (Housecall Pro). Hoy los pagos del trabajo particular se registran a mano.
2. **Vincular la tarjeta y la cuenta de la empresa para que los gastos lleguen solos** y se clasifiquen (el «bank feed» de QuickBooks). Hoy los gastos se cargan a mano con recibo, y la conciliación se hace subiendo un CSV del banco.

El 22 oct el cliente dijo que no usaba «cobro con tarjeta y enlaces de pago». Ahora lo pide, así que pasa de «No lo usan» a pendiente real.

## Alcance

| Parte | Qué resuelve | Proveedor recomendado |
| --- | --- | --- |
| A · Cobro al cliente | Tarjeta y transferencia bancaria (ACH) desde un enlace o un código QR; anticipos; reembolsos | Stripe (Checkout y Payment Links) |
| B · Gastos de tarjeta | Las compras de las tarjetas y cuentas de la empresa llegan solas para clasificarlas por obra | Plaid (Transactions) |
| C · Opcional, después | Cobro presencial con el celular del técnico (Tap to Pay) y tarjetas propias para cada técnico | Stripe Terminal · Stripe Issuing |

Fuera de alcance: la contabilidad general (plan de cuentas y estados financieros), que va en su propio diseño. Este diseño la alimenta.

El cobro a los programas de rebate no cambia: los programas pagan por cheque o transferencia y siguen por el flujo de cobro actual.

## A · Cobro al cliente con Stripe

**Flujo**

1. En una factura del trabajo particular con saldo, Administración o el técnico toca «Cobrar con tarjeta».
2. El sistema crea una sesión de pago de Stripe por el saldo, o por un monto parcial si es anticipo (por ejemplo, 50 % al empezar).
3. El enlace sale al cliente por correo y SMS, con los avisos que ya existen. En la obra se muestra como código QR en el celular.
4. El cliente paga en la página de Stripe con tarjeta, Apple Pay o Google Pay, o con su cuenta bancaria (ACH).
5. Stripe avisa al sistema por un webhook firmado. El sistema registra el pago en la factura (método, referencia y comisión), y la factura queda «Pagada» o «Pago parcial» sola.
6. Los reembolsos y las disputas también llegan por webhook. Un reembolso queda como pago negativo con su motivo, y una disputa genera un aviso a Contabilidad.
7. Cada depósito de Stripe al banco llega como un movimiento ya conciliado contra sus pagos. La comisión de Stripe queda registrada como gasto financiero.

**Reglas**

- Ningún dato de tarjeta pasa por nuestros servidores: el cliente paga en la página de Stripe (PCI SAQ A, el nivel más simple).
- Las llaves van en variables de entorno (`STRIPE_SECRET_KEY` y `STRIPE_WEBHOOK_SECRET`) y nunca se guardan en el repositorio. El webhook valida la firma y es idempotente por el id del evento.
- Permisos: crear un enlace pide `invoices.record_payment`. El técnico puede generarlo solo para las obras que trabaja.
- Un enlace vence a las 24 horas o cuando la factura cambia de saldo. Se puede reenviar.
- Sin llaves configuradas, el botón no aparece y todo sigue como hoy.

**Datos nuevos:** `payment_links` (factura, monto, estado, id de Stripe, quién lo creó, vencimiento) y `payment_events` (eventos del webhook ya procesados). En `InvoicePayment` se agregan el proveedor, la referencia externa y la comisión.

## B · Gastos de tarjeta con Plaid

**Flujo**

1. Contabilidad conecta cada tarjeta de crédito y cuenta bancaria de la empresa con Plaid Link (Chase, Amex, Bank of America, etc.). El usuario entra a su banco en la ventana de Plaid; el sistema nunca ve su clave.
2. Cada mañana, y cuando Plaid avisa por webhook, el sistema trae las transacciones nuevas.
3. Las compras de tarjeta llegan a una bandeja «Por clasificar» con comercio, monto, fecha y la última cifra de la tarjeta.
4. El sistema propone la coincidencia:
   - con un gasto que el técnico ya subió con foto del recibo (mismo monto y fecha cercana);
   - con una salida de bodega o una factura de proveedor ya pagada.
5. Contabilidad confirma o asigna obra, categoría y persona. Lo asignado a una obra entra solo al costo del trabajo y a la rentabilidad.
6. Los movimientos de la cuenta bancaria alimentan la conciliación sin subir CSV. Los depósitos de Stripe se marcan solos.

**Reglas**

- El token de acceso de Plaid se guarda cifrado (llave en variable de entorno) y solo lo usa el servidor.
- Permisos: conectar cuentas pide `payables.manage`; clasificar pide `expenses.approve`. El técnico no ve las cuentas de la empresa.
- Nada se cuenta dos veces. Una compra que coincide con un gasto ya registrado queda enlazada a él, no como un gasto nuevo.
- Desconectar una cuenta deja de traer datos y conserva lo ya clasificado.

**Datos nuevos:** `bank_connections` (institución, cuentas y token cifrado) y `bank_transactions` (transacción de Plaid, estado de clasificación, gasto, obra o pago enlazado).

## C · Opcional, después

- **Tap to Pay (Stripe Terminal):** el técnico cobra acercando la tarjeta a su celular, sin lector. Requiere una app nativa o el lector de Stripe; la web no puede leer tarjetas.
- **Tarjetas por técnico (Stripe Issuing):** cada técnico tiene su tarjeta con límite; cada compra llega al instante con el técnico ya identificado y le pide la foto del recibo. Es lo que hacen Ramp o Brex, y reemplazaría los reembolsos. Requiere aprobación de Stripe.

## Costos (precios públicos de Stripe para EE. UU.; Plaid sin tarifa pública)

| Concepto | Costo | Nota |
| --- | --- | --- |
| Tarjeta en línea (Stripe) | 2,9 % + US$ 0,30 por pago | Tarjeta internacional +1,5 % |
| Transferencia bancaria ACH (Stripe) | 0,8 %, máximo US$ 5 por pago | Conviene en trabajos grandes: un pago de US$ 8.000 cuesta US$ 5 en vez de unos US$ 232 con tarjeta |
| Payment Links (Stripe) | Sin cargo adicional | |
| Tarjeta presente (Terminal) | 2,7 % + US$ 0,05 | Solo si se hace la parte C |
| Plaid Transactions | Por cuenta conectada al mes; tarifa no publicada | Confirmar con Plaid. Referencias de terceros hablan de centavos a pocos dólares por conexión al mes |

Fuentes: [precios de Stripe](https://stripe.com/pricing); para Plaid, [Capterra](https://www.capterra.com/p/174384/Plaid/pricing/) y [CostBench](https://costbench.com/software/api-management/plaid/), sin tarifa oficial.

## Plan

| Fase | Contenido | Esfuerzo |
| --- | --- | --- |
| 1 | Stripe: enlace de pago y QR, webhook, pagos parciales y anticipos, reembolsos, comisión registrada | M · 1 a 1,5 semanas |
| 2 | Plaid: conectar cuentas, traer transacciones, bandeja «Por clasificar», coincidencias con gastos | M · 1,5 a 2 semanas |
| 3 | Conciliación automática con depósitos de Stripe y movimientos del banco | S · 3 a 4 días |
| 4 (opcional) | Tap to Pay y tarjetas por técnico | Por definir |

Todo se construye y prueba en modo de prueba de Stripe y en el sandbox de Plaid, sin dinero real.

## Lo que se necesita del cliente

1. **Cuenta de Stripe** a nombre de Delta HVAC Service Inc. (EIN, cuenta bancaria para depósitos y representante legal). Se abre en minutos y la verificación tarda de 1 a 3 días.
2. **Cuenta de Plaid** con acceso de producción. Plaid revisa la solicitud, y puede tardar días.
3. **Qué tarjetas y bancos** usa la empresa y quién las clasifica.
4. **Si se cobra la comisión al cliente:** en California el recargo por tarjeta tiene reglas propias; recomendamos absorberla o ofrecer ACH en trabajos grandes.
5. **Si quieren anticipos:** qué porcentaje, por ejemplo 50 / 30 / 20 como en Housecall Pro.

## Criterios de aceptación

- Un cliente paga una factura desde el enlace en modo de prueba, y la factura queda «Pagada» sin que nadie toque nada.
- Un anticipo del 50 % deja la factura en «Pago parcial» con el saldo correcto.
- Reenviar el mismo evento del webhook no duplica el pago, y un webhook sin firma válida responde 400.
- Una compra de tarjeta del sandbox de Plaid aparece en «Por clasificar». Al asignarla a una obra, sube el costo real de esa obra una sola vez.
- Ningún número de tarjeta ni clave bancaria queda en la base de datos ni en los registros.
- Pruebas de permisos y de aislamiento entre organizaciones para cada ruta nueva.
