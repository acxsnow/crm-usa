# [CON-002] Numeración consecutiva con emisiones simultáneas

## 1. Información general

- **ID:** CON-002
- **Módulo:** Concurrencia
- **Prioridad:** P1
- **Tipo de prueba:** Concurrencia · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Dos facturas emitidas a la vez no comparten número.

## 3. Precondiciones

- Dos cotizaciones aceptadas.

## 4. Datos de prueba

- Dos `fetch` de emitir al mismo tiempo.

## 5. Procedimiento paso a paso

1. [ ] Emitir las dos a la vez.
2. [ ] Repetir con dos salidas de bodega enviadas a la vez (números SAL-…).

## 6. Resultado esperado

- Números distintos y consecutivos.

## 7. Resultado obtenido

- Qué pasó: Por API, 1 de 1 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (1 de 1):
  - ✔ Dos salidas enviadas a la vez reciben números SAL distintos — `['SAL-2026-0008', 'SAL-2026-0007']`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La restricción única de la base respalda la numeración.

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
- Observaciones:
