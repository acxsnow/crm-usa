# Costo del trabajo: estimado contra real, plantillas y AC Pro — Diseño

Fecha: 22 de octubre de 2026 · Autor: Mateo Mazo (con Claude), a partir de la reunión con Aldo del 22 oct.
Extiende el módulo de bodega (`docs/superpowers/specs/2026-10-19-control-bodega-design.md`), que ya está en `main`.
El borrador técnico de José (`2026-10-19-modulo-bodega-design.md`, paquete `inventory`) quedó superado por lo construido y no se sigue.

## 1. Para qué y por qué

Aldo hoy lleva el costo de cada trabajo en **Housecall Pro**: arma un estimado o cotización antes de empezar, va cargando la factura, los materiales con su costo, la mano de obra («Labor», con el nombre del técnico, que no sale en la factura del cliente) y los consumibles, y **al final** mira la vista «Job costing breakdown»: margen, ingreso, costos, ganancia, una dona de ingreso (ganancia contra costos) y un desglose del costo por categoría, más el bloque de costos esperados.

La decisión es que **todo se haga en nuestro sistema** y Aldo deje Housecall Pro para esto. El éxito es que, al cerrar un trabajo, Aldo vea en un solo panel cuánto esperaba ganar, cuánto ganó y en qué se fue la diferencia, sin volver a capturar lo que el sistema ya registra (salidas de bodega, facturas de proveedor, gastos de campo, cobros).

Aplica a **todos los trabajos**: los de rebate (incluidos los pedestales) y los particulares.

### Lo que dijo el cliente

- Estimado ideal de un trabajo particular: **40% de ganancia como mínimo, 10% permisos (ciudad, construcción…), 30% materiales, 20% mano de obra**. Cada trabajo es distinto, así que los porcentajes deben poder cambiarse por trabajo.
- Ejemplos reales (pedestales, rebate, precio 4.200 USD):

  | Concepto | Con subcontratista | Con personal propio |
  |---|---|---|
  | Representante de ventas (Luis) | 800 | 800 |
  | Permisos | 230 | 238 |
  | Materiales | 1.070 | 1.062 |
  | Mano de obra | 1.050 (contratista) | 600 (instalador de nómina) |
  | Ganancia neta | 1.050 | 1.500 |

- A veces se subcontrata otra compañía porque tiene las licencias que Delta no tiene; sale más caro y deja menos ganancia. Se quiere ver esa diferencia.
- **Luis** es el otro jefe: consigue clientes y parques y maneja vendedores. Cobra por trabajo **solo en los de rebate**; en los particulares no recibe nada. No saben si hoy su pago se anota como «Labor»: **se dejan las dos opciones** y cada trabajo elige.
- Trabajos de un día: estimado antes, y al terminar se sube la factura final y se compara. Trabajos de varios días: se va cargando día a día (ya existe el diario de obra).
- Materiales: AC Pro tiene **templates** (un carrito con todos los componentes de un tipo de instalación, p. ej. «3 TON HOME MATERIALS FROM SCRATCH»). Usan unos ~600 productos y un PDF con todo no le sale a Aldo.
- Pendiente del cliente: ejemplos de minisplit de rebate y de AC central (estimado y lista de materiales); y cómo funciona exactamente la sección de templates de AC Pro.

## 2. Metas, no metas y anti-metas

**Metas**

1. **Estimado por trabajo** con precio esperado y monto por concepto, armado desde una **plantilla de costos** (por porcentaje o por monto fijo) y ajustable a mano.
2. **Lo real sale solo** de lo que ya registra el sistema, más una forma simple de anotar lo que hoy no existe: **mano de obra** (técnico o subcontratista, monto) y **pago del representante**.
3. **Panel «Costo del trabajo»** en la ficha del proyecto, como el boceto aprobado (ver §6), para rebate y particulares.
4. **Importar templates y carritos de AC Pro desde su PDF**: crea o actualiza productos del catálogo y guarda el template como lista predefinida.

**No metas (por ahora)**

