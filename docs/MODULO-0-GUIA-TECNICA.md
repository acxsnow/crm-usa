# Módulo 0 — Manual de operación: menús, permisos y roles

Este archivo responde una sola pregunta: **"quiero cambiar algo del menú o de
los permisos, ¿qué toco y en qué orden?"**

Está escrito para alguien que viene de Django + Vue. Cada pieza lleva su
equivalente, porque el concepto es el mismo aunque el archivo se llame distinto.

---

## 1. Las cuatro piezas

Antes de las recetas hay que tener claro qué es cada cosa. Son cuatro y se
confunden fácil.

- **Permiso** — la unidad mínima. Un código y su descripción: `invoices.read`,
  `cases.create`. No sabe dónde se muestra ni quién lo tiene.
  *En Django es el `Permission`.*

- **Módulo** — un grupo de permisos, nada más. Sirve para que la pantalla de
  *Roles y permisos* los muestre ordenados y puedas marcar un grupo entero de
  una vez. **Un módulo no decide qué se ve en el menú.**
  *En Django no tiene equivalente: es solo una agrupación visual.*

- **Rol** — un conjunto de permisos que se le asigna a una persona. Vendedor,
  Técnico, Contabilidad. Una persona tiene **un** rol y solo uno.
  *En Django es el `Group`.*

- **Ítem de menú** — una línea del menú lateral. Se muestra si la persona tiene
  **el permiso que esa pantalla exige**.
  *En Vue es lo que en `ventas_pap` armabas a mano en el layout.*

> **La regla de oro:** el menú y las rutas van por **permiso**, nunca por
> módulo. Un módulo se abre con *cualquiera* de sus permisos, así que gatear una
> pantalla por módulo deja entrar a quien apenas comparte uno. Esto ya nos pasó:
> el vendedor tiene `programs.read` para elegir el programa en el expediente, y
> eso le mostraba "Configuración de programas" en el menú.

---

## 2. Mapa de archivos

### Backend

- `backend/app/shared/permissions.py` — **el catálogo**: la lista de permisos,
  los módulos y la matriz inicial de roles. Es el archivo que más vas a tocar.
  *Equivale a tus `Permission` más las fixtures que los sembraban.*
- `backend/app/api/deps.py` — aquí vive `require_permission("codigo")`, la
  dependencia que protege un endpoint.
  *Equivale a `permission_classes` de DRF.*
- `backend/app/modules/users/roles_router.py` — los endpoints `/permissions` y
  `/roles`. *Equivale a `urls.py` + `views.py`.*
- `backend/app/modules/users/service.py` — las reglas de negocio: crear un rol,
  asignarle rol a alguien. *Equivale a tu `services.py`.*
- `backend/app/modules/users/selectors.py` — las consultas de lectura.
  *Equivale a tu `selectors.py`.*
- `backend/alembic/versions/` — las migraciones. *Equivale a `migrations/`.*

### Frontend

- `frontend/src/config/navigation.ts` — **la declaración del menú**. Aquí se
  agrega, se quita y se renombra cada ítem. *Equivale a tu array de rutas del
  layout.*
- `frontend/src/app/router.tsx` — las rutas y su guarda `RequireAccess`.
  *Equivale a `router/index.js` más el `beforeEach`.*
- `frontend/src/components/RequireAccess.tsx` — la guarda: si falta el permiso,
  no monta la pantalla.
- `frontend/src/features/<lo-tuyo>/` — una carpeta por funcionalidad.

Cada carpeta de `features/` tiene siempre lo mismo:

- `api.ts` — las llamadas HTTP. Siempre con `apiClient`, nunca `fetch` directo.
  *Es tu capa de servicios de Axios.*
- `queries.ts` — los hooks de TanStack Query que envuelven `api.ts`.
  *Es lo que hacías con Pinia más el estado de carga, pero lo resuelve la
  librería: no escribes `loading`, `error` ni el `try/catch`.*
- `<Algo>Page.tsx` — la pantalla. *Es tu `.vue`, pero el template y la lógica
  van en el mismo archivo.*
- `components/` — las piezas de esa pantalla.

---

## 3. Receta A — Agregar una pantalla nueva al menú

El caso completo, de punta a punta. Ejemplo: una pantalla de "Zonas".

### A.1 — Declarar el permiso

En `backend/app/shared/permissions.py`, dentro de `PERMISSION_CATALOG`:

```python
("zones.manage", "Crear y editar zonas de trabajo"),
```

### A.2 — Meterlo en un módulo

En el mismo archivo, dentro de `DEFAULT_MODULES`, en el módulo que corresponda:

```python
"config": Module(
    "Configuración de programas",
    [
        "programs.manage",
        "zones.manage",   # <- aquí
        ...
    ],
),
```

**Es obligatorio.** Hay un test
(`test_every_permission_belongs_to_a_module_or_is_explicitly_standalone`) que
falla si un permiso no quedó en ningún módulo. Si de verdad no pertenece a
ninguno —como `profile.manage`, que lo tienen todos— se agrega a
`STANDALONE_PERMISSIONS` en vez de a un módulo.

