# Permisos y accesos — Guía de referencia

Cómo se autoriza el acceso en crm-usa y cómo dar o quitar accesos sin tocar
código. Diseño completo en
`docs/superpowers/specs/2026-09-22-modulo-0-roles-design.md`.

> Estado: en construcción (módulo 0, semana del 21 de septiembre de 2026).
> Cada sección se completa al terminar su tarea del plan
> `docs/superpowers/plans/2026-09-22-modulo-0-roles.md`.

## El modelo en una frase

El acceso se controla con **roles** (tabla `roles`) que agrupan **permisos**
(tabla `permissions`) a través de `role_permissions`, y usuarios que
pertenecen a roles (`user_roles`). Es el mismo modelo que el sistema de
Groups de Django: `roles` = `auth_group`, `permissions` = `auth_permission`,
`role_permissions` = `auth_group_permissions`, `user_roles` =
`auth_user_groups`.

## Las tres capas de autorización

1. **Autenticación** — JWT. Sin sesión no se entra (`get_current_user`).
2. **Permiso (gruesa, por módulo)** — `require_permission("codigo")` y
   `require_any_permission("a", "b")` en `app/api/deps.py`. Aquí se decide si
   el rol puede usar la capacidad.
3. **Negocio (fina, en el service o el selector)** — dueño del registro, etapa
   del expediente, proyecto asignado. No se administra desde la aplicación; es
   lógica de negocio. Ejemplo: `projects.read_assigned` deja entrar al módulo,
   y el selector filtra a los proyectos donde el usuario es el técnico.

El usuario con `is_platform_super_admin` pasa la capa 2 completa.

## Módulos (grupos de permisos)

Un **módulo** es un grupo de permisos. Es la unidad de navegación: el menú y
las rutas del frontend preguntan *"¿este usuario tiene algún permiso de este
módulo?"*, no por permisos sueltos.

**El módulo tiene la lista de permisos, no al revés.** El permiso es solo un
código y su descripción; no sabe dónde se muestra. Así la relación es de
muchos a muchos y un mismo permiso puede pertenecer a varios módulos:

- `dashboards.finance` está en Facturación y en Reportes.
- `programs.read` está en Configuración y en Expedientes (el vendedor lo
  necesita para elegir el programa).
- `evidence.read_all` está en Proyectos y en Expedientes (Administración las
  revisa dentro del expediente).

Los módulos se guardan en dos tablas y se administran desde la aplicación
(decisión D9):

- `permission_modules` — clave, etiqueta, orden, `is_system`, y
  `organization_id` (nulo = plantilla del sistema; cada organización recibe su
  copia editable, igual que los roles).
- `permission_module_items` — el detalle: qué permisos tiene cada módulo. Es
  tabla aparte y no una columna en `permissions` justamente porque un permiso
  pertenece a varios módulos.

`DEFAULT_MODULES` en `app/shared/permissions.py` es el **valor inicial** que
siembra `scripts/seed.py`, igual que `DEFAULT_ROLE_PERMISSIONS` lo es para los
roles. Editar un módulo cambia la copia de la organización, nunca la
plantilla ni el código.

Los 15 módulos del sistema se pueden renombrar, reordenar y cambiarles los
permisos, pero **no borrar**, porque el menú del frontend referencia su clave.
Si un módulo se queda sin permisos, su ítem del menú desaparece para todos:
por eso cada módulo tiene "restaurar valores por defecto".

Salen de los cuatro bloques de "Funcionalidades requeridas" del PDF
`Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`. El criterio para separar dos
capacidades en módulos distintos es que **los roles que las necesitan sean
distintos**: por eso los gastos de campo no están dentro de facturación (los
carga el técnico desde el móvil, §4.1) y los permisos municipales no están
dentro de proyectos (los lleva Administración, §3.2 y §3.5).

Operación comercial:

- `customers` — Prospectos y clientes: `leads.manage`, `customers.create`,
  `customers.read`, `customers.update`, `customers.delete`,
  `contacts.manage`, `activities.manage`.
- `cases` — Expedientes: `cases.create`, `cases.read_own`, `cases.read_all`,
  `cases.submit`, `cases.review`, `cases.approve`, `cases.close_admin`,
  `dashboards.commercial`, `programs.read` (compartido con Configuración),
  `evidence.read_all` (compartido con Proyectos). Obsoletos hasta el módulo 1:
  `opportunities.manage`, `quotes.manage`.
