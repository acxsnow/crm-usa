# [TUR-008] Retención de 90 días y borrado de ubicaciones

## 1. Información general

- **ID:** TUR-008
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P2
- **Tipo de prueba:** Privacidad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

Las coordenadas de los técnicos no se guardan más de 90 días.

## 3. Precondiciones

- Puntos de ubicación de un técnico (por la base, uno con fecha de hace 91 días).

## 4. Datos de prueba

- `UPDATE` de prueba de la fecha de un punto (solo en la base local).

## 5. Procedimiento paso a paso

1. [ ] Ejecutar la tarea de limpieza (beat) o esperar su horario.
2. [ ] Usar el borrado manual de ubicaciones de un usuario.

## 6. Resultado esperado

- El punto de 91 días desaparece; los de 89 se quedan.
- El borrado manual quita todo lo de ese usuario.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 9 de 9 comprobaciones bien. La tarea de limpieza del worker quita la ubicación del punto de 91 días y deja la del de 89; el borrado manual quita todas las del usuario; un técnico no borra las de otro (403).
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (9 de 9):
  - ✔ Hay dos puntos con ubicación — `['647a8182-9605-4736-9d06-ab06e917cb78', '85a34ecc-c7ea-424f-bce6-8937f5829bcb']`
  - ✔ El de 89 días la conserva — `False`
  - ✔ Borrado manual de las ubicaciones del usuario — `200 {"purged":2}`
  - ✔ No le queda ninguna ubicación — `0`
  - ✔ Un técnico no borra ubicaciones de otro (403) — `403`
  - ✔ Hay dos puntos con ubicación — `['e6e3a1f4-0927-4b36-9c20-46eead847f7a', 'f4cbcff0-681d-4e9c-8725-ed949234ac0e']`
  - ✔ La tarea de limpieza del worker corre (2026-10-25 21:54:27 [info     ] attendance.locations_purged    events=1
1) [reevaluado: la salida trae la línea del log y el 1] — `2026-10-25 21:54:27 [info     ] attendance.locations_purged    events=1
1`
  - ✔ El punto de 91 días pierde la ubicación
  - ✔ El de 89 días la conserva

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Queda en Auditoría quién borró.

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
