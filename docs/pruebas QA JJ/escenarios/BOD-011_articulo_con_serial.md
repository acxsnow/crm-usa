# [BOD-011] Equipos con serial: rastreo por equipo

## 1. Información general

- **ID:** BOD-011
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · integridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El serial aparece en los equipos instalados de la obra.

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
