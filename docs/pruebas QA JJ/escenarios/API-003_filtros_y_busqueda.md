# [API-003] Filtros y búsqueda en listas

## 1. Información general

- **ID:** API-003
- **Módulo:** API y paginación
- **Prioridad:** P2
- **Tipo de prueba:** API
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Filtros con valores inválidos (`active=quizás`) responden 422.

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
