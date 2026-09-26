# Módulo 0 — Usuarios, roles y acceso por módulo

Fecha: 22 de septiembre de 2026. Autor: José Javier. Estado: **borrador para
aprobar**; después se escribe el plan de tareas.
Entrega: viernes 25 de septiembre de 2026.
Base: `requerimientos-formularios-programas-delta-hvac.md` §18.2 módulo 0,
`decisiones.md` D1, el PDF (los cuatro bloques "Funcionalidades requeridas"),
y el patrón de `ventas_pap` (`PERMISSIONS.md` + `config/navigation.tsx`).

## Supuestos a confirmar

- **S1. El código del técnico se queda como `field_technician`** (etiqueta
  "Técnico"), no `technician` como decía D1. Motivo: Mateo lo tiene quemado
  en `field_ops/router.py` (líneas 129 y 189) para el monitor. Cambiar la
  etiqueta es gratis; cambiar el código le toca su paquete. Se corrige D1.
- **S2. `organization_admin` no se edita ni se borra**: siempre tiene todos
  los permisos. Es la protección contra dejarse sin acceso a Usuarios y
  Roles. Los otros cinco roles del sistema se editan (nombre y permisos)
  pero no se borran. Los roles creados por la organización se editan y se
  borran si no tienen usuarios.
- **S3. Perfil propio y cambio de contraseña van de últimos** en el plan; si
  el viernes no da, pasan al módulo 1 sin afectar la entrega.
- **S4. Las pantallas de login siguen en inglés**; solo lo nuevo de este
  módulo va en español. Traducir auth es deuda aparte, ya listada en
  `frontend/ARCHITECTURE.md`.
- **S5. La migración de roles toma el número `0009`**; el esqueleto de
  `Case` de la semana siguiente pasa a `0010`/`0011`. Se corrige en
  `contratos/case.md`.
- **S6. Usuarios existentes con roles viejos** se reasignan así:
  `commercial_manager` → `salesperson`; `project_manager` y `supervisor` →
  `admin_staff`; `finance_user` → `accounting`; `read_only` → `management`.
  Hoy solo hay datos de demo.
- **S7. Los códigos de permiso existentes no se renombran.** Mateo los usa
  en todos sus endpoints; solo se les asigna módulo y se **agregan** los
  nuevos. Excepción: `opportunities.manage` y `quotes.manage` quedan
  marcados como obsoletos y se retiran en el módulo 1 con `Opportunity`.

## 1. Objetivo

Que cada persona de Delta HVAC entre con el rol que le corresponde según el
PDF y vea únicamente los módulos de su área, y que el administrador pueda
crear roles, darles permisos y asignárselos a la gente **sin tocar código**.
No importa que los módulos de destino estén incompletos; importa la
separación y que el mapa del sistema quede declarado desde ahora.

## 2. La idea en una frase (patrón tomado de ventas_pap)

Cada permiso pertenece a un **módulo**. El menú y las rutas no preguntan por
permisos sueltos: preguntan *"¿este usuario tiene algún permiso del módulo
X?"*. Los permisos finos siguen existiendo para la API; el módulo es la
unidad de navegación. El agrupamiento vive **en código** (una columna más en
el catálogo), no en la base de datos: es conocimiento del desarrollador, no
un dato que el administrador configure.

Lo fino de verdad ("el técnico ve solo sus proyectos asignados") no es
permiso: es filtro en el selector, igual que las cuatro bandejas de
ventas_pap comparten `gestion.acceder_workflow`.

## 3. Lo que ya existe y se conserva

- Tablas `permissions`, `roles` (con `organization_id` nulo = plantilla del
  sistema, `is_system`), `role_permissions`, `user_roles`, `users`,
  `invitations`. **No hay tablas nuevas.**
- `PERMISSION_CATALOG` y `DEFAULT_ROLE_PERMISSIONS` en
  `app/shared/permissions.py`; el seed crea plantillas y copia por
  organización.
- `require_permission()` / `require_any_permission()` /
  `get_effective_permissions()` en `app/api/deps.py` (equivalen a `HasPerm`
  y `HasAnyPerm` de ventas_pap).
- `GET /users`, `POST /users` (invitar con roles), activar/desactivar;
  `GET /roles`; `GET /auth/me` con `roles` y `permissions`.
- Frontend: `AuthContext.hasPermission`, `ProtectedRoute`, `DashboardLayout`
  con `NAV_ITEMS` filtrado por permiso, `UsersPage`.

## 4. Roles del sistema (D1 con S1)

