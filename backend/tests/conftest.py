import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.rate_limit import clear_all_buckets
from app.core.token_denylist import clear_denylist
from app.core.security import hash_password
from app.db.base import Base
from app.db import session as db_session_module
from app.modules.crm.defaults import DEFAULT_FUNDER_STATUSES, DEFAULT_PIPELINE_STAGES
from app.modules.organizations.models import Organization, PlanLimit
from app.modules.users.models import Permission, Role, User, UserRole, UserStatus
from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG, ROLE_LABELS

# Import all model modules so tables register on Base.metadata.
from app.shared import audit_models  # noqa: F401
from app.modules.crm import models as crm_models  # noqa: F401
from app.modules.field_ops import models as field_ops_models  # noqa: F401
from app.modules.billing import models as billing_models  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def _isolate_storage_dir(tmp_path, monkeypatch):
    """Evidence/attestation files go under a per-test tmp dir instead of the
    repo's backend/storage/ folder."""
    from app.modules.field_ops import storage as storage_module

    monkeypatch.setattr(storage_module.settings, "STORAGE_DIR", str(tmp_path / "storage"))
    yield


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    """Tests must never reach the real Redis or SMTP server. When the suite runs
    inside the `api` container both are reachable (docker-compose wires them
    up and backend/.env may set EMAIL_PROVIDER=smtp), which leaks rate-limit
    counters between tests/runs and tries to send real email. Force the
    in-process fallbacks the code already has for the no-Redis / console case."""
    from app.core import rate_limit as rate_limit_module
    from app.core import token_denylist as token_denylist_module
    from app.modules.notifications import email as email_module

    async def _no_redis():
        return None

    monkeypatch.setattr(rate_limit_module, "get_redis_if_available", _no_redis)
    monkeypatch.setattr(token_denylist_module, "get_redis_if_available", _no_redis)
    monkeypatch.setattr(email_module.settings, "EMAIL_PROVIDER", "console")
    yield


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_sessionmaker(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db(db_sessionmaker):
    async with db_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def app_client(db_sessionmaker, monkeypatch):
    from app.main import app

    async def _get_db_override():
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[db_session_module.get_db] = _get_db_override
    clear_all_buckets()
    clear_denylist()

    # `raise_app_exceptions=False` hace que el cliente de pruebas reciba la
    # misma respuesta 500 que recibiría un navegador, en vez de re-lanzar la
    # excepción dentro del test. Sin esto no se puede comprobar qué ve el
    # usuario cuando algo falla de forma inesperada.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_org(db: AsyncSession):
    """Creates an organization with the full default permission/role catalog, per spec 5.2/5.3."""
    org = Organization(name="Acme Field Services")
    db.add(org)
    await db.flush()

    db.add(PlanLimit(organization_id=org.id, max_active_users=30))

    perm_objs: dict[str, Permission] = {}
    for code, description in PERMISSION_CATALOG:
        perm = Permission(code=code, description=description)
        db.add(perm)
        perm_objs[code] = perm
    await db.flush()

    role_objs: dict[str, Role] = {}
    for role_code, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role(
            organization_id=org.id,
            code=role_code,
            name=ROLE_LABELS.get(role_code, role_code),
            is_system=True,
        )
        role.permissions = [perm_objs[c] for c in perm_codes]
        db.add(role)
        role_objs[role_code] = role
    await db.flush()

    # Módulos de permisos: copia de la organización, igual que en el seed real.
    from scripts.seed import build_permission_modules

    for module in build_permission_modules(org.id, perm_objs):
        db.add(module)
    await db.flush()

    from app.modules.crm.models import FunderStatus, PipelineStage

    stage_objs: dict[str, PipelineStage] = {}
    for stage_data in DEFAULT_PIPELINE_STAGES:
        stage = PipelineStage(organization_id=org.id, **stage_data)
        db.add(stage)
        stage_objs[stage_data["code"]] = stage

    funder_status_objs: dict[str, FunderStatus] = {}
    for status_data in DEFAULT_FUNDER_STATUSES:
        funder_status = FunderStatus(organization_id=org.id, **status_data)
        db.add(funder_status)
        funder_status_objs[status_data["code"]] = funder_status
    await db.flush()
    await db.commit()

    return {
        "org": org, "roles": role_objs, "permissions": perm_objs,
        "stages": stage_objs, "funder_statuses": funder_status_objs,
    }


@pytest_asyncio.fixture
async def second_org(db: AsyncSession, seeded_org):
    """Segunda organización con sus propios roles y módulos, para probar que
    editar la configuración de una no afecta a la otra."""
    from scripts.seed import build_permission_modules

    org = Organization(name="Beta Field Services")
    db.add(org)
    await db.flush()
    db.add(PlanLimit(organization_id=org.id, max_active_users=30))

    perm_objs = seeded_org["permissions"]
    role_objs: dict[str, Role] = {}
    for role_code, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role(
            organization_id=org.id,
            code=role_code,
            name=ROLE_LABELS.get(role_code, role_code),
            is_system=True,
        )
        role.permissions = [perm_objs[c] for c in perm_codes]
        db.add(role)
        role_objs[role_code] = role
    await db.flush()

    for module in build_permission_modules(org.id, perm_objs):
        db.add(module)
    await db.commit()
    return {"org": org, "roles": role_objs, "permissions": perm_objs}


@pytest_asyncio.fixture
async def active_admin_user(db: AsyncSession, seeded_org):
    org = seeded_org["org"]
    role = seeded_org["roles"]["organization_admin"]
    user = User(
        organization_id=org.id,
        email="admin@acme-demo.com",
        email_display="admin@acme-demo.com",
        full_name="Ada Admin",
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_technician_user(db: AsyncSession, seeded_org):
    org = seeded_org["org"]
    role = seeded_org["roles"]["field_technician"]
    user = User(
        organization_id=org.id,
        email="tech@acme-demo.com",
        email_display="tech@acme-demo.com",
        full_name="Tom Technician",
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()
    await db.refresh(user)
    return user


async def _make_role_user(db: AsyncSession, seeded_org, *, role_code: str, email: str, full_name: str) -> User:
    org = seeded_org["org"]
    role = seeded_org["roles"][role_code]
    user = User(
        organization_id=org.id,
        email=email,
        email_display=email,
        full_name=full_name,
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()
    await db.refresh(user)
    return user


# Un usuario activo por cada rol del PDF (decisión D1). `active_admin_user` y
# `active_technician_user` están arriba.


@pytest_asyncio.fixture
async def active_salesperson_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="salesperson", email="vendedor@acme-demo.com", full_name="Vic Vendedor"
    )


@pytest_asyncio.fixture
async def active_admin_staff_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="admin_staff", email="admin-staff@acme-demo.com", full_name="Ana Administración"
    )


@pytest_asyncio.fixture
async def active_accounting_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="accounting", email="contabilidad@acme-demo.com", full_name="Coni Contabilidad"
    )


@pytest_asyncio.fixture
async def active_management_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="management", email="gerencia@acme-demo.com", full_name="Gabo Gerencia"
    )


@pytest_asyncio.fixture
async def active_roleless_user(db: AsyncSession, seeded_org):
    """Usuario con un rol de la organización sin ningún permiso: es el estado
    real justo después de que el administrador crea un rol y todavía no le
    marca nada. Sirve para comprobar que ninguna ruta se abre por descuido."""
    org = seeded_org["org"]
    empty_role = Role(
        organization_id=org.id,
        code="sin_permisos",
        name="Sin permisos",
        is_system=False,
    )
    empty_role.permissions = []
    db.add(empty_role)
    await db.flush()

    user = User(
        organization_id=org.id,
        email="sinpermisos@acme-demo.com",
        email_display="sinpermisos@acme-demo.com",
        full_name="Sin Permisos",
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=empty_role.id))
    await db.commit()
    await db.refresh(user)
    return user
