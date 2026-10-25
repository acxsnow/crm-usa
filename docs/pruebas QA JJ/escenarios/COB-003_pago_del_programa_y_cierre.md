# [COB-003] El programa paga: expediente pagado y cerrado

## 1. Información general

- **ID:** COB-003
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 7 de 7 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Administración NO registra pagos (Contabilidad sí)
  - ✔ Contabilidad registra el pago
  - ✔ El expediente quedó «Pagado» — `paid`
  - ✔ Cerrar sin motivo se bloquea
  - ✔ Cierre administrativo con motivo
  - ✔ Expediente «Cerrado» — `closed`
  - ✔ El historial de etapas recorre el ciclo completo — `new_prospect,pending_approval,pending_approval,pending_approval,pending_approval,pending_approval,pending_approval,approved,permit_in_progress,ready_to_install,`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El reporte de tiempos muestra las 15 etapas recorridas con fechas reales (de `case_stage_events`).
- [ ] Un pago parcial deja el cobro abierto (probar con la mitad en otra obra si hay tiempo).

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
