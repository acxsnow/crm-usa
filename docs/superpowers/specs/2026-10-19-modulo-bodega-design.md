# Módulo de bodega (inventario) — Diseño técnico

**Fecha:** 19 de octubre de 2026 · **Para:** equipo de desarrollo (José, Mateo)
**Estado:** borrador. Falta: las respuestas del cuestionario y decidir quién lo construye. Con eso se escribe el plan.

Implementa la mecánica de la propuesta al cliente (`docs/propuesta-control-bodega.docx`) y la carga inicial del cuestionario (`docs/cuestionario-control-bodega.xlsx`).

## 1. Alcance

- **Primera versión:**
  - una sola bodega y su catálogo;
  - entradas por factura de proveedor;
  - entrega y devolución por orden;
  - seriales por unidad para los equipos;
  - costo promedio ponderado;
  - conteo físico con ajuste aprobado;
  - aviso de cantidad mínima;
  - costo de lo que sale de bodega en la rentabilidad.
- **Fuera:**
  - varias bodegas o material en la camioneta;
  - órdenes de compra y recepción parcial;
  - códigos de barras o QR;
  - precios por proveedor.

  El modelo deja espacio (`warehouse_id` a futuro), pero no se construye.

## 2. De la mecánica a las piezas

| Paso de la propuesta | Dónde | Qué escribe | Paquete |
|---|---|---|---|
| 0. Catálogo inicial | Bodega › Catálogo (nueva) e importación del Excel | `inventory_items` y un movimiento `opening` por ítem | inventory (nuevo) |
| 1. Llega una compra | Proveedores y pagos (existe) | Línea de factura con `inventory_item_id` y destino `stock`. Genera un movimiento `receipt` y, si aplica, los seriales | finance + inventory |
| 2. Se prepara la instalación | Proyecto › Orden liberada › Materiales (existe) | `project_materials.inventory_item_id` | field_ops |
| 3. La bodega entrega | Bodega › Entregas y devoluciones (nueva) | Movimiento `delivery` con `project_id`; el serial pasa a `delivered` | inventory |
| 4. El técnico instala | Proyecto › Equipos instalados (existe) | `installed_equipment.inventory_serial_id`; el serial pasa a `installed` | field_ops + inventory |
| 5. Lo que sobra vuelve | Bodega › Entregas y devoluciones | Movimiento `return` con `project_id`; el serial vuelve a `in_stock` | inventory |
| Conteo y mínimos | Bodega › Conteos y Existencias | `inventory_counts`, que al aprobarse genera un movimiento `adjustment`; aviso `inventory.below_minimum` | inventory + notifications |

## 3. Modelo de datos (paquete nuevo `app/modules/inventory/`)

La existencia no se guarda: se calcula del libro de movimientos. Los movimientos son inmutables y un error se corrige con otro movimiento (un ajuste), igual que `case_stage_events`. Dinero y cantidades van en `Decimal` (`billing/money.py`).

### `inventory_items`

| Columna | Tipo | Nota |
|---|---|---|
| `id`, `organization_id` | GUID | `OrgScopedMixin`; único por (`organization_id`, `sku`) |
| `sku`, `name`, `category`, `unit` | texto | Categorías y unidades editables (hoja «Listas» del Excel) |
| `tracks_serial` | bool | Equipos: cada unidad con serial; se entrega e instala por serial |
| `equipment_type` | texto, nulo | Código de `EQUIPMENT_TYPES` cuando es un equipo (para «Equipos instalados») |
| `min_quantity` | Numeric(12,2) | Umbral del aviso |
| `average_cost` | Numeric(12,4) | Costo promedio vigente; se recalcula en cada entrada |
| `active` | bool | Un ítem con movimientos no se borra: se desactiva |

### `inventory_movements` (el libro)

| Columna | Tipo | Nota |
|---|---|---|
| `id`, `organization_id`, `item_id` | GUID | Índice (`organization_id`, `item_id`, `created_at`) |
| `kind` | enum | `opening` · `receipt` · `delivery` · `return` · `adjustment` |
| `quantity` | Numeric(12,2) | Con signo: lo que entra suma, lo que sale resta |
| `unit_cost` | Numeric(12,4) | Foto del costo: en `receipt`, el de la factura; en una salida, el promedio de ese momento |
| `project_id` | GUID, nulo | Obligatorio en `delivery` y `return` |
| `supplier_invoice_line_id` | GUID, nulo | En `receipt`. Único: una línea entra una sola vez |
| `technician_user_id` | GUID, nulo | A quién se entregó o quién devolvió |
| `reason` | texto, nulo | Obligatorio en `adjustment` |
| `created_by_user_id`, `created_at` | — | Además deja evento de auditoría `inventory.*` |

