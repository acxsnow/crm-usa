# Módulo 0 — Usuarios, roles y acceso por módulo — Plan de implementación

> **Para quien ejecute:** cada tarea es un ciclo TDD completo. Se ejecuta una
> tarea, se verifica, el usuario la revisa y aprueba, y solo entonces sigue la
> siguiente. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** que cada persona entre con el rol del PDF y vea solo los módulos
de su área, y que el administrador cree roles y les dé permisos desde la
pantalla, sin tocar código.

**Arquitectura:** se conserva el modelo de roles actual (`roles`,
`permissions`, `role_permissions`, `user_roles` — el equivalente del sistema
de Groups de Django) y se agregan dos tablas para los **módulos**, que son
grupos de permisos y la unidad de navegación: el menú y las rutas preguntan
por módulo, no por permiso suelto (decisión D9). La relación permiso ↔ módulo
es de muchos a muchos, así que el módulo tiene la lista de permisos y no al
revés. Se agregan endpoints para administrar roles y módulos y para cambiar
los roles de un usuario, y las pantallas correspondientes.

**Stack:** FastAPI + SQLAlchemy 2 async + Alembic + pytest (backend);
React 18 + TypeScript + Vite + TanStack Query (frontend).

**Spec:** `docs/superpowers/specs/2026-09-22-modulo-0-roles-design.md`

## Restricciones globales

- Toda query de negocio filtra por `organization_id` del usuario autenticado.
- Todo endpoint protegido lleva `require_permission(...)` y **cada código
  nuevo necesita un test 403 y un test 2xx**.
- Toda edición de roles o de usuarios registra `audit_events`.
- Textos de UI en español; código, identificadores y commits en inglés.
- No se renombra ningún código de permiso existente (S7).
- El técnico conserva el código `field_technician` (S1).
- `organization_admin` no se edita ni se borra y siempre tiene todos los
  permisos (S2).
- Migración de roles = `0010_roles_pdf` (S5).
- Los tests corren en SQLite en memoria; **nunca** contra Postgres real.
- Línea base conocida: `tests/test_field_ops.py::test_evidence_upload_rejects_non_photo_file_types`
  ya falla desde antes (módulo 5, de Mateo). No se arregla aquí; el criterio
  es "no romper nada más".

## Estructura de archivos

Backend:

- `app/shared/permissions.py` — modificar: catálogo, `DEFAULT_MODULES`,
  roles nuevos, matriz.
- `app/modules/users/models.py` — modificar: `PermissionModule` y
  `PermissionModuleItem`.
- `alembic/versions/0009_permission_modules.py` — crear.
- `app/modules/users/selectors.py` — crear: módulos por organización,
  consultas de roles y usuarios.
- `app/modules/users/modules_router.py` — crear: `/permission-modules`
  (listar, editar, restaurar valores por defecto).
- `app/modules/users/service.py` — modificar: crear/editar/borrar rol,
  cambiar roles de usuario, editar nombre.
- `app/modules/users/schemas.py` — modificar: schemas de rol y permisos.
- `app/modules/users/roles_router.py` — crear: `/roles` y `/permissions`.
- `app/modules/users/router.py` — modificar: `PATCH /users/{id}/roles`,
  `PATCH /users/{id}`.
- `app/modules/organizations/router.py` — modificar: quitar `GET /roles`.
- `app/modules/auth/router.py` y `schemas.py` — modificar: `modules` y
  `role_names` en `/auth/me`.
- `app/api/v1/router.py` — modificar: registrar `roles_router`.
- `alembic/versions/0010_roles_pdf.py` — crear.
- `scripts/seed.py` — modificar: roles nuevos.
- `tests/conftest.py` — modificar: fixtures por rol nuevo.
- `tests/test_permissions_catalog.py` — crear: consistencia del catálogo.
- `tests/test_roles.py` — modificar: CRUD de roles.
- `tests/test_users_roles.py` — crear: cambiar roles a un usuario.
- `tests/test_rbac_full.py` — modificar: roles nuevos.

Frontend:

