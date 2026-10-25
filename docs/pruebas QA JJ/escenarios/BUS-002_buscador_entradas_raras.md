# [BUS-002] Buscador con entradas raras

## 1. Información general

- **ID:** BUS-002
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad · validación
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

El buscador no se rompe ni expone datos con caracteres especiales.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- `%`, `_`, `' OR 1=1 --`, `<script>alert(1)</script>`, 300 caracteres, emojis, «Ñandú».

## 5. Procedimiento paso a paso

1. [ ] Buscar cada uno.

## 6. Resultado esperado

- Sin errores; `%` y `_` no devuelven todo; el script se muestra como texto.

## 7. Resultado obtenido

- Qué pasó: El buscador responde sin errores a `%`, `_`, `' OR 1=1 --`, script, 300 caracteres, emojis, «Ñandú» y `DROP TABLE` (200 o 422, nunca 500).
- Diferencias con lo esperado: Falta ver en pantalla que el script se muestra como texto.
- Comprobaciones por API (8 de 8):
  - ✔ buscador «%» sin 500 — `200 resultados=0 · 51 ms`
  - ✔ buscador «_» sin 500 — `200 resultados=0 · 30 ms`
  - ✔ buscador «' OR 1=1 --» sin 500 — `200 resultados=0 · 216 ms`
  - ✔ buscador «<script>alert(1)</script>» sin 500 — `200 resultados=0 · 120 ms`
  - ✔ buscador «xxxxxxxxxxxxxxxxxxxxxxxxx» sin 500 — `422 resultados=- · 63 ms`
  - ✔ buscador «🔧🔥» sin 500 — `200 resultados=0 · 71 ms`
  - ✔ buscador «Ñandú» sin 500 — `200 resultados=0 · 137 ms`
  - ✔ buscador «1; DROP TABLE cases; --» sin 500 — `200 resultados=0 · 87 ms`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
