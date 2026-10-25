# [CON-002] Numeración consecutiva con emisiones simultáneas

## 1. Información general

- **ID:** CON-002
- **Módulo:** Concurrencia
- **Prioridad:** P1
- **Tipo de prueba:** Concurrencia · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Dos facturas emitidas a la vez no comparten número.

## 3. Precondiciones

- Dos cotizaciones aceptadas.

## 4. Datos de prueba

- Dos `fetch` de emitir al mismo tiempo.

## 5. Procedimiento paso a paso

1. [ ] Emitir las dos a la vez.
2. [ ] Repetir con dos salidas de bodega enviadas a la vez (números SAL-…).

## 6. Resultado esperado

- Números distintos y consecutivos.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La restricción única de la base respalda la numeración.

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
