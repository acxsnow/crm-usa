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

    transport = ASGITransport(app=app)
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


@pytest_asyncio.fixture
async def active_commercial_manager_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="commercial_manager", email="commercial@acme-demo.com", full_name="Cara Commercial"
    )


@pytest_asyncio.fixture
async def active_project_manager_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="project_manager", email="pm@acme-demo.com", full_name="Pat Manager"
    )


@pytest_asyncio.fixture
async def active_supervisor_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="supervisor", email="supervisor@acme-demo.com", full_name="Sam Supervisor"
    )


@pytest_asyncio.fixture
async def active_finance_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="finance_user", email="finance@acme-demo.com", full_name="Fiona Finance"
    )


@pytest_asyncio.fixture
async def active_read_only_user(db: AsyncSession, seeded_org):
    return await _make_role_user(
        db, seeded_org, role_code="read_only", email="readonly@acme-demo.com", full_name="Rae Readonly"
    )