- `documents` — Documentos: `documents.manage`, `documents.review`.

Operación de campo:

- `projects` — Proyectos e instalación: `projects.create`,
  `projects.read_all`, `projects.read_assigned`, `projects.update`,
  `projects.assign`, `projects.close`, `tasks.manage`, `checklists.manage`,
  `checklists.complete`, `checklists.approve`, `evidence.create`,
  `evidence.read_all`, `evidence.read_assigned`, `evidence.delete`,
  `equipment.manage`.
- `dispatch` — Agenda y despacho: `dispatch.manage`, `dispatch.read_own`,
  `dashboards.operations`.
- `permits` — Permisos e inspecciones: `permits.manage`,
  `inspections.manage`.

Finanzas:

- `billing` — Facturación y cobros: `invoices.create`, `invoices.read`,
  `invoices.update`, `invoices.record_payment`, `invoices.export`,
  `billing.submit`, `dashboards.finance`.
- `expenses` — Gastos de campo: `expenses.create_own`, `expenses.read_all`,
  `expenses.approve`.
- `payables` — Proveedores y pagos: `suppliers.manage`, `payables.manage`.
- `finance_close` — Conciliación y rentabilidad: `reconciliation.manage`,
  `profitability.read`, `accounting.export`.

Administración:

- `reports` — Reportes e indicadores: `reports.view`, `reports.generate`,
  `reports.export`, y los tableros `dashboards.commercial`,
  `dashboards.operations`, `dashboards.finance` y `profitability.read`
  (compartidos con Expedientes, Agenda, Facturación y Conciliación).
- `config` — Configuración de programas: `programs.read`, `programs.manage`,
  `fields.manage`, `fields.view_sensitive`, `workflows.manage`,
  `workflows.publish`, `zones.manage`, `settings.manage`,
  `organization.manage`.
- `team` — Usuarios y roles: `users.manage`, `roles.manage`.
- `audit` — Auditoría: `audit.read`.
- `notifications` — Notificaciones: `notifications.manage`,
  `notifications.read_own`.

Sin módulo: `profile.manage`, que tienen todos los roles y no habilita
ningún ítem del menú.

## Roles del sistema

Son los del flujo operativo del PDF (decisión D1):

- `organization_admin` — Administrador. Tiene todos los permisos y no se
  edita ni se borra, para que nadie se deje sin acceso a Usuarios y Roles.
- `salesperson` — Vendedor.
- `admin_staff` — Administración.
- `field_technician` — Técnico. Conserva ese código (y no `technician`)
  porque el monitor de técnicos de la Cadena B lo referencia directamente;
  solo cambió su etiqueta.
- `accounting` — Contabilidad.
- `management` — Gerencia.

La matriz inicial rol → permiso está en `DEFAULT_ROLE_PERMISSIONS`
(`app/shared/permissions.py`) y es solo el punto de partida del seed: a
partir de ahí se administra desde la aplicación.

## Migración desde los roles anteriores

La migración `0010_roles_pdf` (23 de septiembre de 2026) dejó la base con los
seis roles del PDF. Reasignó los usuarios de los roles genéricos anteriores:
`commercial_manager` → Vendedor; `project_manager` y `supervisor` →
Administración; `finance_user` → Contabilidad; `read_only` → Gerencia.

Esa migración es la **línea base**: sincronizó `role_permissions` con la
matriz del catálogo. De ahí en adelante la matriz se administra desde la
aplicación y **ninguna migración vuelve a sobrescribirla**.

Su `downgrade()` restaura la estructura anterior, no las asignaciones exactas:
un usuario que estaba en `supervisor` y pasó a Administración vuelve a
`project_manager`, porque al fusionar dos roles en uno esa información se
pierde.

## API de roles y permisos

Todo bajo `/api/v1`. Los `GET` aceptan `roles.manage` **o** `users.manage`
(quien administra usuarios necesita leer los roles para poder asignarlos); las
escrituras exigen `roles.manage`.

- `GET /permissions` — catálogo completo más los módulos de la organización
  con sus permisos. Es lo que la pantalla usa para pintar las casillas
  agrupadas. Los módulos vienen de la base, no del código, porque el
  administrador pudo haberlos editado.
- `GET /roles` — roles de la organización con `code`, `name`, `is_system`,
  `is_locked`, `permissions` y `user_count`. Si existe la copia de la
  organización, esa gana sobre la plantilla del sistema.
