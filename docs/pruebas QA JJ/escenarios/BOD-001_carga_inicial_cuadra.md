# [BOD-001] La carga inicial cuadra con los PDF de AC Pro

## 1. Información general

- **ID:** BOD-001
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Datos · integridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** 2 min (API + SQL)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

El inventario de arranque es el de los PDF: si no cuadra, todas las pruebas de bodega parten mal.

## 3. Precondiciones

- Base en el estado inicial de QA (244 artículos de la demo, 648 unidades, USD 13,209.22 en bodega).
- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- `backend/scripts/qa_data/catalogo_ac_pro.csv` y `docs/bodega/partes.pdf` / `bodega.pdf`.

## 5. Procedimiento paso a paso

1. [ ] Menú **Bodega**: anotar Artículos activos, unidades y valor del resumen.
2. [ ] Buscar 5 artículos del PDF por su código AC Pro (por ejemplo 85980, 3496, 1578, 27948, 61052) y comparar cantidad y costo.
3. [ ] Abrir **Movimientos de bodega** y filtrar por uno de ellos.

## 6. Resultado esperado

- Resumen: 244 artículos (los de AC Pro; el ajeno no se ve), 648 unidades y USD 13,209.22.
- Cada artículo revisado coincide con el PDF; los repetidos suman sus cantidades.
- Cada uno tiene un solo movimiento de conteo inicial.

## 7. Resultado obtenido

- Qué pasó: La organización demo tiene 244 artículos, 648 unidades y USD 13,209.22. Los 5 SKU revisados coinciden con el CSV transcrito de los PDF en cantidad y costo, y cada uno tiene un solo movimiento de carga inicial. El artículo ajeno no aparece.
- Diferencias con lo esperado: El escenario decía «245 artículos»: 245 son los de toda la base (244 de la demo + 1 de la organización ajena). Corregido el texto del escenario; no es defecto.
- Comprobaciones por API (19 de 19):
  - ✔ resumen de bodega — `{'low_count': 0} · 26 ms`
  - ✔ artículos de la organización demo = 244 (el ajeno no se ve) — `244`
  - ✔ SKU 85980: costo = CSV (1050.00) — `1050.00`
  - ✔ SKU 85980: un solo movimiento de carga inicial — `1`
  - ✔ SKU 3496: costo = CSV (8.00) — `8.00`
  - ✔ SKU 3496: un solo movimiento de carga inicial — `1`
  - ✔ SKU 1578: costo = CSV (39.00) — `39.00`
  - ✔ SKU 1578: un solo movimiento de carga inicial — `1`
  - ✔ SKU 27948: costo = CSV (7.68) — `7.68`
  - ✔ SKU 27948: un solo movimiento de carga inicial — `1`
  - ✔ SKU 61052: costo = CSV (89.34) — `89.34`
  - ✔ SKU 61052: un solo movimiento de carga inicial — `1`
  - ✔ «Artículo Ajeno QA» no aparece — `[]`
  - ✔ SKU 85980: existencia = CSV (1) — `total_quantity=1.00 en ['Bodega']`
  - ✔ SKU 3496: existencia = CSV (11) — `total_quantity=11.00 en ['Bodega']`
  - ✔ SKU 1578: existencia = CSV (3) — `total_quantity=3.00 en ['Bodega']`
  - ✔ SKU 27948: existencia = CSV (4) — `total_quantity=4.00 en ['Bodega']`
  - ✔ SKU 61052: existencia = CSV (3) — `total_quantity=3.00 en ['Bodega']`
  - ✔ totales de la organización demo: 648 unidades y USD 13,209.22 — `SQL: sum(quantity)=648.00, sum(quantity*unit_cost)=13209.22`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación: `select sum(s.quantity), sum(s.quantity*i.unit_cost) from warehouse_stock s join warehouse_items i ...` → 648.00 · 13209.22.

## 9. Validaciones complementarias

- [x] El «Artículo Ajeno QA» de la otra organización NO aparece.

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

- Tiempo de ejecución: 2 min (API + SQL)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Verificado por API y SQL; la pantalla Bodega muestra los mismos datos de la API.
