# [TUR-002] Marcar entrada y salida con GPS

## 1. Información general

- **ID:** TUR-002
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · celular
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Repetir negando la ubicación: anotar si deja marcar «Sin GPS» y cómo lo señala.

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