- `POST /roles` — crea un rol propio. `code` en minúsculas, sin espacios
  (`^[a-z][a-z0-9_]{2,49}$`). Errores: 409 si el código ya existe, 400 si
  algún permiso no está en el catálogo, 422 si el código no cumple el formato.
- `PATCH /roles/{code}` — cambia nombre y/o permisos. Editar un rol del
  sistema modifica **la copia de la organización**, nunca la plantilla; si la
  copia no existe todavía, se crea en ese momento. Errores: 409 si el rol está
  bloqueado, 400 si un permiso no existe, 404 si el rol no es de esta
  organización.
- `DELETE /roles/{code}` — solo roles propios y sin usuarios. Errores: 409 si
  es del sistema o si lo tiene alguien asignado.
- `PATCH /users/{id}/roles` — reemplaza los roles de una persona. 409 si
  dejaría a la organización sin ningún administrador activo.
- `PATCH /users/{id}` — cambia el nombre completo.

`GET /auth/me` devuelve, además de `roles` y `permissions`:

- `role_names` — las etiquetas visibles ("Técnico"), para no mostrar códigos
  en la interfaz.
- `modules` — los módulos que ese usuario puede abrir, calculados con los
  módulos **de su organización** (los que el administrador pudo haber
  editado), no con los valores de código. El menú y las rutas del frontend se
  construyen con esta lista en vez de repetir allá la lógica de agrupamiento.
  El super admin de plataforma los recibe todos.

Todas las escrituras quedan en `audit_events` con el antes y el después:
`roles.created`, `roles.updated`, `roles.deleted`, `users.roles_changed`,
`users.updated`.

## Cómo dar o quitar accesos (operación)

Desde la pantalla de Roles y permisos (pendiente, tarea 6 del plan). Mientras
tanto, con la API de arriba.

Dos protecciones que conviene conocer:

- **El rol Administrador está bloqueado.** No se puede editar ni borrar, y
  siempre conserva todos los permisos. Sin eso, alguien podría quitarse el
  acceso a Usuarios y Roles y quedar encerrado fuera de la configuración, sin
  forma de volver a entrar salvo tocando la base de datos.
- **No se puede quitar el último administrador activo.** El sistema responde
  409 y pide asignarle el rol a otra persona primero.

## Cómo proteger un endpoint nuevo (desarrollo)

```python
from app.api.deps import require_permission, require_any_permission

@router.post("/programs")
async def create_program(
    current_user: User = Depends(require_permission("programs.manage")),
    ...
): ...
```

`require_any_permission("projects.read_all", "projects.read_assigned")`
cuando dos permisos —uno amplio y uno estrecho— dan acceso al mismo endpoint;
el selector se encarga de estrechar los resultados.

## Cómo agregar un permiso nuevo (desarrollo)

1. Agregarlo a `PERMISSION_CATALOG` en `app/shared/permissions.py` con su
   descripción.
2. Agregarlo a la lista de permisos de **uno o varios** módulos en `MODULES`
   (o a `STANDALONE_PERMISSIONS` si a propósito no debe aparecer en el menú).
3. Asignarlo a los roles que lo necesiten en `DEFAULT_ROLE_PERMISSIONS`.
4. Usarlo en el endpoint con `require_permission(...)`.
5. Escribir un test que devuelva 403 sin el permiso y 2xx con él.

`tests/test_permissions_catalog.py` verifica automáticamente que ningún
módulo liste permisos inexistentes, que ningún permiso quede fuera de todo
módulo sin declararlo, que ningún rol use códigos inexistentes, que
`organization_admin` los tenga todos, y que **todo permiso exigido por un
endpoint exista en el catálogo**. Si se olvida un paso, ese test falla.

## Deuda conocida

- `PATCH /checklist-items/{id}` (Cadena B) exige `checklists.manage`, que
  también permite crear plantillas de checklist. Por eso hoy el técnico **no
  puede completar su propio checklist**, aunque el PDF §5.5 se lo exige. El
  código `checklists.complete` ya está reservado en el catálogo y asignado al
  técnico; falta que el módulo 5 cambie ese endpoint para exigirlo.
- `opportunities.manage` y `quotes.manage` quedan en el catálogo hasta que el
  módulo 1 retire `Opportunity` y `Quote` (decisión D2).
