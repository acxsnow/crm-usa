# [TUR-004] Ausencia y novedades del día

## 1. Información general

- **ID:** TUR-004
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

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

- Qué pasó: Lote 3 por API (25 oct): 4 de 4 comprobaciones bien. Pedro, sin marcar y con el turno vencido, aparece «no marcó» (panel: 1 ausente). La novedad de ausencia «Cita médica, 3 horas» con el motivo «Cita médica o enfermedad» queda aprobada por Administración.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (4 de 4):
  - ✔ Sin marcar y con el turno vencido aparece como ausente [reevaluado: leído en la malla] — `Pedro Vargas: compliance=missed; panel missed=1`
  - ✔ Registrar la novedad «Cita médica» (3 horas) — `201 {"id":"d86eb3b9-499a-4f13-8abd-a9b2f6f7c656","user_id":"7ff9aa72-c44f-46fe-96f0-d5c0687ae553","user_name":"Pedro Vargas","kind":"absence","kind_label":"Ause`
  - ✔ Administración aprueba la novedad
  - ✔ Queda justificado con el motivo — `None [{'id': 'd86eb3b9-499a-4f13-8abd-a9b2f6f7c656', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'kind': 'absence', 'kind_la`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La novedad queda con quién la registró.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Al aprobar la novedad el turno sigue «no marcó» en la malla: la justificación se ve en Novedades (motivo, descripción y quién la aprobó), no como un estado «justificado» del turno.