- `organization_admin` — Administrador. Todos los permisos. Bloqueado (S2).
- `salesperson` — Vendedor.
- `admin_staff` — Administración.
- `field_technician` — Técnico.
- `accounting` — Contabilidad.
- `management` — Gerencia.

Se eliminan `commercial_manager`, `project_manager`, `supervisor`,
`finance_user`, `read_only`. `platform_super_admin` sigue como bandera en
`User.is_platform_super_admin`, no como rol visible (equivale al
superusuario de ventas_pap: ve todo).

## 5. Módulos y catálogo de permisos

15 módulos, validados contra los cuatro bloques de "Funcionalidades
requeridas" del PDF y las 12 etapas de su §7. El catálogo pasa de
`(code, description)` a `(code, description, module)`.

**Operación comercial**

- `customers` — Prospectos y clientes (PDF §2.3): `leads.manage`,
  `customers.create`, `customers.read`, `customers.update`,
  `customers.delete`, `contacts.manage`, `activities.manage`.
- `cases` — Expedientes; es el "Dashboard centralizado (CRM de proyectos)"
  del PDF §3: `cases.create`, `cases.read_own`, `cases.read_all`,
  `cases.submit`, `cases.review`, `cases.approve`, `cases.close_admin`,
  `dashboards.commercial`. Obsoletos: `opportunities.manage`,
  `quotes.manage`.
- `documents` — Documentos; "Gestor documental inteligente y conversor"
  del PDF §3: `documents.manage`, `documents.review`.

**Operación de campo**

- `projects` — Proyectos e instalación (PDF §5): `projects.create`,
  `projects.read_all`, `projects.read_assigned`, `projects.update`,
  `projects.assign`, `projects.close`, `tasks.manage`,
  `checklists.manage`, `checklists.approve`, `evidence.create`,
  `evidence.read_all`, `evidence.read_assigned`, `evidence.delete`,
  `equipment.manage`.
- `dispatch` — Agenda y despacho; "Field Service Dispatch" del PDF §5.1:
  `dispatch.manage`, `dispatch.read_own`, `dashboards.operations`.
- `permits` — Permisos e inspecciones (PDF §3.2 y §3.5; el dueño es
  Administración, no el técnico): `permits.manage`, `inspections.manage`.

**Finanzas**

- `billing` — Facturación y cobros, AR (PDF §3.4 y §4.2–4.3):
  `invoices.create`, `invoices.read`, `invoices.update`,
  `invoices.record_payment`, `invoices.export`, `billing.submit`,
  `dashboards.finance`.
- `expenses` — Gastos de campo (PDF §4.1; los carga el técnico y el
  vendedor desde el móvil, por eso **no** va dentro de facturación):
  `expenses.create_own`, `expenses.read_all`, `expenses.approve`.
- `payables` — Proveedores y pagos, AP (PDF §4.4): `suppliers.manage`,
  `payables.manage`.
- `finance_close` — Conciliación y rentabilidad (PDF §4.5):
  `reconciliation.manage`, `profitability.read`, `accounting.export`.

**Administración**

- `reports` — Reportes e indicadores (PDF §4.5 y §7): `reports.view`,
  `reports.generate`, `reports.export`.
- `config` — Configuración de programas (Cadena A, módulo 1):
  `programs.read`, `programs.manage`, `fields.manage`,
  `fields.view_sensitive`, `workflows.manage`, `workflows.publish`,
  `zones.manage`, `settings.manage`, `organization.manage`.
- `team` — Usuarios y roles: `users.manage`, `roles.manage`.
- `audit` — Auditoría: `audit.read`.
- `notifications` — Notificaciones (PDF §3): `notifications.manage`,
  `notifications.read_own`.

Sin módulo: `profile.manage` (lo tiene todo rol; no aparece en el menú).

Criterio que justifica cada separación: **dos capacidades van en módulos
distintos si los roles que las necesitan son distintos.** Por eso gastos no
está dentro de facturación, ni permisos dentro de proyectos, ni conciliación
dentro de reportes.

Un test de consistencia verifica que todo código de
`DEFAULT_ROLE_PERMISSIONS` existe en el catálogo, que todo código usado en
`require_permission(...)`/`require_any_permission(...)` bajo `app/` existe
en el catálogo, y que todo permiso tiene módulo válido (o `None` explícito).

## 6. Matriz inicial rol → permiso

Punto de partida del seed; el administrador la cambia desde la UI.

- **Administrador**: todos.
- **Vendedor**: `leads.manage`, `customers.create`, `customers.read`,
  `customers.update`, `contacts.manage`, `activities.manage`,
  `cases.create`, `cases.read_own`, `cases.submit`, `documents.manage`,
  `programs.read`, `expenses.create_own`, `notifications.read_own`,
  `profile.manage`.
