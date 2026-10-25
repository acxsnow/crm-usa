# [API-001] Paginación: límite por defecto, máximo y total

## 1. Información general

- **ID:** API-001
- **Módulo:** API y paginación
- **Prioridad:** P0
- **Tipo de prueba:** API · rendimiento
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Ningún listado devuelve todo de una vez: 100 por defecto, 500 como máximo y el total en `X-Total-Count`.

## 3. Precondiciones

- Base QA (245 artículos).

## 4. Datos de prueba

- `http://localhost:8000/api/v1/warehouse/items`.

## 5. Procedimiento paso a paso

1. [ ] Llamar sin parámetros: contar filas y leer `X-Total-Count`.
2. [ ] Con `limit=500`, `limit=501`, `limit=0` y `limit=-1`.
3. [ ] Con `offset=200&limit=100` y `offset=10000`.
4. [ ] Recorrer las páginas en la pantalla de Artículos.

## 6. Resultado esperado

- 100 filas y total 245; 501, 0 y -1 responden 422; offset 200 trae 45; offset 10000 trae lista vacía.
- La pantalla muestra 245 en total y pasa de página sin repetir ni saltar.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `tests/test_pagination_everywhere.py` pasa (todas las listas paginan, salvo las 3 excepciones documentadas).

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