### `inventory_serials`

| Columna | Tipo | Nota |
|---|---|---|
| `id`, `organization_id`, `item_id`, `serial` | — | Único por (`organization_id`, `item_id`, `serial`) |
| `status` | enum | `in_stock` · `delivered` · `installed` · `returned_to_supplier` |
| `project_id` | GUID, nulo | Orden a la que se entregó o en la que se instaló |
| `receipt_movement_id`, `last_movement_id` | GUID | Trazabilidad compra → entrega → instalación |

### `inventory_counts` e `inventory_count_lines`

El conteo pasa por `draft` → `submitted` → `approved`. Cada línea guarda lo contado y lo que decía el sistema. Al aprobar, la diferencia se convierte en un movimiento `adjustment` con el motivo del conteo.

## 4. Cambios en lo que ya existe

### finance · `SupplierInvoiceLine`

- Columnas nuevas: `inventory_item_id` (nulo) y `destination` (`stock` | `project`).
- **Con `stock`:**
  - `project_id` debe quedar nulo;
  - al registrar la factura se crea el `receipt`;
  - si el ítem tiene `tracks_serial`, los seriales se capturan en la misma pantalla.
- **Con `project`:** todo sigue igual que hoy.

> **Para no contar dos veces el mismo costo:** lo que entra a bodega no se carga al proyecto en la factura; su costo llega al proyecto cuando se entrega. Para anular una factura con líneas a bodega, esas unidades tienen que seguir en existencia; si ya salieron, hace falta un ajuste explícito.

### field_ops · `ProjectMaterial`

- Columna nueva: `inventory_item_id` (nulo).
- Las órdenes viejas se quedan con texto libre. Las nuevas eligen del catálogo y muestran la existencia.

### field_ops · `InstalledEquipment`

- Columnas nuevas: `inventory_serial_id` (nulo) y `source` (`stock` | `manual`).
- En «Equipos instalados», el técnico elige entre los seriales entregados a su orden. Marca, modelo y serial salen del catálogo.
- `manual` queda para un equipo que no pasó por bodega; Administración lo ve resaltado al confirmar el acta.
- Agregar o quitar un equipo sigue anulando `equipment_confirmed_at`.

### field_ops · cierre de la instalación

- `installation_gaps` no bloquea por material sin devolver, solo avisa. Se puede configurar para que bloquee.
- La confirmación del acta muestra, por ítem, lo entregado, lo instalado y lo devuelto.

### finance · `profitability.project_costs`

- Categoría nueva `stock_materials`: Σ(−`quantity` × `unit_cost`) de los movimientos `delivery` y `return` del proyecto.
- Se agrega a `COST_KEYS`.

### notifications

- Aviso `inventory.below_minimum` (audiencia: `inventory.manage`) dentro de `daily_alerts`, con `dedupe_key` por ítem y día.

## 5. API (prefijo `/api/v1/inventory`)

| Ruta | Permiso | Qué hace |
|---|---|---|
| `GET/POST /items`, `PUT /items/{id}` | `inventory.read` / `inventory.catalog` | Catálogo paginado (filtros: texto, categoría, bajo mínimo) |
| `POST /items/import` | `inventory.catalog` | Carga la hoja «Catálogo» (CSV o XLSX) con las existencias iniciales y reporta las filas inválidas, como `import_suppliers_csv` |
| `GET /stock` | `inventory.read` | Existencia y valor por ítem, calculados del libro |
| `GET /movements` | `inventory.read` | Libro paginado (por ítem, proyecto, tipo y fechas) |
| `POST /projects/{id}/deliveries` | `inventory.move` | Entrega: líneas {ítem, cantidad}, seriales y técnico. Valida la existencia |
| `POST /projects/{id}/returns` | `inventory.move` | Devolución de lo entregado a esa orden |
| `GET /projects/{id}/kit` | `projects.read_*` | Lista de la orden frente a lo entregado, instalado y devuelto. La usan el técnico y la confirmación del acta |
| `CRUD /counts`, `POST /counts/{id}/approve` | `inventory.count` / `inventory.adjust_approve` | Conteos y aprobación de ajustes |

Todas las rutas:
- paginan en la base (`paginate`);
- toman el `organization_id` del token;
- usan `get_visible_project` cuando son por proyecto, como el resto de `field_ops`.

