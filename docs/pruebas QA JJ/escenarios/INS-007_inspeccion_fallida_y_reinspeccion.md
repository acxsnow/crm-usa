# [INS-007] Inspección fallida: la obra vuelve a campo

## 1. Información general

- **ID:** INS-007
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución + 60 min de preparación
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Una inspección fallida reabre la obra con observaciones obligatorias y exige una nueva inspección.

## 3. Precondiciones

- Otra obra en el mismo punto que INS-006 (repetir P-01 e INS-001 a INS-005 con Luis Herrera, `tecnico04@demo-org.com`).

## 4. Datos de prueba

- Observaciones: «Falta soporte antivibración».

## 5. Procedimiento paso a paso

1. [ ] Registrar la inspección como fallida sin observaciones: anotar el mensaje.
2. [ ] Registrarla con las observaciones.
3. [ ] Como Luis: ver la obra «Reabierta por inspección fallida», registrar la jornada de corrección y cerrar otra vez.
4. [ ] Agendar y aprobar la reinspección.

## 6. Resultado esperado

- Sin observaciones no se guarda («obligatorias si falla»).
- La obra queda «Fallida: la orden volvió a campo» y luego avanza con la reinspección aprobada.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial con las dos inspecciones.
- [ ] El reporte de rechazos cuenta la inspección fallida.

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
