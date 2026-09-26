"""Los módulos (grupos de permisos) viven en base de datos y son editables.

Decisión D9: el código define los valores iniciales (`DEFAULT_MODULES`) y el
seed crea una plantilla del sistema más una copia por organización, igual que
los roles. A partir de ahí el administrador los edita desde la pantalla."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Permission, PermissionModule, PermissionModuleItem
from app.shared.permissions import DEFAULT_MODULES, modules_for_permissions
from app.modules.users.selectors import modules_for_organization


async def test_seeded_org_has_a_copy_of_every_system_module(db: AsyncSession, seeded_org):
    org = seeded_org["org"]
    result = await db.execute(
        select(PermissionModule).where(PermissionModule.organization_id == org.id)
    )
    modules = {m.key: m for m in result.scalars().all()}
    assert set(modules) == set(DEFAULT_MODULES)
    assert all(m.is_system for m in modules.values())
    assert modules["billing"].label == "Facturación y cobros"


async def test_module_items_reproduce_the_code_defaults(db: AsyncSession, seeded_org):
    org = seeded_org["org"]
    modules = await modules_for_organization(db, org.id)
    for key, default in DEFAULT_MODULES.items():
        assert set(modules[key].permissions) == set(default.permissions), key


async def test_a_permission_can_belong_to_several_modules_in_the_database(
    db: AsyncSession, seeded_org
):
    org = seeded_org["org"]
    modules = await modules_for_organization(db, org.id)
    assert "dashboards.finance" in modules["billing"].permissions
    assert "dashboards.finance" in modules["reports"].permissions


async def test_modules_for_permissions_uses_the_database_copy(db: AsyncSession, seeded_org):
    """Si el administrador saca un permiso de un módulo, ese módulo deja de
    encenderse para quien solo tenía ese permiso."""
    org = seeded_org["org"]
    modules = await modules_for_organization(db, org.id)
    assert modules_for_permissions(["dashboards.finance"], modules) == {"billing", "reports"}

    billing = (
        await db.execute(
            select(PermissionModule).where(
                PermissionModule.organization_id == org.id,
                PermissionModule.key == "billing",
            )
        )
    ).scalar_one()
    finance = (
        await db.execute(select(Permission).where(Permission.code == "dashboards.finance"))
    ).scalar_one()
    item = (
        await db.execute(
            select(PermissionModuleItem).where(
                PermissionModuleItem.module_id == billing.id,
                PermissionModuleItem.permission_id == finance.id,
            )
        )
    ).scalar_one()
    await db.delete(item)
    await db.commit()

    modules = await modules_for_organization(db, org.id)
    assert modules_for_permissions(["dashboards.finance"], modules) == {"reports"}


async def test_modules_are_scoped_per_organization(db: AsyncSession, seeded_org, second_org):
    """Editar los módulos de una organización no afecta a la otra."""
    modules_a = await modules_for_organization(db, seeded_org["org"].id)
    modules_b = await modules_for_organization(db, second_org["org"].id)
    assert set(modules_a) == set(modules_b) == set(DEFAULT_MODULES)

    billing_a = (
        await db.execute(
            select(PermissionModule).where(
                PermissionModule.organization_id == seeded_org["org"].id,
                PermissionModule.key == "billing",
            )
        )
    ).scalar_one()
    billing_a.label = "Cobranza"
    await db.commit()

    modules_b = await modules_for_organization(db, second_org["org"].id)
    assert modules_b["billing"].label == "Facturación y cobros"
