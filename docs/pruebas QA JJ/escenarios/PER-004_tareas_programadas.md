# [PER-004] Tareas programadas (Celery beat) no bloquean la app

## 1. Información general

- **ID:** PER-004
- **Módulo:** Rendimiento
- **Prioridad:** P2
- **Tipo de prueba:** Rendimiento · operación
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 (revisión de logs)
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018

## 2. Objetivo

Las tareas de fondo corren y no frenan las pantallas.

## 3. Precondiciones

- worker y beat arriba.

## 4. Datos de prueba

- `docker compose logs beat worker`.

## 5. Procedimiento paso a paso

1. [ ] Ver qué tareas corren y cada cuánto.
2. [ ] Navegar mientras corren.

## 6. Resultado esperado

- Las tareas terminan sin error; la app no se frena.

## 7. Resultado obtenido

- Qué pasó: Lote 3 (25 oct): 4 de 4 comprobaciones bien. Las 6 tareas programadas corren; los únicos errores son de los reinicios de la base de QA; la limpieza corre en el worker.
- Diferencias con lo esperado: Falta navegar en pantalla mientras corren.
- Comprobaciones por API (4 de 4):
  - ✔ Tareas programadas (beat): avisos pendientes y campañas cada 60 s; alertas diarias 14:00 UTC; facturas vencidas 06:00 UTC; bancos (Plaid) 12:00 UTC; limpieza de ubicaciones 09:30 UTC — `app/workers/celery_app.py beat_schedule`
  - ✔ Las tareas terminan sin error: los únicos errores de 24 h en worker y beat son `UndefinedTableError` en los 4 momentos en que la QA reinició la base (las tareas de cada minuto no encontraron las tablas mientras se recreaban) — `docker compose logs worker beat --since 24h: 4 errores por tabla, uno por reinicio`
  - ✔ La limpieza de ubicaciones corre en el worker de verdad (TUR-008) — `attendance.locations_purged events=1`
  - ✔ Las tareas de avisos tardaron hasta 8.8 s con la carga de las pruebas, en segundo plano; las pantallas siguieron por debajo de 500 ms (PER-001) — `notifications.process_event succeeded in 4.2–8.8 s`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna tarea falla en los registros durante el ciclo.

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

- Tiempo de ejecución: lote 3 (revisión de logs)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Las tareas de avisos tardan varios segundos con carga: no frenan las pantallas porque corren en el worker.
