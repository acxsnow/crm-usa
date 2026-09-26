# Guía: de Django/DRF a FastAPI en crm-usa

Para quien viene de `ventas_pap` (Django + DRF, capas services + selectors,
permisos `has_perm`) y va a construir módulos en este repo. Cada sección
muestra el equivalente **tal como ya está hecho aquí**, con la ruta real.

## 0. Mapa mental rápido

| Django / DRF | FastAPI en este repo | Dónde |
|---|---|---|
| `settings.py` + `django-environ` | `pydantic-settings` `BaseSettings` | `backend/app/core/config.py` |
| `urls.py` raíz + `include()` | `APIRouter` raíz + `include_router()` | `backend/app/api/v1/router.py` |
| `urls.py` por app + `DefaultRouter` | `APIRouter(prefix=..., tags=[...])` por módulo | `app/modules/<m>/router.py` |
| `apps/<app>/` | `app/modules/<modulo>/` | `models.py, schemas.py, service.py, router.py` |
| `models.Model` + `objects` | SQLAlchemy 2 `DeclarativeBase` + `Mapped[...]` | `app/db/base.py`, `app/modules/<m>/models.py` |
| `Serializer` (entrada) | `BaseModel` `XxxCreate` / `XxxUpdate` | `app/modules/<m>/schemas.py` |
| `Serializer` (salida) + `to_representation` | `BaseModel` `XxxResponse` con `from_attributes=True` | `app/modules/<m>/schemas.py` |
| `ViewSet` / `APIView` | Funciones `async def` decoradas con `@router.get/post/...` | `app/modules/<m>/router.py` |
| `services.py` | `service.py` (misma idea: lógica de negocio, sin HTTP) | `app/modules/<m>/service.py` |
| `selectors.py` | Aún no existe como capa; las consultas van inline en router/service. **Para la Cadena A: crear `selectors.py` por módulo** | (nuevo) |
| `permission_classes` / `has_perm("app.codename")` | `Depends(require_permission("modulo.accion"))` | `app/api/deps.py`, catálogo en `app/shared/permissions.py` |
| `request.user` | `current_user: User = Depends(get_current_user)` | `app/api/deps.py` |
| `Group ↔ Permission` (admin) | `Role ↔ Permission` (tablas propias) + `DEFAULT_ROLE_PERMISSIONS` | `app/modules/users/models.py`, `app/shared/permissions.py` |
| `makemigrations` / `migrate` | `alembic revision --autogenerate -m "..."` / `alembic upgrade head` | `backend/alembic/versions/000N_nombre.py` |
| `PageNumberPagination` | `pagination_params` + `paginate()` → header `X-Total-Count` | `app/shared/pagination.py` |
| `django-filter` | `Query(...)` params + `stmt.where(...)` a mano | ej. `crm/router.py::list_applications` |
| `django-simple-history` / signals de auditoría | `record_audit_event()` explícito en el service | `app/shared/audit.py` |
| `ValidationError` / `PermissionDenied` / `Http404` | `HTTPException(status_code=400/403/404, detail=...)` | en `service.py` o `router.py` |
| `transaction.atomic()` | `await db.flush()` dentro; `await db.commit()` una sola vez al final | patrón en `crm/router.py::create_application` |
| `FileField` + `MEDIA_ROOT` | `UploadFile` + `field_ops/storage.py` (sanitiza, valida, guarda) | `app/modules/field_ops/storage.py` |
| Celery (`@shared_task`) | Celery igual (`@celery_app.task`) | `app/workers/celery_app.py`, `tasks.py` |
| `APITestCase` / `APIClient` | `pytest` + `httpx.AsyncClient` + SQLite en memoria | `backend/tests/conftest.py` |
| `manage.py shell` / `seed` command | `python -m scripts.seed` | `backend/scripts/seed.py` |
| Browsable API | Swagger automático | `http://localhost:8000/api/docs` |
| `manage.py runserver` | `uvicorn app.main:app --reload` (lo hace docker compose) | `docker-compose.yml` |

## 1. Settings

Django: una clase gigante en `settings.py` leída con `os.environ`.
Aquí: una clase Pydantic que lee `.env` y valida tipos.

