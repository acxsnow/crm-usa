# Arquitectura — Backend (FastAPI + SQLAlchemy 2 async)

> 🔒 **Documento canónico — CONGELADO.** Junto con `frontend/ARCHITECTURE.md`
> y la cadena de verdad de `.claude/CLAUDE.md`, es **fuente de verdad**. No se
> modifica automáticamente; solo cambia con **aprobación explícita** del
> responsable (José Javier).

Backend del proyecto **crm-usa** (Delta HVAC). Expone una API REST versionada
(`/api/v1`) que el frontend React consume como único cliente. Arquitectura por
capas estilo **services + selectors** (heredada de `ventas_pap`): los routers
son delgados y toda la lógica vive en capas dedicadas y testeables.
Multi-tenant por `organization_id`, RBAC por códigos de permiso, auditoría
append-only.

Para quien viene de Django/DRF: `docs/guia-drf-a-fastapi.md` mapea cada pieza.

---

## Estructura de carpetas (estado real)

```
backend/
├── app/
│   ├── main.py                    # FastAPI(), CORS, security headers, static de storage, include api_router
│   ├── api/
│   │   ├── deps.py                # get_current_user, require_permission, require_any_permission, get_organization_id
│   │   └── v1/router.py           # ÚNICO punto de agregación de routers de módulos
│   ├── core/                      # infraestructura sin negocio
│   │   ├── config.py              #   Settings (pydantic-settings, .env)
│   │   ├── security.py            #   Argon2, JWT, tokens seguros
│   │   ├── rate_limit.py · token_denylist.py · redis_client.py · logging.py
│   ├── db/
│   │   ├── base.py                #   Base + mixins UUIDPKMixin / TimestampMixin / OrgScopedMixin
│   │   ├── session.py             #   engine async + get_db()
│   │   └── types.py               #   GUID portable (Postgres uuid / SQLite char)
│   ├── shared/                    # utilidades transversales de negocio
│   │   ├── permissions.py         #   PERMISSION_CATALOG + DEFAULT_ROLE_PERMISSIONS (matriz rol→permiso)
│   │   ├── audit.py · audit_models.py   # record_audit_event() append-only
│   │   ├── pagination.py          #   pagination_params + paginate() → X-Total-Count
│   │   ├── normalize.py           #   email/teléfono/dirección normalizados (duplicados)
│   │   └── datetime_utils.py      #   as_utc()
│   ├── modules/                   # un paquete por dominio
│   │   ├── auth/  users/  organizations/  crm/  field_ops/  billing/  notifications/
│   │   └── <modulo>/{models,schemas,service,router}.py  (+ selectors.py en lo nuevo)
│   └── workers/                   # Celery: celery_app.py (beat_schedule) + tasks.py
├── alembic/                       # env.py importa TODOS los models; versions/000N_nombre.py
├── scripts/seed.py                # catálogo de permisos + roles por defecto (+ --demo-org)
├── storage/                       # archivos subidos (local; S3 diferido). Ignorado por git
├── tests/                         # pytest + httpx + SQLite en memoria; conftest.py con fixtures por rol
├── pytest.ini · requirements.txt · Dockerfile · Dockerfile.render
```

---

## Capas y responsabilidades

| Capa | Archivo | Responsabilidad | NO hace |
|------|---------|-----------------|---------|
| **Models** | `models.py` | Persistencia e invariantes (constraints, enums, relaciones) | Lógica de aplicación |
| **Schemas** | `schemas.py` | Validación de entrada (`XxxCreate/Update`) y forma de salida (`XxxResponse`) | Reglas de negocio, acceso a BD |
| **Selectors** | `selectors.py` | **Lectura**: `select()` con scope de organización, filtros, `selectinload`, `get_x_or_404` | Escritura |
| **Service** | `service.py` | **Escritura** y reglas de negocio; transiciones de estado; auditoría; `flush()` | HTTP (`Request`/`Response`) |
| **Router** | `router.py` | Capa HTTP delgada: deps (db, org, permiso) → selector/service → `commit()` → respuesta | Queries ni lógica |
| **Deps** | `api/deps.py` | Autenticación, autorización, contexto de organización | Negocio |

Regla de oro: **un endpoint no contiene lógica de negocio ni queries
complejas**. Delega en `service` (escritura) y `selectors` (lectura).

> Los módulos existentes (fases 1–5) tienen las consultas inline en `router.py`
> y no tienen `selectors.py`. **No se refactorizan de paso.** Todo módulo
> nuevo (Cadena A) nace con las cinco capas.

---

## Invariantes que no se negocian

1. **Multi-tenant**: toda entidad de negocio usa `OrgScopedMixin`; toda query
   filtra por `organization_id` obtenido de `Depends(get_organization_id)`
   (nunca del body, query ni path).
2. **RBAC en servidor**: todo endpoint protegido lleva
   `Depends(require_permission("<modulo>.<accion>"))`. Los códigos se declaran
   en `app/shared/permissions.py` y se asignan a roles en
   `DEFAULT_ROLE_PERMISSIONS`. **Cada código nuevo exige un test 403 + 2xx** en
   `tests/test_rbac_full.py`.
3. **Auditoría**: crear / cambiar estado / revisar / aprobar / devolver /
   someter / firmar / borrar → `record_audit_event()` desde el service.
