# [BOD-006] Reintegro: el material vuelve de la camioneta a bodega

## 1. Información general

- **ID:** BOD-006
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Lo que sobra en la obra vuelve a bodega y sale del costo de la obra.

## 3. Precondiciones

- Una salida entregada (INS-003).

## 4. Datos de prueba

- Devolver 1 unidad de un renglón entregado.

## 5. Procedimiento paso a paso

1. [ ] En la salida, **Devolver** la unidad a bodega.
2. [ ] Intentar devolver más de lo entregado.
3. [ ] Revisar la existencia, la camioneta y el costo de la obra en Rentabilidad.

## 6. Resultado esperado

- Bodega sube 1, la camioneta baja 1 y el costo de la obra baja en ese valor.
- No permite devolver más de lo entregado.

## 7. Resultado obtenido

- Qué pasó: 3 de 4 comprobaciones bien.
- Diferencias con lo esperado: Con 1 unidad afuera se registró una devolución de 50 a la obra (201) y la existencia subió 50.
- Reejecución (25 oct, tras corregir D-008, base QA reiniciada): 4 de 4. Devolver 50 con 1 afuera responde 400 «A esta obra solo le quedan 1.00 por devolver de este artículo» y la existencia no cambia. Aprobado.
- Comprobaciones por API (3 de 4):
  - ✔ Devolución de 3 a bodega con la obra
  - ✔ La bodega sube 3 — `7.0`
  - ✔ Lo que sigue afuera baja a 1 — `{'can_cancel': True, 'open_releases': [], 'material_in_field': [{'item_id': 'c283275b-2900-4b1b-bc3f-02c3f9363b92', 'item_name': 'PVC Pipe 3/4" x 10\'', 'sku': `
  - ✘ Devolver más de lo entregado a la obra se rechaza — `201 {"id":"7f16136b-e65a-4345-b8fe-801a5e7d498a","item_id":"c283275b-2900-4b1b-bc3f-02c3f9363b92","item_name":"PVC Pipe 3/4\" x 10'","unit_label":"unidade`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Movimiento `devolucion` con referencia a la salida.
- [ ] Lo entregado no se edita: se corrige con la devolución.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-008 | La devolución a bodega no tiene tope: se devuelve más de lo que salió para la obra | P1 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
