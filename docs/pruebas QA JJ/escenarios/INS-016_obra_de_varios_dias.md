# [INS-016] Obra de varios días con cuadrilla y ayudantes

## 1. Información general

- **ID:** INS-016
- **Módulo:** Instalación en campo
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Varias jornadas, cada una con su gente, suman bien en el diario y en el costo de mano de obra.

## 3. Precondiciones

- Una obra en curso de Miguel Torres (`tecnico05@demo-org.com`).

## 4. Datos de prueba

- Día 1: Miguel + 1 ayudante; día 2: Miguel + Pedro Vargas.

## 5. Procedimiento paso a paso

1. [ ] Registrar las dos jornadas.
2. [ ] Revisar el Diario de obra y el costo de mano de obra en Rentabilidad.

## 6. Resultado esperado

- Las dos jornadas con sus personas y horas; la mano de obra suma ambas.

## 7. Resultado obtenido

- Qué pasó: Por API, 7 de 7 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ El material del diario no puede salir de la bodega principal → 400 — `400 {"detail":"«QA 1025164900 Tubo cobre 3/8» solo puede salir de tu camioneta; lo de bodega se pide con una orden de salida`
  - ✔ El técnico registra la jornada con material de su camioneta
  - ✔ Lo de la camioneta descuenta; lo comprado en la obra solo se anota — `[{"id": "f521c2ce-c68b-4e1f-8823-300d0aaecf4f", "item_id": "f0441f61-835e-4d8a-b21f-c714e9403720", "item_name": "QA 1025164900 Tubo cobre 3/8", "sku": "QA102516`
  - ✔ La camioneta bajó de 20 a 14 ft
  - ✔ Una sola jornada por día y obra → 400 — `400 {"detail":"Esa obra ya tiene una jornada de ese día.","code":"day_log_date_taken","request_id":"a5497548-bf7f-4a56-b2aa-`
  - ✔ Gerencia lee el diario de la obra
  - ✔ El diario trae la jornada con su avance

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si un técnico no tiene tarifa aparece «Sin tarifa», no un costo inventado.

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
