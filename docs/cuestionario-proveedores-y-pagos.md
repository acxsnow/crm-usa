# Cuestionario: Proveedores y cuentas por pagar

**Para:** Delta HVAC
**Preparado por:** equipo de desarrollo del CRM (José Javier Miranda y Mateo Mazo)
**Fecha:** 8 de octubre de 2026

## Por qué les enviamos esto

El documento «Flujo de Trabajo Operativo» (sección 4.4) describe este módulo en dos líneas:

> Registro de proveedores de equipos, materiales eléctricos y contratistas. Programación de pagos y control de vencimientos.

Con eso no alcanza para construirlo bien. Necesitamos entender cómo trabajan hoy con sus proveedores, qué datos manejan y quién hace cada paso.

El módulo también es la base de la **rentabilidad por proyecto** (sección 4.5: lo cobrado al programa menos materiales, gastos del técnico y viáticos). Sin saber cuánto costó cada instalación, la plataforma puede decir cuánto se cobró, pero no cuánto se ganó.

**Cómo responder:** basta con marcar la opción o escribir unas líneas. Si algo no aplica, escriban «No aplica». Si una pregunta no está clara, la vemos en una llamada. Al final les pedimos algunos ejemplos reales; son lo que más nos ayuda.

---

## 1. Alcance y prioridad

1.1 ¿Necesitan este módulo para la primera salida a producción, o puede esperar a una segunda fase?
- [ ] Primera salida
- [ ] Segunda fase
- [ ] No lo necesitamos en la plataforma (lo seguimos llevando en Excel)

1.2 Sabemos que hoy llevan el control en Excel. ¿Es un solo archivo o varios (uno de proveedores, otro de pagos…)? ¿Quién lo actualiza y cada cuánto?

1.3 ¿La plataforma debe reemplazar ese Excel, o lo siguen usando y la plataforma solo lo alimenta (por ejemplo, exportando a Excel)? Ver también la sección 9.

1.4 ¿Cuántos proveedores activos tienen aproximadamente? ¿Cuántas facturas de proveedor reciben al mes?

---

## 2. Quién hace qué

Para cada tarea, indiquen quién la hace hoy: Contabilidad, Administración, Gerencia, el dueño u otra persona.

| Tarea | ¿Quién la hace? |
|---|---|
| Crear o dar de alta a un proveedor nuevo | |
| Registrar una factura que llega de un proveedor | |
| Revisar que la factura corresponde a lo que se recibió | |
| Aprobar que una factura se pague | |
| Programar la fecha de pago | |
| Registrar que el pago se hizo | |
| Consultar lo que se debe y a quién | |

2.1 ¿Una factura necesita aprobación antes de pagarse? Si sí: ¿a partir de qué monto? ¿Una sola aprobación o dos?

2.2 ¿El técnico o el vendedor tienen que ver algo de este módulo? Por ejemplo, el técnico confirmando que recibió el material de un proveedor.

2.3 ¿Gerencia solo consulta o también aprueba pagos?

---

## 3. Datos del proveedor

3.1 ¿Qué tipos de proveedor manejan? Marquen todos los que apliquen.
- [ ] Equipos (mini-splits, bombas de calor)
- [ ] Material eléctrico
- [ ] Contratistas o subcontratistas (instaladores externos, electricistas)
- [ ] Servicios (permisos, grúa, disposición de equipos viejos)
- [ ] Otros (escríbanlos en la respuesta)

