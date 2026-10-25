# [API-002] Orden estable entre páginas

## 1. Información general

- **ID:** API-002
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Las páginas no repiten ni pierden filas cuando hay empates.

## 3. Precondiciones

- Base QA.

## 4. Datos de prueba

- Movimientos de bodega (244 creados en el mismo segundo por la carga).

## 5. Procedimiento paso a paso

1. [ ] Bajar `/warehouse/movements` en páginas de 50 hasta el final.
2. [ ] Comparar los ids.

## 6. Resultado esperado

- 244 ids distintos, ninguno repetido.

## 7. Resultado obtenido

- Qué pasó: Al bajar `/warehouse/movements` en páginas de 50 llegan 244 filas pero solo 243 ids distintos: un movimiento sale dos veces y otro no sale.
- Diferencias con lo esperado: El orden es `movement_date desc, created_at desc` sin desempate por id; los 244 movimientos de la carga tienen la misma fecha y casi la misma hora, y Postgres los devuelve en distinto orden en cada página.
- Reejecución (25 oct, tras corregir D-003, base QA reiniciada): 244 filas y 244 ids distintos en páginas de 50. Aprobado.
- Comprobaciones por API (0 de 1):
  - ✘ movimientos en páginas de 50: 244 ids distintos — `244 filas, 243 distintas`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El orden incluye un desempate por id.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-003 | Movimientos de bodega: el orden no tiene desempate y la paginación repite y omite filas | P1 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