- Nómina: el pago del técnico se anota como monto por trabajo; no se calculan horas ni salarios.
- Migrar el histórico de Housecall Pro.
- Comisiones de los vendedores puerta a puerta (siguen fuera, como en rentabilidad, hasta que el cliente diga cómo se calculan). Luis no es esa comisión: es un concepto propio.
- Entrar a AC Pro con usuario y clave de Aldo para extraer datos (ver §5).

**Anti-metas (fallaría aunque funcione)**

- Contar un costo dos veces (la regla D-BOD-2 sigue: lo que entra a bodega es inventario; cuesta cuando sale).
- Que la mano de obra o el pago de Luis aparezcan en la factura o cotización del cliente.
- Que el técnico vea costos, ganancia o el pago de otros.
- Que Aldo tenga que capturar dos veces algo que el sistema ya sabe.

## 3. Conceptos del tablero

Son los de Aldo, en este orden, y mapean a las categorías del presupuesto que ya existen:

| Concepto del tablero | Categorías (presupuesto y real) |
|---|---|
| Representante | `sales_rep` (**nueva**) |
| Permisos | `permit` |
| Materiales | `materials`, `equipment`, `consumables` (**nueva**) |
| Mano de obra | `labor` (personal propio), `contractor` (subcontratista) |
| Otros | `services`, `other`, gastos de campo (`field_expenses`) |
| **Ganancia** | precio − suma de lo anterior |

El tablero muestra los conceptos agrupados y deja ver el detalle por categoría (por ejemplo, Mano de obra: propio 600 / subcontratista 0).

## 4. Piezas

### 4.1 Estimado (extiende el presupuesto del proyecto)

El presupuesto que ya existe (`project_budgets`, `project_budget_lines`, con aprobación y «reemplazado») **es** el estimado. Cambios:

- `project_budgets.expected_revenue` (Money, opcional): el precio esperado del trabajo. Si está vacío, se usa lo facturado al proyecto cuando exista.
- `project_budgets.template_id` (opcional): de qué plantilla salió, solo como referencia.
- Categorías nuevas `sales_rep` («Representante») y `consumables` («Consumibles») en `BUDGET_CATEGORIES`.
- La ganancia esperada no se guarda como renglón: es `expected_revenue − total del estimado`.

### 4.2 Plantillas de costos (nuevo)

`cost_templates` (por organización): nombre, tipo de trabajo (texto libre, p. ej. «Pedestal»), aplica a `rebate` / `particular` / ambos, activa.
`cost_template_lines`: categoría, descripción, **modo** `percent` o `amount`, valor, orden.

Aplicar una plantilla a un presupuesto en borrador, con un precio esperado:

- Renglón `percent` → monto = precio × %.
- Renglón `amount` → ese monto.
- La ganancia queda como lo que sobra; si la plantilla trae un % de ganancia objetivo (renglón de categoría especial `target_profit`, que no suma al costo), el panel avisa cuando el estimado queda por debajo.
- Se puede aplicar además una **lista predefinida** de materiales (ya existe `apply-kit`) para que Materiales salga del catálogo en vez de un %.

Plantillas iniciales (sembradas en la migración, editables):

1. «Trabajo particular ideal»: ganancia objetivo 40%, permisos 10%, materiales 30%, mano de obra 20%.
2. «Pedestal (rebate) con personal propio»: representante 800, permisos 238, materiales 1.062, mano de obra (propio) 600 → ganancia 1.500 sobre 4.200.
3. «Pedestal (rebate) con subcontratista»: representante 800, permisos 230, materiales 1.070, contratista 1.050 → ganancia 1.050 sobre 4.200.

Pantalla: «Plantillas de costo» dentro del grupo Bodega (o junto a Listas), con quien tenga `budgets.manage`.

### 4.3 Costos reales que hoy no existen (nuevo)

`project_cost_entries`: proyecto, fecha, categoría (`labor`, `contractor`, `sales_rep`, `permit`, `consumables`, `other`), descripción, monto, persona (usuario del sistema **o** nombre libre, p. ej. la compañía subcontratada), nota, quién lo registró.