- `src/config/navigation.ts` — crear: módulos, grupos y `buildNavForUser`.
- `src/components/RequireAccess.tsx` — crear: guarda de ruta por módulo.
- `src/components/NoAccess.tsx` — crear: pantalla "Sin acceso".
- `src/app/router.tsx` — modificar: envolver cada ruta.
- `src/app/DashboardLayout.tsx` — modificar: usar `buildNavForUser`.
- `src/features/auth/AuthContext.tsx` — modificar: `hasModule`.
- `src/features/roles/{api.ts,queries.ts,RolesPage.tsx,components/}` — crear.
- `src/features/modules/{api.ts,queries.ts,ModulesPage.tsx}` — crear: pantalla
  de módulos (si el viernes no alcanza, se pasa al módulo 1).
- `src/features/users/{api.ts,queries.ts,UsersPage.tsx}` — modificar.
- `src/types/{auth.ts,users.ts}` — modificar.

Documentación (se escribe junto con el código, no al final):

- `docs/PERMISOS.md` — crear en la tarea 1 y ampliar en cada tarea.
- `docs/decisiones.md` — actualizar D1 al cerrar la tarea 2.
- `docs/contratos/case.md` — corregir numeración de migraciones (tarea 2).

---

### Tarea 1 — Catálogo de permisos y módulos editables ✅ HECHA (23 sep)

Creció respecto a lo planeado por la decisión D9: los módulos no quedaron en
código sino en base de datos y editables desde la aplicación, y la relación
permiso ↔ módulo es de muchos a muchos.

**Archivos:**
- Modificar: `backend/app/shared/permissions.py`, `backend/scripts/seed.py`,
  `backend/tests/conftest.py`, `backend/app/modules/users/models.py`
- Crear: `backend/app/modules/users/selectors.py`,
  `backend/alembic/versions/0009_permission_modules.py`,
  `backend/tests/test_permissions_catalog.py`,
  `backend/tests/test_permission_modules.py`, `docs/PERMISOS.md`

**Lo que quedó:**

- `PERMISSION_CATALOG: list[tuple[str, str]]` — 72 permisos, solo código y
  descripción. **El permiso no sabe a qué grupo pertenece.**
- `DEFAULT_MODULES: dict[str, Module]` — los 15 grupos con su etiqueta y su
  lista de permisos. Es el valor inicial que siembra el seed, igual que
  `DEFAULT_ROLE_PERMISSIONS` lo es para los roles.
- `STANDALONE_PERMISSIONS` — permisos que a propósito no están en ningún
  módulo (`profile.manage`).
- `ROLE_LABELS` y `DEFAULT_ROLE_PERMISSIONS` — los 6 roles del PDF.
- `modules_for_permissions(codes, modules=None)` — función pura; con el mapa
  de la base decide qué módulos se encienden, y sin argumento usa los del
  sistema.
- Modelos `PermissionModule` y `PermissionModuleItem`, migración `0009`
  (aplicada a la base local el 23 de septiembre).
- `selectors.modules_for_organization(db, org_id)` — arma los módulos desde
  la base con `populate_existing`; si la organización no tiene copia cae en la
  plantilla del sistema, y si tampoco existe, en los valores de código.
- `scripts.seed.build_permission_modules(org_id, permissions)` y
  `seed_system_permission_modules` — plantilla del sistema y copia por
  organización.
- `checklists.complete` reservado: hoy `PATCH /checklist-items/{id}` exige
  `checklists.manage`, que también permite crear plantillas, así que el
  técnico no puede completar su propio checklist (PDF §5.5). Queda anotado en
  la deuda conocida de `docs/PERMISOS.md` para el módulo 5.
- `docs/PERMISOS.md` con el modelo, las tres capas de autorización, los 15
  módulos, los roles, cómo proteger un endpoint y cómo agregar un permiso.

**Verificación:** 15 tests nuevos en verde (10 de catálogo + 5 de módulos, uno
de ellos prueba que un permiso está en dos módulos **en la base** y otro que
quitarle un permiso a un módulo lo apaga). Suite completa: 80 pasan, 1 falla
(la preexistente de `field_ops`), 9 errores por fixtures de roles viejos que
resuelve la tarea 2. En la base local: 15 módulos, 77 items, 72 permisos, y 6
permisos pertenecen a 2 módulos cada uno.

