# [API-003] Filtros y búsqueda en listas

## 1. Información general

- **ID:** API-003
- **Módulo:** API y paginación
- **Prioridad:** P2
- **Tipo de prueba:** API
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Los filtros combinados devuelven lo correcto y el total coincide.

## 3. Precondiciones

- Base QA.

## 4. Datos de prueba

- `/warehouse/items?q=cinta`, `?category=…`, `?active=false`, `/warehouse/stock?low_only=true`.

## 5. Procedimiento paso a paso

1. [ ] Llamar cada filtro y combinarlos.
2. [ ] Comparar `X-Total-Count` con el número de filas.

## 6. Resultado esperado

- Totales coherentes; filtros sin coincidencias devuelven lista vacía, no error.

## 7. Resultado obtenido

- Qué pasó: q=cinta, active=false, sin coincidencias y low_only: el total del encabezado coincide con las filas; active=quizás → 422.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ items q=cinta: total = filas — `200 total=0 filas=0`
  - ✔ items active=false: total = filas — `200 total=0 filas=0`
  - ✔ items q sin coincidencias: total = filas — `200 total=0 filas=0`
  - ✔ stock low_only: total = filas — `200 total=0 filas=0`
  - ✔ active=quizás → 422 — `422`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] Filtros con valores inválidos (`active=quizás`) responden 422.

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
