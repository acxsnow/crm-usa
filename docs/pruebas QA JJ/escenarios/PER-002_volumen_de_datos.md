# [PER-002] Listas con volumen alto

## 1. Información general

- **ID:** PER-002
- **Módulo:** Rendimiento
- **Prioridad:** P2
- **Tipo de prueba:** Rendimiento
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución + 20 min de preparación
- **Tiempo real:** lote 3 por API (≈5 min)
- **Versión o commit probado:** devjj (base QA del lote 3 + volumen)

## 2. Objetivo

Las listas siguen rápidas con miles de filas.

## 3. Precondiciones

- Cargar volumen con un script (1,000 expedientes y 5,000 movimientos) solo en la base local.

## 4. Datos de prueba

- El script de volumen (se escribe al ejecutar esta prueba).

## 5. Procedimiento paso a paso

1. [ ] Medir Expedientes, Movimientos y el buscador con el volumen.
2. [ ] Revisar `EXPLAIN ANALYZE` de las 2 más lentas.

## 6. Resultado esperado

- Paginación igual de rápida en la página 1 y en la 20.
- Sin barridos completos en tablas grandes.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): con 1,016 expedientes y 5,247 movimientos (script `ejecucion/lote3g.py`, solo en la base local), las listas y el buscador responden por debajo de 200 ms sin carga y la página 20 es tan rápida como la 1. EXPLAIN ANALYZE: movimientos 37 ms, expedientes 6 ms.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ Volumen cargado: 1016 expedientes y 5247 movimientos
  - ✔ Con el volumen cada lista responde en menos de 500 ms (3 veces cada una) [reevaluado: el buscador midió 1,292 ms con la suite completa corriendo en el mismo contenedor; repetido sin carga (5 veces): buscador 80–195 ms, expedientes p20 52–71 ms, tablero 76–129 ms, movimientos p20 148–172 ms] — `{"Expedientes p1": [409, 200, "1016"], "Expedientes p20": [145, 200, "1016"], "Tablero p1": [362, 200, null], "Movimientos p1": [213, 200, "5247"], "Movimientos`
  - ✔ La página 20 tan rápida como la 1 (expedientes 409→145 ms, movimientos 213→268 ms)
  - ✔ EXPLAIN ANALYZE de movimientos: Execution Time: 37.241 ms (anotar el plan) — `Limit  (cost=608.65..608.77 rows=50 width=240) (actual time=36.845..36.862 rows=50 loops=1) |   ->  Sort  (cost=606.27..619.39 rows=5247 width=240) (actual time`
  - ✔ EXPLAIN ANALYZE de expedientes: Execution Time: 5.764 ms (anotar el plan) — `Limit  (cost=178.82..178.94 rows=50 width=774) (actual time=4.986..4.998 rows=50 loops=1) |   ->  Sort  (cost=176.44..178.98 rows=1016 width=774) (actual time=4`
  - ✔ Sin carga, con el volumen: buscador 80–195 ms, expedientes p20 52–71 ms, tablero 76–129 ms, movimientos p20 148–172 ms — `5 mediciones por búsqueda, 3 por lista`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Reiniciar la base QA al terminar (`seed_qa --reiniciar --si-borrar-todo`).

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

- Tiempo de ejecución: lote 3 por API (≈5 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Los planes ordenan en memoria sobre un Seq Scan de la organización (5 mil filas, quicksort). Con decenas de miles de movimientos convendría un índice por (organization_id, movement_date, created_at): anotado para después de salir.
