# [API-001] Paginación: límite por defecto, máximo y total

## 1. Información general

- **ID:** API-001
- **Módulo:** API y paginación
- **Prioridad:** P0
- **Tipo de prueba:** API · rendimiento
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Ningún listado devuelve todo de una vez: 100 por defecto, 500 como máximo y el total en `X-Total-Count`.

## 3. Precondiciones

- Base QA (244 artículos de la demo).

## 4. Datos de prueba

- `http://localhost:8000/api/v1/warehouse/items`.

## 5. Procedimiento paso a paso

1. [ ] Llamar sin parámetros: contar filas y leer `X-Total-Count`.
2. [ ] Con `limit=500`, `limit=501`, `limit=0` y `limit=-1`.
3. [ ] Con `offset=200&limit=100` y `offset=10000`.
4. [ ] Recorrer las páginas en la pantalla de Artículos.

## 6. Resultado esperado

- 100 filas y total 244; 501, 0 y -1 responden 422; offset 200 trae 44; offset 10000 trae lista vacía.
- La pantalla muestra 244 en total y pasa de página sin repetir ni saltar.

## 7. Resultado obtenido

- Qué pasó: Sin parámetros trae 100 filas y `X-Total-Count: 244`; limit=500 → 200; 501, 0 y -1 → 422; offset=200 trae 44; offset=10000 trae lista vacía; las 3 páginas suman 244 ids sin repetir.
- Diferencias con lo esperado: El escenario decía 245 y «offset 200 trae 45»: son 244 y 44 en la demo (corregido el texto). Falta el paso 4 en pantalla.
- Comprobaciones por API (8 de 8):
  - ✔ sin parámetros: 100 filas y X-Total-Count — `filas=100 total=244 · 56 ms`
  - ✔ limit=500 → 200 — `200 filas=244`
  - ✔ limit=501 → 422 — `422 filas=-`
  - ✔ limit=0 → 422 — `422 filas=-`
  - ✔ limit=-1 → 422 — `422 filas=-`
  - ✔ offset=200 trae las 44 restantes — `44`
  - ✔ offset=10000 trae lista vacía — `200`
  - ✔ recorrer las páginas: 244 ids sin repetir — `244/244`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- Artículos muestra «1–25 de 244» y pasar de página trae otras filas, sin repetir.
- Comprobaciones (2 de 2):
  - ✔ Artículos muestra 244 en total — `['1–25 de 244']`
  - ✔ Pasar de página trae otras filas (sin repetir) — `['4-in-1 Condenser Fan Motor 1/6', 'AA Battery Sold Individually\nR', 'AAA Battery Sold Individually\n'] / ['Bit-Tip Screw Hex-Head 8-18 x '`
- Capturas:
  - [pagina-2.jpg](../evidencias/pantalla/API-001/pagina-2.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] `tests/test_pagination_everywhere.py` pasa (todas las listas paginan, salvo las 3 excepciones documentadas).

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
