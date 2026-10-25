# [BOD-005] Pedir más de lo que hay en bodega

## 1. Información general

- **ID:** BOD-005
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 4 de 4 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (4 de 4):
  - ✔ Pedir 15 con 10 en bodega: ¿avisa al pedir? (anotar) — `200 {"id":"879d68bf-976b-450d-ac1f-2db8afa32eeb","number":"SAL-2026-0004","status":"por_autorizar","project_id":null,"location_id":"bde44503-d601-48e5-a6c`
  - ✔ ¿Avisa al autorizar? (anotar) — `200`
  - ✔ Entrega solo los 10 y lo deja como faltante — `stock=0.0 faltantes=[{'line_id': 'ca4bb21c-3731-4f8d-8f4d-cabd656de5a5', 'item_id': 'c251c4af-7d68-42f6-8977-8a9a230949ab', 'pedida': '15.00', 'entregada': '10.`
  - ✔ Ninguna existencia negativa en toda la base — `0`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna existencia negativa en la base (`SELECT ... WHERE quantity < 0`).

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
- Observaciones: No avisa al pedir ni al autorizar: la entrega sale parcial y deja el faltante escrito (decisión D-BOD-4 del cliente). Ninguna existencia negativa.