- Es lo que en Housecall Pro es «Labor»: una línea interna, nunca visible al cliente ni al técnico.
- **Luis:** en trabajos de rebate, al crear el estimado o al cerrar, se ofrece la línea «Representante» con el valor de la plantilla. Cada trabajo elige si su pago va como `sales_rep` o como `labor` (decisión del cliente: dejar las dos).
- **Sin doble conteo:** si el subcontratista o el permiso llegan como **factura de proveedor asignada al proyecto**, ya cuentan por `project_costs`; la pantalla lo muestra y avisa si además se anota una línea manual de la misma categoría y monto parecido. No se bloquea (puede haber dos pagos legítimos).
- Permiso: `budgets.manage` registra y corrige; queda en auditoría.

### 4.4 Lo real

`costing.budget_vs_actual` ya suma salidas de bodega, compras directas y gastos de campo por categoría. Se le agregan las `project_cost_entries` y el **ingreso**:

- **Ingreso real** = lo facturado al proyecto sin anulados (`invoices` del proyecto: en rebate, el cobro al programa; en particular, la factura al cliente). Confirmado por el cliente (22 oct): en rebate el precio del trabajo (p. ej. los 4.200 del pedestal) **es lo que paga el programa**; el cliente no paga nada. Por eso en rebate el precio esperado del estimado se llena con la tarifa vigente del programa (la misma que usa el cobro) y se puede corregir. También se muestra lo **cobrado** (pagos recibidos), igual que en rentabilidad.
- **Ganancia real** = ingreso − costo real. **Margen** = ganancia / ingreso.
- **Cobros adicionales en trabajos de rebate** (dicho por el cliente el 22 oct): en un pedestal el dueño de casa puede pedir algo extra (un breaker, más cable, mover algo). La empresa lo cobra aparte, **no va en la factura al programa** y se recibe **en efectivo**. Se registra en el proyecto como «cobro adicional»: fecha, descripción, monto, forma de pago (efectivo por defecto), quién lo recibió. **El efectivo lo recibe el técnico en la obra y se lo lleva a Aldo**: por eso el técnico del proyecto puede anotar el cobro adicional desde su celular (solo los suyos, sin ver costos ni ganancia), y queda «por entregar» hasta que Aldo u Oficina (`budgets.manage`) marca «recibido». El tablero muestra los cobros adicionales por entregar, para que el efectivo no se pierda entre la obra y la oficina. Suma al **ingreso real** del trabajo y se muestra como renglón propio del ingreso («Programa» + «Adicionales del cliente»). El material o la mano de obra de ese extra entra como cualquier otro costo del trabajo. Nunca aparece en el cobro al programa. Tabla nueva `project_extra_charges` (o un tipo de ingreso equivalente; decide quien construye), con auditoría.
- La rentabilidad por proyecto (`finance/profitability.py`) usa la misma suma, para que el reporte y el panel nunca den números distintos (una sola función de costo real por proyecto).

### 4.5 Importar desde AC Pro (PDF)

Aldo imprime a PDF un template o un carrito de AC Pro y lo sube. Se aceptan los dos formatos que ya mandó:

- **Print Cart** (`bodega.pdf`): por producto, nombre; «Marca | número de fabricante»; «AC Pro: <código>»; cantidad; precio.
- **Template** (`partes.pdf`, «3 TON HOME MATERIALS FROM SCRATCH»): nombre; «MFG #: …»; «Qnty: n»; precio; número del código de barras (= código AC Pro).

Los dos PDF de ejemplo van en `docs/ejemplos/acpro/` (`partes.pdf`: template de 3 páginas, 46 productos; `bodega.pdf`: Print Cart de 24 páginas, subtotal 7.190,39) y son la base de las pruebas del lector. **Comprobado el 22 oct: los dos PDF son solo imagen** (sin fuentes ni capa de texto; `pypdf` no extrae nada). Así no se pueden leer sin OCR. Pendiente del cliente: probar si AC Pro exporta el carrito o template a CSV/Excel, o si «Imprimir → Guardar como PDF» desde Chrome deja texto. Si ninguna sirve, se evalúa OCR (Tesseract en el contenedor) con vista previa obligatoria, porque puede leer mal precios y códigos.

Resultado:

