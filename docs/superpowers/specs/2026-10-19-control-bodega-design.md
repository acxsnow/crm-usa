# Control de la bodega, presupuesto y diario de obra — Diseño

**Fecha:** 19 de octubre de 2026 · **Pidió:** Delta HVAC (cuestionario y propuesta del 19 de octubre)

## Problema

Hoy nadie sabe qué hay en la bodega, a qué instalación se fue cada cosa, ni cuánto costó de verdad cada trabajo. El cliente confirma cuatro necesidades:

1. **Salidas autorizadas.** Retirar material de bodega debe generar una orden de salida que autoricen él o el supervisor, de forma electrónica.
2. **Listas predefinidas.** Aires y pedestales siempre llevan el mismo material (a veces cambian algunas cantidades o calibres). Quiere una lista base que el técnico use como checklist para no olvidar lo que sí o sí debe llevar, con cantidades, calibres y extras a mano.
3. **Presupuesto por proyecto.** El supervisor estima antes de instalar; al cerrar se compara lo presupuestado con lo real, y con eso compran por adelantado.
4. **Diario de obra.** Los trabajos fuera de rebate duran varios días, con técnicos distintos cada día. Quiere ver, día por día, qué se gastó, qué se hizo, qué material faltó, hasta dónde se avanzó y qué llevar al día siguiente.

Las respuestas del cuestionario fijan el diseño: hay **1 bodega** y los técnicos guardan extras en la camioneta; el encargado es **Ricardo (supervisor)**; Ricardo recibe la compra; el sobrante vuelve a bodega, **salvo en obras de más de dos días, que queda en la camioneta**; los **equipos grandes van directo a la obra**; si no hay existencias **se entrega igual, con aviso**; el conteo es **mensual** y el inicial será un **fin de semana**; los seriales se exigen para **todos** los equipos; el rol de bodega se da a **Administración**, no se crea uno nuevo.

## Lo que ya existe