```python
# app/core/config.py (ya existe — solo AGREGA campos)
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "postgresql+asyncpg://crm:crm@localhost:5432/crm"
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    STORAGE_DIR: str = "storage"
    # Cadena A — ejemplo de nuevo setting:
    APPLICATION_MAX_DOCUMENT_MB: int = 15

@lru_cache
def get_settings() -> Settings: ...
```

Uso: `settings = get_settings()` al inicio del módulo. Nunca `os.getenv`
suelto. Un valor sin default = obligatorio (la app no arranca si falta).

## 2. URLs (routers)

Django: `urls.py` por app + `include()` en el raíz.
Aquí: un `APIRouter` por módulo, registrado en `app/api/v1/router.py`.

```python
# app/modules/programs/router.py  (módulo nuevo de la Cadena A)
from fastapi import APIRouter, Depends
router = APIRouter(prefix="/programs", tags=["programs"])

@router.get("", response_model=list[ProgramResponse])
async def list_programs(...): ...

# app/api/v1/router.py  ← equivalente al urls.py raíz
from app.modules.programs.router import router as programs_router
api_router.include_router(programs_router)
```

El prefijo global `/api/v1` lo pone `main.py`. Ruta final:
`GET /api/v1/programs`. Convención del repo: sustantivo plural, sin barra
final, acciones como sub-recurso (`POST /applications/{id}/customer-sign`).

## 3. Modelos

Django ORM → SQLAlchemy 2 con tipado `Mapped[]`. Los mixins ya existen:
`UUIDPKMixin` (pk uuid), `TimestampMixin` (`created_at/updated_at`),
`OrgScopedMixin` (`organization_id`, **obligatorio en toda entidad de negocio**).

```python
# app/modules/programs/models.py
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

class Program(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_program_org_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)   # AZ_EFFICIENCY
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    funder_name: Mapped[str | None] = mapped_column(String(255))

    versions: Mapped[list["FormVersion"]] = relationship(back_populates="program")

class FormVersion(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "form_versions"
    program_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")  # draft|active|archived
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    program: Mapped[Program] = relationship(back_populates="versions")
```

Equivalencias directas:

| Django | SQLAlchemy |
|---|---|
| `CharField(max_length=50)` | `Mapped[str] = mapped_column(String(50))` |
| `null=True` | `Mapped[str \| None]` |
| `TextField` | `Text` |
| `JSONField` | `JSON` |
| `ForeignKey(X, on_delete=CASCADE)` | `ForeignKey("tabla.id", ondelete="CASCADE")` + `relationship()` |
| `related_name` | `back_populates` en ambos lados |
| `unique_together` | `UniqueConstraint(...)` en `__table_args__` |
| `choices=` / `TextChoices` | `class X(str, enum.Enum)` + `String` (ver `crm/models.py::LeadStatus`) |
| `auto_now_add` / `auto_now` | ya en `TimestampMixin` |
| `Meta.ordering` | no existe; el `order_by` va en la consulta |

**Cada modelo nuevo se importa en dos sitios** o Alembic/tests no lo ven:
`alembic/env.py` y `tests/conftest.py` (bloque "Import all model modules").

## 4. Serializadores → Schemas Pydantic

Un serializer de DRF hace 3 cosas; aquí son 3 clases pequeñas:

```python
# app/modules/programs/schemas.py
from pydantic import BaseModel, Field, field_validator

class ProgramCreate(BaseModel):                 # ≈ serializer de entrada (POST)
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=255)
    funder_name: str | None = None

    @field_validator("code")                    # ≈ validate_code(self, value)
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()

class ProgramUpdate(BaseModel):                 # ≈ partial=True (todo opcional)
    name: str | None = None
    active: bool | None = None
    funder_name: str | None = None

class ProgramResponse(BaseModel):               # ≈ serializer de salida
    id: uuid.UUID
    code: str
    name: str
    active: bool
    funder_name: str | None
    created_at: datetime
    model_config = {"from_attributes": True}    # ≈ ModelSerializer: lee atributos del ORM
```

- `validate()` a nivel objeto → `@model_validator(mode="after")`.
- `SerializerMethodField` → `@computed_field` o un campo calculado en el service.
- Nested read → un `Response` que contiene `list[OtroResponse]`.
- Nested write → recibe `list[OtroCreate]` y el **service** crea los hijos.
- Para PATCH usa `payload.model_dump(exclude_unset=True)` (≈ `partial=True`).

