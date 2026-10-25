# [TUR-004] Ausencia y novedades del día

## 1. Información general

- **ID:** TUR-004
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Un técnico que no marca aparece como ausente y la novedad se registra con su motivo.

## 3. Precondiciones

- Un técnico con turno hoy que no marca.

## 4. Datos de prueba

- Novedad: «Cita médica», 3 horas.

## 5. Procedimiento paso a paso

1. [ ] Ver el Panel de asistencia pasada la tolerancia.
2. [ ] **Novedades y horas**: registrar la novedad.
3. [ ] Volver al panel.

## 6. Resultado esperado

- Ausente y luego justificado con el motivo.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La novedad queda con quién la registró.

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
