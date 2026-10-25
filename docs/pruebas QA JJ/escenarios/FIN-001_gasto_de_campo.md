# [FIN-001] Gasto de campo: enviar, aprobar y rechazar

## 1. Información general

- **ID:** FIN-001
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El técnico registra sus gastos con comprobante y Contabilidad los aprueba o rechaza.

## 3. Precondiciones

- Sesión de Tito y de contabilidad.

## 4. Datos de prueba

- Gasolina USD 45.20 «Ej.: gasolina ida y vuelta a Sunrise Park» con foto del recibo; Hotel USD 89.00 sin comprobante.

## 5. Procedimiento paso a paso

1. [ ] Como Tito, **Mis gastos** › registrar y **Enviar gasto** (los dos).
2. [ ] Como contabilidad, aprobar el primero y rechazar el segundo con motivo.
3. [ ] Como Tito, ver el resultado.

## 6. Resultado esperado

- «Gasto enviado a revisión.»; el aprobado suma al costo de su obra; el rechazado muestra el motivo.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Tito no ve los gastos de otros técnicos.

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