## 5. Vistas → endpoints

Un `ViewSet` se convierte en 5 funciones. Cada una declara sus dependencias
en la firma (DB, org, permiso); FastAPI las resuelve (≈ mixins + `permission_classes`).

```python
# app/modules/programs/router.py
@router.post("", response_model=ProgramResponse, status_code=201)
async def create_program(
    payload: ProgramCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("programs.manage")),
):
    program = await programs_service.create_program(db, organization_id=organization_id, actor=current_user, payload=payload)
    await db.commit()
    return program

@router.get("", response_model=list[ProgramResponse])
async def list_programs(
    response: Response,
    active: bool | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("programs.read")),
):
    stmt = programs_selectors.programs_query(organization_id, active=active)
    limit, offset = pagination
    return await paginate(db, stmt, limit=limit, offset=offset, response=response)

@router.patch("/{program_id}", response_model=ProgramResponse)
async def update_program(program_id: uuid.UUID, payload: ProgramUpdate, ...):
    program = await programs_selectors.get_program_or_404(db, organization_id, program_id)
    program = await programs_service.update_program(db, program=program, actor=current_user, payload=payload)
    await db.commit()
    return program
```

Regla del repo: **router delgado**. Parsear entrada, llamar service/selector,
`commit`, devolver. `response_model` filtra la salida (nada se fuga aunque
devuelvas el ORM entero).

Equivalencias:

| DRF | FastAPI |
|---|---|
| `@action(detail=True, methods=["post"])` | `@router.post("/{id}/accion")` |
| `get_queryset()` filtrando por usuario | selector que recibe `organization_id` (y `current_user` si aplica) |
| `get_object()` → 404 | `get_x_or_404()` en selectors |
| `serializer.is_valid(raise_exception=True)` | automático: 422 con detalle por campo |
| `Response(status=201)` | `status_code=201` en el decorador |
| `request.query_params.get("x")` | `x: str \| None = Query(None)` |
| `request.FILES["f"]` | `f: UploadFile = File(...)` + campos `Form(...)` |

## 6. Services

Misma filosofía que `ventas_pap`: lógica de negocio, reglas, transiciones,
auditoría. Sin `Request`, sin `Response`. Recibe `db` y datos ya validados.
Lanza `HTTPException` para errores de negocio (el repo lo hace así; no hay
capa de excepciones propia).

```python
# app/modules/programs/service.py
async def publish_version(db: AsyncSession, *, version: FormVersion, actor: User) -> FormVersion:
    if version.status != "draft":
        raise HTTPException(status_code=400, detail="Solo una versión en borrador puede publicarse.")
    # archivar la activa anterior
    current = await selectors.get_active_version(db, version.organization_id, version.program_id)
    if current:
        current.status = "archived"
    version.status = "active"
    version.published_by_user_id = actor.id
    await db.flush()                                   # ≈ save() dentro de atomic()
    await record_audit_event(db, organization_id=version.organization_id, actor_user_id=actor.id,
                             action="form_version.published", entity_type="FormVersion", entity_id=str(version.id))
    return version
```

Transacciones: **el service hace `flush()`, el router hace `commit()`**. Así
una operación compuesta (crear aplicación + documentos + auditoría) es
atómica: si algo lanza, no hay commit. Es el `transaction.atomic()` implícito.

## 7. Selectors (capa nueva para la Cadena A)

Hoy el repo mete las consultas en el router. Para no repetir el
`select(...).where(organization_id == ...)` veinte veces, crea
`selectors.py` por módulo, exactamente como en `ventas_pap`:

```python
# app/modules/programs/selectors.py
def programs_query(organization_id: uuid.UUID, *, active: bool | None = None) -> Select:
    stmt = select(Program).where(Program.organization_id == organization_id).order_by(Program.name)
    if active is not None:
        stmt = stmt.where(Program.active.is_(active))
    return stmt

async def get_program_or_404(db: AsyncSession, organization_id: uuid.UUID, program_id: uuid.UUID) -> Program:
    program = (await db.execute(
        select(Program).where(Program.id == program_id, Program.organization_id == organization_id)
    )).scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado.")
    return program

async def get_active_version_with_fields(db, organization_id, program_code: str) -> FormVersion | None:
    stmt = (
        select(FormVersion)
        .join(Program)
        .options(selectinload(FormVersion.fields))          # ≈ prefetch_related
        .where(Program.organization_id == organization_id, Program.code == program_code, FormVersion.status == "active")
    )
    return (await db.execute(stmt)).scalar_one_or_none()
```

