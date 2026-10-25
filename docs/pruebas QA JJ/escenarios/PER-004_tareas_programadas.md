# [PER-004] Tareas programadas (Celery beat) no bloquean la app

## 1. Información general

- **ID:** PER-004
- **Módulo:** Rendimiento
- **Prioridad:** P2
- **Tipo de prueba:** Rendimiento · operación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
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

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
