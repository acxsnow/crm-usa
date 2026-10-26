# [TUR-002] Marcar entrada y salida con GPS

## 1. Información general

- **ID:** TUR-002
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · celular
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

El técnico marca su turno desde el celular con ubicación.

## 3. Precondiciones

- TUR-001 con turno hoy para Carlos.
- Ubicación concedida.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, **Mi turno** › marcar entrada.
2. [ ] Marcar entrada otra vez.
3. [ ] Marcar salida.

## 6. Resultado esperado

- Entrada y salida con hora y GPS; la doble entrada no se duplica.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 21 de 21 comprobaciones bien. Entrada con GPS; tres entradas simultáneas dejan una sola marcación abierta; repetir la marca no duplica; en camino y llegué con km; pausa; cola sin señal sin duplicar; salida con resumen.
- Diferencias con lo esperado: Se hizo con Tito (técnico de la base QA), no con Carlos.
- Comprobaciones por API (21 de 21):
  - ✔ Administración programa el turno del técnico hoy
  - ✔ El turno queda creado (o ya había uno a esa hora) — `{"created": [{"id": "be442fdf-b62d-4a9c-821c-2bb5b13a3327", "user_id": "f9c2c322-ff13-4215-9094-dece2583c4e7", "user_name": "Tito T\u00e9cnico", "shift_date": "`
  - ✔ El técnico no programa turnos
  - ✔ Al entrar, la ventana obligatoria aparece — `{"must_clock_in": true, "shift_status": "pending"}`
  - ✔ Tres entradas simultáneas: una 201 y dos 409 — `[201, 409, 409]`
  - ✔ Queda una sola marcación abierta en la base — `1`
  - ✔ Reintentar la misma marca no duplica — `201`
  - ✔ En camino a la obra
  - ✔ Llegué a la obra
  - ✔ La llegada guarda km estimados en línea recta — `12.367|straight_line`
  - ✔ Pausa
  - ✔ Segunda pausa sin cerrar la primera se rechaza
  - ✔ Reanuda
  - ✔ Llega la cola sin señal
  - ✔ Reenviar la cola no duplica — `{"results": [{"client_event_id": "qa-1025215010-off1", "status": "duplicate", "event_id": "2cdbab28-dcc8-4969-96d0-4e48c443bc57"}, {"client_event_id": "qa-10252`
  - ✔ La primera vez entró bien — `{"results": [{"client_event_id": "qa-1025215010-off1", "status": "ok", "event_id": "2cdbab28-dcc8-4969-96d0-4e48c443bc57"}, {"client_event_id": "qa-1025215010-o`
  - ✔ La marca sin señal queda señalada (hora del teléfono) [reevaluado: la consulta devuelve True y no «t»] — `True`
  - ✔ Resumen antes de finalizar
  - ✔ El resumen trae horas efectivas y pausas
  - ✔ FINALIZAR TURNO
  - ✔ Administración la aprueba

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Repetir negando la ubicación: anotar si deja marcar «Sin GPS» y cómo lo señala.

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
