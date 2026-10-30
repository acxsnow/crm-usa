# [TUR-001] Armar la malla de turnos de la semana

## 1. Información general

- **ID:** TUR-001
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

Administración programa los turnos de los 15 técnicos.

## 3. Precondiciones

- Sesión de administración.

## 4. Datos de prueba

- Turno 7:00–16:00 de lunes a viernes para 5 técnicos; un turno que se cruza con otro del mismo técnico.

## 5. Procedimiento paso a paso

1. [ ] **Malla de turnos**: asignar los turnos.
2. [ ] Intentar el turno cruzado.
3. [ ] Ver la malla a 390 px.

## 6. Resultado esperado

- Los turnos quedan en la malla; el cruce se rechaza.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 4 de 4 comprobaciones bien. Turno 7:00–16:00 de lunes a viernes para 5 técnicos: 25 turnos en la malla; un turno que se cruza con otro del mismo técnico se rechaza.
- Diferencias con lo esperado: Falta ver la malla a 390 px.
- Comprobaciones por API (4 de 4):
  - ✔ Turno 7:00–16:00 de lunes a viernes para 5 técnicos
  - ✔ Quedan 25 turnos en la malla ([{'id': '01489dfc-0469-4594-9d16-f9aae430d01e', 'user_id': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'user_name': 'Miguel Torres', 'shift_date': '2026-10-26', 'starts_at': '2026-10-26T12:00:00+00:00', 'ends_at': '2026-10-26T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '8ea2c63f-11b9-482f-849e-fe0f349a03a3', 'user_id': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'user_name': 'Miguel Torres', 'shift_date': '2026-10-27', 'starts_at': '2026-10-27T12:00:00+00:00', 'ends_at': '2026-10-27T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'a409c916-5bac-4a18-b00b-1f12c1e351d5', 'user_id': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'user_name': 'Miguel Torres', 'shift_date': '2026-10-28', 'starts_at': '2026-10-28T12:00:00+00:00', 'ends_at': '2026-10-28T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'ef660f58-cfff-463b-b343-67229e7aa48c', 'user_id': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'user_name': 'Miguel Torres', 'shift_date': '2026-10-29', 'starts_at': '2026-10-29T12:00:00+00:00', 'ends_at': '2026-10-29T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'b13eafa9-d7fa-464e-8e51-61a4b8754786', 'user_id': '917b4cfb-2bc8-45c1-bd64-c199948a5132', 'user_name': 'Miguel Torres', 'shift_date': '2026-10-30', 'starts_at': '2026-10-30T12:00:00+00:00', 'ends_at': '2026-10-30T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '3eac9541-9111-4b64-a1b2-6db3e6942e0e', 'user_id': 'dab1985f-df38-4c31-bff2-87b2a419a20c', 'user_name': 'José Castillo', 'shift_date': '2026-10-26', 'starts_at': '2026-10-26T12:00:00+00:00', 'ends_at': '2026-10-26T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '3235dadd-9ee5-447b-8b2a-84719869d583', 'user_id': 'dab1985f-df38-4c31-bff2-87b2a419a20c', 'user_name': 'José Castillo', 'shift_date': '2026-10-27', 'starts_at': '2026-10-27T12:00:00+00:00', 'ends_at': '2026-10-27T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'dd52ea2c-e44e-4dc8-9c57-d37d76cc4fe2', 'user_id': 'dab1985f-df38-4c31-bff2-87b2a419a20c', 'user_name': 'José Castillo', 'shift_date': '2026-10-28', 'starts_at': '2026-10-28T12:00:00+00:00', 'ends_at': '2026-10-28T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'd0841fb9-9e3c-4bb8-8340-ba0246f39bfa', 'user_id': 'dab1985f-df38-4c31-bff2-87b2a419a20c', 'user_name': 'José Castillo', 'shift_date': '2026-10-29', 'starts_at': '2026-10-29T12:00:00+00:00', 'ends_at': '2026-10-29T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '8fc34a7d-2b5f-4c6b-8711-79a283ace086', 'user_id': 'dab1985f-df38-4c31-bff2-87b2a419a20c', 'user_name': 'José Castillo', 'shift_date': '2026-10-30', 'starts_at': '2026-10-30T12:00:00+00:00', 'ends_at': '2026-10-30T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '6e8ed141-0381-4705-a8f4-73067a795b68', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'shift_date': '2026-10-26', 'starts_at': '2026-10-26T12:00:00+00:00', 'ends_at': '2026-10-26T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '102d74cd-2034-49f3-97a8-6336e91e44ac', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'shift_date': '2026-10-27', 'starts_at': '2026-10-27T12:00:00+00:00', 'ends_at': '2026-10-27T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '9d98975d-e439-4585-a06a-28437068716f', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'shift_date': '2026-10-28', 'starts_at': '2026-10-28T12:00:00+00:00', 'ends_at': '2026-10-28T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'c1e09a1b-2b3b-484f-b7ce-b0dc55fc88c5', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'shift_date': '2026-10-29', 'starts_at': '2026-10-29T12:00:00+00:00', 'ends_at': '2026-10-29T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '628aeac3-2685-4d29-9702-11da07a0571b', 'user_id': '7ff9aa72-c44f-46fe-96f0-d5c0687ae553', 'user_name': 'Pedro Vargas', 'shift_date': '2026-10-30', 'starts_at': '2026-10-30T12:00:00+00:00', 'ends_at': '2026-10-30T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '64ee5b63-04b4-430c-813c-d4b241543454', 'user_id': 'f1794000-8ca2-480f-bf1c-bfc1663e5d3f', 'user_name': 'Andrés Morales', 'shift_date': '2026-10-26', 'starts_at': '2026-10-26T12:00:00+00:00', 'ends_at': '2026-10-26T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '563742f3-c993-4db0-8794-084367c2e427', 'user_id': 'f1794000-8ca2-480f-bf1c-bfc1663e5d3f', 'user_name': 'Andrés Morales', 'shift_date': '2026-10-27', 'starts_at': '2026-10-27T12:00:00+00:00', 'ends_at': '2026-10-27T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '544ee7de-0720-4028-ad97-8cf7009a94e0', 'user_id': 'f1794000-8ca2-480f-bf1c-bfc1663e5d3f', 'user_name': 'Andrés Morales', 'shift_date': '2026-10-28', 'starts_at': '2026-10-28T12:00:00+00:00', 'ends_at': '2026-10-28T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'a06b55df-1d33-4e2d-a8e0-070317d15eae', 'user_id': 'f1794000-8ca2-480f-bf1c-bfc1663e5d3f', 'user_name': 'Andrés Morales', 'shift_date': '2026-10-29', 'starts_at': '2026-10-29T12:00:00+00:00', 'ends_at': '2026-10-29T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '4a496747-6a5c-4647-8f1c-f42d8ac67c19', 'user_id': 'f1794000-8ca2-480f-bf1c-bfc1663e5d3f', 'user_name': 'Andrés Morales', 'shift_date': '2026-10-30', 'starts_at': '2026-10-30T12:00:00+00:00', 'ends_at': '2026-10-30T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'ad9304a2-2af5-4f23-8da5-94f2ddd6715c', 'user_id': 'fa80eea1-fa79-49fc-b385-48b6db2be181', 'user_name': 'Diego Jiménez', 'shift_date': '2026-10-26', 'starts_at': '2026-10-26T12:00:00+00:00', 'ends_at': '2026-10-26T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '2de49990-c923-450b-b64a-1b7445ec3bcb', 'user_id': 'fa80eea1-fa79-49fc-b385-48b6db2be181', 'user_name': 'Diego Jiménez', 'shift_date': '2026-10-27', 'starts_at': '2026-10-27T12:00:00+00:00', 'ends_at': '2026-10-27T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': 'd79c65a9-286c-4e01-b323-2837b606ada8', 'user_id': 'fa80eea1-fa79-49fc-b385-48b6db2be181', 'user_name': 'Diego Jiménez', 'shift_date': '2026-10-28', 'starts_at': '2026-10-28T12:00:00+00:00', 'ends_at': '2026-10-28T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '3d1ab9d9-d381-44f2-a306-da3efb027dd1', 'user_id': 'fa80eea1-fa79-49fc-b385-48b6db2be181', 'user_name': 'Diego Jiménez', 'shift_date': '2026-10-29', 'starts_at': '2026-10-29T12:00:00+00:00', 'ends_at': '2026-10-29T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}, {'id': '12bc5d2a-f81f-41dc-8c3b-201fe158a574', 'user_id': 'fa80eea1-fa79-49fc-b385-48b6db2be181', 'user_name': 'Diego Jiménez', 'shift_date': '2026-10-30', 'starts_at': '2026-10-30T12:00:00+00:00', 'ends_at': '2026-10-30T21:00:00+00:00', 'break_minutes': 60, 'scheduled_minutes': 480, 'project_id': None, 'project_title': None, 'notes': 'QA 1025215010 TUR-001', 'status': 'scheduled'}]) — `{"created": [{"id": "01489dfc-0469-4594-9d16-f9aae430d01e", "user_id": "917b4cfb-2bc8-45c1-bd64-c199948a5132", "user_name": "Miguel Torres", "shift_date": "2026`
  - ✔ La malla de la semana los muestra (25) — `25`
  - ✔ Un turno que se cruza con otro del mismo técnico se rechaza — `201 {"created":[],"skipped":[{"user_id":"917b4cfb-2bc8-45c1-bd64-c199948a5132","user_name":"Miguel Torres","shift_date":"2026-10-26"}]}`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- La malla de turnos a 390 px no desborda la página.
- Comprobaciones (1 de 1):
  - ✔ La malla a 390 px no desborda la página — `390`
- Capturas:
  - [malla-celular.jpg](../evidencias/pantalla/TUR-001/malla-celular.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo Administrador y Administración ven la malla (decisión de Don Aldo).

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