---

### Tarea 2 — Migración a los roles del PDF y suite verde ✅ HECHA (23 sep)

**Archivos:**
- Crear: `backend/alembic/versions/0010_roles_pdf.py`
- Modificar: `backend/tests/conftest.py`, `backend/tests/test_rbac_full.py`,
  `backend/tests/test_technician_monitor.py`, `docs/decisiones.md`,
  `docs/PERMISOS.md`

**Lo que quedó:**

- Migración `0010_roles_pdf`, aplicada a la base local. Inserta los permisos
  que faltan, crea los seis roles del PDF como plantilla y como copia de cada
  organización, sincroniza `role_permissions` con la matriz del catálogo,
  reasigna los usuarios de los roles viejos y borra esos roles.
  `downgrade()` restaura la estructura anterior (no las asignaciones exactas,
  porque `project_manager` y `supervisor` se fusionaron en Administración).
- El mapa `OLD_TO_NEW` y la matriz anterior están escritos dentro de la
  migración; la matriz nueva se importa del catálogo, porque el objetivo es
  justamente dejar la base igual que el código. Es la **línea base**: de ahí
  en adelante la matriz la administra el usuario y ninguna migración la
  sobrescribe.
- Fixtures nuevas: `active_salesperson_user`, `active_admin_staff_user`,
  `active_accounting_user`, `active_management_user` y `active_roleless_user`
  (usuario con un rol sin permisos, que es el estado real justo después de
  crear un rol desde la pantalla).
- Tests reescritos eligiendo para cada uno el rol que de verdad tiene la
  combinación que ese test verifica, no un reemplazo mecánico:
  `accounting` para los de facturación y CRM, `management` para "lee pero no
  escribe en campo", `admin_staff` para "lee facturas pero no el tablero
  financiero" y para el monitor de técnicos.
- Un cambio de expectativa consciente: Contabilidad **sí** puede listar
  proyectos (los necesita para la rentabilidad por proyecto, PDF §4.5), donde
  el rol financiero anterior recibía 403. El test lo dice explícitamente.

**Verificación:** suite completa **89 pasan, 1 falla** — la preexistente de
`field_ops`, ajena a este trabajo. En la base local quedaron los 6 roles con
sus etiquetas en español (Administrador 72 permisos, Administración 35,
Contabilidad 23, Gerencia 15, Vendedor 14, Técnico 11), plantilla y copia de
la organización. Login y `/auth/me` verificados contra la API real: el admin
conserva sus 72 permisos.

---

### Tarea 3 — API de roles y permisos

**Archivos:**
- Crear: `backend/app/modules/users/selectors.py`,
  `backend/app/modules/users/roles_router.py`
- Modificar: `backend/app/modules/users/{service.py,schemas.py}`,
  `backend/app/modules/organizations/router.py`, `backend/app/api/v1/router.py`
- Modificar: `backend/tests/test_roles.py`

**Interfaces:**
- Produce: `GET /permissions`, `GET /roles`, `POST /roles`,
  `PATCH /roles/{code}`, `DELETE /roles/{code}`.
  `RoleResponse = {code, name, is_system, is_locked, permissions: list[str], user_count: int}`.
  `PermissionResponse = {code, description, module}`.
  `PermissionCatalogResponse = {modules: list[{key, label}], permissions: list[PermissionResponse]}`.

- [ ] **Paso 1: escribir los tests que fallan** — `backend/tests/test_roles.py`

Tests (con el helper `_login` que ya usan los otros archivos de test):