## 6. Reglas

- **Costo promedio ponderado al entrar:** `nuevo = (existencia × promedio + cantidad × costo) / (existencia + cantidad)`. Las salidas no lo cambian: usan el promedio vigente como `unit_cost`.
- **Sin existencias no se entrega** (`409 out_of_stock`). El ajuste de organización `inventory_allow_negative` cambia esto a «permitir con aviso».
- **Concurrencia:** la entrega bloquea el ítem con `SELECT … FOR UPDATE`, así dos entregas simultáneas no dejan existencia negativa. Es el mismo mecanismo de la numeración en `billing/numbering.py`.
- **Un serial está en un solo lugar:** solo se entrega si está `in_stock`, y solo se instala si está `delivered` a esa misma orden.
- **Nada se borra:** cada movimiento deja su evento de auditoría.

## 7. Permisos y rol

Permisos nuevos en `shared/permissions.py`, agregados como líneas nuevas: `inventory.read`, `inventory.catalog`, `inventory.move`, `inventory.count`, `inventory.adjust_approve` e `inventory.manage` (avisos). Rol nuevo `warehouse` («Bodega») en la migración y en el seed, como se hizo con `payables.approve` en la 0025.

| Rol | Permisos de bodega |
|---|---|
| Bodega (nuevo) | read, move, count |
| Administración | read, catalog, manage |
| Contabilidad | read, catalog |
| Gerencia | read, adjust_approve |
| Técnico | Ninguno; ve el kit de sus órdenes con `projects.read_assigned` |
| Administrador | Todos |

## 8. Pantallas

- **Nueva:** «Operación de campo › Bodega», con pestañas Catálogo, Existencias, Entregas y devoluciones, y Conteos (`navigation.ts`, permiso `inventory.read`).
- **Se amplían:**
  - Proveedores y pagos: cada línea con su ítem, su destino y sus seriales.
  - Materiales de la orden: selector del catálogo con la existencia.
  - Equipos instalados: elegir un serial entregado.
  - Confirmación de Administración: el kit de la orden.
  - Rentabilidad: columna del costo de bodega.
- **Celular:** la entrega se hace en la bodega, con tablet o computador. «Equipos instalados» ya funciona en el celular.

## 9. Migración y carga inicial

- **Migración `0027_inventory`:**
  - las tablas nuevas;
  - columnas en `supplier_invoice_lines`, `project_materials` e `installed_equipment`, todas nulas;
  - los permisos y el rol.

  Debe poder revertirse.
- **Carga inicial:** se importa la hoja «Catálogo», que crea los ítems y un movimiento `opening` por cada uno con su costo. Los equipos con serial necesitan los seriales que hay en existencia; falta decidir si van en una columna o en una segunda hoja.
- **Datos existentes:** no se migran. Lo anterior queda como texto libre.

## 10. Pruebas clave

- Costo promedio con varias entradas y salidas; la existencia es la suma del libro.
- Entrega sin existencia (409) y dos entregas simultáneas.
- Seriales: uno no se entrega dos veces, y no se instala uno entregado a otra orden.
- Una factura a bodega no suma al proyecto; la entrega sí suma y la devolución resta.
- El técnico ve solo el kit de sus órdenes; otra organización no ve nada.
- El aviso de mínimo sale una vez por día.
- QA de punta a punta extendido: compra → entrega → instalación → devolución → rentabilidad.

## 11. Decisiones abiertas (cuestionario)

| Pregunta | Qué cambia en el diseño |
|---|---|
| P1 · ¿Varias bodegas o camionetas? | Si la respuesta es sí, `warehouse_id` en los movimientos desde la primera versión |
| P6 y P11 · ¿Compras que van directo a la obra? | Cuántas líneas usan destino `project`, y la entrada y entrega en un solo paso |
| P7 · ¿Se entrega sin existencia? | Valor por defecto de `inventory_allow_negative` |
| P10 · ¿Entran las herramientas? | Si entran, hace falta préstamo con devolución obligatoria (otra regla) |
| P13 y P14 · Seriales | En qué momento se capturan y para qué tipos de equipo |
| P15 · ¿Serial obligatorio desde ya? | Cambio pequeño en `EquipmentPanel`, independiente del módulo |
| P16 y P17 · ¿Rol Bodega? | Crear `warehouse` o sumar los permisos a un rol que ya existe |

**Paquetes:** `inventory` es nuevo y toca `finance`, `field_ops` y `notifications`, que son de Mateo. Hay que definir quién lo construye antes de escribir el plan.
