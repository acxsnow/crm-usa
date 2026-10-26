# Matriz de permisos por rol

Sacada del código (`backend/app/shared/permissions.py`, `DEFAULT_ROLE_PERMISSIONS`) en `main 23260ae`. Es lo que traen los roles de sistema al crear la organización; el Administrador puede cambiarlos en **Roles y permisos**.

En SEC-003 se prueba cada fila por la API con el token de cada rol y se anota en la última columna si coincide (✔) o el defecto (`D-###`).

| Permiso | Qué permite | Admin | Administración | Vendedor | Técnico | Contabilidad | Gerencia | Verificado en SEC-003 |
|---|---|---|---|---|---|---|---|---|
| `customers.create` | Crear clientes | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `customers.read` | Ver clientes | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ || ✔ SEC-003 |
| `customers.update` | Editar clientes | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `customers.delete` | Eliminar clientes | ✔ |  |  |  |  |  || ✔ D-014 (25 oct): borrar un cliente sin expedientes, obras, facturas ni cotizaciones (`DELETE /customers/{id}`) |
| `contacts.manage` | Gestionar contactos del cliente | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `activities.manage` | Gestionar actividades | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `cases.create` | Crear expedientes | ✔ |  | ✔ |  |  |  || ✔ SEC-003 |
| `cases.read_own` | Ver los expedientes propios | ✔ |  | ✔ |  |  |  || ✔ SEC-003 |
| `cases.read_all` | Ver todos los expedientes | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `cases.submit` | Enviar expedientes a revisión | ✔ |  | ✔ |  |  |  || ✔ SEC-003 |
| `cases.review` | Revisar y devolver expedientes | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `cases.approve` | Aprobar o rechazar expedientes | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `cases.close_admin` | Cerrar expedientes administrativamente | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `dashboards.commercial` | Ver el tablero comercial | ✔ | ✔ |  |  |  | ✔ || ✔ D-014 (25 oct): el reporte comercial (`/reports/commercial`) |
| `documents.manage` | Cargar y reemplazar documentos | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `documents.review` | Aceptar o rechazar documentos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `projects.create` | Crear proyectos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `projects.read_all` | Ver todos los proyectos | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `projects.read_assigned` | Ver los proyectos asignados | ✔ |  |  | ✔ |  |  || ✔ SEC-003 |
| `projects.update` | Editar proyectos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `projects.assign` | Asignar personas a proyectos | ✔ | ✔ |  |  |  |  || ✔ D-014 (25 oct): poner o cambiar el técnico de una obra (agendar y crear obra) |
| `projects.close` | Cerrar proyectos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `tasks.manage` | Gestionar tareas | ✔ | ✔ |  | ✔ |  |  || ✔ SEC-003 |
| `checklists.manage` | Administrar plantillas de checklist | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `checklists.complete` | Completar ítems del checklist en campo | ✔ | ✔ |  | ✔ |  |  || ✔ SEC-003 |
| `checklists.approve` | Aprobar checklists | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `evidence.create` | Cargar evidencias | ✔ |  |  | ✔ |  |  || ✔ SEC-003 |
| `evidence.read_all` | Ver todas las evidencias | ✔ | ✔ |  |  |  | ✔ || ✔ SEC-003 |
| `evidence.read_assigned` | Ver evidencias de proyectos asignados | ✔ |  |  | ✔ |  |  || ✔ SEC-003 |
| `evidence.delete` | Eliminar evidencias | ✔ |  |  |  |  |  || ✔ D-014 (25 oct): quitar una evidencia con la instalación abierta (`DELETE /evidence/{id}`) |
| `equipment.manage` | Registrar equipos instalados | ✔ | ✔ |  | ✔ |  |  || ✔ SEC-003 |
| `dispatch.manage` | Programar y despachar órdenes | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `dispatch.read_own` | Ver la agenda propia | ✔ |  |  | ✔ |  |  || ✔ SEC-003 |
| `dashboards.operations` | Ver el monitor de operación | ✔ | ✔ |  |  |  | ✔ || ✔ SEC-003 |
| `permits.manage` | Gestionar permisos municipales | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `inspections.manage` | Gestionar inspecciones | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `invoices.create` | Crear facturas | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `invoices.read` | Ver facturas | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `invoices.update` | Editar facturas | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `invoices.record_payment` | Registrar pagos | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `invoices.export` | Exportar facturas | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `billing.submit` | Radicar el cobro ante el programa | ✔ | ✔ |  |  | ✔ |  || ✔ SEC-003 |
| `billing.configure` | Configurar el cobro de los programas (tarifas, jurisdicciones y requisitos) | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `quotes.manage` | Gestionar cotizaciones de trabajo particular | ✔ | ✔ |  |  | ✔ |  || ✔ SEC-003 |
| `dashboards.finance` | Ver el tablero financiero | ✔ |  |  |  | ✔ | ✔ || ✔ SEC-003 |
| `expenses.create_own` | Registrar gastos propios | ✔ |  | ✔ | ✔ |  |  || ✔ SEC-003 |
| `expenses.read_all` | Ver todos los gastos | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `expenses.approve` | Aprobar gastos | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `suppliers.manage` | Gestionar proveedores | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `payables.manage` | Gestionar cuentas por pagar | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `payables.approve` | Aprobar y programar pagos a proveedores | ✔ |  |  |  |  | ✔ || ✔ SEC-003 |
| `reconciliation.manage` | Conciliar pagos y movimientos | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `profitability.read` | Ver la rentabilidad por proyecto | ✔ |  |  |  | ✔ | ✔ || ✔ SEC-003 |
| `accounting.export` | Exportar información contable | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `reports.view` | Ver reportes | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `reports.generate` | Generar reportes | ✔ |  |  |  | ✔ | ✔ || ✔ D-014 (25 oct): los reportes de operación y finanzas |
| `reports.export` | Exportar reportes | ✔ |  |  |  | ✔ | ✔ || ✔ SEC-003 |
| `programs.read` | Ver programas | ✔ | ✔ | ✔ |  |  |  || ✔ SEC-003 |
| `programs.manage` | Administrar programas | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `fields.manage` | Administrar el catálogo de campos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `fields.view_sensitive` | Ver campos sensibles | ✔ | ✔ |  |  |  |  || ✔ SEC-003 (se revisa en `cases/intake.py`, campos sensibles) |
| `workflows.manage` | Administrar flujos y formularios | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `workflows.publish` | Publicar versiones de flujo | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `zones.manage` | Administrar zonas y asignación de vendedores | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `settings.manage` | Administrar la configuración de la organización | ✔ |  |  |  |  |  || ✔ SEC-003 |
| `organization.manage` | Administrar la organización | ✔ |  |  |  |  |  || ✔ D-014 (25 oct): los datos de la organización (nombre, logo, dirección, contacto) |
| `warehouse.read` | Ver el catálogo, las existencias y los movimientos de bodega | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `warehouse.manage` | Administrar el catálogo, ubicaciones, entradas y cargas del Excel | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `warehouse.kits_manage` | Administrar las listas predefinidas por tipo de trabajo | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `warehouse.request_release` | Pedir una salida de material de bodega | ✔ | ✔ |  | ✔ |  |  || ✔ SEC-003 |
| `warehouse.approve_release` | Autorizar o rechazar una salida de material | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `warehouse.deliver` | Entregar el material de una salida autorizada | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `warehouse.count` | Registrar el conteo físico de la bodega | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `budgets.manage` | Armar el presupuesto de un proyecto | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `budgets.approve` | Aprobar el presupuesto de un proyecto | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `daylogs.manage` | Registrar el diario de obra (jornadas de un proyecto) | ✔ | ✔ |  | ✔ |  |  || ✔ SEC-003 |
| `attendance.clock` | Marcar el turno propio, pausas, desplazamientos y novedades | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ || ✔ SEC-003 |
| `shifts.manage` | Administrar la malla de turnos | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `attendance.review` | Aprobar horas, novedades y correcciones de asistencia | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `attendance.dashboard` | Ver el panel de asistencia y el reporte de nómina | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `payroll.close` | Cerrar y reabrir períodos de nómina | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `locations.view` | Ver la ubicación del personal y el mapa operativo | ✔ | ✔ |  |  |  | ✔ || ✔ SEC-003 |
| `payments.collect` | Cobrar facturas en línea: enlace de pago, QR y anticipos | ✔ | ✔ |  | ✔ | ✔ |  || ✔ SEC-003 |
| `bankfeeds.manage` | Conectar bancos y tarjetas, revisar y clasificar sus movimientos | ✔ |  |  |  | ✔ |  || ✔ SEC-003 |
| `users.manage` | Administrar usuarios | ✔ |  |  |  |  |  || ✔ SEC-003 |
| `users.read` | Ver la lista de usuarios | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `roles.manage` | Administrar roles y permisos | ✔ |  |  |  |  |  || ✔ SEC-003 |
| `audit.read` | Ver la auditoría | ✔ | ✔ |  |  | ✔ | ✔ || ✔ SEC-003 |
| `notifications.manage` | Administrar notificaciones | ✔ | ✔ |  |  |  |  || ✔ SEC-003 |
| `notifications.read_own` | Ver las notificaciones propias | ✔ |  | ✔ | ✔ | ✔ | ✔ || ✔ SEC-003 |
| `profile.manage` | Editar el perfil propio | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ || ✔ D-014 (25 oct): editar el propio nombre (`PATCH /auth/me`, «Mi perfil») |
| **Total** | | 91 | 58 | 14 | 15 | 32 | 21 | |