```python
async def test_list_permissions_groups_by_module(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.get("/api/v1/permissions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert {"key": "billing", "label": "Facturación y cobros"} in body["modules"]
    codes = {p["code"]: p["module"] for p in body["permissions"]}
    assert codes["invoices.read"] == "billing"
    assert codes["expenses.create_own"] == "expenses"


async def test_list_permissions_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, active_technician_user.email)
    resp = await app_client.get("/api/v1/permissions", headers=headers)
    assert resp.status_code == 403


async def test_create_role(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "zone_coordinator", "name": "Coordinador de zona",
              "permissions": ["projects.read_all", "dispatch.manage"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_system"] is False
    assert set(resp.json()["permissions"]) == {"projects.read_all", "dispatch.manage"}


async def test_create_role_rejects_unknown_permission(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "x_role", "name": "X", "permissions": ["no.existe"]},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_create_role_rejects_system_code(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "salesperson", "name": "Otro", "permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_update_system_role_permissions(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.patch(
        "/api/v1/roles/salesperson",
        json={"permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["permissions"] == ["customers.read"]


async def test_cannot_edit_locked_admin_role(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.patch(
        "/api/v1/roles/organization_admin",
        json={"permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_cannot_delete_system_role(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.delete("/api/v1/roles/salesperson", headers=headers)
    assert resp.status_code == 409


async def test_delete_role_with_users_is_rejected(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, active_admin_user.email)
    await app_client.post(
        "/api/v1/roles",
        json={"code": "temp_role", "name": "Temporal", "permissions": ["customers.read"]},
        headers=headers,
    )
    await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["temp_role"]}, headers=headers,
    )
    resp = await app_client.delete("/api/v1/roles/temp_role", headers=headers)
    assert resp.status_code == 409


async def test_delete_role_without_users(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    await app_client.post(
        "/api/v1/roles",
        json={"code": "temp_role", "name": "Temporal", "permissions": ["customers.read"]},
        headers=headers,
    )
    resp = await app_client.delete("/api/v1/roles/temp_role", headers=headers)
    assert resp.status_code == 204


async def test_roles_are_scoped_to_the_organization(app_client, active_admin_user, other_org_admin_user):
    headers = await _login(app_client, other_org_admin_user.email)
    resp = await app_client.patch(
        "/api/v1/roles/zone_coordinator", json={"name": "X"}, headers=headers
    )
    assert resp.status_code == 404
```

(`other_org_admin_user` es una fixture nueva: admin de una segunda
organización; se agrega en `conftest.py` reutilizando `seeded_org`.)

- [ ] **Paso 2: correr y verlos fallar**

Ejecutar: `docker compose exec -T api python -m pytest tests/test_roles.py -q`
Esperado: FALLAN con 404 (las rutas no existen).

- [ ] **Paso 3: implementar selectors, service, schemas y router**

`selectors.py`: `roles_for_org(db, organization_id)` (dedup plantilla vs
copia, con `user_count`), `get_role_or_404(db, organization_id, code)`.
`service.py`: `create_role`, `update_role` (crea la copia de la organización
si aún no existe antes de modificarla), `delete_role`, todos con
`record_audit_event`. `roles_router.py` con los cinco endpoints y
`require_any_permission("roles.manage", "users.manage")` en los GET,
`require_permission("roles.manage")` en las escrituras. Quitar `GET /roles`
de `organizations/router.py` y registrar el router nuevo en `api/v1/router.py`.

- [ ] **Paso 4: correr los tests hasta que pasen**

Ejecutar: `docker compose exec -T api python -m pytest tests/test_roles.py -q`
Esperado: PASAN.

- [ ] **Paso 5: suite completa + Swagger**

Ejecutar: `docker compose exec -T api python -m pytest -q` (sin fallos nuevos)
y revisar `http://localhost:8000/api/docs` que los cinco endpoints aparezcan.

- [ ] **Paso 6: documentar y commit**

`docs/PERMISOS.md`: sección "API de roles" con los cinco endpoints, sus
permisos y sus códigos de error.

```bash
git add backend/app/modules/users backend/app/modules/organizations/router.py backend/app/api/v1/router.py backend/tests/test_roles.py docs/PERMISOS.md
git commit -m "feat(roles): add roles and permissions API"
```

---

### Tarea 4 — Cambiar roles de un usuario y exponer módulos en `/auth/me`

**Archivos:**
- Modificar: `backend/app/modules/users/{router.py,service.py,schemas.py}`
- Modificar: `backend/app/modules/auth/{router.py,schemas.py}`
- Crear: `backend/tests/test_users_roles.py`

**Interfaces:**
- Produce: `PATCH /users/{id}/roles`, `PATCH /users/{id}`.
  `CurrentUserResponse` gana `role_names: list[str]` y `modules: list[str]`.

