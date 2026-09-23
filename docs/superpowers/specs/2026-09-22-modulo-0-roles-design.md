# Módulo 0 — Usuarios, roles y acceso por módulo

Fecha: 22 de septiembre de 2026. Autor: José Javier. Estado: **borrador para
aprobar en la mañana**; después se escribe el plan de tareas.
Entrega: viernes 25 de septiembre de 2026.
Base: `requerimientos-formularios-programas-delta-hvac.md` §18.2 módulo 0,
`decisiones.md` D1, `backend/ARCHITECTURE.md`, `frontend/ARCHITECTURE.md`.

## Supuestos que tomé mientras dormías (confirmar o corregir)

- **S1. El código del técnico se queda como `field_technician`** (etiqueta
  "Técnico"), no `technician` como decía D1. Motivo: el monitor de técnicos
  de Mateo lo tiene quemado en `field_ops/router.py` (líneas 129 y 189);
  renombrarlo obliga a tocar su paquete. Cambiar una etiqueta es gratis.
  Se actualiza D1 con esta nota.
- **S2. `organization_admin` no se edita ni se borra**: siempre tiene todos
  los permisos. Es la protección contra dejarse sin acceso a "Usuarios" y
  "Roles". Los otros cinco roles del sistema se pueden editar (permisos y
  nombre), no borrar. Los roles creados por la organización se editan y se
  borran si no tienen usuarios.
- **S3. Usuarios existentes con roles viejos** se reasignan así en la
  migración de datos: `commercial_manager` → `salesperson`,
  `project_manager` y `supervisor` → `admin_staff`, `finance_user` →
  `accounting`, `read_only` → `management`. Hoy solo hay datos de demo, así
  que el mapeo importa poco, pero queda hecho para Render.
- **S4. Los códigos de permiso existentes no se renombran** (`leads.manage`,
  `projects.read_all`, `invoices.read`, …): Mateo los usa en todos sus
  endpoints. Solo se **agregan** los nuevos.
