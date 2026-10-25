# [SEC-004] Inyección SQL y XSS en formularios y filtros

## 1. Información general

- **ID:** SEC-004
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** FALLIDO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Lo que escribe el usuario nunca se ejecuta ni en la base ni en el navegador.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- `' OR '1'='1`, `1; DROP TABLE cases; --`, `<img src=x onerror=alert(1)>`, `{{7*7}}`.

## 5. Procedimiento paso a paso

1. [ ] Ponerlos en: nombre de cliente, notas de obra, motivo de rechazo, filtro `q` de listas y nombre de artículo.
2. [ ] Abrir cada pantalla donde se muestran y el PDF del acta.

## 6. Resultado esperado

- Se guardan y se muestran como texto; ninguna alerta; ninguna consulta alterada.

## 7. Resultado obtenido

- Qué pasó: Ninguna entrada rara produce error ni altera la consulta (todo va parametrizado). Pero en los filtros de artículos, `%` y `_` traen los 244 artículos: el texto se usa como comodín.
- Diferencias con lo esperado: Unos 10 filtros de texto no escapan `%` y `_` (expedientes, clientes, obras, proveedores, auditoría, usuarios, listas, salidas y artículos); el buscador y otros sí los escapan. Falta la parte de pantalla (ver los textos guardados y el PDF del acta).
- Comprobaciones por API (14 de 16):
  - ✘ filtro de artículos «%» sin 500 y sin traer todo — `200 total=244`
  - ✔ filtro de clientes «%» sin 500 — `200`
  - ✘ filtro de artículos «_» sin 500 y sin traer todo — `200 total=244`
  - ✔ filtro de clientes «_» sin 500 — `200`
  - ✔ filtro de artículos «' OR 1=1 --» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «' OR 1=1 --» sin 500 — `200`
  - ✔ filtro de artículos «<script>alert(1)</script>» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «<script>alert(1)</script>» sin 500 — `200`
  - ✔ filtro de artículos «xxxxxxxxxxxxxxxxxxxxxxxxx» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «xxxxxxxxxxxxxxxxxxxxxxxxx» sin 500 — `200`
  - ✔ filtro de artículos «🔧🔥» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «🔧🔥» sin 500 — `200`
  - ✔ filtro de artículos «Ñandú» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «Ñandú» sin 500 — `200`
  - ✔ filtro de artículos «1; DROP TABLE cases; --» sin 500 y sin traer todo — `200 total=0`
  - ✔ filtro de clientes «1; DROP TABLE cases; --» sin 500 — `200`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La tabla `cases` sigue existiendo :)
- [ ] Ningún 500.

## 10. Resultado final

- [ ] APROBADO
- [x] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-004 | Filtros de texto no escapan % y _ (comodines) | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
