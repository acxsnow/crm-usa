# [PAR-003] Registrar el pago de una factura (efectivo, cheque, transferencia)

## 1. Información general

- **ID:** PAR-003
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Antigüedad de cartera actualizada.

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
