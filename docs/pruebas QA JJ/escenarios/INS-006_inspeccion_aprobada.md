# [INS-006] Inspección municipal aprobada

## 1. Información general

- **ID:** INS-006
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Registrar la inspección aprobada deja la obra lista para el cobro.

## 3. Precondiciones

- INS-005 hecho.

## 4. Datos de prueba

- Inspector o entidad: «City of Phoenix»; fecha y hora: hoy 10:00.

## 5. Procedimiento paso a paso

1. [ ] En la obra: **Agendar inspección** con los datos.
2. [ ] Registrar el resultado **Inspección aprobada** con su evidencia.
3. [ ] Abrir el expediente: mirar la etapa.

## 6. Resultado esperado

- El expediente sale de inspección pendiente y queda listo para el cobro.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un solo evento de etapa por el resultado de la inspección.

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
