# [BOD-003] Entrada de mercancía de proveedor

## 1. Información general

- **ID:** BOD-003
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Una compra sube la existencia y queda en el libro.

## 3. Precondiciones

- BOD-002 hecho.

## 4. Datos de prueba

- Entrada de 10 rollos de `QA-0001` a la bodega principal.

## 5. Procedimiento paso a paso

1. [ ] Registrar la entrada.
2. [ ] Ver la existencia y el libro de movimientos.

## 6. Resultado esperado

- Existencia 10; movimiento `entrada` con usuario, fecha y costo.

## 7. Resultado obtenido

- Qué pasó: Por API, 4 de 4 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (4 de 4):
  - ✔ Entrada de 10 rollos
  - ✔ Existencia 10 — `10.0`
  - ✔ El valor de bodega sube USD 75.00 — `7182.39 → 7257.39`
  - ✔ Movimiento `entrada` con usuario y costo — `entrada|True|7.50`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El valor de la bodega sube 10 × 7.50 = USD 75.00.

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
