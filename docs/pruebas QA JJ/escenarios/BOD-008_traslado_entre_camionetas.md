# [BOD-008] Traslado de material entre camionetas

## 1. Información general

- **ID:** BOD-008
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Pasar material de un técnico a otro sin pasar por bodega.

## 3. Precondiciones

- Material en la camioneta de Carlos (INS-003).

## 4. Datos de prueba

- Trasladar 1 unidad de la camioneta de Carlos a la de Luis.

## 5. Procedimiento paso a paso

1. [ ] Registrar el traslado.
2. [ ] Intentar trasladar más de lo que hay en la camioneta de Carlos.
3. [ ] Ver ambas camionetas.

## 6. Resultado esperado

- Carlos baja 1 y Luis sube 1; el total de la organización no cambia.
- El exceso se rechaza.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Movimiento `traslado` con origen y destino.

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
