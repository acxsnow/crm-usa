# Contabilidad para reemplazar QuickBooks

Fecha: 1 de noviembre de 2026. Autor: Mateo Mazo. Módulo `backend/app/modules/accounting/`, pantalla `/accounting`, migración `0048`.

## Decisión de diseño

La contabilidad se **deriva** de los documentos que ya existen, sin tocar sus módulos. `posting.desired()` calcula qué asiento le corresponde a cada documento y `posting.sync()` lo compara con lo registrado: nuevo → asiento; cambiado → reversa y asiento nuevo; anulado o borrado → reversa. Correrla dos veces no cambia nada. Corre cada hora con Celery y antes de cada reporte. Un asiento nunca se edita ni se borra.

## Qué genera asiento (base de causación)

| Documento | Débito | Crédito |
|---|---|---|
| Factura emitida | Cuentas por cobrar | Ingresos (particular o rebate) |
| Pago de factura | Banco, o Stripe por liquidar | Cuentas por cobrar |
| Comisión de Stripe | Comisiones de cobro | Stripe por liquidar |
| Factura de proveedor aprobada | Costo o gasto por categoría; Inventario si entró a bodega | Cuentas por pagar |
| Pago a proveedor | Cuentas por pagar | Banco, o tarjeta |
| Gasto aprobado con tarjeta o desde la banca | Gasto | Tarjeta o banco, según la cuenta real |
| Gasto con dinero propio / reembolso | Gasto / Reembolsos por pagar | Reembolsos por pagar / Banco |
| Salida de bodega / devolución | Costo / Inventario | Inventario / Costo |
| Ajuste de conteo / conteo inicial | Inventario o Ajustes | Ajustes o Patrimonio inicial |
| Cobro adicional en obra | Fondos por depositar | Cobros adicionales |

## Lo que queda por asiento manual, a propósito

- **Nómina y mano de obra:** el sistema no calcula ni paga nómina, y `warehouse/labor.py` es un costo de gestión; causarlo solo contaría la nómina dos veces.
- **Traslados entre cuentas:** liquidación de Stripe al banco, depósito del efectivo y pago de la tarjeta.
- **Saldos iniciales** al arrancar y aportes de los socios.

## Controles

- Cierre contable (`locked_through`): nada se registra con fecha cerrada; lo que cambie después cae el primer día abierto y el documento conserva su fecha en `source_date`.
- Un asiento manual debe cuadrar y se corrige con reversa; uno automático se corrige en su documento.
- Permisos: `accounting.read` (Administrador, Contabilidad, Gerencia), `accounting.manage` (Administrador, Contabilidad) y `accounting.export` para los CSV. Aislamiento por organización en toda consulta. Los CSV neutralizan fórmulas de Excel.

## Impuestos

`GET /accounting/reports/tax-summary` da el resultado del año por renglón y la lista para el **1099-NEC**: proveedores de contratistas o servicios con pagos desde el umbral del año, sin tarjeta, y qué les falta (W-9, TIN, dirección). Umbral: $600 para pagos de 2025 y **$2,000 desde 2026** (P.L. 119-21; se indexa por inflación después de 2026, y se puede pasar `threshold`).

Es el insumo para el contador: **no presenta nada** ante el IRS ni ante el estado, no calcula impuesto de ventas ni nómina (941, W-2), y los renglones los valida el contador según el tipo de empresa.

## Límites conocidos

- Una sola cuenta de banco del sistema; el contador puede crear más y mover con asientos manuales. No se concilia solo contra los saldos de Plaid.
- `sync()` recorre los documentos de la organización: bien para este volumen; si crece mucho, habría que hacerlo incremental.
- Sin multimoneda ni presupuesto contable. Falta que el contador del cliente valide el plan de cuentas antes de cerrar un año real.
