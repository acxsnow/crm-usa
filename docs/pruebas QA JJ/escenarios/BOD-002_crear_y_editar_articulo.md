# [BOD-002] Crear y editar un artículo con validaciones

## 1. Información general

- **ID:** BOD-002
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · validación
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

El alta manual valida los campos y no permite códigos repetidos.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Nuevo: «Cinta de aluminio QA», código `QA-0001`, unidad «rollo», costo 7.35, mínimo 4.
- Inválidos: costo -1, costo «abc», código repetido `3496`, nombre vacío.

## 5. Procedimiento paso a paso

1. [x] **Nuevo artículo** con cada dato inválido, uno a la vez.
2. [x] Crearlo con los datos válidos.
3. [x] Editar: cambiar el costo a 7.50 y marcar **Con serial**.

## 6. Resultado esperado

- Cada inválido se rechaza con su mensaje; el código repetido dice que ya existe.
- El artículo queda creado con existencia 0 y luego con el costo nuevo.

## 7. Resultado obtenido

- Qué pasó: 12 de 14 comprobaciones bien.
- Diferencias con lo esperado: Costo -1 se guarda (201) y un SKU repetido revienta con 500 (uq_warehouse_item_sku sin capturar).
- Reejecución (25 oct, tras corregir los P2 y D-007, base QA reiniciada): 15 de 15. Costo -1 responde 400 «El costo no puede ser negativo.» (D-009) y el SKU repetido 409 (D-010).
- Reejecución (25 oct, tras corregir D-010, base QA reiniciada): 13 de 14. El SKU repetido 3496 responde 409 «Ya existe un artículo con el código 3496» (D-010 cerrado). Sigue fallando solo por el costo -1 (D-009, abierto).
- Comprobaciones por API (12 de 14):
  - ✘ Artículo con costo -1 se rechaza — `201 {"id":"5ff6c652-a29b-486f-8ee2-bce8fa48383a","name":"QA X","sku":null,"brand":null,"manufacturer_part":null,"category":"other","category_label":"Otro"`
  - ✔ Artículo con costo abc se rechaza — `400 {"detail":"«abc» no es un número válido.","code":"invalid_number","request_id":"7428e99b-c3ec-4ca4-ae2b-b893c7fbf1e2"}`
  - ✘ Artículo con código repetido 3496 se rechaza — `500 Internal Server Error`
  - ✔ Artículo con nombre vacío se rechaza — `422 {"detail":"Hay datos inválidos en: name.","code":"validation_error","request_id":"6476a444-8176-4eae-b927-90af4830225b","errors":[{"field":"name","mes`
  - ✔ Crear «Cinta de aluminio QA» (QA-0001)
  - ✔ Existencia inicial 0 — `0.0`
  - ✔ Editar costo a 7.50 y marcar «con serial» — `200 {"id":"c251c4af-7d68-42f6-8977-8a9a230949ab","name":"Cinta de aluminio QA","sku":"QA-0001-1025164900","brand":null,"manufacturer_part":null,"category"`
  - ✔ Administración crea una categoría propia
  - ✔ El técnico no administra categorías
  - ✔ Artículo con código AC Pro, número del fabricante y marca
  - ✔ El buscador lo encuentra por el número del fabricante — `[{"id": "eef1c8c1-230c-4453-b491-c6096717802c", "name": "QA 1025164900 Condensate Pump 22' Lift", "sku": "QA1025164900-1936", "brand": "Diversitech", "manufactu`
  - ✔ Desactivar la categoría
  - ✔ La categoría desactivada ya no se ofrece
  - ✔ Un artículo nuevo no puede usar la categoría desactivada — `400`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Cambiar el costo no cambia el costo de las salidas ya entregadas.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-009 | Un artículo acepta costo unitario negativo | P2 | `01_REGISTRO_DEFECTOS.md` |
| D-010 | Crear un artículo con un SKU repetido responde 500 | P1 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