### A.3 — Dárselo a los roles que lo necesitan

En `DEFAULT_ROLE_PERMISSIONS`, al rol que corresponda. Esto es solo el **valor
inicial**: una vez sembrado, quien manda es lo que el administrador haya dejado
en la pantalla de Roles. Ninguna migración vuelve a pisarlo.

### A.4 — La migración

**Este es el paso que se olvida y te hace perder una hora.**

`PERMISSION_CATALOG` es código, pero la asignación rol↔permiso vive en la tabla
`permissions` de la base. Si agregas el permiso solo en el código:

- sí aparece en el selector de la pantalla de Roles (ese endpoint lee el
  código),
- pero al guardar sale **"Estos permisos no existen: zones.manage"**.

Se crea `backend/alembic/versions/0012_zones_permission.py` —numeración
secuencial, mira cuál es la última— que inserte la fila en `permissions` y, si
quieres que aparezca dentro de un módulo en la pantalla de Roles, también en
`permission_module_items` de cada organización.

Usa `0011_programs_read_out_of_config.py` como plantilla: hace exactamente eso
al revés, borra en vez de insertar.

### A.5 — El endpoint

En el router del módulo:

```python
@router.get("/zones")
async def list_zones(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("zones.manage")),
):
    ...
```

Dos cosas que no se negocian en este repo:

1. **Toda ruta protegida lleva `require_permission`.**
2. **Toda consulta filtra por `organization_id`** del usuario autenticado, nunca
   por un valor que mande el cliente.

*El `Depends(...)` de FastAPI es la inyección de dependencias: se ejecuta antes
del cuerpo de la función y, si lanza, el cuerpo no corre. Es el equivalente de
un decorador de DRF, pero declarado como parámetro.*

### A.6 — La carpeta del frontend

```
frontend/src/features/zones/
  api.ts
  queries.ts
  ZonesPage.tsx
```

Copia el patrón de `features/roles/`, no lo escribas de memoria.

### A.7 — La ruta con su guarda

En `frontend/src/app/router.tsx`:

```tsx
{
  path: "zones",
  element: (
    <RequireAccess permission="zones.manage" moduleLabel="Zonas">
      <ZonesPage />
    </RequireAccess>
  ),
},
```

`RequireAccess` **no monta** los hijos si falta el permiso. Es a propósito: si
solo escondieras la pantalla, los componentes igual se montarían y dispararían
sus consultas, que el backend rechazaría una por una con 403.

Si la pantalla sirve para varios permisos, se pasa un arreglo y se lee como
"alguno de":

```tsx
<RequireAccess permission={["zones.manage", "zones.read"]} moduleLabel="Zonas">
```

### A.8 — El ítem del menú

En `frontend/src/config/navigation.ts`, dentro del grupo que corresponda:

```ts
{ label: "Zonas", to: "/zones", icon: "◈", permission: "zones.manage" },
```

**El permiso tiene que ser el mismo que pusiste en `RequireAccess`.** Si no
coinciden pasa una de dos: el ítem aparece y al entrar rebota, o no aparece pero
la pantalla sí es accesible escribiendo la URL.

Si la pantalla todavía no existe pero quieres que se vea el mapa completo:

```ts
{ label: "Zonas", to: "/zones", icon: "◈", permission: "zones.manage", disabled: true },
```

Sale en gris y no es clickeable. Cuando la construyas, borras `disabled: true`.

### A.9 — Probar

```bash
docker compose exec -T api python -m pytest -q
docker compose exec -T frontend npm run build
```

Y entrar con un rol que **no** tenga el permiso, para confirmar dos cosas: que
no aparece en el menú, y que escribiendo la URL a mano sale "No tienes acceso".

---

## 4. Receta B — Quitar un ítem del menú

Depende de qué quieras, y son tres cosas distintas.

### B.1 — Que un rol deje de verlo (lo normal)

**No se toca código.** Entras a *Roles y permisos*, abres el rol y desmarcas el
permiso. El menú de esa persona cambia en su siguiente ingreso y queda
registrado en auditoría.

Esto es lo que vas a hacer el 95% de las veces.

### B.2 — Que nadie lo vea, pero la pantalla sigue existiendo

Borras el objeto del array en `navigation.ts`. La ruta de `router.tsx` sigue
viva y protegida, así que quien sepa la URL y tenga el permiso entra igual.

### B.3 — Eliminar la pantalla de verdad

En este orden:

1. Borrar el ítem de `navigation.ts`.
2. Borrar la ruta de `router.tsx` y el `import` de la página.
3. Borrar la carpeta `features/<lo-tuyo>/`.
4. Borrar el endpoint del router del backend.
5. Sacar el permiso de `PERMISSION_CATALOG`, de `DEFAULT_MODULES` y de
   `DEFAULT_ROLE_PERMISSIONS`.
6. Migración que borre la fila de `permissions`. El `ON DELETE CASCADE` se
   encarga de `role_permissions` y `permission_module_items`.
7. Borrar sus tests.

