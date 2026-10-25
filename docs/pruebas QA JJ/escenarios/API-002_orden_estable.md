# [API-002] Orden estable entre páginas

## 1. Información general

- **ID:** API-002
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las páginas no repiten ni pierden filas cuando hay empates.

## 3. Precondiciones

- Base QA.

## 4. Datos de prueba

- Movimientos de bodega (244 creados en el mismo segundo por la carga).

## 5. Procedimiento paso a paso

1. [ ] Bajar `/warehouse/movements` en páginas de 50 hasta el final.
2. [ ] Comparar los ids.

## 6. Resultado esperado

- 244 ids distintos, ninguno repetido.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El orden incluye un desempate por id.

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
