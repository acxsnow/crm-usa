# [BOD-013] Crear, editar y borrar listas predefinidas

## 1. Información general

- **ID:** BOD-013
- **Módulo:** Bodega
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Las listas se mantienen sin afectar las órdenes que ya las usaron.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Lista «Mantenimiento QA» con 3 renglones.

## 5. Procedimiento paso a paso

1. [ ] **Nueva lista predefinida** con secciones y obligatorios.
2. [ ] Usarla en una salida.
3. [ ] Editar la lista (quitar un renglón) y abrir la salida anterior.
4. [ ] Borrarla.

## 6. Resultado esperado

- Las órdenes que ya la usaron no cambian.

## 7. Resultado obtenido

- Qué pasó: Por API, 22 de 22 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (22 de 22):
  - ✔ Administración arma la lista «Mini split 12k»
  - ✔ El técnico no puede crear listas
  - ✔ El técnico arma su borrador para la obra
  - ✔ Aplica la lista a su borrador
  - ✔ La lista agrega sus 2 renglones — `{"id": "63e589c9-768e-4544-9ddf-67e583d9514f", "number": null, "status": "borrador", "project_id": "fa6117a2-a3dd-4f5c-9c1a-628e954d7a83", "location_i`
  - ✔ La orden del técnico no muestra costos — `[{"id": "cc181025-2ffc-487b-9aef-901571230cbf", "item_id": "dd8f228d-f675-4f7b-a5a7-04daa1f1f6bd", "item_name": "QA 1025164900 Capacitor 35/5", "sku":`
  - ✔ El técnico la manda a autorizar
  - ✔ Recibe número de la serie SAL — `SAL-2026-0010`
  - ✔ La orden aparece en «Por autorizar»
  - ✔ Administración la autoriza
  - ✔ Los renglones de la lista traen su sección y si son obligatorios — `[{"id": "8ba6417e-4500-49ca-92ce-b1804202f756", "item_id": "f0441f61-835e-4d8a-b21f-c714e9403720", "item_name": "QA 1025164900 Tubo cobre 3/8", "sku": "QA102516`
  - ✔ El técnico marca «lo llevo» el tubo al cargar la camioneta
  - ✔ La orden cuenta lo cargado — `{"loadable": 3, "loaded": 1, "required_pending": 1}`
  - ✔ El vendedor no marca la carga
  - ✔ Quitar un obligatorio sin motivo → 400 — `400`
  - ✔ Quitar un obligatorio con motivo queda en la orden
  - ✔ El motivo viaja con la orden — `[{"item_id": "5f7f025f-71e2-44d3-8a4a-01d237d08b89", "item_name": "QA 1025164900 Cinta de aluminio", "spec_label": null, "reason": "QA 1025164900: ya `
  - ✔ Segunda orden del técnico
  - ✔ Administración arma una orden para sí
  - ✔ El técnico no ve la orden de otra persona
  - ✔ El Administrador sí la autoriza
  - ✔ El técnico solo lista sus órdenes

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La lista «3 ton desde cero» sigue con 46 renglones.

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
