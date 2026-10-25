# [INS-007] Inspección fallida: la obra vuelve a campo

## 1. Información general

- **ID:** INS-007
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución + 60 min de preparación
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 5 de 5 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (5 de 5):
  - ✔ Agendar inspección
  - ✔ Falla sin observaciones se rechaza
  - ✔ Inspección fallida con observaciones
  - ✔ Técnico corrige y cierra de nuevo
  - ✔ Administración confirma de nuevo

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Historial con las dos inspecciones.
- [ ] El reporte de rechazos cuenta la inspección fallida.

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