- **S5. Perfil propio y cambio de contraseña van de últimos** en el plan; si
  el viernes no da, se pasan al módulo 1 sin afectar la entrega ("cada rol
  entra y ve lo suyo").
- **S6. Pantallas de login siguen en inglés**; solo la pantalla nueva "sin
  acceso" y todo lo del módulo van en español. Traducir auth es deuda
  aparte (ya listada en `frontend/ARCHITECTURE.md`).
- **S7. La migración de roles toma el número `0009`**; el esqueleto de
  `Case` de la semana que viene pasa a `0010`/`0011`. Se corrige en
  `contratos/case.md`.

## 1. Objetivo

Que cada persona de Delta HVAC entre con el rol que le corresponde según
el PDF y vea únicamente los módulos de su área, y que el administrador
pueda crear roles, darles permisos y asignárselos a la gente **sin tocar
código**. No importa que los módulos de destino estén incompletos; importa
la separación.

## 2. Lo que ya existe y se conserva

- Tablas `permissions`, `roles` (con `organization_id` nulo = plantilla del
  sistema, `is_system`), `role_permissions`, `user_roles`, `users`,
  `invitations`. **No hay tablas nuevas.**
- `PERMISSION_CATALOG` y `DEFAULT_ROLE_PERMISSIONS` en
  `app/shared/permissions.py`; el seed crea las plantillas y una copia por
  organización.
- `require_permission()` / `require_any_permission()` /
  `get_effective_permissions()` en `app/api/deps.py`.
- `GET /users`, `POST /users` (invitar con roles), `POST /users/{id}/activate`
  y `/deactivate`; `GET /roles` (en `organizations/router.py`); `GET /auth/me`
  devuelve `roles` y `permissions`.
- Frontend: `AuthContext.hasPermission`, `ProtectedRoute` (con
  `requiredPermission` opcional que **ninguna ruta usa hoy**),
  `DashboardLayout` filtra el menú por permiso, `UsersPage` invita con
  checkboxes de rol y activa/desactiva.

## 3. Roles del sistema (D1 con S1)

Códigos y etiquetas en español:

- `organization_admin` — Administrador. Todos los permisos. Bloqueado (S2).
- `salesperson` — Vendedor.
- `admin_staff` — Administración.
- `field_technician` — Técnico (S1).
- `accounting` — Contabilidad.
- `management` — Gerencia.

Se eliminan: `commercial_manager`, `project_manager`, `supervisor`,
`finance_user`, `read_only`. `platform_super_admin` sigue existiendo como
bandera en `User.is_platform_super_admin`, no como rol visible.

## 4. Catálogo de permisos

Se conservan todos los códigos actuales (S4). Se agregan, agrupados por
módulo para la pantalla de roles:

- Expedientes (Cadena A): `cases.create`, `cases.read_own`, `cases.read_all`,
  `cases.submit`, `cases.review`, `cases.approve`, `cases.close_admin`.
- Programas y formularios (Cadena A): `programs.read`, `programs.manage`,
  `fields.manage`, `fields.view_sensitive`, `workflows.manage`,
  `workflows.publish`, `zones.manage`.
- Documentos (Cadena A): `documents.manage`, `documents.review`.
- Permisos e inspección (Cadena B, reservados): `permits.manage`,
  `inspections.manage`.
- Cobro (Cadena B, reservados): `billing.submit`, `billing.reconcile`.
- Notificaciones (Cadena B, reservados): `notifications.manage`.
- Reportes: `reports.view` (además de los `reports.generate`/`export`
  existentes).
- Usuarios: `profile.manage` (editar su propio perfil; lo tiene todo rol).

Cada permiso tiene `code`, `description` y **`module`** (nuevo campo en el
catálogo, solo en código, no en BD) para agrupar en la UI. La BD sigue con
`code` y `description`; el agrupamiento se resuelve leyendo el catálogo.

Un test de consistencia verifica: todo código de `DEFAULT_ROLE_PERMISSIONS`
existe en el catálogo, y todo código usado en `require_permission(...)` en
`app/` existe en el catálogo (búsqueda estática sobre el código fuente).

## 5. Matriz inicial rol → permiso

Es el punto de partida del seed; el administrador la cambia desde la UI.

- **Administrador**: todos.
- **Vendedor**: `leads.manage`, `customers.create`, `customers.read`,
  `customers.update`, `contacts.manage`, `cases.create`, `cases.read_own`,
  `cases.submit`, `documents.manage`, `programs.read`, `profile.manage`.
- **Administración**: `leads.manage`, `customers.*`, `contacts.manage`,
  `cases.read_all`, `cases.review`, `cases.approve`, `documents.manage`,
  `documents.review`, `programs.read`, `projects.create`, `projects.read_all`,
  `projects.update`, `projects.assign`, `projects.close`, `tasks.manage`,
  `checklists.manage`, `checklists.approve`, `evidence.read_all`,
  `permits.manage`, `inspections.manage`, `invoices.read`, `billing.submit`,
  `dashboards.operations`, `audit.read`, `notifications.manage`,
  `profile.manage`.
- **Técnico**: `customers.read`, `projects.read_assigned`, `tasks.manage`,
  `evidence.create`, `evidence.read_assigned`, `profile.manage`.
- **Contabilidad**: `customers.read`, `cases.read_all`, `projects.read_all`,
  `invoices.create`, `invoices.read`, `invoices.update`,
  `invoices.record_payment`, `invoices.export`, `billing.submit`,
  `billing.reconcile`, `reports.view`, `reports.generate`, `reports.export`,
  `dashboards.finance`, `audit.read`, `profile.manage`.
- **Gerencia**: `customers.read`, `cases.read_all`, `projects.read_all`,
  `evidence.read_all`, `invoices.read`, `reports.view`, `reports.generate`,
  `reports.export`, `dashboards.commercial`, `dashboards.operations`,
  `dashboards.finance`, `audit.read`, `profile.manage`.

Qué ve cada uno en el menú con esa matriz (los nombres actuales del menú):

- Vendedor: Inicio, Prospectos, Aplicaciones, Clientes.
- Administración: Inicio, Prospectos, Aplicaciones, Clientes, Proyectos,
  Monitor de técnicos, Facturación (solo lectura), Actividad.
- Técnico: Inicio, Proyectos (solo los asignados).
- Contabilidad: Inicio, Clientes, Proyectos, Facturación, Actividad.
- Gerencia: Inicio, Clientes, Proyectos, Monitor de técnicos, Facturación,
  Actividad.
- Administrador: todo, más Equipo y Roles y permisos.

"Pipeline" y "Aplicaciones" quedan con los permisos actuales hasta que el
módulo 1 y 2 los reemplacen por Expedientes.

## 6. Backend

Paquete `app/modules/users/` (se agrega `selectors.py` y se amplía
`service.py` y `router.py`). `GET /roles` se muda de `organizations` a
`users/roles_router.py` con prefijo `/roles`; la ruta pública no cambia.

Endpoints:

- `GET /permissions` — catálogo con `code`, `description`, `module`.
  Permiso: `roles.manage` o `users.manage`.
- `GET /roles` — roles de la organización (la copia de la org gana sobre la
  plantilla, como hoy) con `code`, `name`, `is_system`, `is_locked`
  (`organization_admin`), `permissions`, `user_count`. Permiso:
  `roles.manage` o `users.manage` (hoy exige `roles.manage` y por eso
  `UsersPage` falla para quien solo tiene `users.manage`).
- `POST /roles` — crea rol de la organización: `code` (`^[a-z][a-z0-9_]{2,49}$`,
  único en la org y distinto de los del sistema), `name`, `permissions`.
  Permiso: `roles.manage`.
- `PATCH /roles/{code}` — `name` y/o `permissions`. Rechaza con 409 si el
  rol está bloqueado. Los permisos deben existir en el catálogo (400 si no).
  Permiso: `roles.manage`.
- `DELETE /roles/{code}` — solo roles de la organización (no `is_system`),
  sin usuarios (409 si tiene). Permiso: `roles.manage`.
- `PATCH /users/{id}/roles` — `role_codes: list[str]` (mínimo uno);
  reemplaza el conjunto. Regla de seguridad: un usuario no puede quitarse
  a sí mismo `organization_admin` si es el último activo con ese rol (409).
  Permiso: `users.manage`.
- `PATCH /users/{id}` — `full_name`. Permiso: `users.manage`.
- `GET /me` — ya existe; se agrega `role_names` (etiquetas) para mostrar.
- `PATCH /me` — `full_name`. Permiso: `profile.manage`. (S5)
- `POST /me/change-password` — `current_password`, `new_password`; valida
  la actual, aplica la política de contraseña existente, incrementa
  `token_version` y devuelve tokens nuevos para no expulsar al usuario de
  su propia sesión. Permiso: `profile.manage`. (S5)

Service:

- Toda edición de rol o de roles de usuario registra `audit_events`
  (`roles.created`, `roles.updated`, `roles.deleted`, `users.roles_changed`,
  `users.updated`, `users.password_changed`) con `before_data`/`after_data`.
- Editar permisos de un rol del sistema modifica **la copia de la
  organización**; la plantilla (`organization_id` nulo) no se toca. Si la
  organización aún no tiene copia (organizaciones creadas antes del seed
  por-org), se crea la copia en ese momento a partir de la plantilla.
- `get_effective_permissions()` no cambia: sigue siendo la unión de los
  roles del usuario.

Migraciones:

- `0009_roles_pdf` (esquema + datos en una, porque no cambia el esquema):
  crea los permisos nuevos; crea las plantillas y copias por organización
  de `salesperson`, `admin_staff`, `accounting`, `management`; renombra las
  etiquetas de `organization_admin` y `field_technician`; reasigna usuarios
  según S3; borra `user_roles` de los roles viejos, sus `role_permissions`
  y los roles viejos (plantillas y copias). `downgrade()`: recrea los roles
  viejos con la matriz anterior y reasigna al revés (mapa inverso
  aproximado; se documenta que es una restauración de estructura, no
  exacta de asignaciones).
- `scripts/seed.py` pasa a usar la lista nueva; idempotente como hoy.

Tests (`tests/test_roles.py` existe y se amplía; `tests/test_rbac_full.py`
y `tests/conftest.py` se actualizan a los roles nuevos):

- Fixtures: `active_salesperson_user`, `active_admin_staff_user`,
  `active_accounting_user`, `active_management_user`; se conservan
  `active_admin_user` y `active_technician_user`; se eliminan las de los
  roles viejos y se reemplazan sus usos (el monitor de técnicos usa
  `active_project_manager_user` → pasa a `active_admin_staff_user`).
- Por cada endpoint nuevo: un 403 sin permiso y un 2xx con permiso.
- Reglas: no editar rol bloqueado (409), no borrar rol del sistema (409),
  no borrar rol con usuarios (409), permisos inexistentes (400), último
  admin no puede perder `organization_admin` (409), rol de otra
  organización no visible ni editable (404).
- Editar un rol del sistema cambia solo la copia de la organización.
- Cambiar roles a un usuario cambia sus permisos efectivos en el siguiente
  `GET /me`.
- Test de consistencia del catálogo (sección 4).
- Migración: test que aplica `0009` sobre una BD con los roles viejos y
  verifica el mapeo S3 (se hace con SQLite en memoria creando el esquema
  anterior a mano; si resulta costoso, se reemplaza por una verificación
  manual documentada en el plan).

## 7. Frontend

Feature `src/features/users/` (existente) y nueva `src/features/roles/`.
Convención nueva: `api.ts` + `queries.ts` + `components/`.

- **Rutas protegidas por permiso**: cada ruta hija de `"/"` en
  `app/router.tsx` declara `requiredPermission` (o lista con "alguno de")
  vía un wrapper `<RequirePermission any={[...]}>`. Hoy cualquier usuario
  logueado puede abrir `/invoices` por URL.
- **Pantalla "Sin acceso"** en español, con el nombre del módulo y un enlace
  a Inicio; reemplaza el texto en inglés de `ProtectedRoute`.
- **Menú** (`DashboardLayout.tsx`): mismos ítems, permisos ajustados donde
  cambia el código (Aplicaciones → `cases.read_own` o `cases.read_all` o
  `leads.manage` mientras exista), ítem nuevo "Roles y permisos"
  (`roles.manage`) debajo de "Equipo". El nombre del rol del usuario
  (etiqueta en español) se muestra en la cabecera en lugar del código.
- **Roles y permisos** (`RolesPage.tsx`): lista de roles con nombre, código,
  tipo (sistema / organización), usuarios; crear rol (código, nombre);
  editar rol: nombre y **permisos agrupados por módulo** con casillas,
  botón "seleccionar todo el módulo"; el rol bloqueado se muestra con todo
  marcado y deshabilitado; borrar rol de la organización sin usuarios.
  Estados de carga, vacío y error. Mobile: la lista de permisos se colapsa
  por módulo.
- **Equipo** (`UsersPage.tsx`): la columna Roles muestra etiquetas; acción
  "Editar" abre un panel con nombre completo y casillas de roles (los
  mismos que en invitar); el invitar ya existente pasa a usar
  `react-hook-form` + `zod` (patrón para lo nuevo).
- **Perfil** (`ProfilePage.tsx`, ruta `/profile`, enlace desde el nombre en
  la cabecera): nombre, email, roles, cambio de contraseña. (S5)
- Tipos en `src/types/users.ts`: `Role` gana `is_system`, `is_locked`,
  `user_count`; nuevo `Permission { code, description, module }`.

## 8. Lo que NO entra

- Matriz rol → módulo administrable como pantalla aparte: la matriz **es**
  la edición de permisos por rol. No hay una segunda pantalla.
- Permisos por objeto (este vendedor ve este case): eso es scope en cada
  módulo (`read_own` vs `read_all`), no del módulo 0.
- Asignación vendedor ↔ zona: módulo 1 (D5).
- Traducir las pantallas de auth (S6).
- Invitación con roles de otra organización, multi-organización por
  usuario: fuera de alcance.

## 9. Criterio de terminado

- `pytest -q` verde con los roles nuevos; `tsc -b` y `vite build` limpios.
- En navegador, seis usuarios (uno por rol, creados por seed de demo o por
  invitación) entran y ven exactamente el menú de la sección 5; abrir por
  URL una ruta sin permiso muestra "Sin acceso".
- El administrador crea un rol "Coordinador de zona", le da tres permisos,
  se lo asigna a un usuario existente, y ese usuario ve el menú cambiado
  en su siguiente carga, sin tocar código ni base de datos.
- Todo lo anterior queda en `audit_events`.
- `docs/contratos/case.md` actualizado con S7 (numeración de migraciones) y
  `decisiones.md` D1 con S1.

## 10. Orden sugerido para el plan

1. Catálogo, matriz y roles nuevos en `permissions.py` + seed + test de
   consistencia.
2. Migración `0009` + actualizar `conftest.py` y `test_rbac_full.py` →
   suite verde.
3. Endpoints de roles (`GET /permissions`, `GET/POST/PATCH/DELETE /roles`)
   con service, selectors, auditoría y tests.
4. `PATCH /users/{id}/roles`, `PATCH /users/{id}`, `GET /me` con etiquetas;
   tests.
5. Frontend: rutas con permiso, "Sin acceso", menú, tipos.
6. Frontend: `RolesPage`.
7. Frontend: edición de roles en `UsersPage`.
8. Verificación en navegador por rol (skill browser-automation) y cierre.
9. Si queda tiempo: perfil y cambio de contraseña (S5).