- **El patrón a copiar:** `checklist_templates` + `project_checklist_items` (plantilla → copia por proyecto) es justo el mecanismo del punto 2, pero para tareas. Las listas de materiales se modelan igual.
- `field_ops`: `projects` (`case_id`, `project_type`, `scheduled_date`), `installed_equipment` (serial, marca, modelo, con confirmación `equipment_confirmed_at`), `project_materials` — «Lo que la orden necesita (PDF §5.1). No es inventario.» (`field_ops/models.py`, [§ 377](file:///Users/mateo/CRM-USA/crm-usa/backend/app/modules/field_ops/models.py#L376-L389)).
- `finance`: `expenses` (con `project_id` y `expense_date`), `supplier_invoice_lines` (con `project_id`) y `profitability.py`, que ya compara facturado contra costos reales ([profitability.py](file:///Users/mateo/CRM-USA/crm-usa/backend/app/modules/finance/profitability.py)).
- `billing`: `numbering.py` numera por serie con contador bloqueado ([numbering.py](file:///Users/mateo/CRM-USA/crm-usa/backend/app/modules/billing/numbering.py#L22-L26)).
- **No existe:** catálogo de materiales, existencias, movimientos, órdenes de salida, listas predefinidas, presupuesto de proyecto ni diario de obra.

## Diseño

Paquete nuevo `app/modules/warehouse/`, con las reglas de siempre: `organization_id` del token, permiso por ruta, auditoría y aislamiento por organización.

### Existencias (la base)

- `warehouse_items`: nombre, SKU, categoría, unidad, costo unitario, proveedor, `has_serial`, `min_quantity`, `active`. Categorías y unidades de la hoja «Listas» (Tubería y cobre, Eléctrico, Refrigerante, Ductos, Soportes y fijación, Consumibles, Equipos, Herramienta, Otro).
- `warehouse_locations`: **Bodega** y una camioneta por técnico. Es lo que permite «el sobrante queda en la camioneta» cuando la obra pasa de dos días.
- `warehouse_stock`: saldo por (artículo, ubicación); se mueve en la misma transacción que el movimiento.
- `warehouse_movements`: libro que nunca se edita ni se borra. Tipo `entrada` (compra o conteo inicial), `salida` (orden entregada), `devolucion`, `traslado`, `ajuste`. Guarda artículo, ubicación, cantidad con signo, tipo, referencia (factura, orden, conteo), usuario y fecha.
- La lista de existencias avisa cuando un artículo está en o bajo su mínimo.

### Entradas

- **Carga inicial:** importar el Excel del catálogo y registrar el conteo inicial. Crea los artículos y un movimiento de `entrada` por «conteo inicial».
- **Compras:** una línea de factura de proveedor puede ingresar a bodega, sin volver a escribir lo que Contabilidad ya capturó. Las líneas de equipos grandes se marcan **directo a la obra** y no entran.

### Salidas: orden de salida autorizada (punto 1)

- `warehouse_release_orders`: número de serie nueva `SAL`, proyecto (opcional), solicitante, estado `borrador → por autorizar → autorizada / rechazada → entregada`, autorizador y motivo de rechazo.
- `warehouse_release_lines`: artículo, cantidad pedida, cantidad entregada, especificación (calibre), notas y origen (`lista` o `manual`).
- **Flujo:** se arma la orden, se manda a autorizar, autoriza quien tenga el permiso (él o el supervisor), Bodega entrega, y ahí se crean los movimientos y baja el saldo.
- **Sin existencias:** no se bloquea; se entrega con aviso y queda registrado el motivo.
- La autorización es el botón «Autorizar», con permiso propio, y queda en auditoría quién y cuándo. Hay una bandeja **«Salidas por autorizar»** para el autorizador.

### Listas predefinidas por tipo de trabajo (punto 2)

- `warehouse_kit_templates` + `warehouse_kit_items`: nombre («Instalación de aire — estándar», «Pedestal»), tipo de trabajo (`project_type`), sección, artículo, cantidad sugerida, unidad, `spec_label` (calibre) y `is_required`.
- Al armar una orden de salida o un presupuesto se aplica una lista y se **copia** al documento (snapshot, igual que `project_checklist_items`); de ahí en adelante el usuario cambia cantidades y calibres y agrega los extras que pida el trabajo.
- Espera el listado que el cliente envía esta semana; el mecanismo queda listo y la carga es un seed.

### Presupuesto del proyecto (punto 3)

- `project_budgets` + `project_budget_lines`: por proyecto, lo hace el supervisor antes de instalar. Línea: categoría (material, equipo, mano de obra, permiso, otro), artículo del catálogo (opcional), descripción, cantidad, costo unitario y monto. Estados `borrador → aprobado`.
- Se puede generar desde una lista predefinida (punto 2) o a mano.
- **Estimado contra real:** el real es el costo de lo **consumido** —salidas de bodega valoradas a costo del catálogo—, más los gastos de campo (`expenses`) y las compras directas a la obra (`supplier_invoice_lines` sin paso por bodega). Reporte por proyecto con desviación por categoría y total. Reutiliza la forma de `profitability.py`.
- **Decisión D-BOD-2:** lo que entra a bodega es inventario, no costo de la obra; la obra se cuesta cuando el material sale. Así el mismo material no se cuenta dos veces.
- **Compras por adelantado:** reporte agregado de «presupuestado por venir − existencia», por artículo. Es el insumo para comprar antes de la temporada.

### Diario de obra (punto 4)

- `project_day_logs`: proyecto, fecha, técnico(s) del día, horas, qué se hizo, hasta dónde se avanzó, qué material faltó, qué llevar al día siguiente e incidencias.
- `project_day_log_materials`: material usado ese día (artículo o descripción libre, cantidad), que descuenta de lo que la camioneta llevó.
- Los gastos del día **se leen** de `expenses` por fecha; no se vuelven a capturar.
- El técnico vive en la jornada, no en el proyecto: por eso se pueden tener técnicos distintos cada día.
- Pantalla «Diario» dentro del proyecto: una línea por día. La Agenda marca las obras de varios días.

### Permisos y menú

Permisos nuevos (solo líneas nuevas en `shared/permissions.py`): `warehouse.read`, `warehouse.manage`, `warehouse.kits_manage`, `warehouse.request_release`, `warehouse.approve_release`, `warehouse.deliver`, `warehouse.count`, `budgets.manage`, `budgets.approve`, `daylogs.manage`.

Módulo nuevo en `DEFAULT_MODULES`: **Bodega**. Asignación por defecto, según las respuestas 2 y 17:

- `admin_staff` (Administración, donde entra Ricardo): bodega completo, presupuesto y diario.
- `field_technician` (Técnico): `warehouse.request_release`, `warehouse.read`, `daylogs.manage`.
- `accounting` (Contabilidad): `warehouse.read` y las entradas por compra.
- `management` (Gerencia): lectura de bodega, presupuestos y compras sugeridas.

Grupo de menú **Bodega**: Existencias `/warehouse`, Artículos `/warehouse/items`, Listas predefinidas `/warehouse/kits`, Salidas `/warehouse/releases` (con «Salidas por autorizar»), Movimientos `/warehouse/movements`, Conteos `/warehouse/counts`, Compras sugeridas `/warehouse/purchasing`. En el proyecto, dos secciones nuevas: «Presupuesto» y «Diario».

### Avisos

Se suman al catálogo de `notifications`: `warehouse.stock_low` (artículo en mínimo), `warehouse.release_pending` (salida por autorizar) y `warehouse.release_delivered`.

### Fases

- **Fase 0 — Carga inicial.** Catálogo + importación del Excel + conteo inicial. Es lo que se necesita para el fin de semana del primer conteo.
- **Fase 1 — Existencias y salidas autorizadas.** Puntos 1 y base del resto.
- **Fase 2 — Listas predefinidas.** Punto 2.
- **Fase 3 — Presupuesto y estimado contra real.** Punto 3.
- **Fase 4 — Diario de obra.** Punto 4.

## Decisiones a confirmar

- **D-BOD-1:** el conteo inicial carga de una sola vez artículos y cantidades desde el Excel; después, los conteos son ajustes.
- **D-BOD-2:** lo que entra a bodega es inventario, no costo de la obra; la obra se cuesta al salir.
- **D-BOD-3:** los equipos grandes no pasan por bodega, pero su serial sigue siendo obligatorio en «Equipos instalados» (respuestas 11, 14 y 15).
- **D-BOD-4:** sin existencias no se bloquea la entrega; se avisa y se registra el motivo (respuesta 7).
- **D-BOD-5:** no se crea rol «Bodega»; los permisos van a Administración (respuesta 17).

## Fuera de alcance

- Códigos de barras o QR.
- Órdenes de compra a proveedores: solo se **sugiere** qué comprar.
- Integración con QuickBooks.
- Más de una bodega.
- Costeo FIFO o promedio ponderado: se usa el costo del catálogo.

## Datos pendientes del cliente

- Listado predefinido del punto 2 (lo envía esta semana).
- Categorías y calibres de JJ (esta semana).
- Lista de herramientas que sí entran al inventario.
- Fecha del conteo inicial (fin de semana).

## Paquetes

Módulo nuevo `warehouse`. Se tocan archivos compartidos con **solo líneas nuevas**: `shared/permissions.py`, `api/v1/router.py`, `frontend/src/config/navigation.ts` y `frontend/src/app/router.tsx`. Además `billing/numbering.py` (serie `SAL`), `finance` (costo real) y `notifications` (avisos). Todo de Cadena B (Mateo).