- **Administración**: `leads.manage`, `customers.create`, `customers.read`,
  `customers.update`, `contacts.manage`, `activities.manage`,
  `cases.read_all`, `cases.review`, `cases.approve`, `cases.close_admin`,
  `dashboards.commercial`, `documents.manage`, `documents.review`,
  `projects.create`, `projects.read_all`, `projects.update`,
  `projects.assign`, `projects.close`, `tasks.manage`, `checklists.manage`,
  `checklists.approve`, `evidence.read_all`, `equipment.manage`,
  `dispatch.manage`, `dashboards.operations`, `permits.manage`,
  `inspections.manage`, `invoices.read`, `billing.submit`, `reports.view`,
  `programs.read`, `audit.read`, `notifications.manage`, `profile.manage`.
- **Técnico**: `customers.read`, `projects.read_assigned`, `tasks.manage`,
  `checklists.manage`, `evidence.create`, `evidence.read_assigned`,
  `equipment.manage`, `dispatch.read_own`, `expenses.create_own`,
  `notifications.read_own`, `profile.manage`.
- **Contabilidad**: `customers.read`, `cases.read_all`,
  `projects.read_all`, `invoices.create`, `invoices.read`,
  `invoices.update`, `invoices.record_payment`, `invoices.export`,
  `billing.submit`, `dashboards.finance`, `expenses.read_all`,
  `expenses.approve`, `suppliers.manage`, `payables.manage`,
  `reconciliation.manage`, `profitability.read`, `accounting.export`,
  `reports.view`, `reports.generate`, `reports.export`, `audit.read`,
  `notifications.read_own`, `profile.manage`.
- **Gerencia**: `customers.read`, `cases.read_all`,
  `dashboards.commercial`, `projects.read_all`, `evidence.read_all`,
  `dashboards.operations`, `invoices.read`, `dashboards.finance`,
  `profitability.read`, `reports.view`, `reports.generate`,
  `reports.export`, `audit.read`, `notifications.read_own`,
  `profile.manage`.

## 7. Menú resultante

Estructura por grupos, como `navigation.tsx` de ventas_pap. Los módulos que
todavía no existen se declaran con `disabled: true` y se ven en gris: el
mapa completo del sistema queda visible desde el viernes y Mateo no tiene
que tocar la matriz cuando construya los suyos.

- **Inicio** — `/` — sin restricción.
- **Operación comercial**
  - Prospectos — `/leads` — módulo `customers`.
  - Clientes — `/customers` — módulo `customers`.
  - Expedientes — `/applications` — módulo `cases`. (Se renombra desde
    "Aplicaciones"; la ruta cambia a `/cases` en el módulo 2.)
  - Pipeline — `/opportunities` — módulo `cases`. Se retira en el módulo 1,
    reemplazado por el Kanban de expedientes.
  - Documentos — deshabilitado — módulo `documents` (módulo 3).
- **Operación de campo**
  - Proyectos — `/projects` — módulo `projects`.
  - Monitor de técnicos — `/technician-monitor` — permiso puntual
    `dashboards.operations`, no el módulo completo: es la vista de
    supervisión de todos los técnicos y su endpoint (de Mateo) ya exige ese
    permiso. Si se declarara por módulo, el técnico lo vería en el menú y
    recibiría 403 al entrar.
  - Mi agenda — deshabilitado — permiso `dispatch.read_own` (la agenda
    propia del técnico; pantalla del módulo 5).
  - Permisos e inspecciones — deshabilitado — módulo `permits`.
- **Finanzas**
  - Facturación y cobros — `/invoices` — módulo `billing`.
  - Gastos de campo — deshabilitado — módulo `expenses`.
  - Proveedores y pagos — deshabilitado — módulo `payables`.
  - Conciliación y rentabilidad — deshabilitado — módulo `finance_close`.
- **Administración**
  - Reportes — deshabilitado — módulo `reports`.
  - Configuración de programas — deshabilitado — módulo `config`.
  - Equipo — `/users` — módulo `team`.
  - Roles y permisos — `/roles` — permiso `roles.manage` (dentro de `team`).
  - Auditoría — `/audit-log` — módulo `audit`.
  - Notificaciones — deshabilitado — módulo `notifications`.

Qué ve cada rol con la matriz de la sección 6 (sin contar los
deshabilitados):

- Vendedor: Inicio, Prospectos, Clientes, Expedientes, Documentos (cuando
  exista).
- Administración: Inicio, Prospectos, Clientes, Expedientes, Pipeline,
  Documentos, Proyectos, Monitor de técnicos, Permisos, Facturación,
  Reportes, Auditoría, Notificaciones.
