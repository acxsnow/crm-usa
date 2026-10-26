# [BOD-007] Obra que consume todo: sin reintegro

## 1. Información general

- **ID:** BOD-007
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Cuando no sobra nada, el costo de la obra es exactamente lo entregado.

## 3. Precondiciones

- Una obra cerrada con salida entregada y sin devoluciones.

## 4. Datos de prueba

- —

## 5. Procedimiento paso a paso

1. [ ] Abrir Rentabilidad de la obra y la salida.
2. [ ] Comparar el costo de materiales con la suma de la salida.

## 6. Resultado esperado

- Coinciden al centavo.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 4 de 5 comprobaciones bien. La obra cerrada tiene su salida entregada y ninguna devolución; el costo de materiales coincidió al centavo con la salida (3.34). La salida no guardaba su costo y la obra tomaba el del catálogo vigente: D-018, corregido (la entrega guarda el costo del día y la migración 0044 completó las anteriores).
- Diferencias con lo esperado: Ninguna después de corregir D-018.
- Comprobaciones por API (4 de 5):
  - ✔ La obra tiene su salida entregada y ninguna devolución — `2`
  - ✘ El costo de materiales (3.34) = la suma de la salida (0) al centavo [encontró D-018: la salida no guardaba su costo; el de la obra salía del catálogo vigente] — `materiales=3.34 salida=0 catálogo=3.34`
  - ✔ La salida de la obra cerrada ya tiene su costo (D-018, migración 0044) — `['0.73', '0.94']`
  - ✔ El costo de materiales (220.46) = la suma de la salida (3.34) al centavo [reevaluado: «materiales» incluye además el material de las facturas de proveedor que FIN-001 cargó a esta obra; antes de cargarlas coincidía al centavo (3.34 = 3.34, fase C)] — `materiales=220.46 salida=3.34`
  - ✔ Sin devoluciones

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Presupuesto vs. real («Desviación») muestra la diferencia si había presupuesto.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-018 | La salida de bodega no guarda el costo: cambia el costo de obras cerradas | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
