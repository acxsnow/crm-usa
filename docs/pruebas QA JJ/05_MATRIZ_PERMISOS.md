# Matriz de permisos por rol

Sacada del código (`backend/app/shared/permissions.py`, `DEFAULT_ROLE_PERMISSIONS`) en `main 23260ae`. Es lo que traen los roles de sistema al crear la organización; el Administrador puede cambiarlos en **Roles y permisos**.

En SEC-003 se prueba cada fila por la API con el token de cada rol y se anota en la última columna si coincide (✔) o el defecto (`D-###`).

| Permiso | Qué permite | Admin | Administración | Vendedor | Técnico | Contabilidad | Gerencia | Verificado en SEC-003 |
|---|---|---|---|---|---|---|---|---|
| `customers.create` | Crear clientes | ✔ | ✔ | ✔ |  |  |  | |
| `customers.read` | Ver clientes | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| `customers.update` | Editar clientes | ✔ | ✔ | ✔ |  |  |  | |
| `customers.delete` | Eliminar clientes | ✔ |  |  |  |  |  | |
| `contacts.manage` | Gestionar contactos del cliente | ✔ | ✔ | ✔ |  |  |  | |
| `activities.manage` | Gestionar actividades | ✔ | ✔ | ✔ |  |  |  | |
| `cases.create` | Crear expedientes | ✔ |  | ✔ |  |  |  | |
| `cases.read_own` | Ver los expedientes propios | ✔ |  | ✔ |  |  |  | |
| `cases.read_all` | Ver todos los expedientes | ✔ | ✔ |  |  | ✔ | ✔ | |
| `cases.submit` | Enviar expedientes a revisión | ✔ |  | ✔ |  |  |  | |
| `cases.review` | Revisar y devolver expedientes | ✔ | ✔ |  |  |  |  | |
| `cases.approve` | Aprobar o rechazar expedientes | ✔ | ✔ |  |  |  |  | |
| `cases.close_admin` | Cerrar expedientes administrativamente | ✔ | ✔ |  |  |  |  | |
| `dashboards.commercial` | Ver el tablero comercial | ✔ | ✔ |  |  |  | ✔ | |
| `documents.manage` | Cargar y reemplazar documentos | ✔ | ✔ | ✔ |  |  |  | |
| `documents.review` | Aceptar o rechazar documentos | ✔ | ✔ |  |  |  |  | |
| `projects.create` | Crear proyectos | ✔ | ✔ |  |  |  |  | |
| `projects.read_all` | Ver todos los proyectos | ✔ | ✔ |  |  | ✔ | ✔ | |
| `projects.read_assigned` | Ver los proyectos asignados | ✔ |  |  | ✔ |  |  | |
| `projects.update` | Editar proyectos | ✔ | ✔ |  |  |  |  | |
| `projects.assign` | Asignar personas a proyectos | ✔ | ✔ |  |  |  |  | |
| `projects.close` | Cerrar proyectos | ✔ | ✔ |  |  |  |  | |
| `tasks.manage` | Gestionar tareas | ✔ | ✔ |  | ✔ |  |  | |
| `checklists.manage` | Administrar plantillas de checklist | ✔ | ✔ |  |  |  |  | |
| `checklists.complete` | Completar ítems del checklist en campo | ✔ | ✔ |  | ✔ |  |  | |
| `checklists.approve` | Aprobar checklists | ✔ | ✔ |  |  |  |  | |
| `evidence.create` | Cargar evidencias | ✔ |  |  | ✔ |  |  | |
| `evidence.read_all` | Ver todas las evidencias | ✔ | ✔ |  |  |  | ✔ | |
| `evidence.read_assigned` | Ver evidencias de proyectos asignados | ✔ |  |  | ✔ |  |  | |
| `evidence.delete` | Eliminar evidencias | ✔ |  |  |  |  |  | |
| `equipment.manage` | Registrar equipos instalados | ✔ | ✔ |  | ✔ |  |  | |
| `dispatch.manage` | Programar y despachar órdenes | ✔ | ✔ |  |  |  |  | |
| `dispatch.read_own` | Ver la agenda propia | ✔ |  |  | ✔ |  |  | |
| `dashboards.operations` | Ver el monitor de operación | ✔ | ✔ |  |  |  | ✔ | |
| `permits.manage` | Gestionar permisos municipales | ✔ | ✔ |  |  |  |  | |
| `inspections.manage` | Gestionar inspecciones | ✔ | ✔ |  |  |  |  | |
| `invoices.create` | Crear facturas | ✔ |  |  |  | ✔ |  | |
| `invoices.read` | Ver facturas | ✔ | ✔ |  |  | ✔ | ✔ | |
| `invoices.update` | Editar facturas | ✔ |  |  |  | ✔ |  | |
| `invoices.record_payment` | Registrar pagos | ✔ |  |  |  | ✔ |  | |
| `invoices.export` | Exportar facturas | ✔ |  |  |  | ✔ |  | |
| `billing.submit` | Radicar el cobro ante el programa | ✔ | ✔ |  |  | ✔ |  | |
| `billing.configure` | Configurar el cobro de los programas (tarifas, jurisdicciones y requisitos) | ✔ |  |  |  | ✔ |  | |
| `quotes.manage` | Gestionar cotizaciones de trabajo particular | ✔ | ✔ |  |  | ✔ |  | |
| `dashboards.finance` | Ver el tablero financiero | ✔ |  |  |  | ✔ | ✔ | |
| `expenses.create_own` | Registrar gastos propios | ✔ |  | ✔ | ✔ |  |  | |
| `expenses.read_all` | Ver todos los gastos | ✔ |  |  |  | ✔ |  | |
| `expenses.approve` | Aprobar gastos | ✔ |  |  |  | ✔ |  | |
| `suppliers.manage` | Gestionar proveedores | ✔ |  |  |  | ✔ |  | |
| `payables.manage` | Gestionar cuentas por pagar | ✔ |  |  |  | ✔ |  | |
| `payables.approve` | Aprobar y programar pagos a proveedores | ✔ |  |  |  |  | ✔ | |
| `reconciliation.manage` | Conciliar pagos y movimientos | ✔ |  |  |  | ✔ |  | |
| `profitability.read` | Ver la rentabilidad por proyecto | ✔ |  |  |  | ✔ | ✔ | |
| `accounting.export` | Exportar información contable | ✔ |  |  |  | ✔ |  | |
| `reports.view` | Ver reportes | ✔ | ✔ |  |  | ✔ | ✔ | |
| `reports.generate` | Generar reportes | ✔ |  |  |  | ✔ | ✔ | |
| `reports.export` | Exportar reportes | ✔ |  |  |  | ✔ | ✔ | |
| `programs.read` | Ver programas | ✔ | ✔ | ✔ |  |  |  | |
| `programs.manage` | Administrar programas | ✔ | ✔ |  |  |  |  | |
| `fields.manage` | Administrar el catálogo de campos | ✔ | ✔ |  |  |  |  | |
| `fields.view_sensitive` | Ver campos sensibles | ✔ | ✔ |  |  |  |  | |
| `workflows.manage` | Administrar flujos y formularios | ✔ | ✔ |  |  |  |  | |
| `workflows.publish` | Publicar versiones de flujo | ✔ | ✔ |  |  |  |  | |
| `zones.manage` | Administrar zonas y asignación de vendedores | ✔ | ✔ |  |  |  |  | |
| `settings.manage` | Administrar la configuración de la organización | ✔ |  |  |  |  |  | |
| `organization.manage` | Administrar la organización | ✔ |  |  |  |  |  | |
| `warehouse.read` | Ver el catálogo, las existencias y los movimientos de bodega | ✔ | ✔ |  |  | ✔ | ✔ | |
| `warehouse.manage` | Administrar el catálogo, ubicaciones, entradas y cargas del Excel | ✔ | ✔ |  |  |  |  | |
| `warehouse.kits_manage` | Administrar las listas predefinidas por tipo de trabajo | ✔ | ✔ |  |  |  |  | |
| `warehouse.request_release` | Pedir una salida de material de bodega | ✔ | ✔ |  | ✔ |  |  | |
| `warehouse.approve_release` | Autorizar o rechazar una salida de material | ✔ | ✔ |  |  |  |  | |
| `warehouse.deliver` | Entregar el material de una salida autorizada | ✔ | ✔ |  |  |  |  | |
| `warehouse.count` | Registrar el conteo físico de la bodega | ✔ | ✔ |  |  |  |  | |
| `budgets.manage` | Armar el presupuesto de un proyecto | ✔ | ✔ |  |  |  |  | |
| `budgets.approve` | Aprobar el presupuesto de un proyecto | ✔ | ✔ |  |  |  |  | |
| `daylogs.manage` | Registrar el diario de obra (jornadas de un proyecto) | ✔ | ✔ |  | ✔ |  |  | |
| `attendance.clock` | Marcar el turno propio, pausas, desplazamientos y novedades | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| `shifts.manage` | Administrar la malla de turnos | ✔ | ✔ |  |  |  |  | |
| `attendance.review` | Aprobar horas, novedades y correcciones de asistencia | ✔ | ✔ |  |  |  |  | |
| `attendance.dashboard` | Ver el panel de asistencia y el reporte de nómina | ✔ | ✔ |  |  | ✔ | ✔ | |
| `payroll.close` | Cerrar y reabrir períodos de nómina | ✔ |  |  |  | ✔ |  | |
| `locations.view` | Ver la ubicación del personal y el mapa operativo | ✔ | ✔ |  |  |  | ✔ | |
| `payments.collect` | Cobrar facturas en línea: enlace de pago, QR y anticipos | ✔ | ✔ |  | ✔ | ✔ |  | |
| `bankfeeds.manage` | Conectar bancos y tarjetas, revisar y clasificar sus movimientos | ✔ |  |  |  | ✔ |  | |
| `users.manage` | Administrar usuarios | ✔ |  |  |  |  |  | |
| `users.read` | Ver la lista de usuarios | ✔ | ✔ |  |  | ✔ | ✔ | |
| `roles.manage` | Administrar roles y permisos | ✔ |  |  |  |  |  | |
| `audit.read` | Ver la auditoría | ✔ | ✔ |  |  | ✔ | ✔ | |
| `notifications.manage` | Administrar notificaciones | ✔ | ✔ |  |  |  |  | |
| `notifications.read_own` | Ver las notificaciones propias | ✔ |  | ✔ | ✔ | ✔ | ✔ | |
| `profile.manage` | Editar el perfil propio | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| **Total** | | 91 | 58 | 14 | 15 | 32 | 21 | |
