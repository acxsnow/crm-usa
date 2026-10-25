# [BOD-011] Equipos con serial: rastreo por equipo

## 1. Información general

- **ID:** BOD-011
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integridad
- **Estado:** FALLIDO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Cada condensadora o evaporadora entregada queda identificada por su serial.

## 3. Precondiciones

- Salida con el artículo 85980 (con serial) autorizada.

## 4. Datos de prueba

- Serial `QA-SER-0001`; luego el mismo serial otra vez.

## 5. Procedimiento paso a paso

1. [ ] Entregar con el serial.
2. [ ] En otra salida, entregar el mismo serial.
3. [ ] Entregar sin serial.

## 6. Resultado esperado

- El serial repetido o vacío se rechaza (anotar el mensaje).

## 7. Resultado obtenido

- Qué pasó: 0 de 1 comprobaciones bien.
- Diferencias con lo esperado: La entrega no pide ni guarda seriales; el serial solo se captura después en «Equipos instalados».
- Comprobaciones por API (0 de 1):
  - ✘ Al entregar el equipo con serial (85980) la bodega pide el serial — `DeliverIn solo recibe note y lines(line_id, quantity); `has_serial` no se usa fuera del catálogo`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El serial aparece en los equipos instalados de la obra.

## 10. Resultado final

- [ ] APROBADO
- [x] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-007 | «Con serial» no tiene efecto: la bodega no registra seriales al entregar | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
