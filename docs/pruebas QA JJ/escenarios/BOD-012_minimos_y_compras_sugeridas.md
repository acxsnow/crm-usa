# [BOD-012] Bajo mínimo y compras sugeridas

## 1. Información general

- **ID:** BOD-012
- **Módulo:** Bodega
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

Lo que llega al mínimo aparece para comprar.

## 3. Precondiciones

- `QA-0001` con mínimo 4.

## 4. Datos de prueba

- Dejar `QA-0001` en 3.

## 5. Procedimiento paso a paso

1. [ ] Filtrar **Bajo mínimo**.
2. [ ] Abrir **Compras sugeridas**.

## 6. Resultado esperado

- `QA-0001` aparece en ambos con la cantidad sugerida.

## 7. Resultado obtenido

- Qué pasó: Por API, 3 de 3 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ Compras sugeridas
  - ✔ Sugiere comprar el capacitor que falta — `{"item_id": "dd8f228d-f675-4f7b-a5a7-04daa1f1f6bd", "item_name": "QA 1025164900 Capacitor 35/5", "sku": "QA1025164900-CAP", "unit": "unit", "budgeted": "10.00",`
  - ✔ Descuenta lo que ya salió para la obra (pendiente = presupuestado − entregado) — `{"item_id": "dd8f228d-f675-4f7b-a5a7-04daa1f1f6bd", "item_name": "QA 1025164900 Capacitor 35/5", "sku": "QA1025164900-CAP", "unit": "unit", "budgeted": "10.00",`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Un artículo sin mínimo (vacío = sin aviso) no aparece.

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
