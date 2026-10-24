"""Categorías del catálogo de bodega, por organización (plan bodega-cierre, fase 3).

Antes eran un diccionario fijo en `catalogs.py`; el cuestionario decía que el
cliente podía cambiarlas o agregar las suyas, y el catálogo de AC Pro trae
grupos que no cabían (termostatos, filtros, B-Vent…). El artículo guarda el
código, que no cambia: renombrar toca la etiqueta y desactivar solo la saca de
las opciones.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.warehouse.catalogs import DEFAULT_CATEGORY, ITEM_CATEGORIES
from app.modules.warehouse.models import WarehouseCategory
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError


async def ensure_categories(db: AsyncSession, organization_id) -> None:
    """Siembra las categorías iniciales la primera vez que la organización las
    usa; si ya tiene alguna (aunque las haya cambiado), no toca nada."""
    hay = (await db.execute(select(WarehouseCategory.id).where(
        WarehouseCategory.organization_id == organization_id).limit(1))).first()
    if hay:
        return
    for posicion, (code, label) in enumerate(ITEM_CATEGORIES.items()):
        db.add(WarehouseCategory(organization_id=organization_id, code=code, label=label, sort_order=posicion))
    try:
        await db.commit()
    except IntegrityError:
        # Dos pantallas las pidieron a la vez la primera vez: la otra ya las sembró.
        await db.rollback()


async def list_categories(db: AsyncSession, organization_id, *, active: bool | None = None) -> list[WarehouseCategory]:
    await ensure_categories(db, organization_id)
    stmt = select(WarehouseCategory).where(WarehouseCategory.organization_id == organization_id)
    if active is not None:
        stmt = stmt.where(WarehouseCategory.active.is_(active))
    return list((await db.execute(stmt.order_by(WarehouseCategory.sort_order, WarehouseCategory.label))).scalars())


async def category_labels(db: AsyncSession, organization_id) -> dict[str, str]:
    """Código → etiqueta de todas, también las inactivas: un artículo viejo
    sigue mostrando su categoría aunque ya no se ofrezca."""
    return {c.code: c.label for c in await list_categories(db, organization_id)}


async def check_category(db: AsyncSession, organization_id, code: str, *, current: str | None = None) -> None:
    """Para guardar un artículo la categoría tiene que existir y estar activa,
    salvo que sea la que el artículo ya tenía (se puede editar un artículo de
    una categoría desactivada sin moverlo de ella)."""
    categorias = {c.code: c for c in await list_categories(db, organization_id)}
    categoria = categorias.get(code)
    if categoria is None:
        raise InvalidInputError("La categoría no existe.", code="invalid_item_category")
    if not categoria.active and code != current:
        raise InvalidInputError(f"La categoría «{categoria.label}» está desactivada.", code="inactive_item_category")


def _slug(texto: str) -> str:
    """«Ventilación (B-Vent)» → «ventilacion_b_vent»: el código se deriva del
    nombre la primera vez y después no cambia."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.casefold()).strip("_")[:24] or "categoria"


async def create_category(db: AsyncSession, *, organization_id, user, label: str, commit: bool = True) -> WarehouseCategory:
    nombre = " ".join((label or "").split())
    if not nombre:
        raise InvalidInputError("La categoría necesita un nombre.", code="category_label_required")
    if len(nombre) > 80:
        raise InvalidInputError("El nombre de la categoría es demasiado largo (máximo 80).", code="category_label_too_long")
    existentes = await list_categories(db, organization_id)
    if any(c.label.casefold() == nombre.casefold() for c in existentes):
        raise ConflictError(f"Ya existe la categoría «{nombre}».", code="category_exists")
    codigos = {c.code for c in existentes}
    base = _slug(nombre)
    code, n = base, 2
    while code in codigos:
        code, n = f"{base}_{n}", n + 1
    categoria = WarehouseCategory(organization_id=organization_id, code=code, label=nombre,
                                  sort_order=max((c.sort_order for c in existentes), default=0) + 1)
    db.add(categoria)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.category_created", entity_type="warehouse_category",
                             entity_id=str(categoria.id), after_data={"code": code, "label": nombre})
    if commit:
        await db.commit()
        await db.refresh(categoria)
    return categoria


async def update_category(db: AsyncSession, *, organization_id, user, category_id, label: str | None,
                          active: bool | None) -> WarehouseCategory:
    categoria = await db.get(WarehouseCategory, category_id)
    if categoria is None or categoria.organization_id != organization_id:
        raise NotFoundError("La categoría no existe.", code="warehouse_category_not_found")
    antes = {"label": categoria.label, "active": categoria.active}
    if label is not None:
        nombre = " ".join(label.split())
        if not nombre:
            raise InvalidInputError("La categoría necesita un nombre.", code="category_label_required")
        if len(nombre) > 80:
            raise InvalidInputError("El nombre de la categoría es demasiado largo (máximo 80).",
                                    code="category_label_too_long")
        otra = (await db.execute(select(WarehouseCategory.id).where(
            WarehouseCategory.organization_id == organization_id, WarehouseCategory.id != categoria.id,
            WarehouseCategory.label.ilike(nombre)))).first()
        if otra:
            raise ConflictError(f"Ya existe la categoría «{nombre}».", code="category_exists")
        categoria.label = nombre
    if active is not None:
        if not active and categoria.code == DEFAULT_CATEGORY:
            raise InvalidInputError("«Otro» no se desactiva: es la categoría de lo que no tiene otra.",
                                    code="default_category_required")
        categoria.active = active
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.category_updated", entity_type="warehouse_category",
                             entity_id=str(categoria.id), before_data=antes,
                             after_data={"label": categoria.label, "active": categoria.active})
    await db.commit()
    await db.refresh(categoria)
    return categoria


def category_out(c: WarehouseCategory, *, item_count: int | None = None) -> dict:
    salida = {"id": str(c.id), "code": c.code, "label": c.label, "active": c.active, "sort_order": c.sort_order}
    if item_count is not None:
        salida["item_count"] = item_count
    return salida
