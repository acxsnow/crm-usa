# [COB-003] El programa paga: expediente pagado y cerrado

## 1. Información general

- **ID:** COB-003
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Registrar el pago cierra el ciclo completo del expediente.

## 3. Precondiciones

- COB-001 (o COB-002) radicado.

## 4. Datos de prueba

- Pago por el valor completo, cheque `CHK-10442`.

## 5. Procedimiento paso a paso

1. [ ] Registrar el pago con el número del cheque.
2. [ ] Abrir el expediente y la obra.
3. [ ] Revisar el reporte de tiempos (Reportes).

## 6. Resultado esperado

- Cobro «Pagado por el programa»; expediente «Pagado» y luego cerrado según la regla.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El reporte de tiempos muestra las 15 etapas recorridas con fechas reales (de `case_stage_events`).
- [ ] Un pago parcial deja el cobro abierto (probar con la mitad en otra obra si hay tiempo).

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
