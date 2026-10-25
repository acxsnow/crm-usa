# [API-004] Códigos HTTP y formato de error uniformes

## 1. Información general

- **ID:** API-004
- **Módulo:** API y paginación
- **Prioridad:** P1
- **Tipo de prueba:** API · contrato
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

Los errores siguen `docs/ERRORES.md`: mismo formato, código correcto, mensaje en español.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- Un id inexistente, un id mal formado (`abc`), un cuerpo vacío, un JSON roto.

## 5. Procedimiento paso a paso

1. [ ] Provocar cada error en 3 módulos distintos.

## 6. Resultado esperado

- 404, 422, 422 y 400/422 respectivamente, con el mismo formato de `docs/ERRORES.md`.

## 7. Resultado obtenido

- Qué pasó: En artículos, clientes y obras: id inexistente → 404, id mal formado → 422; POST con cuerpo vacío → 422 y con JSON roto → 422, siempre con `detail`, `code` y `request_id`.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (15 de 15):
  - ✔ /warehouse/items/{}: id inexistente → 404 — `404 {'detail': 'El artículo no existe.', 'code': 'warehouse_item_not_found', 'request_id': '2c5b060e-1ac9-48c0-a4e4-87e866b79a1c'}`
  - ✔ /warehouse/items/{}: id mal formado → 422 — `422`
  - ✔ /customers/{}: id inexistente → 404 — `404 {'detail': 'El cliente no existe.', 'code': 'customer_not_found', 'request_id': '5b5d3f79-04af-49e4-bd03-a668553edcba'}`
  - ✔ /customers/{}: id mal formado → 422 — `422`
  - ✔ /projects/{}: id inexistente → 404 — `404 {'detail': 'El proyecto no existe.', 'code': 'project_not_found', 'request_id': '10a80089-aec9-4c22-88f5-578b591671d7'}`
  - ✔ /projects/{}: id mal formado → 422 — `422`
  - ✔ POST /warehouse/items cuerpo vacío → 422 — `422 {"detail":"Hay datos inválidos en: name.","code":"validation_error","request_id":"eee2d4fd-5796-4fd7-90b7-881643df9179","errors":[{"field":"name","mes`
  - ✔ POST /warehouse/items JSON roto → 400/422 (no 500) — `422`
  - ✔ POST /warehouse/items: formato de error con detail — `{"detail":"Hay datos inválidos en: 1.","code":"validation_error","request_id":"b2af7055-06ca-4d14-9b14-3085f1c474a8","errors":[{"field":"1","message":`
  - ✔ POST /customers cuerpo vacío → 422 — `422 {"detail":"Hay datos inválidos en: legal_name.","code":"validation_error","request_id":"a43c97eb-5da6-4643-855d-5b94dc778c76","errors":[{"field":"lega`
  - ✔ POST /customers JSON roto → 400/422 (no 500) — `422`
  - ✔ POST /customers: formato de error con detail — `{"detail":"Hay datos inválidos en: 1.","code":"validation_error","request_id":"bdfdb484-a9ed-4a7e-9c31-4acf4a49c42e","errors":[{"field":"1","message":`
  - ✔ POST /warehouse/movements cuerpo vacío → 422 — `422 {"detail":"Hay datos inválidos en: item_id, movement_type, quantity.","code":"validation_error","request_id":"2cd89325-70db-4d43-bc8c-a29d9ec8b104","e`
  - ✔ POST /warehouse/movements JSON roto → 400/422 (no 500) — `422`
  - ✔ POST /warehouse/movements: formato de error con detail — `{"detail":"Hay datos inválidos en: 1.","code":"validation_error","request_id":"4fd157ae-4643-4f13-a80e-606235e953b7","errors":[{"field":"1","message":`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [x] Nunca 500 por una entrada del usuario.

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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