Si haces el 4 pero te saltas el 5, ningún test se queja —el permiso sigue en un
módulo— pero queda un permiso que no autoriza nada. Nadie lo nota hasta que
alguien lo marca y se pregunta por qué no hace nada.

---

## 5. Receta C — Cambiar qué permisos tiene un módulo

Un módulo es solo la agrupación de la pantalla de Roles. Cambiarlo **no** cambia
lo que la gente ve en el menú.

- **Desde la aplicación:** los módulos se guardan en `permission_modules` y
  `permission_module_items`, y cada organización tiene su copia editable. El
  administrador puede reagruparlos sin tocar código.
- **Desde el código:** cambiar `DEFAULT_MODULES` afecta solo a organizaciones
  **nuevas**. Para las que ya existen hace falta una migración; mira
  `0011_programs_read_out_of_config.py`.

Un permiso puede estar en varios módulos a la vez y está bien:
`dashboards.finance` está en Facturación y en Reportes. Pero si lo pones en un
módulo donde no pertenece conceptualmente, no rompes el menú —que va por
permiso— pero sí confundes a quien asigna permisos. Fue exactamente el problema
de `programs.read` metido en `config`.

---

## 6. Receta D — Crear un rol nuevo

**Desde la aplicación, sin tocar código.** *Roles y permisos* → "Nuevo rol" →
código, nombre y marcar permisos. Los seis roles del PDF son el punto de
partida, no un límite.

Un rol creado así es de la organización y se puede borrar; los del sistema no.

**Cuidado con la escalada de privilegios:** si le das `users.manage` a un rol
propio, esa persona puede administrar usuarios. **No** puede repartir el rol de
Administrador —eso lo bloquea el backend en `_require_admin_to_grant_admin` y la
opción ni siquiera le aparece en pantalla— pero sí puede mover gente entre los
demás roles.

---

## 7. Receta E — Proteger un endpoint que quedó abierto

```python
current_user: User = Depends(require_permission("invoices.read")),
```

o, si vale con cualquiera de varios:

```python
current_user: User = Depends(require_any_permission("roles.manage", "users.manage")),
```

Y agregar el test de enforcement en `backend/tests/test_rbac_full.py`: un rol
que **no** tenga el permiso debe recibir 403. Sin ese test, el día que alguien
cambie la matriz nadie se entera de que se abrió.

---

## 8. Cómo probar cada cosa

**Backend.** Obligatorio escribir el test **antes** que el código, verlo fallar,
implementar y verlo pasar:

```bash
docker compose exec -T api python -m pytest -q                              # todo
docker compose exec -T api python -m pytest tests/test_permissions_catalog.py -q   # uno solo
docker compose exec -T api python -m pytest -q -k nombre_del_test           # por nombre
```

Los tests usan SQLite en memoria: **no tocan Postgres**.

**Frontend.** No hay runner de tests todavía. El equivalente es:

```bash
docker compose exec -T frontend npm run build   # tsc -b && vite build
```

más entrar al navegador y probar el flujo que tocaste, **incluido el camino de
error**. Para automatizarlo está la skill `browser-automation`.

**Migraciones.** Nunca contra la base real sin permiso explícito:

```bash
docker compose exec -T api alembic current      # en qué versión está
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic downgrade -1 # probar que el downgrade sirve
```

---

## 9. Trampas que ya nos costaron tiempo

**El permiso existe en el código pero no en la base.** Aparece en el selector y
al guardar dice "Estos permisos no existen". Falta la migración del paso A.4.

**El ítem aparece pero al entrar rebota.** El permiso de `navigation.ts` y el de
`RequireAccess` no son el mismo.

**Gatear por módulo en vez de por permiso.** Deja entrar a quien comparte un
solo permiso del grupo. Por eso `RequireAccess` ya no acepta `module`.

**`docker compose restart` no relee el `.env`.** Hay que hacer
`docker compose up -d --force-recreate api`.

**Un panel de edición que conserva los datos de la fila anterior.** Todo panel
que tome su estado inicial de una prop necesita `key={algo.id}`. Sin eso, abrir
otra fila con el panel abierto muestra —y guarda— los datos del anterior. Es una
diferencia con Vue que muerde: React no remonta el componente solo porque le
cambien las props.

**Un test que pasa porque el entorno de prueba no reproduce producción.** Nos
pasó con los roles duplicados al invitar: en los tests no existían las
plantillas del sistema, la consulta no encontraba el duplicado, el test pasaba
y en pantalla salía "Técnico · Técnico".

---

## 10. Dónde está la referencia completa

- `docs/PERMISOS.md` — los 72 permisos, los 15 módulos y qué significa cada uno.
- `docs/menu-por-rol.md` — qué ve cada perfil y qué hace cada pantalla.
- `docs/ERRORES.md` — cómo se manejan los fallos y cómo rastrear uno que te
  reportaron.
- `backend/ARCHITECTURE.md` y `frontend/ARCHITECTURE.md` — las capas y sus
  invariantes. Están congelados: no se editan sin aprobación.
- `docs/guia-drf-a-fastapi.md` — la traducción pieza por pieza desde DRF.