- [ ] **Paso 1: escribir los tests que fallan** — `backend/tests/test_users_roles.py`

```python
async def test_change_user_roles(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["accounting"]


async def test_change_user_roles_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, active_technician_user.email)
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]}, headers=headers,
    )
    assert resp.status_code == 403


async def test_cannot_remove_last_organization_admin(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.patch(
        f"/api/v1/users/{active_admin_user.id}/roles",
        json={"role_codes": ["management"]}, headers=headers,
    )
    assert resp.status_code == 409


async def test_role_change_updates_effective_permissions(app_client, active_admin_user, active_technician_user):
    admin_headers = await _login(app_client, active_admin_user.email)
    await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]}, headers=admin_headers,
    )
    tech_headers = await _login(app_client, active_technician_user.email)
    me = (await app_client.get("/api/v1/auth/me", headers=tech_headers)).json()
    assert "invoices.read" in me["permissions"]
    assert "billing" in me["modules"]
    assert "projects" not in me["modules"]
    assert me["role_names"] == ["Contabilidad"]


async def test_me_exposes_modules_for_technician(app_client, active_technician_user):
    headers = await _login(app_client, active_technician_user.email)
    me = (await app_client.get("/api/v1/auth/me", headers=headers)).json()
    assert set(me["modules"]) >= {"projects", "customers", "dispatch", "expenses"}
    assert "team" not in me["modules"]
    assert "billing" not in me["modules"]


async def test_update_user_name(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, active_admin_user.email)
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}",
        json={"full_name": "Nombre Nuevo"}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Nombre Nuevo"
```

- [ ] **Paso 2: correr y verlos fallar** (404 y KeyError en `modules`).

- [ ] **Paso 3: implementar**

`service.set_user_roles(db, organization_id, user_id, actor, role_codes)`:
valida que los roles existan en la organización, cuenta los
`organization_admin` activos antes de quitarlo (409 si queda en cero),
reemplaza `user_roles`, audita `users.roles_changed` con antes y después.
`service.update_user(db, ..., full_name)`. En `auth/router.py`, `/auth/me`
agrega `role_names` (desde `ROLE_LABELS` con respaldo al nombre del rol) y
`modules` (desde `modules_for_permissions`); para el super admin, todos los
módulos.

- [ ] **Paso 4: correr los tests hasta que pasen.**

- [ ] **Paso 5: suite completa sin fallos nuevos.**

- [ ] **Paso 6: documentar y commit**

```bash
git add backend/app/modules/users backend/app/modules/auth backend/tests/test_users_roles.py docs/PERMISOS.md
git commit -m "feat(users): change user roles and expose modules in /auth/me"
```

---

### Tarea 5 — Menú por módulo y protección de rutas (frontend)

**Archivos:**
- Crear: `frontend/src/config/navigation.ts`,
  `frontend/src/components/RequireAccess.tsx`,
  `frontend/src/components/NoAccess.tsx`
- Modificar: `frontend/src/app/{router.tsx,DashboardLayout.tsx}`,
  `frontend/src/features/auth/AuthContext.tsx`,
  `frontend/src/types/auth.ts`

**Interfaces:**
- Consume: `/auth/me` con `modules` y `role_names` (tarea 4).
- Produce: `buildNavForUser(user): NavGroup[]`; `hasModule(module): boolean`
  en `useAuth()`; `<RequireAccess module="billing">` y
  `<RequireAccess permission="roles.manage">`.

- [ ] **Paso 1: `navigation.ts`**

Constantes `MODULE` (las 15 claves), y `NAV_GROUPS` con la estructura de la
sección 7 del spec: cada ítem con `label`, `href`, `icon`, y **o**
`module` **o** `permission`, más `disabled: true` en los módulos que aún no
existen. `buildNavForUser(user)` devuelve los grupos con sus ítems visibles
(el super admin ve todo) y descarta los grupos que quedan vacíos.

- [ ] **Paso 2: `hasModule` en `AuthContext`**

```tsx
const hasModule = useCallback(
  (module: string) => user?.modules.includes(module) ?? false,
  [user]
);
```
y `modules: string[]`, `role_names: string[]` en `CurrentUser`.

