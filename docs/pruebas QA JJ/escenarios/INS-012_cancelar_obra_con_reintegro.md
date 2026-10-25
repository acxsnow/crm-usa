# [INS-012] Cancelar una obra y reintegrar el material

## 1. Información general

- **ID:** INS-012
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Cancelar exige motivo, salidas de bodega resueltas y el material reintegrado o explicado; la obra queda en solo lectura y el expediente se cierra.

## 3. Precondiciones

- La obra de INS-011 con material entregado y una salida nueva «Por autorizar».

## 4. Datos de prueba

- Motivo «El cliente desistió del programa»; devolver todo menos 1 unidad; nota «Se quedó cortado en la casa».

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, buscar **Cancelar la obra…** (no debe tenerlo).
2. [ ] Como administración, **Cancelar la obra…**: leer lo que muestra (salidas abiertas y material afuera).
3. [ ] Intentar cancelar con la salida «Por autorizar»: anotar el mensaje. Rechazarla en Bodega › Salidas.
4. [ ] Intentar cancelar sin explicar el material: anotar el mensaje con la lista.
5. [ ] En Bodega › Movimientos registrar la **Devolución** de casi todo con la obra; volver y ver que la lista baja.
6. [ ] Escribir qué pasó con lo que falta y el motivo; **Cancelar la obra**.
7. [ ] Revisar la obra (aviso «Obra cancelada»), el expediente y la existencia de bodega.
8. [ ] Como Carlos: ver el aviso de la campana e intentar registrar algo en la obra.

## 6. Resultado esperado

- Sin motivo, con salidas abiertas o con material sin explicar no cancela, y dice qué falta.
- Cancelada: solo lectura, sin «Orden liberada» ni acciones de campo; el expediente queda «Cerrado» con el motivo.
- La existencia sube en lo devuelto.

## 7. Resultado obtenido

- Qué pasó: Por API, 13 de 13 comprobaciones bien.
- Diferencias con lo esperado: Falta la pantalla: «Cancelar la obra…» con salidas abiertas, material afuera y el aviso «Obra cancelada».
- Comprobaciones por API (13 de 13):
  - ✔ El técnico no cancela
  - ✔ Sin motivo no cancela
  - ✔ Con una salida «Por autorizar» → 409 open_releases — `{"detail":"Primero resuelve las salidas de bodega abiertas de la obra: SAL-2026-0003 (Por autorizar). Recházalas o entrégalas antes de cancelar.","code":"open_r`
  - ✔ cancellation-check lista el material afuera (4) — `{'can_cancel': True, 'open_releases': [], 'material_in_field': [{'item_id': 'c283275b-2900-4b1b-bc3f-02c3f9363b92', 'item_name': 'PVC Pipe 3/4" x 10\'', 'sku': `
  - ✔ Sin explicar el material → 409 material_pending_return — `{"detail":"Hay material entregado a la obra sin reintegrar: 4.00 × PVC Pipe 3/4\" x 10'. Regístralo como devolución a bodega, o explica qué pasó con él para can`
  - ✔ Cancelar con motivo y la explicación del material
  - ✔ La obra queda «cancelled» con el motivo — `cancelled`
  - ✔ El expediente queda «Cerrado» — `closed`
  - ✔ Liberar orden en la cancelada → 409
  - ✔ Registrar visita fallida en la cancelada → 409
  - ✔ Pedir material para la cancelada → 409
  - ✔ Auditoría projects.cancelled
  - ✔ El técnico recibe el aviso de obra cancelada

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No se puede crear cobro ni pedir material para la obra cancelada.
- [ ] Auditoría: `projects.cancelled` con el material afuera y la explicación.
- [ ] Una instalación ya cerrada no se cancela (`installation_closed`).

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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
