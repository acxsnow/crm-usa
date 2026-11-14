"""Catálogo real del cliente para cualquier organización, también en producción
(14 nov 2026).

El catálogo de AC Pro y la lista «Instalación 3 ton desde cero» salen de los
PDF del cliente (`docs/bodega/`). Hasta ahora solo los cargaba `seed_qa.py`,
que es de desarrollo (también crea técnicos ficticios y existencias de prueba),
así que producción nunca los tuvo.

Corre en el seed del arranque y es seguro repetirlo:
- Solo crea los artículos cuyo SKU no existe; lo que ya está no se toca, para no
  pisar lo que el cliente edite en producción (precio, nombre, mínimo).
- No carga existencias: el inventario real entra con un conteo en Bodega.
- La lista se crea una vez, si no existe una con ese nombre.
"""
import csv
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

DATOS = Path(__file__).resolve().parents[3] / "scripts" / "qa_data"
LISTA = "Instalación 3 ton desde cero"


def _filas() -> list[dict]:
    with open(DATOS / "catalogo_ac_pro.csv", encoding="utf-8") as f:
        return [{"name": r["nombre"], "sku": r["sku"], "manufacturer_part": r["fabricante"] or None,
                 "brand": r["marca"] or None, "category": r["categoria"], "unit": r["unidad"],
                 "unit_cost": Decimal(r["costo"]), "supplier_name": "AC Pro", "quantity": Decimal("0"),
                 "min_quantity": None, "notes": "Catálogo de AC Pro (docs/bodega)",
                 "has_serial": r["con_serial"] == "si"} for r in csv.DictReader(f, delimiter=";")]


async def apply(db: AsyncSession, *, organization_id, user) -> dict:
    """Crea lo que falte del catálogo y la lista. Devuelve cuántos artículos creó."""
    from app.modules.warehouse import kits
    from app.modules.warehouse.models import WarehouseItem, WarehouseKitTemplate
    from app.modules.warehouse.service import import_catalog

    existentes = set((await db.execute(select(WarehouseItem.sku).where(
        WarehouseItem.organization_id == organization_id, WarehouseItem.sku.is_not(None)))).scalars())
    nuevas = [f for f in _filas() if f["sku"] not in existentes]
    if nuevas:
        await import_catalog(db, organization_id=organization_id, user=user, rows=nuevas,
                             filename="catalogo_ac_pro.csv")
        await db.commit()
    lista_creada = False
    if not (await db.execute(select(WarehouseKitTemplate.id).where(
            WarehouseKitTemplate.organization_id == organization_id, WarehouseKitTemplate.name == LISTA))).first():
        por_sku = {i.sku: i.id for i in (await db.execute(select(WarehouseItem).where(
            WarehouseItem.organization_id == organization_id))).scalars()}
        with open(DATOS / "kit_3ton.csv", encoding="utf-8") as f:
            renglones = [{"item_id": por_sku[r["sku"]], "quantity": r["cantidad"], "section": r["seccion"],
                          "is_required": r["obligatorio"] == "si"}
                         for r in csv.DictReader(f, delimiter=";") if r["sku"] in por_sku]
        if renglones:
            await kits.save_kit(db, organization_id=organization_id, user=user, data={
                "name": LISTA, "project_type": "hvac_install", "items": renglones,
                "description": "Kit de AC Pro «3 TON HOME MATERIALS FROM SCRATCH» (docs/bodega/partes.pdf)."})
            lista_creada = True
    return {"items_created": len(nuevas), "kit_created": lista_creada}