- [ ] **Paso 3: `NoAccess.tsx` y `RequireAccess.tsx`**

`NoAccess` muestra "No tienes acceso a este módulo", el nombre del módulo y
un enlace a Inicio. `RequireAccess` recibe `module` o `permission`, y
devuelve `<NoAccess/>` si el usuario no cumple; **no** monta los hijos, para
que no se disparen consultas.

- [ ] **Paso 4: envolver todas las rutas en `router.tsx`**

Cada ruta hija de `"/"` queda envuelta: `/leads` y `/customers` con
`module="customers"`; `/applications` y `/opportunities` con `module="cases"`;
`/projects` con `module="projects"`; `/technician-monitor` con
`permission="dashboards.operations"`; `/invoices` con `module="billing"`;
`/users` con `module="team"`; `/audit-log` con `module="audit"`.
`/customers/:customerId` y `/projects/:projectId` heredan el de su listado.

- [ ] **Paso 5: `DashboardLayout` usa `buildNavForUser`**

Quitar `NAV_ITEMS` del layout; pintar grupos con su etiqueta, ítems
deshabilitados en gris y sin enlace. Mostrar `role_names` en la cabecera.

- [ ] **Paso 6: verificar compilación**

Ejecutar: `docker compose exec -T frontend sh -c "npx tsc -b && npx vite build"`
Esperado: limpio.

- [ ] **Paso 7: verificar en navegador con dos roles**

Con la skill `browser-automation`: entrar como admin (ve todo, incluido
"Roles y permisos" deshabilitado hasta la tarea 6) y como técnico (ve solo
lo suyo). Abrir `/invoices` por URL como técnico y confirmar "Sin acceso"
sin peticiones a `/invoices` en la consola de red.

- [ ] **Paso 8: documentar y commit**

`docs/PERMISOS.md`: sección "Menú y rutas" explicando `navigation.ts`,
`hasModule` y `RequireAccess`.

```bash
git add frontend/src docs/PERMISOS.md
git commit -m "feat(frontend): module-based menu and route protection"
```

---

### Tarea 6 — Pantalla de roles y permisos

**Archivos:**
- Crear: `frontend/src/features/roles/{api.ts,queries.ts,RolesPage.tsx}`,
  `frontend/src/features/roles/components/{RoleForm.tsx,PermissionPicker.tsx}`
- Modificar: `frontend/src/app/router.tsx`, `frontend/src/types/users.ts`,
  `frontend/src/index.css`

**Interfaces:**
- Consume: `GET /permissions`, `GET/POST/PATCH/DELETE /roles` (tarea 3).
- Produce: ruta `/roles` con `permission="roles.manage"`.

- [ ] **Paso 1: `api.ts` y `queries.ts`**

Funciones `listPermissionCatalog`, `listRoles`, `createRole`, `updateRole`,
`deleteRole`; hooks con `queryKey` centralizada (`rolesKeys.all`,
`rolesKeys.catalog`) e invalidación tras cada mutación.

- [ ] **Paso 2: `PermissionPicker.tsx`**

Recibe el catálogo y los códigos marcados; pinta un bloque por módulo con su
etiqueta, una casilla "todo el módulo" (estado indeterminado si hay
selección parcial) y las casillas de cada permiso con su descripción. En
móvil, cada módulo colapsado. Deshabilitado completo cuando el rol está
bloqueado.

- [ ] **Paso 3: `RoleForm.tsx` y `RolesPage.tsx`**

Lista con nombre, código, tipo (Sistema / Organización), número de usuarios y
acciones. Crear rol (código, nombre, permisos) y editar (nombre, permisos).
Borrar solo roles de organización sin usuarios, con confirmación. Estados de
carga, vacío y error. Textos en español.

- [ ] **Paso 4: ruta y enlace**

`/roles` en `router.tsx` con `RequireAccess permission="roles.manage"`; el
ítem del menú ya existe desde la tarea 5 (se le quita `disabled`).

- [ ] **Paso 5: compilación**

Ejecutar: `docker compose exec -T frontend sh -c "npx tsc -b && npx vite build"`