1. Una **vista previa** con cada producto leído (nuevo / existe y cambia precio / existe igual) antes de guardar.
2. Al confirmar: crea los productos nuevos en el catálogo y actualiza el costo de los existentes. La llave es el **código AC Pro** (campo nuevo `warehouse_items.supplier_code`, único por organización cuando no es vacío); el número de fabricante va en `sku` si está vacío.
3. Si el PDF es un template, crea (o actualiza) una **lista predefinida** con su nombre y sus cantidades.
4. La categoría del producto se propone por palabras clave (filter → consumables, wire/connector → electrical, copper/lineset → pipe_copper, duct/plenum → ducts, condenser/air handler/heat pump → equipment, tape/sealant/screw → consumables o supports) y se puede corregir en la vista previa.
5. Nada mueve existencias: importar no es comprar. La compra sigue entrando por factura de proveedor o movimiento de entrada.

Seguridad: mismo validador de archivos (tipo real PDF, tamaño), tope de páginas, y el texto se extrae con una librería PDF pura en Python que pase `pip-audit`.

## 5. AC Pro: por qué no con usuario y clave

Aldo ofreció su usuario y clave de AC Pro para sacar los ~600 productos. No se usan: serían credenciales de un tercero en manos del equipo de desarrollo, y raspar el sitio puede romper sus condiciones de uso. El camino es que Aldo exporte a PDF sus templates y carritos (lo que ya hace) y los suba; el catálogo crece con lo que de verdad usan. Si AC Pro ofrece exportar a CSV o Excel, se acepta también por el importador de catálogo que ya existe.

## 6. El panel «Costo del trabajo»

En la ficha del proyecto, reemplaza al panel «Presupuesto» actual (lo contiene):

- Arriba, cuatro cifras: **margen real** (con el estimado al lado), **ingreso**, **costos del trabajo**, **ganancia**. Mientras el trabajo no tenga ingreso, se muestran las del estimado con la etiqueta «estimado».
- **Dona** del ingreso: ganancia contra costos.
- **Desglose del costo** por concepto (§3), en barra o mapa de bloques.
- **Tabla estimado contra real** por concepto: estimado, % del precio, real, diferencia (en rojo cuando el real supera el estimado o la ganancia queda por debajo), y de dónde sale lo real.
- Acciones: «Armar estimado» (elige plantilla y precio), «Aplicar lista de materiales», «Anotar mano de obra / representante», «Anotar cobro adicional», «Aprobar estimado».
- Aviso de ganancia por debajo del objetivo de la plantilla.
- Diseño: el boceto aprobado (`.superpowers/brainstorm/…/costo-del-trabajo.html`), pulido con el sistema de diseño de la app; usable en celular.

En el reporte de rentabilidad se agrega la columna de **margen estimado** para ver de un vistazo qué trabajos quedaron por debajo.

## 7. Permisos

- Ver el panel: `budgets.manage`, `budgets.approve`, `warehouse.read` (Administración, Gerencia, Contabilidad, Administrador). El técnico no lo ve.
- Armar estimado, aplicar plantilla, anotar costos reales, plantillas e importación de AC Pro: `budgets.manage` (importación también con `warehouse.manage`).
- Aprobar estimado: `budgets.approve`.
- Sin permisos nuevos; si hiciera falta uno, va con migración que lo conceda a los roles existentes.

## 8. Fases

1. **Estimado y plantillas**: campos y categorías nuevas, plantillas con las 3 iniciales, aplicar plantilla, panel con estimado.
2. **Lo real**: `project_cost_entries`, ingreso real, panel completo estimado contra real, rentabilidad usando la misma suma.
3. **AC Pro** (**bloqueada** hasta que el cliente mande un archivo con texto, CSV/Excel o PDF guardado desde Chrome; ver §4.5): importador con vista previa, `supplier_code`, listas desde templates.
4. **Pendientes del cliente**: plantillas de minisplit y AC central cuando lleguen los ejemplos.

Cada fase con pruebas, QA de punta a punta extendido (estimado → salidas → mano de obra → factura → panel) y barrido por rol.

## 9. Decide quien construye

- Nombres exactos de rutas, componentes y archivos, siguiendo los de bodega.
- Librería de gráficas o SVG propio para la dona y el desglose.
- Cómo se extrae el texto del PDF y las expresiones para leer cada formato, con pruebas sobre los dos PDF de ejemplo.
- Palabras clave exactas de la categoría propuesta.
