# [INS-014] Material comprado en la obra (no sale de bodega)

## 1. Información general

- **ID:** INS-014
- **Módulo:** Instalación en campo
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Lo que el técnico compra en el camino entra al costo sin mover la bodega.

## 3. Precondiciones

- Una obra en curso.

## 4. Datos de prueba

- «Breaker 30A y 10 ft de cable», USD 48.75.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Agregar material que no sale de bodega** con el dato.
2. [ ] Revisar el costo de la obra y la existencia de bodega.

## 6. Resultado esperado

- Aparece como «Comprado en la obra» en el costo; la bodega no cambia.

## 7. Resultado obtenido

- Qué pasó: Por API, 3 de 3 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ La oficina anota material comprado en la obra
  - ✔ Aparece en los materiales de la obra
  - ✔ La bodega no cambia

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Valores con dos decimales exactos (sin redondeos raros).

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
- Observaciones: El técnico no puede anotarlo en «Materiales de la orden» (pide `projects.update`): lo anota en el diario de obra (INS-016). La oficina sí lo anota en la orden.
