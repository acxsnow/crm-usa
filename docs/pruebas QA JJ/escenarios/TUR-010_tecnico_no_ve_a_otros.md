# [TUR-010] El técnico no ve la asistencia ni la ubicación de otros

## 1. Información general

- **ID:** TUR-010
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad · privacidad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las ubicaciones son datos personales del técnico.

## 3. Precondiciones

- Token de Carlos.

## 4. Datos de prueba

- Rutas /attendance, /operations-map, /payroll.

## 5. Procedimiento paso a paso

1. [ ] Escribirlas a mano como Carlos.
2. [ ] Llamar a sus APIs con el token.

## 6. Resultado esperado

- Sin acceso en pantalla; 403 en la API.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún punto GPS de otro técnico en ninguna respuesta.

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
