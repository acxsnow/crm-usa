# [INS-012] Cancelar una obra y reintegrar el material

## 1. Información general

- **ID:** INS-012
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Bloqueado (D-001)
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Cancelar con motivo cierra la obra, devuelve el material a bodega y deja el expediente en su etapa de cierre.

## 3. Precondiciones

- D-001 implementado.
- Obra de INS-011 con el límite alcanzado y material en la camioneta.

## 4. Datos de prueba

- Motivo: «Cliente desistió».

## 5. Procedimiento paso a paso

1. [ ] Como administración, cancelar la obra sin motivo y luego con él.
2. [ ] Reintegrar el material a bodega.
3. [ ] Revisar la obra, el expediente y la existencia.

## 6. Resultado esperado

- Sin motivo no cancela.
- La obra queda «Cancelado», sin acciones de campo.
- La existencia vuelve a subir en lo reintegrado.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No se puede crear cobro de una obra cancelada.
- [ ] El historial del expediente registra la cancelación.

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
