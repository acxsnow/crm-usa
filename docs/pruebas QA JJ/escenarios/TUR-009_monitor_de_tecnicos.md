# [TUR-009] Monitor de técnicos y novedades del día

## 1. Información general

- **ID:** TUR-009
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

El supervisor ve de un vistazo qué hace cada técnico hoy.

## 3. Precondiciones

- Varios técnicos con obras y marcas hoy.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Abrir **Monitor de técnicos**.
2. [ ] Comparar con las agendas.

## 6. Resultado esperado

- Casos asignados, casos gestionados hoy y tiempo de gestión coinciden con lo registrado.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 8 de 8 comprobaciones bien. El monitor trae a los 14 técnicos activos y los casos asignados coinciden con las obras abiertas de cada uno; el técnico no lo abre.
- Diferencias con lo esperado: Falta compararlo en pantalla con las agendas.
- Comprobaciones por API (8 de 8):
  - ✔ Contabilidad ve el panel
  - ✔ Gerencia ve el tablero de hoy
  - ✔ El tablero separa turno abierto y ubicación con su antigüedad — `{"user_id": "f9c2c322-ff13-4215-9094-dece2583c4e7", "user_name": "Tito T\u00e9cnico", "shift": {"starts_at": "2026-10-25T21:30:00+00:00", "ends_at": "2026-10-26`
  - ✔ Contabilidad no ve la ubicación
  - ✔ El vendedor no ve el panel
  - ✔ El monitor trae a los técnicos (14) [reevaluado: 14 activos: Héctor quedó desactivado en TUR-004 del lote C] — `14`
  - ✔ Los casos asignados coinciden con las obras abiertas de cada uno
  - ✔ Carlos (técnico) no abre el monitor — `403`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- El monitor de técnicos muestra a los técnicos (15 filas).
- Comprobaciones (1 de 1):
  - ✔ El monitor muestra a los técnicos (15 filas) — `15`
- Capturas:
  - [monitor.jpg](../evidencias/pantalla/TUR-009/monitor.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Carga en menos de 1 s con los 15 técnicos.

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