Cheatsheet ORM:

| Django | SQLAlchemy 2 async |
|---|---|
| `Model.objects.filter(a=1).order_by("-x")` | `select(Model).where(Model.a == 1).order_by(Model.x.desc())` |
| `.get(pk=id)` | `(await db.execute(select(M).where(M.id == id))).scalar_one_or_none()` |
| `.first()` | `.scalars().first()` |
| `.all()` | `.scalars().all()` |
| `.count()` | `select(func.count()).select_from(stmt.subquery())` |
| `.exists()` | `select(exists().where(...))` |
| `select_related("fk")` | `.options(joinedload(M.fk))` |
| `prefetch_related("hijos")` | `.options(selectinload(M.hijos))` |
| `Q(a=1) \| Q(b=2)` | `or_(M.a == 1, M.b == 2)` |
| `field__icontains="x"` | `M.field.ilike("%x%")` |
| `field__in=[...]` | `M.field.in_([...])` |
| `field__isnull=True` | `M.field.is_(None)` |
| `Model.objects.create(**d)` | `obj = Model(**d); db.add(obj); await db.flush()` |
| `obj.save()` | mutar atributos + `await db.flush()` |
| `obj.delete()` | `await db.delete(obj)` |
| `bulk_create` | `db.add_all([...])` |
| `annotate(n=Count(...))` | `select(M, func.count(X.id).label("n")).join(...).group_by(M.id)` |
| `refresh_from_db()` | `await db.refresh(obj)` |

**Regla de oro N+1**: si vas a tocar `obj.relacion` dentro de un bucle, la
consulta debe llevar `selectinload`. En async, acceder a una relación no
cargada **lanza error** (`MissingGreenlet`), no hace una query silenciosa —
eso te obliga a hacerlo bien.

## 8. Funciones auxiliares

| Django (`utils.py`) | Aquí |
|---|---|
| Normalizar email/teléfono/dirección | `app/shared/normalize.py` (ya existe) |
| Fechas UTC seguras | `app/shared/datetime_utils.as_utc()` |
| Paginación | `app/shared/pagination.py` |
| Auditoría | `app/shared/audit.py::record_audit_event` |
| Hash / tokens / JWT | `app/core/security.py` |
| Rate limit | `app/core/rate_limit.py` |
| Archivos (guardar/leer con sanitización) | `app/modules/field_ops/storage.py` |
| Marca de agua GPS+fecha | `app/modules/field_ops/watermark.py` |
| PDF | `app/modules/field_ops/pdf.py` (ReportLab) |

Lo transversal va a `app/shared/`; lo de un módulo, dentro del módulo
(`app/modules/<m>/utils.py` si hace falta).

## 9. Permisos

Django: `Permission` por modelo + `Group` desde el admin + `has_perm`.
Aquí: catálogo en código + matriz rol→permiso en código + tablas
`roles/permissions/user_roles` sembradas por `scripts/seed.py`.

Para un módulo nuevo:

1. Agregar códigos a `PERMISSION_CATALOG` en `app/shared/permissions.py`:
   `("programs.manage", "Manage program catalog")`, `("programs.read", ...)`.
2. Asignarlos a roles en `DEFAULT_ROLE_PERMISSIONS`.
3. Usar `Depends(require_permission("programs.manage"))` en cada endpoint.
   Si dos permisos dan acceso al mismo endpoint (ancho/estrecho):
   `require_any_permission("projects.read_all", "projects.read_assigned")` y
   el selector estrecha resultados.
4. **Obligatorio**: un test en `tests/test_rbac_full.py` que pruebe 403 sin el
   permiso y 2xx con él.

`organization_id` **siempre** sale de `Depends(get_organization_id)`, jamás
del body ni de la URL.

## 10. Migraciones

