# [TUR-003] Llegada tarde con tolerancia de 10 minutos

## 1. Información general

- **ID:** TUR-003
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Regla de negocio
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

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

- Qué pasó: Lote 3 por API (25 oct): 7 de 7 comprobaciones bien. Turnos que empezaron hace 5, 10 y 15 minutos: los de 5 y 10 llegaron a tiempo y el de 15 tarde (tolerancia de 10 min de Don Aldo).
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Turno que empezó hace 5 min — `{"created":[{"id":"0fb3786b-737e-40a5-a1fe-841b8d56a7f0","user_id":"f1794000-8ca2-480f-bf1c-bfc1663e5d3f","user_name":"Andrés Morales","shift_date":"2`
  - ✔ Marca entrada (hace 5 min) — `201 {"entry":{"id":"1433e253-e51e-4b75-a8cd-99f3d3716ea6","user_id":"f1794000-8ca2-480f-bf1c-bfc1663e5d3f","shift_id":"0fb3786b-737e-40a5-a1fe-841b8d56a7f`
  - ✔ Turno que empezó hace 10 min — `{"created":[{"id":"2d31ad48-b3e2-487b-9316-8e95a364bbfc","user_id":"fa80eea1-fa79-49fc-b385-48b6db2be181","user_name":"Diego Jiménez","shift_date":"20`
  - ✔ Marca entrada (hace 10 min) — `201 {"entry":{"id":"7a5dad48-2e4c-4176-bb5e-52bf5715b478","user_id":"fa80eea1-fa79-49fc-b385-48b6db2be181","shift_id":"2d31ad48-b3e2-487b-9316-8e95a364bbf`
  - ✔ Turno que empezó hace 15 min — `{"created":[{"id":"4e7ff58c-0d94-40e8-8549-2f937f772fe2","user_id":"7be19cad-1e08-4c48-80a1-ecbd3c10064e","user_name":"Jorge Rojas","shift_date":"2026`
  - ✔ Marca entrada (hace 15 min) — `201 {"entry":{"id":"bb083a9b-8e95-4bb8-be5b-13b15fcec090","user_id":"7be19cad-1e08-4c48-80a1-ecbd3c10064e","shift_id":"4e7ff58c-0d94-40e8-8549-2f937f772fe`
  - ✔ A 5 y 10 min: a tiempo; a 15 min: tarde (tolerancia de 10 min) [reevaluado: leído en la malla] — `Andrés (hace 5 min) y Diego (hace 10 min): early_departure, llegaron a tiempo (salida inmediata de la prueba); Jorge (hace 15 min): late_and_early, llegó tarde`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La hora usa la zona de la organización (America/Phoenix), no la del navegador (riesgo TST-05).

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
- Observaciones:
