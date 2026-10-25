# [BOD-004] Entrega parcial y rechazo de una salida

## 1. Información general

- **ID:** BOD-004
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Bodega puede entregar menos de lo pedido o rechazar con motivo, y la existencia refleja solo lo entregado.

## 3. Precondiciones

- Dos salidas «Por autorizar» de una obra (INS-003 sin entregar).

## 4. Datos de prueba

- Salida A: entregar la mitad de un renglón de cinta; salida B: rechazar con «Ya hay en la camioneta».

## 5. Procedimiento paso a paso

1. [ ] Autorizar A y al entregar bajar una cantidad (cada cantidad va de 0 a lo pedido).
2. [ ] Intentar una cantidad mayor a la pedida y una negativa.
3. [ ] **Rechazar la salida** B sin motivo y luego con él.

## 6. Resultado esperado

- A entrega solo lo indicado; lo no entregado no descuenta.
- Mayor o negativa se rechazan.
- B queda «Rechazada» con su motivo; sin motivo no se rechaza.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El técnico recibe aviso de la entrega parcial y del rechazo.

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
