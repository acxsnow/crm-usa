# [TUR-008] Retención de 90 días y borrado de ubicaciones

## 1. Información general

- **ID:** TUR-008
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P2
- **Tipo de prueba:** Privacidad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Queda en Auditoría quién borró.

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
