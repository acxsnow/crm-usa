# [BOD-002] Crear y editar un artículo con validaciones

## 1. Información general

- **ID:** BOD-002
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · validación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El alta manual valida los campos y no permite códigos repetidos.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Nuevo: «Cinta de aluminio QA», código `QA-0001`, unidad «rollo», costo 7.35, mínimo 4.
- Inválidos: costo -1, costo «abc», código repetido `3496`, nombre vacío.

## 5. Procedimiento paso a paso

1. [ ] **Nuevo artículo** con cada dato inválido, uno a la vez.
2. [ ] Crearlo con los datos válidos.
3. [ ] Editar: cambiar el costo a 7.50 y marcar **Con serial**.

## 6. Resultado esperado

- Cada inválido se rechaza con su mensaje; el código repetido dice que ya existe.
- El artículo queda creado con existencia 0 y luego con el costo nuevo.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Cambiar el costo no cambia el costo de las salidas ya entregadas.

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