- Técnico: Inicio, Clientes, Proyectos, Mi agenda, Gastos. **No** ve el
  Monitor de técnicos (es la vista de supervisión).
- Contabilidad: Inicio, Clientes, Expedientes, Proyectos, Facturación,
  Gastos, Proveedores, Conciliación, Reportes, Auditoría.
- Gerencia: Inicio, Clientes, Expedientes, Proyectos, Monitor de técnicos,
  Facturación, Conciliación, Reportes, Auditoría.
- Administrador: todo, más Configuración, Equipo y Roles y permisos.

## 8. Backend

Paquete `app/modules/users/`; se agrega `selectors.py` y se amplían
`service.py` y `router.py`. `GET /roles` se muda de `organizations` a
`users/roles_router.py` con prefijo `/roles` (la ruta pública no cambia).

- `GET /permissions` — catálogo con `code`, `description`, `module`, y la
  lista de módulos con su etiqueta. Permiso: `roles.manage` o `users.manage`.
- `GET /roles` — roles de la organización (la copia de la org gana sobre la
  plantilla) con `code`, `name`, `is_system`, `is_locked`, `permissions`,
  `user_count`. Permiso: `roles.manage` **o** `users.manage` — hoy exige
  solo `roles.manage`, y por eso `UsersPage` se queda sin roles para quien
  únicamente administra usuarios.
- `POST /roles` — crea rol de la organización: `code`
  (`^[a-z][a-z0-9_]{2,49}$`, único en la org y distinto de los del
  sistema), `name`, `permissions`. Permiso: `roles.manage`.
- `PATCH /roles/{code}` — `name` y/o `permissions`. 409 si el rol está
  bloqueado; 400 si algún permiso no existe en el catálogo. Editar un rol
  del sistema modifica **la copia de la organización**, nunca la plantilla;
  si la organización no tiene copia todavía, se crea a partir de la
  plantilla en ese momento. Permiso: `roles.manage`.
- `DELETE /roles/{code}` — solo roles de la organización, sin usuarios (409
  si tiene). Permiso: `roles.manage`.
- `PATCH /users/{id}/roles` — `role_codes` (mínimo uno); reemplaza el
  conjunto. 409 si deja a la organización sin ningún `organization_admin`
  activo. Permiso: `users.manage`.
- `PATCH /users/{id}` — `full_name`. Permiso: `users.manage`.
- `GET /auth/me` — se agrega `role_names` (etiquetas) y `modules` (lista de
  módulos con al menos un permiso), para que el frontend no tenga que
  recalcularla.
- `PATCH /auth/me` — `full_name`. Permiso: `profile.manage`. (S3)
- `POST /auth/me/change-password` — `current_password`, `new_password`;
  valida la actual, incrementa `token_version` y devuelve tokens nuevos
  para no expulsar al usuario de su propia sesión. Permiso:
  `profile.manage`. (S3)

Reglas transversales: toda edición registra `audit_events`
(`roles.created`, `roles.updated`, `roles.deleted`, `users.roles_changed`,
`users.updated`, `users.password_changed`) con `before_data`/`after_data`.
`get_effective_permissions()` no cambia.

Migración `0009_roles_pdf` (esquema sin cambios; es migración de datos):
crea los permisos nuevos; crea plantillas y copias por organización de
`salesperson`, `admin_staff`, `accounting`, `management`; actualiza
etiquetas de `organization_admin` y `field_technician`; reasigna usuarios
según S6; borra `user_roles`, `role_permissions` y los roles viejos.
`downgrade()` recrea los roles viejos con la matriz anterior (restauración
de estructura, no exacta de asignaciones; queda documentado).
`scripts/seed.py` pasa a la lista nueva, idempotente como hoy.

Tests: se amplía `tests/test_roles.py`; se actualizan `conftest.py` y
`test_rbac_full.py`.

- Fixtures nuevas: `active_salesperson_user`, `active_admin_staff_user`,
  `active_accounting_user`, `active_management_user`. Se conservan
  `active_admin_user` y `active_technician_user`; se eliminan las de roles
  viejos (el monitor de técnicos usa `active_project_manager_user` → pasa a
  `active_admin_staff_user`).
- Por cada endpoint nuevo: un 403 sin permiso y un 2xx con permiso.
- Reglas: rol bloqueado no se edita ni se borra (409), rol del sistema no
  se borra (409), rol con usuarios no se borra (409), permiso inexistente
  (400), última cuenta admin no pierde el rol (409), rol de otra
  organización invisible (404).
