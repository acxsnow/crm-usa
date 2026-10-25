# [BOD-005] Pedir más de lo que hay en bodega

## 1. Información general

- **ID:** BOD-005
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La bodega nunca queda en negativo.

## 3. Precondiciones

- Un artículo con existencia baja (por ejemplo `QA-0001` con 10).

## 4. Datos de prueba

- Salida de 15 unidades de `QA-0001`.

## 5. Procedimiento paso a paso

1. [ ] Armar y enviar la salida de 15.
2. [ ] Autorizar y tratar de entregar 15.
3. [ ] Entregar 10.

## 6. Resultado esperado

- Anotar en qué punto avisa (al pedir, al autorizar o al entregar).
- No permite entregar más de lo disponible; con 10 queda en 0.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna existencia negativa en la base (`SELECT ... WHERE quantity < 0`).

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
