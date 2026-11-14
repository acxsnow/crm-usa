"""Catálogo de AC Pro del cliente en cualquier organización (14 nov 2026)."""
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.warehouse import client_catalog
from app.modules.warehouse.models import WarehouseItem, WarehouseKitTemplate, WarehouseStock


async def test_loads_the_catalog_and_kit_without_stock_and_never_overwrites(db, seeded_org, active_admin_user):
    org = seeded_org["org"].id
    r = await client_catalog.apply(db, organization_id=org, user=active_admin_user)
    filas = len(client_catalog._filas())
    assert (r["items_created"], r["kit_created"]) == (filas, True)
    assert (await db.execute(select(func.count()).select_from(WarehouseKitTemplate).where(
        WarehouseKitTemplate.organization_id == org, WarehouseKitTemplate.name == client_catalog.LISTA))).scalar() == 1
    # Sin existencias inventadas: el inventario real entra con un conteo.
    total = (await db.execute(select(func.coalesce(func.sum(WarehouseStock.quantity), 0)).where(
        WarehouseStock.organization_id == org))).scalar()
    assert Decimal(str(total)) == 0

    # Lo que el cliente edite en producción no se pisa al volver a correr.
    item = (await db.execute(select(WarehouseItem).where(WarehouseItem.organization_id == org)
                             .order_by(WarehouseItem.sku).limit(1))).scalar_one()
    item.unit_cost = Decimal("1.23")
    await db.commit()
    r = await client_catalog.apply(db, organization_id=org, user=active_admin_user)
    assert r == {"items_created": 0, "kit_created": False}
    await db.refresh(item)
    assert item.unit_cost == Decimal("1.23")