3.2 ¿Qué datos de cada proveedor necesitan guardar? Marquen los que sí.
- [ ] Nombre comercial
- [ ] Razón social (nombre legal)
- [ ] Tax ID / EIN
- [ ] Dirección
- [ ] Persona de contacto, teléfono y correo
- [ ] Estados donde opera (California, Arizona, Nevada)
- [ ] Condiciones de pago (contado, Net 15, Net 30, Net 60…)
- [ ] Forma de pago habitual (cheque, ACH, transferencia, tarjeta, Zelle)
- [ ] Datos bancarios para pagarle
- [ ] Licencia de contratista y su vencimiento
- [ ] Seguro (certificado de responsabilidad o workers' comp) y su vencimiento
- [ ] Formulario W-9
- [ ] Otros (escríbanlos en la respuesta)

3.3 Para los contratistas: ¿necesitan generar el formulario 1099 al final del año? ¿Desde la plataforma o desde su sistema contable?

3.4 ¿Hay que guardar documentos del proveedor (W-9, licencia, seguro, contrato)? ¿La plataforma debe avisar cuando una licencia o un seguro está por vencer?

3.5 ¿Manejan una lista de precios por proveedor (por ejemplo, cuánto cuesta cada modelo de mini-split con cada distribuidor)?

---

## 4. Facturas de proveedor

4.1 ¿Qué datos trae una factura de proveedor que necesitan registrar? Marquen los que sí.
- [ ] Número de factura del proveedor
- [ ] Fecha de la factura
- [ ] Fecha de vencimiento
- [ ] Detalle por línea (producto, cantidad, precio unitario)
- [ ] Impuestos (sales tax)
- [ ] Costo de envío
- [ ] Total
- [ ] Orden de compra con la que se pidió
- [ ] El PDF o la foto de la factura
- [ ] Otros (escríbanlos en la respuesta)

4.2 ¿Las facturas se registran con el detalle línea por línea o basta con el total?

4.3 ¿Una factura puede cubrir material para varios proyectos? Si es así, ¿cómo reparten el costo entre ellos?

4.4 ¿Les llegan notas de crédito o devoluciones de proveedores? ¿Cómo las manejan?

4.5 ¿Hacen órdenes de compra antes de pedirle algo a un proveedor, o solo registran la factura cuando llega?

---

## 5. Relación con los proyectos (lo que más importa para la rentabilidad)

5.1 ¿Cada compra a proveedor se asocia a un proyecto (una instalación) específico?
- [ ] Siempre
- [ ] A veces (algunas son para bodega o inventario general)
- [ ] Nunca

5.2 Si compran para bodega: ¿necesitan controlar inventario (cuánto hay, qué sale para cada instalación) o basta con registrar el gasto?

5.3 Hoy el técnico registra en cada instalación los equipos (con modelo y serial) y los materiales usados. ¿Esos equipos y materiales deberían ligarse a la factura del proveedor que los vendió, para saber su costo exacto?

5.4 Un contratista que hace una instalación completa: ¿se le paga por proyecto, por hora o por un monto fijo acordado?

5.5 Para la rentabilidad, ¿qué costos cuentan en cada proyecto? Marquen los que sí.
- [ ] Equipos
- [ ] Materiales
- [ ] Contratistas
- [ ] Gastos del técnico (gasolina, viáticos)
- [ ] Permiso municipal
- [ ] Comisión del vendedor
- [ ] Otros (escríbanlos en la respuesta)

---

## 6. Pagos

6.1 ¿Pagan las facturas completas o también hacen pagos parciales (abonos)?

6.2 ¿Un solo pago puede cubrir varias facturas del mismo proveedor?

6.3 ¿Qué datos registran al pagar? Por ejemplo: fecha, monto, forma de pago, número de cheque o referencia de la transferencia, cuenta bancaria de la que salió, comprobante.

6.4 ¿Programan pagos con anticipación (por ejemplo, «todos los viernes se pagan las facturas que vencen la semana siguiente»)?

6.5 ¿Toman descuentos por pronto pago que ofrezcan los proveedores?

6.6 ¿La plataforma debe hacer el pago (conectada al banco), o solo registrar que ya se hizo por fuera?

---

## 7. Vencimientos y avisos

7.1 ¿Con cuántos días de anticipación quieren el aviso de que una factura está por vencer?

7.2 ¿Quién debe recibir esos avisos, y por dónde: dentro de la plataforma, por correo o por SMS?

7.3 ¿Necesitan ver lo que se debe por antigüedad (al día, vencido 1 a 30 días, 31 a 60, más de 60)?

---

## 8. Reportes

8.1 ¿Qué necesitan consultar de este módulo? Marquen los que sí.
- [ ] Saldo pendiente por proveedor
- [ ] Facturas por vencer en los próximos días
- [ ] Facturas vencidas
- [ ] Pagos hechos en un periodo
- [ ] Compras por proyecto
- [ ] Compras por tipo (equipos, materiales, contratistas)
- [ ] Flujo de caja proyectado (lo que hay que pagar contra lo que se espera cobrar)
- [ ] Otros (escríbanlos en la respuesta)

8.2 ¿Necesitan exportar a Excel o PDF?

---

## 9. Sistema contable y conciliación

9.1 Además del Excel, ¿usan o piensan usar algún sistema contable (QuickBooks, Xero u otro)? ¿Su contador externo trabaja con alguno?

9.2 ¿Cómo debería relacionarse la plataforma con el Excel o el sistema contable?
- [ ] Exportar un archivo (Excel o CSV) que ustedes importan
- [ ] Sincronización automática
- [ ] No necesitamos conexión

9.3 ¿La conciliación bancaria (cuadrar lo que dice el banco contra lo registrado) la hacen hoy en Excel, la hace su contador, o la quieren en la plataforma?

---

## 10. Ejemplos que nos ayudarían mucho

Si pueden, envíennos (pueden tachar datos sensibles):

- [ ] 2 o 3 facturas reales de proveedores: una de equipos, una de material y una de contratista.
- [ ] La hoja de Excel (o la herramienta) con la que hoy llevan proveedores y pagos.
- [ ] Un ejemplo de cómo calculan hoy la ganancia de un proyecto, si ya lo hacen.
- [ ] Una orden de compra, si las usan.

---

## Glosario

- **Cuentas por pagar (AP):** lo que Delta HVAC le debe a otros (proveedores y contratistas). Es lo contrario de lo que ya está en la plataforma: los cobros a los programas y a clientes particulares, que es lo que le deben a Delta HVAC.
- **Net 30:** condición de pago en la que la factura se paga 30 días después de su fecha.
- **W-9 / 1099:** formularios fiscales de EE. UU. para contratistas independientes.
