# [FIN-002] Proveedor, factura de compra y pago

## 1. Información general

- **ID:** FIN-002
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · dinero
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Las cuentas por pagar se registran y pagan con su soporte.

## 3. Precondiciones

- Sesión de `contabilidad@demo-org.com`.

## 4. Datos de prueba

- Proveedor «HOME DEPOT»; factura de USD 350.00 a 30 días.

## 5. Procedimiento paso a paso

1. [ ] **Proveedores y pagos**: crear el proveedor y la factura.
2. [ ] Pagarla con **Adjuntar comprobante**.
3. [ ] Crear otro proveedor con el mismo nombre.

## 6. Resultado esperado

- Saldo en cero tras el pago.
- Anotar si permite el proveedor duplicado.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 32 de 32 comprobaciones bien. Proveedor «HOME DEPOT» y factura de USD 350.00 a 30 días, pagada con comprobante: saldo 0. El proveedor con el mismo nombre se rechaza (409 «Ya hay un proveedor con ese nombre.»). Además el flujo de proveedores: factura con líneas por obra, duplicada rechazada, dos aprobaciones sobre el umbral, pago repartido y antigüedad. Una factura o pago con un campo inválido respondía 500: D-016, corregido (422).
- Diferencias con lo esperado: Ninguna después de corregir D-016.
- Comprobaciones por API (32 de 32):
  - ✔ Contabilidad crea proveedor de equipos con datos bancarios
  - ✔ Importar proveedores desde CSV (QuickBooks)
  - ✔ Dos proveedores importados — `{'created': 2, 'skipped': 0, 'invalid': []}`
  - ✔ Gerencia (Aldo) no ve datos bancarios
  - ✔ Factura de equipos con líneas por instalación (TECH y Arizona)
  - ✔ Total con impuestos y envío (4270.00) — `4270.00`
  - ✔ Factura duplicada se rechaza
  - ✔ Aldo (Gerencia) aprueba
  - ✔ Aldo programa el pago
  - ✔ Factura de contratista de 12.500 USD
  - ✔ Necesita dos aprobaciones — `['approve', 'accounting']`
  - ✔ Primera aprobación (Aldo)
  - ✔ Aldo no puede dar la segunda
  - ✔ Segunda aprobación (Contabilidad)
  - ✔ Aprobada con las dos — `approved`
  - ✔ Compra con tarjeta, pagada al momento
  - ✔ Queda pagada sin pasar por aprobación — `paid`
  - ✔ Factura de material que vence en 3 días (para la alerta)
  - ✔ Pago que no cuadra con el reparto se rechaza
  - ✔ Pago de dos facturas: completa la primera y abona 2.500 a la grande
  - ✔ Grande parcial con saldo 10.000 (10000.00)
  - ✔ Antigüedad de cuentas por pagar
  - ✔ Aparece lo que se le debe al proveedor
  - ✔ Exportación de pagos para el contador
  - ✔ El técnico no entra a proveedores
  - ✔ Crear el proveedor «HOME DEPOT»
  - ✔ Factura con el proveedor vacío → 422, no 500 (D-016) — `422 {"detail":"Hay datos inválidos en: data.supplier_id, data.number, data.invoice_date.","code":"validation_error","request_id":"782f4617-e970-4f35-8eb2-`
  - ✔ Factura de USD 350.00 a 30 días — `201 {"id":"716eb280-e4ca-4c98-b203-ce863f556f64","supplier_id":"2b708b32-a1ff-40bc-a7b6-1e451730c0d4","supplier_name":"QA HOME DEPOT C2 1025214209","numbe`
  - ✔ Gerencia la aprueba
  - ✔ Pagarla adjuntando el comprobante — `201 {"id":"d9cbd5dd-de23-4643-bd2e-d1e1b2d78491","supplier_id":"2b708b32-a1ff-40bc-a7b6-1e451730c0d4","supplier_name":"QA HOME DEPOT C2 1025214209","paid_`
  - ✔ Saldo en cero tras el pago — `0.00 paid`
  - ✔ Proveedor con el mismo nombre (anotar): 409 — `{"detail":"Ya hay un proveedor con ese nombre.","code":"supplier_duplicate","request_id":"93b624c6-3d94-40a4-bd8c-735530`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo quien tiene «Autoriza pagos» puede pagar.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-016 | Factura, pago y gasto con datos inválidos responden 500 | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
