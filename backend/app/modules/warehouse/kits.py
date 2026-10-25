"""Listas predefinidas por tipo de trabajo (punto 2 del cuestionario).

Aires y pedestales llevan siempre lo mismo, con cantidades y calibres que cambian
un poco de un trabajo a otro. La lista guarda lo que siempre va; al armar una
orden de salida se **copia** lo que la lista tiene y de ahí en adelante se ajusta
la copia: cantidades, calibres y los extras que pida el trabajo.

Que sea copia y no una referencia es lo que hace que corregir la plantilla en
enero no cambie la orden que se pidió en diciembre.
"""
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.warehouse import releases as rel
from app.modules.warehouse import service as wh
from app.modules.warehouse.catalogs import ITEM_UNITS, LineOrigin
from app.modules.warehouse.models import (
    WarehouseItem,
    WarehouseKitItem,
    WarehouseKitTemplate,
    WarehouseReleaseLine,
)
from app.shared.decimals import to_quantity
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError
from app.shared.text_search import LIKE_ESCAPE, contains_pattern

Q2 = Decimal("0.01")


def _q(value) -> Decimal:
    return to_quantity(value)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

async def get_kit(db: AsyncSession, organization_id, kit_id) -> WarehouseKitTemplate:
    kit = await db.get(WarehouseKitTemplate, kit_id)
    if kit is None or kit.organization_id != organization_id:
        raise NotFoundError("La lista predefinida no existe.", code="warehouse_kit_not_found")
    return kit


async def kit_items_of(db: AsyncSession, organization_id, kit_ids) -> dict:
    """Renglones de varias listas, agrupados. Se leen aparte porque la relación
    está en `lazy="raise"`."""
    ids = list(kit_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(WarehouseKitItem).where(
        WarehouseKitItem.organization_id == organization_id,
        WarehouseKitItem.template_id.in_(ids),
    ).order_by(WarehouseKitItem.sort_order, WarehouseKitItem.created_at))).scalars().all()
    agrupados: dict = {}
    for renglon in filas:
        agrupados.setdefault(renglon.template_id, []).append(renglon)
    return agrupados


def kits_stmt(organization_id, *, q: str | None = None, project_type: str | None = None,
              active: bool | None = None):
    stmt = select(WarehouseKitTemplate).where(WarehouseKitTemplate.organization_id == organization_id)
    if q:
        patron = contains_pattern(q)
        stmt = stmt.where(or_(WarehouseKitTemplate.name.ilike(patron, escape=LIKE_ESCAPE), WarehouseKitTemplate.description.ilike(patron, escape=LIKE_ESCAPE)))
    if project_type:
        stmt = stmt.where(WarehouseKitTemplate.project_type == project_type)
    if active is not None:
        stmt = stmt.where(WarehouseKitTemplate.active.is_(active))
    return stmt.order_by(WarehouseKitTemplate.name)


# ---------------------------------------------------------------------------
# Guardar y borrar
# ---------------------------------------------------------------------------

async def _normalizar_renglones(db, organization_id, renglones: list[dict]) -> list[dict]:
    """Cada renglón con su artículo verificado y su cantidad.

    La cantidad 0 no se acepta: un renglón que no pide nada no es un renglón, es
    una lista a medio armar que después alguien manda a autorizar tal cual.
    """
    limpios = []
    for posicion, renglon in enumerate(renglones):
        item = await wh.get_item(db, organization_id, renglon["item_id"])
        cantidad = _q(renglon.get("quantity") or ZERO)
        if cantidad <= ZERO:
            raise InvalidInputError(f"«{item.name}» necesita una cantidad mayor que cero.",
                                    code="invalid_kit_quantity")
        limpios.append({
            "item_id": item.id, "quantity": cantidad,
            "spec_label": (renglon.get("spec_label") or "").strip() or None,
            "section": (renglon.get("section") or "").strip() or None,
            "is_required": True if renglon.get("is_required") is None else bool(renglon["is_required"]),
            "notes": (renglon.get("notes") or "").strip() or None,
            "sort_order": posicion,
        })
    return limpios


async def save_kit(db: AsyncSession, *, organization_id, user, data: dict,
                  kit_id=None) -> WarehouseKitTemplate:
    """Crea o reemplaza la lista completa: la plantilla se guarda entera, con sus
    renglones, porque es una sola cosa (nombre + lo que lleva)."""
    nombre = (data.get("name") or "").strip()
    if not nombre:
        raise InvalidInputError("La lista necesita un nombre.", code="kit_name_required")
    renglones = await _normalizar_renglones(db, organization_id, data.get("items") or [])

    kit = await get_kit(db, organization_id, kit_id) if kit_id else WarehouseKitTemplate(
        organization_id=organization_id)
    if kit_id is None:
        db.add(kit)
    kit.name = nombre
    kit.project_type = (data.get("project_type") or "").strip() or None
    kit.description = (data.get("description") or "").strip() or None
    if data.get("active") is not None:
        kit.active = bool(data["active"])
    await db.flush()

    for previo in (await kit_items_of(db, organization_id, [kit.id])).get(kit.id, []):
        await db.delete(previo)
    await db.flush()
    for renglon in renglones:
        db.add(WarehouseKitItem(organization_id=organization_id, template_id=kit.id, **renglon))
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.kit_saved", entity_type="warehouse_kit_template",
                             entity_id=str(kit.id), after_data={"name": kit.name, "renglones": len(renglones)})
    await db.commit()
    await db.refresh(kit)
    return kit


