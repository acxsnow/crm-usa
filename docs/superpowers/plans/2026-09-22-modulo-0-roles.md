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

### Tarea 3 — API de roles y permisos ✅ HECHA (23 sep)

**Archivos:**
- Crear: `backend/app/modules/users/roles_router.py`
- Modificar: `backend/app/modules/users/{selectors,service,schemas,router}.py`,
  `backend/app/modules/organizations/router.py`, `backend/app/api/v1/router.py`,
  `backend/tests/test_roles.py`, `docs/PERMISOS.md`

**Lo que quedó:** `GET /permissions`, `GET/POST/PATCH/DELETE /roles`, y
—adelantado de la tarea 4 porque los tests de borrado lo necesitaban—
`PATCH /users/{id}/roles` y `PATCH /users/{id}`. `GET /roles` se mudó de
`organizations` a `users/roles_router.py`; la ruta pública no cambió.

Reglas implementadas, cada una con su test:

- El rol Administrador está bloqueado: 409 al intentar editarlo o borrarlo.
- No se puede quitar el último administrador activo de la organización: 409.
- Editar un rol del sistema crea y modifica **la copia de la organización**,
  nunca la plantilla que comparten todas.
- Un permiso inventado da 400 con el código exacto en el mensaje, en vez de
  guardarse en silencio.
- Un rol con usuarios asignados no se borra: 409 diciendo cuántos.
- `GET /roles` y `GET /permissions` aceptan `users.manage` además de
  `roles.manage`: antes exigían solo `roles.manage` y la pantalla de Equipo se
  quedaba sin la lista para quien únicamente administra usuarios.
- Aislamiento por organización: los roles de una no se ven ni se editan desde
  otra (404).

**Verificación:** 19 tests de roles en verde; suite completa **110 pasan, 0
fallan**. Probado también contra la API real: catálogo con 15 módulos y 72
permisos, `dashboards.finance` aparece en `billing` y en `reports`, se creó y
borró el rol "Coordinador de zona", editar Administrador devolvió 409, y
`audit_events` registró `roles.created` y `roles.deleted`.

---

### Tarea 4 — Roles de usuario y módulos en `/auth/me` ✅ HECHA (23 sep)

**Archivos:** `backend/app/modules/auth/{router,schemas}.py`,
`backend/app/modules/users/service.py`, `backend/tests/test_users_roles.py`,
`docs/PERMISOS.md`.

**Lo que quedó:** `/auth/me` devuelve `role_names` (etiquetas visibles) y
`modules` (los que ese usuario puede abrir), calculados con los módulos de su
organización, no con los valores de código. El super admin de plataforma
recibe todos. `accept_invitation` usa la misma respuesta, así que quien acepta
una invitación entra con su menú ya resuelto.

Un detalle que costó un test: tras cambiar los roles de alguien, la respuesta
devolvía los roles **anteriores**, porque la relación seguía cacheada en la
sesión. Se relee con `selectinload` + `populate_existing`, igual que en el
selector de módulos.

**Verificación:** 10 tests nuevos en verde; suite completa **120 pasan, 0
fallan**. Contra la API real, el admin recibe sus 15 módulos y
`role_names: Administrador`. Un test comprueba el caso que importa: quitarle
permisos a un módulo desde la base hace que ese módulo deje de aparecer en
`/auth/me` para quien solo entraba por ahí, y los demás siguen intactos.

---

### Tarea 5 — Menú por módulo y protección de rutas ✅ HECHA (23 sep)

**Archivos:** `frontend/src/config/navigation.ts`,
`frontend/src/components/{RequireAccess,NoAccess}.tsx`,
`frontend/src/app/{router,DashboardLayout}.tsx`,
`frontend/src/features/auth/AuthContext.tsx`, `frontend/src/types/auth.ts`,
`frontend/src/index.css`.

**Lo que quedó:**

- `navigation.ts` con los 15 módulos en 5 grupos y `buildNavForUser(user)`,
  calcado del `navigation.tsx` de `ventas_pap`. El layout ya no lleva el menú
  adentro: solo lo pinta.
- Los módulos que aún no existen salen **en gris** (`disabled`), así que el mapa
  completo del sistema se ve desde el primer día.