- Editar un rol del sistema toca la copia de la organización, no la
  plantilla.
- Cambiar roles a un usuario cambia sus permisos y sus `modules` en el
  siguiente `GET /auth/me`.
- Test de consistencia del catálogo (sección 5).

## 9. Frontend

- **`src/config/navigation.ts`** (nuevo, calcado de ventas_pap): constantes
  `PERMS` y `MODULES`, la estructura de grupos de la sección 7, y
  `buildNavForUser(user)` que devuelve solo lo visible. `DashboardLayout`
  deja de tener el menú adentro y solo lo pinta.
- **`hasModule(module)`** en `AuthContext`, junto a `hasPermission`. Lee
  `user.modules` que ahora viene de `/auth/me`.
- **Protección de rutas — la pieza que hoy no existe.** Ninguna ruta valida
  permiso: cualquier usuario autenticado abre `/invoices` o `/users`
  escribiendo la URL, y aunque la API responda 403, la pantalla se monta y
  dispara sus consultas. Se agrega `<RequireAccess module="billing">` (o
  `permission="roles.manage"` para casos puntuales) envolviendo cada ruta
  hija de `"/"` en `app/router.tsx`. Sin acceso → pantalla "Sin acceso", no
  pantalla en blanco ni tabla vacía.
- **Pantalla "Sin acceso"** en español, con el nombre del módulo y enlace a
  Inicio; reemplaza el texto en inglés de `ProtectedRoute`.
- **`src/features/roles/`** (nueva, con `api.ts` + `queries.ts` +
  `components/`): `RolesPage` con la lista de roles (nombre, código, tipo,
  usuarios), crear rol, editar nombre y permisos **agrupados por módulo**
  con casilla "marcar todo el módulo", y borrar rol de la organización. El
  rol bloqueado se muestra todo marcado y deshabilitado. Estados de carga,
  vacío y error. En móvil los módulos van colapsados.
- **`UsersPage`**: la columna Roles muestra etiquetas; acción "Editar" con
  nombre completo y casillas de roles; el formulario de invitar pasa a
  `react-hook-form` + `zod` (patrón para lo nuevo).
- **`ProfilePage`** (`/profile`, enlace desde el nombre en la cabecera):
  datos, roles y cambio de contraseña. (S3)
- Tipos: `Role` gana `is_system`, `is_locked`, `user_count`; nuevos
  `Permission { code, description, module }` y `Module { key, label }`;
  `CurrentUser` gana `role_names` y `modules`.

## 10. Lo que NO entra

- Pantalla aparte de "matriz rol → módulo": la matriz **es** la edición de
  permisos por rol agrupada por módulo.
- Permisos por objeto (este vendedor ve este expediente): eso es filtro en
  el selector de cada módulo, no del módulo 0.
- Asignación vendedor ↔ zona: módulo 1 (D5).
- Construir los módulos deshabilitados.
- Traducir las pantallas de auth (S4).
- Permisos directos por usuario (el `user_permissions` de ventas_pap): aquí
  todo pasa por roles. Si algún día hace falta, se crea un rol.

## 11. Criterio de terminado

- `pytest -q` verde con los roles nuevos; `tsc -b` y `vite build` limpios.
- En navegador, seis usuarios (uno por rol) entran y ven exactamente el
  menú de la sección 7; abrir por URL una ruta sin acceso muestra "Sin
  acceso" y no dispara consultas.
- El administrador crea un rol "Coordinador de zona", le marca el módulo
  Proyectos completo, se lo asigna a un usuario existente, y ese usuario ve
  el menú cambiado en su siguiente carga, sin tocar código ni base de datos.
- Todo lo anterior queda en `audit_events`.
- `decisiones.md` D1 actualizado con S1 y con la lista de módulos;
  `contratos/case.md` con S5.

## 12. Orden para el plan

1. Catálogo con módulos, roles nuevos y matriz en `permissions.py` + seed +
   test de consistencia.
2. Migración `0009` + actualizar `conftest.py` y `test_rbac_full.py` →
   suite verde.
3. `GET /permissions`, `GET/POST/PATCH/DELETE /roles` con service,
   selectors, auditoría y tests.
4. `PATCH /users/{id}/roles`, `PATCH /users/{id}`, `/auth/me` con
   `role_names` y `modules`; tests.
5. Frontend: `navigation.ts`, `hasModule`, `RequireAccess` en todas las
   rutas, pantalla "Sin acceso", tipos.
6. Frontend: `RolesPage`.
7. Frontend: edición de roles en `UsersPage`.
8. Verificación en navegador por rol y cierre.
9. Si queda tiempo: perfil y cambio de contraseña (S3).
