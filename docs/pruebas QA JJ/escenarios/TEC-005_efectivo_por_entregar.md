# [TEC-005] Cobro en efectivo en campo y efectivo por entregar

## 1. Información general

- **ID:** TEC-005
- **Módulo:** Técnicos
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El efectivo que recibe el técnico queda a su cargo hasta que lo entrega.

## 3. Precondiciones

- Una obra con **Cobro adicional del cliente** anotado.

## 4. Datos de prueba

- Efectivo USD 150.00.

## 5. Procedimiento paso a paso

1. [ ] Como técnico, **Anotar cobro** en efectivo.
2. [ ] Ver «Efectivo por entregar».
3. [ ] Como administración, recibir la entrega.

## 6. Resultado esperado

- El efectivo aparece a cargo del técnico hasta la entrega y luego en cero.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El valor es exacto (Decimal), sin centavos perdidos.

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
