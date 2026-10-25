# [PAR-004] Cobrar en línea con tarjeta (Stripe, modo prueba)

## 1. Información general

- **ID:** PAR-004
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P1
- **Tipo de prueba:** Integración
- **Estado:** Bloqueado (faltan llaves de prueba de Stripe/Plaid)
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El enlace de pago cobra con tarjeta de prueba y marca la factura pagada por el aviso de Stripe.

## 3. Precondiciones

- Llaves de prueba de Stripe en `backend/.env` (pedirlas a Mateo).
- Una factura emitida.

## 4. Datos de prueba

- Tarjeta de prueba 4242 4242 4242 4242; tarjeta rechazada 4000 0000 0000 0002.

## 5. Procedimiento paso a paso

1. [ ] **Cobrar en línea**: generar el **Enlace de pago** y el código QR.
2. [ ] Pagar con la tarjeta rechazada.
3. [ ] Pagar con la tarjeta buena.
4. [ ] Anular un enlace y abrirlo.

## 6. Resultado esperado

- Rechazada: la factura sigue abierta.
- Buena: queda pagada sin intervención.
- El enlace anulado dice «Enlace anulado».

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo roles con `payments.collect` ven el botón.
- [ ] Anticipo según el porcentaje configurado (pendiente de definir con el cliente).

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
