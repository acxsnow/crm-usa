# [BOD-004] Entrega parcial y rechazo de una salida

## 1. Información general

- **ID:** BOD-004
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 6 de 6 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (6 de 6):
  - ✔ Administración la entrega
  - ✔ Se entrega aunque falte capacitor, con aviso de faltante (pidió 6, había 4) — `[{"line_id": "cc181025-2ffc-487b-9aef-901571230cbf", "item_id": "dd8f228d-f675-4f7b-a5a7-04daa1f1f6bd", "pedida": "6.00", "entregada": "4.00", "motivo": "Solo h`
  - ✔ Entregar dos veces no descuenta dos veces (tubo 200 − 25 = 175) — `400 · tubo 175.00`
  - ✔ Rechazar exige motivo
  - ✔ Administración la rechaza con motivo
  - ✔ Queda rechazada con su motivo — `rechazada`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El técnico recibe aviso de la entrega parcial y del rechazo.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