async def delete_kit(db: AsyncSession, *, organization_id, user, kit_id) -> None:
    """Borrar la plantilla no toca nada ya pedido: las órdenes tienen su copia."""
    kit = await get_kit(db, organization_id, kit_id)
    nombre = kit.name
    await db.delete(kit)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.kit_deleted", entity_type="warehouse_kit_template",
                             entity_id=str(kit_id), after_data={"name": nombre})
    await db.commit()


# ---------------------------------------------------------------------------
# Aplicar a una orden de salida
# ---------------------------------------------------------------------------

async def apply_to_release(db: AsyncSession, *, organization_id, user, kit_id, release_id) -> dict:
    """Copia los renglones de la lista a un borrador de orden de salida.

    Devuelve la orden con lo que se agregó. Lo que ya estaba (mismo artículo y
    mismo calibre) no se repite: un doble clic no manda el material dos veces.
    """
    kit = await get_kit(db, organization_id, kit_id)
    order = await rel.get_own_draft(db, organization_id, user, release_id)
    if order.status != "borrador":
        raise InvalidInputError("Una orden ya enviada no se edita; recházala y haz otra.",
                                code="release_not_editable")

    renglones = (await kit_items_of(db, organization_id, [kit.id])).get(kit.id, [])
    if not renglones:
        raise InvalidInputError(f"«{kit.name}» todavía no tiene material.", code="empty_kit")

    previas = (await rel.lines_of(db, organization_id, [order.id])).get(order.id, [])
    ya_estan = {(l.item_id, l.spec_label) for l in previas}
    posicion = len(previas)
    agregadas = 0
    for renglon in renglones:
        etiqueta = (renglon.spec_label or "").strip() or None
        if (renglon.item_id, etiqueta) in ya_estan:
            continue
        db.add(WarehouseReleaseLine(
            organization_id=organization_id, order_id=order.id, item_id=renglon.item_id,
            quantity_requested=_q(renglon.quantity), spec_label=etiqueta,
            notes=renglon.notes, origin=LineOrigin.LISTA, sort_order=posicion,
            section=renglon.section, is_required=renglon.is_required,
        ))
        ya_estan.add((renglon.item_id, etiqueta))
        posicion += 1
        agregadas += 1
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.kit_applied", entity_type="warehouse_release_order",
                             entity_id=str(order.id),
                             after_data={"kit": kit.name, "agregadas": agregadas})
    await db.commit()
    await db.refresh(order)
    return {"order": order, "kit": kit, "agregadas": agregadas,
            "omitidas": len(renglones) - agregadas}


# ---------------------------------------------------------------------------
# Salidas para las pantallas
# ---------------------------------------------------------------------------

async def kits_out(db: AsyncSession, organization_id, kits: list[WarehouseKitTemplate]) -> list[dict]:
    """Listas con sus renglones y el nombre del artículo, en dos consultas."""
    if not kits:
        return []
    agrupados = await kit_items_of(db, organization_id, [k.id for k in kits])
    item_ids = {r.item_id for rs in agrupados.values() for r in rs}
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(item_ids)))).scalars().all()} if item_ids else {}
    return [kit_out(k, agrupados.get(k.id, []), items=items) for k in kits]


def kit_item_out(renglon: WarehouseKitItem, *, item: WarehouseItem | None = None) -> dict:
    return {
        "id": str(renglon.id), "item_id": str(renglon.item_id),
        "item_name": item.name if item else None, "sku": item.sku if item else None,
        "unit": item.unit if item else None,
        "unit_label": ITEM_UNITS.get(item.unit, item.unit) if item else None,
        "quantity": str(_q(renglon.quantity)),
        "unit_cost": str(to_money(item.unit_cost)) if item else None,
        "spec_label": renglon.spec_label, "section": renglon.section,
        "is_required": renglon.is_required, "notes": renglon.notes,
    }


def kit_out(kit: WarehouseKitTemplate, renglones: list[WarehouseKitItem], *,
            items: dict | None = None) -> dict:
    catalogo = items or {}
    return {
        "id": str(kit.id), "name": kit.name, "project_type": kit.project_type,
        "description": kit.description, "active": kit.active,
        "created_at": kit.created_at.isoformat() if kit.created_at else None,
        "items": [kit_item_out(r, item=catalogo.get(r.item_id)) for r in renglones],
    }