- [ ] **Paso 6: verificar en navegador**

Crear el rol "Coordinador de zona" con el módulo Proyectos completo,
guardarlo, recargar y ver que persiste; intentar editar "Administrador" y ver
que está bloqueado.

- [ ] **Paso 7: documentar y commit**

```bash
git add frontend/src docs/PERMISOS.md
git commit -m "feat(roles): add roles and permissions admin screen"
```

---

### Tarea 7 — Editar roles de un usuario desde Equipo

**Archivos:**
- Modificar: `frontend/src/features/users/{api.ts,UsersPage.tsx}`
- Crear: `frontend/src/features/users/{queries.ts,components/UserEditPanel.tsx}`

**Interfaces:**
- Consume: `PATCH /users/{id}/roles`, `PATCH /users/{id}` (tarea 4).

- [ ] **Paso 1: `api.ts` y `queries.ts`** — `updateUserRoles`, `updateUser`.

- [ ] **Paso 2: `UserEditPanel.tsx`** — nombre completo y casillas de roles
  (etiquetas, no códigos), con `react-hook-form` + `zod`. Muestra el error
  del backend cuando se intenta dejar la organización sin administrador.

- [ ] **Paso 3: `UsersPage.tsx`** — columna Roles con etiquetas; acción
  "Editar" que abre el panel; invalidación de la lista al guardar. El
  formulario de invitar pasa a `react-hook-form` + `zod`.

- [ ] **Paso 4: compilación limpia.**

- [ ] **Paso 5: verificar en navegador** — cambiarle el rol al usuario
  técnico a Contabilidad, entrar con ese usuario y ver el menú cambiado.

- [ ] **Paso 6: documentar y commit**

```bash
git add frontend/src docs/PERMISOS.md
git commit -m "feat(users): edit user roles from the team screen"
```

---

### Tarea 8 — Verificación por rol y cierre

**Archivos:**
- Modificar: `docs/PERMISOS.md`, `docs/decisiones.md`, `README.md`

- [ ] **Paso 1: sembrar un usuario por rol**

Agregar a `scripts/seed.py` un flag `--demo-users` que cree seis usuarios
activos (uno por rol) con contraseña conocida, solo para el entorno de
desarrollo. Correrlo contra la base local.

- [ ] **Paso 2: recorrer los seis roles en el navegador**

Con `browser-automation`, un script que entre con cada usuario, capture el
menú visible y lo compare con la sección 7 del spec. Reportar diferencias.

- [ ] **Paso 3: probar el caso de aceptación completo**

Crear rol nuevo → darle un módulo → asignarlo → entrar con ese usuario → ver
el menú cambiado. Sin tocar código ni base de datos.

- [ ] **Paso 4: verificar auditoría**

`select action, count(*) from audit_events group by action;` — deben
aparecer `roles.created`, `roles.updated`, `users.roles_changed`.

- [ ] **Paso 5: suite completa y compilación**

`pytest -q` (sin fallos nuevos), `tsc -b`, `vite build`.

- [ ] **Paso 6: cerrar documentación**

`docs/PERMISOS.md` completo; `decisiones.md` D1 cerrado; `README.md` con una
línea sobre roles y `--demo-users`.

- [ ] **Paso 7: commit final**

```bash
git add -A
git commit -m "docs(permissions): document roles, modules and access control"
```

---

### Tarea 9 (si queda tiempo) — Perfil y cambio de contraseña

**Archivos:**
- Modificar: `backend/app/modules/auth/{router.py,service.py,schemas.py}`
- Crear: `backend/tests/test_profile.py`,
  `frontend/src/features/auth/ProfilePage.tsx`

- [ ] **Paso 1: tests de `PATCH /auth/me` y `POST /auth/me/change-password`**
  (contraseña actual incorrecta → 400; correcta → 200 y tokens nuevos; la
  sesión anterior queda invalidada por `token_version`).
- [ ] **Paso 2: implementar y pasar los tests.**
- [ ] **Paso 3: `ProfilePage` con datos, roles y cambio de contraseña.**
- [ ] **Paso 4: compilación, navegador, documentación y commit.**
