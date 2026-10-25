# [BOD-016] Dos entregas a la vez sobre la misma existencia

## 1. Información general

- **ID:** BOD-016
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Concurrencia
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Dos personas entregando lo último que queda no dejan la bodega en negativo.

## 3. Precondiciones

- Un artículo con existencia 1 y dos salidas autorizadas de 1 cada una.

## 4. Datos de prueba

- Dos ventanas con sesión de administración (o el script de `CON-001`).

## 5. Procedimiento paso a paso

1. [ ] Preparar las dos entregas y tocarlas casi al mismo tiempo.
2. [ ] Revisar la existencia y el libro.

## 6. Resultado esperado

- Solo una entrega pasa; la otra recibe un error claro.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Existencia final 0, nunca -1.
- [ ] Un solo movimiento de salida.

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
