# Gastos de campo, proveedores y pagos, conciliación y rentabilidad, reportes, permisos e inspecciones

Fecha: 13 de octubre de 2026. Cadena B (Mateo). Paquete nuevo `app/modules/finance/`
(gastos, cuentas por pagar, conciliación, rentabilidad y reportes) y una vista nueva en
`field_ops` (permisos e inspecciones). Base: `Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`
§4.4–4.5 y las respuestas del cliente al cuestionario de proveedores (8 oct).

## Respuestas del cliente (decisiones)

| Pregunta | Respuesta | Cómo queda |
|---|---|---|
| 1.2 Control hoy | Lo que se compra se paga al momento, o con tarjeta de crédito | Una factura se puede registrar **ya pagada** (contado o tarjeta) |
| 1.3 Sistema contable | Reemplazar QuickBooks y Housecall, cargando la información que ya tienen | Importación de proveedores por CSV y exportación CSV de facturas y pagos |
| 1.4 Volumen | 10 a 30 facturas por proveedor al mes | Listas paginadas y filtros por proveedor, estado y fechas |
| 2 Quién hace qué | Proveedores, aprobar y programar el pago: Aldo Martínez. Registrar y revisar facturas, registrar el pago: Contabilidad. Consultar: ambos | Permiso nuevo `payables.approve` (Gerencia y Administrador, donde está Aldo). Contabilidad: `payables.manage` y `suppliers.manage` |
| 2.1 Aprobación | Desde 10.000 USD dos aprobaciones: Contabilidad y Aldo | Bajo el umbral: una aprobación con `payables.approve`. Desde el umbral: dos personas distintas, una con `payables.approve` y otra con `payables.manage`. El umbral es configurable |

## Supuestos por confirmar con el cliente (lo que el cuestionario no respondió)

- Tipos de proveedor: equipos, material eléctrico, contratistas, servicios, otros.
- Datos del proveedor: los del §3.2 completos; los datos bancarios solo los ve quien tiene `payables.manage`.
- Facturas con o sin líneas; cada línea se puede asignar a un proyecto (así se calcula la rentabilidad).
- Pagos parciales y un pago para varias facturas del mismo proveedor.
- La plataforma **no paga**: registra el pago hecho por fuera.
- Aviso de vencimiento 5 días antes, en la app (y correo si la persona lo tiene activo).
- Gastos de campo: categorías gasolina, viáticos, hotel, comida, peajes y parqueo, material menor, herramienta, otro; foto del recibo obligatoria; tope de 5.000 USD por gasto; los aprueba Contabilidad (`expenses.approve`).
- Rentabilidad por proyecto = lo cobrado − (facturas de proveedor asignadas al proyecto + gastos aprobados del proyecto). La comisión del vendedor queda fuera hasta que el cliente diga cómo se calcula.

## Módulos

### Gastos de campo (`/expenses`)
El técnico o vendedor registra el gasto con foto del recibo (validada como toda subida) y, si aplica,
el proyecto. Contabilidad aprueba o rechaza con motivo; nadie aprueba lo propio. Lo pagado con dinero
propio se marca reembolsado. Avisos: gasto por revisar (a quien aprueba) y gasto revisado (a quien lo registró).

### Proveedores y pagos (`/payables`)
- Proveedores con documentos (W-9, licencia, seguro, contrato) y vencimientos; alerta diaria de licencia o seguro por vencer.
- Facturas: número del proveedor (único por proveedor), fechas (vencimiento según las condiciones de pago), líneas o total, impuestos, envío, archivo. Estados: por aprobar → aprobada → pagada parcialmente → pagada; anulada con motivo.
- Pagos: fecha, monto, forma, referencia, cuenta, comprobante; reparto entre facturas aprobadas del proveedor sin pasarse del saldo.
- Antigüedad: al día, 1–30, 31–60, 61–90, más de 90 días. Alerta diaria de facturas por vencer.
- Exportación CSV (`accounting.export`) e importación de proveedores por CSV.

### Conciliación y rentabilidad (`/finance-close`)
- **Rentabilidad** (`profitability.read`): por proyecto, esperado, cobrado, costos por tipo, margen y %; totales y filtros por fechas y programa.
- **Conciliación bancaria** (`reconciliation.manage`): importar el extracto CSV del banco; cada movimiento se cruza con lo registrado (pagos recibidos, pagos a proveedores, reembolsos de gastos) por monto y fecha ±5 días; los que coinciden sin ambigüedad se concilian solos, el resto a mano o se marcan como «otro» con nota.

### Reportes (`/reports`, `reports.view`; CSV con `reports.export`)
- Comercial: visitas por resultado, expedientes por etapa, conversión, días hábiles hasta aprobación, rechazos y devoluciones, por vendedor.
- Operación: instalaciones por semana y por técnico, inspecciones aprobadas y fallidas, días de aprobación a instalación.
- Finanzas: cobrado por mes, por cobrar, por pagar con antigüedad, gastos por categoría.
Todo sale de los datos guardados (`case_stage_events` para los tiempos).

### Permisos e inspecciones (`/permits`)
Vista de todos los permisos (estado, vencimiento) e inspecciones (agendadas, resultados) de los proyectos,
con filtros. Lo que se registra sigue estando en el proyecto.

## Fuera de alcance
Pagar desde la plataforma (conexión bancaria), sincronización automática con QuickBooks, 1099,
inventario de bodega, órdenes de compra, lista de precios por proveedor.
