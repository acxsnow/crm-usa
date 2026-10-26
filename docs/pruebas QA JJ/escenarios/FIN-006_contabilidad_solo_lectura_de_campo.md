# [FIN-006] Contabilidad no opera campo ni gerencia escribe

## 1. Información general

- **ID:** FIN-006
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Contabilidad no cierra instalaciones y Gerencia solo consulta.

## 3. Precondiciones

- Sesiones de contabilidad y gerencia.

## 4. Datos de prueba

- Una obra en curso; una factura emitida.

## 5. Procedimiento paso a paso

1. [ ] Como contabilidad, intentar registrar una jornada y autorizar una salida.
2. [ ] Como gerencia, intentar emitir, anular y pagar facturas.

## 6. Resultado esperado

- 403 en cada intento; las pantallas no muestran esos botones.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 6 de 6 comprobaciones bien. Contabilidad no registra jornadas ni autoriza salidas; Gerencia no emite, no paga ni anula facturas (403), pero sí las consulta.
- Diferencias con lo esperado: Falta ver que las pantallas no muestran esos botones (se revisa con AUTH-001).
- Comprobaciones por API (6 de 6):
  - ✔ Contabilidad no registra jornadas (403) — `403`
  - ✔ Contabilidad no autoriza salidas (403) — `403`
  - ✔ Gerencia no emite facturas (403) — `403`
  - ✔ Gerencia no registra pagos (403) — `403`
  - ✔ Gerencia no anula facturas (403) — `403`
  - ✔ Gerencia sí consulta las facturas

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Comparar con `05_MATRIZ_PERMISOS.md`.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
