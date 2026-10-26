# [PAR-003] Registrar el pago de una factura (efectivo, cheque, transferencia)

## 1. Información general

- **ID:** PAR-003
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Pagos parciales y totales dejan el saldo exacto.

## 3. Precondiciones

- Una factura emitida de USD 500.00.

## 4. Datos de prueba

- Abono de 200.00 en efectivo y 300.00 por transferencia; un tercer intento de 0.01.

## 5. Procedimiento paso a paso

1. [ ] Registrar el primer abono.
2. [ ] Registrar el segundo.
3. [ ] Intentar el tercero.

## 6. Resultado esperado

- Saldo 300.00 y luego 0 («Factura pagada»).
- No permite pagar de más.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 4 de 5 comprobaciones bien. Abonos de 200.00 (efectivo) y 300.00 (transferencia): saldo 300.00 y luego 0 con «Factura pagada». Un pago de 0.01 de más se aceptaba y dejaba saldo negativo: D-015, corregido y reejecutado.
- Diferencias con lo esperado: Ninguna después de corregir D-015.
- Comprobaciones por API (4 de 5):
  - ✘ Pagar 0.01 de más se rechaza [encontró D-015; corregido y reejecutado abajo] — `201 {"id":"72f0fd01-266a-44f7-bbc1-1a4aa67d7799","kind":"particular","project_id":null,"case_id":null,"customer_id":"c758854c-2f26-4571-b705-64917885b8d3"`
  - ✔ Abono de 200.00 en efectivo: saldo 300.00 — `300.0 partial`
  - ✔ Abono de 300.00 por transferencia: saldo 0 y «Factura pagada» — `0.0 paid`
  - ✔ Pagar 0.01 de más se rechaza (D-015) — `400 {"detail":"El pago supera el saldo de la factura (USD 0.00).","code":"payment_exceeds_balance","request_id":"e318482e-8ae2-459d-9086-370633ef9c5b"}`
  - ✔ El saldo sigue en 0 — `0.0`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Antigüedad de cartera actualizada.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-015 | Una factura acepta pagos por encima del saldo | P1 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