4. **Transacción**: el service hace `await db.flush()`; el router hace **un**
   `await db.commit()` al final. Si algo lanza antes, no hay commit.
5. **Paginación**: todo listado que pueda crecer usa `pagination_params` +
   `paginate()` (default 100, máx 500, total en `X-Total-Count`).
6. **Archivos**: solo a través de `app/modules/field_ops/storage.py`
   (sanitiza nombre, valida MIME y tamaño, contiene la ruta). Se persiste la
   ruta **relativa** a `STORAGE_DIR`. Descarga por endpoint con permiso, nunca
   como estático público.
7. **Errores**: los services y selectors lanzan **excepciones de dominio**
   (`app/shared/errors.py`: `NotFoundError`, `ConflictError`,
   `InvalidInputError`, `ForbiddenError`, `AuthenticationError`) con mensaje
   en español para el usuario y un `code` estable. `app/shared/error_handlers.py`
   es el único sitio que traduce eso a HTTP, normaliza los 422 de Pydantic,
   convierte `IntegrityError` en 409 y atrapa cualquier fallo no previsto como
   500 neutro con traza en el log. Toda respuesta de error lleva `request_id`.
   `HTTPException` sigue funcionando con el mismo formato (la Cadena B todavía
   lo usa). Detalle en `docs/ERRORES.md`.
8. **Nada de secretos en código**: todo por `Settings`; la app se niega a
   arrancar fuera de `development` con `JWT_SECRET_KEY` por defecto.
9. **Fechas**: siempre `DateTime(timezone=True)` y `datetime.now(timezone.utc)`;
   comparar con `as_utc()`.

---

## Modelos base (`app/db/base.py`)

| Mixin | Aporta |
|-------|--------|
| `UUIDPKMixin` | `id: uuid` (pk, `default=uuid4`) |
| `TimestampMixin` | `created_at`, `updated_at` (server-side) |
| `OrgScopedMixin` | `organization_id` indexado, `nullable=False` |

No hay soft-delete ni `created_by/updated_by` genéricos como en `ventas_pap`:
el actor queda en `audit_events` (`actor_user_id`). Si un modelo necesita
autoría explícita (p. ej. `published_by_user_id`), se declara como columna.

---

## Plantilla de un módulo de dominio

```
app/modules/<modulo>/
├── __init__.py
├── models.py          # SQLAlchemy; enums como class X(str, enum.Enum)
├── schemas.py         # XxxCreate / XxxUpdate / XxxResponse(from_attributes=True)
├── selectors.py       # lecturas: xxx_query(org_id, **filters) -> Select ; get_xxx_or_404()
├── service.py         # escritura: create_xxx(db, *, organization_id, actor, payload) ; transiciones
├── router.py          # APIRouter(prefix="/xxx", tags=["xxx"])
└── defaults.py        # (opcional) datos semilla del módulo
tests/test_<modulo>.py # negocio + permisos
```

Pasos para añadir un módulo:

1. `models.py` → importar el módulo en `alembic/env.py` **y** en `tests/conftest.py`.
2. `docker compose exec api alembic revision --autogenerate -m "..."` → renombrar a
   `000N_nombre.py`, fijar `revision`/`down_revision`, revisar `upgrade()`, escribir `downgrade()`.
3. `schemas.py`, `selectors.py`, `service.py`, `router.py`.
4. Códigos de permiso en `app/shared/permissions.py` + asignación a roles.
5. `include_router` en `app/api/v1/router.py`.
6. Tests: comportamiento + un 403/2xx por permiso nuevo.
7. Tipos en `frontend/src/types/<modulo>.ts` espejando `XxxResponse`.

---

## Convenciones

- **Rutas**: sustantivo plural, sin barra final, acciones como sub-recurso
  (`POST /applications/{id}/submit`). Prefijo `/api/v1` lo pone `main.py`.
- **Naming**: `snake_case` en Python y en JSON (el frontend usa las mismas
  claves; no hay camelCase de por medio).
- **Estados**: enums en `models.py`; transiciones válidas como dict en el
  service (`ALLOWED_TRANSITIONS = {"draft": {"pending_review"}, ...}`) y una
  única función `transition(obj, to, actor)` que valida, aplica y audita.
- **JSON dinámico** (respuestas del formulario, opciones, reglas): columna `JSON`
  genérica (SQLite en tests no soporta `JSONB`).
- **Async**: acceder a una relación no cargada lanza `MissingGreenlet` — usar
  `selectinload`/`joinedload` en el selector. Es a propósito: obliga a evitar N+1.
- **Celery**: tareas síncronas que abren su propia sesión; se encolan
  **después** del `commit`.
- **Tests**: `pytest -q` corre todo en SQLite en memoria (no toca Postgres).
  Fixtures por rol en `conftest.py` (`active_admin_user`, `active_technician_user`, …).

---

## Puesta en marcha y verificación

```bash
docker compose up --build
docker compose exec api python -m scripts.seed --demo-org     # una vez, BD local vacía
docker compose exec api pytest -q                              # o: cd backend && pytest -q
docker compose exec api alembic current                        # estado de migraciones
# Swagger: http://localhost:8000/api/docs  ← ese es el contrato que se entrega a Cadena B
```