```bash
# dentro del contenedor api (o con DATABASE_URL apuntando a un Postgres local)
docker compose exec api alembic revision --autogenerate -m "programs catalog"   # ≈ makemigrations
docker compose exec api alembic upgrade head                                     # ≈ migrate
docker compose exec api alembic downgrade -1                                     # ≈ migrate app 000N-1
docker compose exec api alembic current                                          # ≈ showmigrations
```

Después del autogenerate:

- Renombra el archivo a `000N_nombre.py` y fija `revision = "000N"`,
  `down_revision = "000N-1"` (convención del repo, ver `0008_user_presence.py`).
- Revisa el `upgrade()`: autogenerate no detecta renombres (los ve como
  drop + add) ni cambios en `server_default` con seguridad.
- Escribe `downgrade()` real.
- Cada nueva columna NOT NULL sobre tabla con datos necesita `server_default`.

Migraciones de datos (≈ `RunPython`): `op.execute(...)` o
`op.get_bind()` + SQL. Los seeds de catálogo (permisos, roles, programas
iniciales) van en `scripts/seed.py`, no en migraciones.

## 11. Archivos (uploads)

```python
@router.post("/applications/{application_id}/documents", response_model=ApplicationDocumentResponse, status_code=201)
async def upload_document(
    application_id: uuid.UUID,
    field_key: str = Form(...),
    file: UploadFile = File(...),
    ...
):
    validate_upload(file, allowed=DOCUMENT_MIME_TYPES, max_mb=settings.APPLICATION_MAX_DOCUMENT_MB)
    rel_path = await storage.save(organization_id, "applications", application_id, file)   # sanitiza + contención
    ...
```

Se guarda **la ruta relativa** al `STORAGE_DIR` (nunca absoluta) para que
el cambio a S3 futuro no toque modelos. Descargas: endpoint que valida
permiso y devuelve `FileResponse` — nunca exponer `storage/` como estático.

## 12. Tareas Celery

Igual que Django. `app/workers/tasks.py`:

```python
@celery_app.task(name="applications.process_document")
def process_document_task(document_id: str) -> None:
    asyncio.run(_process(uuid.UUID(document_id)))   # las tareas son sync; abren su propia sesión
```

Encolar: `process_document_task.delay(str(doc.id))` **después** del commit.
Periódicas: `celery_app.conf.beat_schedule` en `celery_app.py`.

## 13. Tests

```python
# tests/test_programs.py
async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

async def test_create_program_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, active_technician_user.email)   # rol sin programs.manage
    r = await app_client.post("/api/v1/programs", json={"code": "AZ_EFFICIENCY", "name": "Arizona"}, headers=headers)
    assert r.status_code == 403

async def test_create_program(app_client, active_admin_user):
    headers = await _login(app_client, active_admin_user.email)
    r = await app_client.post("/api/v1/programs", json={"code": "az_efficiency", "name": "Arizona"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["code"] == "AZ_EFFICIENCY"
```

Fixtures ya disponibles en `conftest.py`: `db`, `app_client`, `seeded_org`
(org + catálogo de permisos + roles por defecto) y un usuario activo por rol:
`active_admin_user`, `active_technician_user`, `active_commercial_manager_user`,
`active_project_manager_user`, `active_supervisor_user`, `active_finance_user`,
`active_read_only_user` (todos con clave `SuperSecret123`). El login es por
HTTP como arriba (`tests/test_rbac_full.py` tiene el mismo helper). Todo corre
en SQLite en memoria; **no toca Postgres**. Ejecutar: `cd backend && pytest -q`.

Cuidado con SQLite: no soporta `JSONB` ni algunas funciones de Postgres; usa
`JSON` genérico y evita SQL específico de Postgres en el código de negocio.

## 14. Checklist para un módulo nuevo de la Cadena A

1. `app/modules/<m>/models.py` → importar en `alembic/env.py` y `tests/conftest.py`.
2. `alembic revision --autogenerate` → renombrar, revisar, `downgrade()`.
3. `schemas.py`: `Create` / `Update` / `Response`.
4. Códigos de permiso en `app/shared/permissions.py` + roles.
5. `selectors.py` (consultas) y `service.py` (reglas + auditoría + `flush`).
6. `router.py` delgado + `include_router` en `app/api/v1/router.py`.
7. Tests: negocio + un 403/2xx por cada permiso nuevo.
8. `pytest -q` limpio y Swagger revisado en `/api/docs` (ese es el contrato para Mateo).
