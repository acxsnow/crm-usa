# [PER-001] Tiempos de respuesta de las pantallas principales

## 1. Información general

- **ID:** PER-001
- **Módulo:** Rendimiento
- **Prioridad:** P1
- **Tipo de prueba:** Rendimiento
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Medir y dejar la línea base de las APIs más usadas.

## 3. Precondiciones

- Datos de varias pruebas cargados (al final del ciclo).
- F12 › Network sin caché.

## 4. Datos de prueba

- Inicio, Mi día, Expedientes, Por revisar, Proyectos, Agenda, Existencias, Salidas, Facturas, Mapa.

## 5. Procedimiento paso a paso

1. [ ] Abrir cada pantalla 3 veces.
2. [ ] Anotar el tiempo de la llamada más lenta y el total.

## 6. Resultado esperado

- Cada llamada < 500 ms en local; ninguna pantalla > 2 s.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar el número de llamadas por pantalla (más de 10 es señal de N+1).

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
