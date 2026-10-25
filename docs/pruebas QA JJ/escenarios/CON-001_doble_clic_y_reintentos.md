# [CON-001] Doble clic y reintentos en acciones que crean cosas

## 1. Información general

- **ID:** CON-001
- **Módulo:** Concurrencia
- **Prioridad:** P0
- **Tipo de prueba:** Concurrencia
- **Estado:** FALLIDO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: 2 de 2 comprobaciones bien.
- Diferencias con lo esperado: En el lote pasó una sola, pero al repetirlo 10 veces (script `carrera.py`) en 6 casos las dos respondieron 200 y quedaron dos `warehouse.release_authorized` en la auditoría. La entrega doble sí está protegida (BOD-016).
- Comprobaciones por API (2 de 2):
  - ✔ Dos autorizaciones simultáneas de la misma salida: una pasa — `[400, 200]`
  - ✔ Y queda una sola autorización en la auditoría — `1`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Revisar en la base que no hay duplicados.

## 10. Resultado final

- [ ] APROBADO
- [x] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-012 | Dos autorizaciones simultáneas de la misma salida pasan las dos | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
