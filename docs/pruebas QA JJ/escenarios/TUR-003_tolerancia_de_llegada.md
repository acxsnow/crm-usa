# [TUR-003] Llegada tarde con tolerancia de 10 minutos

## 1. Información general

- **ID:** TUR-003
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La malla marca tarde solo después de 10 minutos (decisión de Don Aldo).

## 3. Precondiciones

- Turnos de prueba con inicio 5, 10 y 15 minutos antes de la hora actual.

## 4. Datos de prueba

- Tres técnicos distintos.

## 5. Procedimiento paso a paso

1. [ ] Marcar entrada con los tres.
2. [ ] Ver el **Panel de asistencia**.

## 6. Resultado esperado

- A 5 y 10 min: a tiempo; a 15 min: tarde.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La hora usa la zona de la organización (America/Phoenix), no la del navegador (riesgo TST-05).

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
