# [BOD-017] El técnico ve su camioneta sin costos

## 1. Información general

- **ID:** BOD-017
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Los costos de bodega son información de la empresa, no del técnico.

## 3. Precondiciones

- Material en la camioneta de Carlos.

## 4. Datos de prueba

- Token de Carlos.

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, abrir lo que puede ver de bodega y su camioneta.
2. [ ] Llamar `GET /api/v1/warehouse/stock` con su token.

## 6. Resultado esperado

- No ve costos ni valor en pantalla ni en la respuesta JSON.
- No ve la bodega de otras camionetas.

## 7. Resultado obtenido

- Qué pasó: Por API, 12 de 12 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (12 de 12):
  - ✔ Administración crea la camioneta del técnico
  - ✔ El técnico ve el artículo sin costo — `{"id": "f0441f61-835e-4d8a-b21f-c714e9403720", "name": "QA 1025164900 Tubo cobre 3/8", "sku": "QA1025164900-CU38", "brand": null, "manufacturer_part":`
  - ✔ De existencias, el técnico solo ve su camioneta (20 ft) — `[{"location_id": "115fbb6d-8eb3-4bb9-a201-9ad6d045aaef", "name": "QA 1025164900 Camioneta", "kind": "truck", "quantity": "20.00"}]`
  - ✔ El buscador del técnico encuentra el capacitor por su referencia, sin costo — `[{"id": "dd8f228d-f675-4f7b-a5a7-04daa1f1f6bd", "name": "QA 1025164900 Capacitor 35/5", "sku": "QA1025164900-CAP", "brand": null, "manufacturer_part": null, "ca`
  - ✔ técnico GET /warehouse/stock → 403
  - ✔ técnico GET /warehouse/movements → 403
  - ✔ técnico GET /warehouse/purchasing → 403
  - ✔ técnico GET /warehouse/budgets → 403
  - ✔ El vendedor no entra a bodega
  - ✔ Contabilidad ve existencias (las entradas por compra son suyas)
  - ✔ Gerencia ve existencias
  - ✔ Gerencia no mueve existencias

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Revisar el JSON completo: ni `unit_cost` ni totales en dinero.

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