- `hasModule()` en `AuthContext`, alimentado por `modules` de `/auth/me`.
- `RequireAccess` en **todas** las rutas. No monta los hijos cuando no hay
  acceso: si solo escondiera la pantalla, los componentes se montarían igual y
  dispararían consultas que el backend rechaza una por una.
- Pantalla "Sin acceso" en español, con enlace a Inicio.
- El nombre del rol se muestra en la cabecera.

**Tres cosas que encontró la prueba en navegador, no los tests:**

1. **El rol se asignaba dos veces al invitar.** Un rol del sistema existe como
   plantilla y como copia de la organización, y `invite_user` traía las dos.
   En pantalla salía "Técnico · Técnico". Corregido con deduplicación por
   código (gana la copia de la organización) y un test que **reproduce las
   condiciones reales**: el primer intento pasó en verde porque el entorno de
   pruebas no creaba las plantillas del sistema.
2. **El técnico veía "Prospectos".** `customers` agrupa prospectos y clientes,
   y el técnico tiene `customers.read` (necesita ver el cliente de su proyecto)
   pero no `leads.manage`. Habría entrado para recibir un 403. Prospectos pasó
   a declararse por permiso puntual. Es el riesgo conocido de agrupar: cuando
   un ítem no corresponde al módulo completo, se declara con `permission`.
3. **Mi propio script de prueba estaba mal**: comprobaba "el técnico entra a
   facturación" con la sesión del contable, que sí tiene acceso. Corregido.

**Verificación en navegador, con tres usuarios reales:**

- Administrador: los 11 ítems construidos + 9 en gris.
- Técnico: Inicio, Clientes, Proyectos.
- Contabilidad: Inicio, Clientes, Expedientes, Pipeline, Proyectos,
  Facturación, Auditoría.
- El técnico entrando por URL a `/invoices`, `/users` y `/leads` ve "No tienes
  acceso a esta sección" y **no dispara ninguna consulta** (`pidio_datos:
  false` en los tres casos).

Suite: **141 pasan, 0 fallan**; `tsc -b` y `vite build` limpios.

---

### Tarea 6 — Pantalla de roles y permisos ✅ HECHA (23 sep)

**Archivos:** `frontend/src/features/roles/{api,queries,RolesPage}.tsx`,
`frontend/src/features/roles/components/PermissionPicker.tsx`,
`frontend/src/app/router.tsx`, `frontend/src/types/users.ts`,
`frontend/src/index.css`, `docs/PERMISOS.md`.

**Lo que quedó:**

- Lista de roles con nombre, origen (Sistema o Propio), número de permisos y
  de usuarios.
- Crear rol con código validado, editar nombre y permisos, eliminar los
  propios con confirmación.
- `PermissionPicker`: permisos agrupados por módulo, con casilla por grupo en
  tres estados (todo, nada, parcial) y "Ver detalle" para el permiso
  individual. El administrador piensa en módulos, no en 72 códigos.
- Un permiso que está en varios módulos aparece en cada uno; marcarlo desde
  cualquiera lo activa en todos. Al **desmarcar** un módulo completo, los
  permisos que también pertenecen a otro módulo marcado se conservan: de lo
  contrario, apagar Facturación apagaría `dashboards.finance` en Reportes.
- El rol Administrador se muestra con todo marcado, deshabilitado y con un
  aviso que explica por qué está bloqueado.
- Los errores que se muestran son los del backend, que ya vienen en español y
  explican la regla concreta ("Este rol lo tienen 2 usuario(s)…").
- `queries.ts` centraliza las claves de consulta, para que guardar siempre
  refresque la lista.

**Verificación en navegador:** la lista muestra los 6 roles con su metadata
correcta; el rol Administrador sale bloqueado (aviso presente, botón Guardar
ausente, todas las casillas deshabilitadas); se creó "Coordinador de zona"
marcando el módulo Proyectos completo (15 permisos) y persiste tras recargar.

**Criterio de aceptación del módulo 0, comprobado de punta a punta:** el
administrador creó el rol desde la pantalla, se lo asignó al usuario técnico
por API, y ese usuario pasó a tener `role_names: ["Coordinador de zona"]` con
los módulos `cases` y `projects` — sin tocar código ni base de datos. Todo
quedó en `audit_events` (`roles.created`, `roles.deleted`,
`users.roles_changed`).

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
