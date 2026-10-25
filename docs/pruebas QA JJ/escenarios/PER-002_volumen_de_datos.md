# [PER-002] Listas con volumen alto

## 1. Información general

- **ID:** PER-002
- **Módulo:** Rendimiento
- **Prioridad:** P2
- **Tipo de prueba:** Rendimiento
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución + 20 min de preparación
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las listas siguen rápidas con miles de filas.

## 3. Precondiciones

- Cargar volumen con un script (1,000 expedientes y 5,000 movimientos) solo en la base local.

## 4. Datos de prueba

- El script de volumen (se escribe al ejecutar esta prueba).

## 5. Procedimiento paso a paso

1. [ ] Medir Expedientes, Movimientos y el buscador con el volumen.
2. [ ] Revisar `EXPLAIN ANALYZE` de las 2 más lentas.

## 6. Resultado esperado

- Paginación igual de rápida en la página 1 y en la 20.
- Sin barridos completos en tablas grandes.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Reiniciar la base QA al terminar (`seed_qa --reiniciar --si-borrar-todo`).

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
