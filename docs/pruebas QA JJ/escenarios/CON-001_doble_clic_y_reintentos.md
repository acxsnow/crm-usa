# [CON-001] Doble clic y reintentos en acciones que crean cosas

## 1. Información general

- **ID:** CON-001
- **Módulo:** Concurrencia
- **Prioridad:** P0
- **Tipo de prueba:** Concurrencia
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Un toque doble o un reintento por mala señal no duplica registros.

## 3. Precondiciones

- Expediente por aprobar, salida por entregar, factura por emitir.

## 4. Datos de prueba

- Script de la consola que lanza 2 `fetch` iguales al mismo tiempo.

## 5. Procedimiento paso a paso

1. [ ] Lanzar 2 aprobaciones, 2 entregas y 2 emisiones simultáneas.

## 6. Resultado esperado

- Una pasa y la otra recibe error; una sola obra, una entrega y una factura.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Revisar en la base que no hay duplicados.

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
