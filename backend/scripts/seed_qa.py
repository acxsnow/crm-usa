"""Datos iniciales para el plan de QA manual (`docs/pruebas QA JJ/`).

    docker compose exec api python -m scripts.seed_qa --reiniciar --si-borrar-todo
    docker compose exec api python -m scripts.seed_qa            # solo completa lo que falte

Con `--reiniciar` borra TODA la base local (esquema `public`), la vuelve a crear
con las migraciones y carga el estado inicial. Sin esa bandera solo agrega lo que
falte: correrlo dos veces no duplica nada.

Estado inicial (detalle en `docs/pruebas QA JJ/04_DATOS_DE_PRUEBA.md`):
- Permisos, roles, organización demo, un usuario por rol y los programas de
  Arizona y TECH (el seed oficial, `scripts/seed.py`).
- 15 técnicos (Tito y 14 más), cada uno con su camioneta, y un segundo vendedor.
- El catálogo de AC Pro de `docs/bodega/` (kit «3 ton desde cero» y carrito de
  material frecuente), con la existencia que traen los PDF como conteo inicial.
- La lista «Instalación 3 ton desde cero» con los renglones del kit.
- Una segunda organización con su administrador, un cliente y un artículo, para
  las pruebas de aislamiento.

Solo para desarrollo: se niega a correr si el entorno no es `development` o si la
base no es la del Docker local.
"""
import argparse
import asyncio
import csv
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from scripts import seed  # noqa: E402  (registra todos los modelos)
from app.modules.organizations.models import Organization, PlanLimit  # noqa: E402
from app.modules.users.models import Role, User, UserRole, UserStatus  # noqa: E402

DATOS = Path(__file__).resolve().parent / "qa_data"
CLAVE = "ChangeMe123!"
ORG = "Demo Organization"
ORG_AJENA = "Organización Ajena QA"

# Tito ya lo crea el seed oficial (tecnico@demo-org.com); estos son los otros 14.
TECNICOS = [
    "Toño Segundo", "Carlos Ramírez", "Luis Herrera", "Miguel Torres", "José Castillo",
    "Pedro Vargas", "Andrés Morales", "Diego Jiménez", "Jorge Rojas", "Raúl Mendoza",
    "Fernando Ortiz", "Ricardo Silva", "Manuel Navarro", "Héctor Ruiz",
]
VENDEDOR_2 = ("vendedor2@demo-org.com", "Valeria Ventas")


def _proteger() -> None:
    s = get_settings()
    url = s.DATABASE_URL
    if s.ENVIRONMENT != "development" or "@postgres:" not in url:
        sys.exit(f"Se detiene: este script es solo para la base local de Docker (ENVIRONMENT={s.ENVIRONMENT}).")


async def _reiniciar_esquema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    subprocess.run(["alembic", "upgrade", "head"], check=True, cwd=Path(__file__).resolve().parent.parent)


async def _usuario(db, org, rol: Role, correo: str, nombre: str) -> User:
    u = (await db.execute(select(User).where(User.organization_id == org.id, User.email == correo))).scalar_one_or_none()
    if u:
        return u
    u = User(organization_id=org.id, email=correo, email_display=correo, full_name=nombre,
             password_hash=hash_password(CLAVE), status=UserStatus.active)
    db.add(u)
    await db.flush()
    db.add(UserRole(user_id=u.id, role_id=rol.id))
    return u


def _correo_tecnico(i: int) -> str:
    return f"tecnico{i:02d}@demo-org.com"


async def _tecnicos_y_vendedor(db, org) -> list[User]:
    roles = {r.code: r for r in (await db.execute(select(Role).where(Role.organization_id == org.id))).scalars()}
    tecnicos = [(await db.execute(select(User).where(User.email == "tecnico@demo-org.com"))).scalar_one()]
    for i, nombre in enumerate(TECNICOS, start=2):
        tecnicos.append(await _usuario(db, org, roles["field_technician"], _correo_tecnico(i), nombre))
    await _usuario(db, org, roles["salesperson"], *VENDEDOR_2)
    await db.commit()
    return tecnicos


async def _camionetas(db, org, admin, tecnicos) -> None:
    from app.modules.warehouse import service as wh
    from app.modules.warehouse.models import WarehouseLocation

    for t in tecnicos:
        ya = (await db.execute(select(WarehouseLocation).where(
            WarehouseLocation.organization_id == org.id, WarehouseLocation.technician_user_id == t.id))).first()
        if not ya:
            await wh.save_location(db, organization_id=org.id, user=admin,
                                   data={"name": f"Camioneta · {t.full_name}", "kind": "truck", "technician_user_id": t.id})


def _filas_catalogo() -> list[dict]:
    filas = []
    with open(DATOS / "catalogo_ac_pro.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            filas.append({
                "name": r["nombre"], "sku": r["sku"], "manufacturer_part": r["fabricante"] or None,
                "brand": r["marca"] or None, "category": r["categoria"], "unit": r["unidad"],
                "unit_cost": Decimal(r["costo"]), "supplier_name": "AC Pro", "quantity": Decimal(r["cantidad"]),
                "min_quantity": None, "notes": f"Carga QA ({r['origen']})", "has_serial": r["con_serial"] == "si",
            })
    return filas


async def _catalogo_y_lista(db, org, admin) -> dict:
    from app.modules.warehouse import kits
    from app.modules.warehouse.models import WarehouseItem, WarehouseKitTemplate
    from app.modules.warehouse.service import import_catalog

    resultado = await import_catalog(db, organization_id=org.id, user=admin, rows=_filas_catalogo(),
                                     filename="qa_data/catalogo_ac_pro.csv")
    await db.commit()
    nombre = "Instalación 3 ton desde cero"
    if not (await db.execute(select(WarehouseKitTemplate).where(
            WarehouseKitTemplate.organization_id == org.id, WarehouseKitTemplate.name == nombre))).first():
        por_sku = {i.sku: i.id for i in (await db.execute(select(WarehouseItem).where(
            WarehouseItem.organization_id == org.id))).scalars()}
        renglones = []
        with open(DATOS / "kit_3ton.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                renglones.append({"item_id": por_sku[r["sku"]], "quantity": r["cantidad"], "section": r["seccion"],
                                  "is_required": r["obligatorio"] == "si"})
        await kits.save_kit(db, organization_id=org.id, user=admin, data={
            "name": nombre, "project_type": "hvac_install", "items": renglones,
            "description": "Kit de AC Pro «3 TON HOME MATERIALS FROM SCRATCH» (docs/bodega/partes.pdf)."})
    return resultado


async def _org_ajena(db, permisos) -> None:
    from app.modules.crm.models import Customer
    from app.modules.warehouse.models import WarehouseItem
    from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS, ROLE_LABELS

    org = (await db.execute(select(Organization).where(Organization.name == ORG_AJENA))).scalar_one_or_none()
    if org:
        return
    org = Organization(name=ORG_AJENA, timezone="America/Phoenix", currency="USD")
    db.add(org)
    await db.flush()
    db.add(PlanLimit(organization_id=org.id, max_active_users=10))
    rol = Role(organization_id=org.id, code="organization_admin", name=ROLE_LABELS["organization_admin"], is_system=True)
    rol.permissions = [permisos[c] for c in DEFAULT_ROLE_PERMISSIONS["organization_admin"]]
    db.add(rol)
    await db.flush()
    await _usuario(db, org, rol, "admin@otra-org.com", "Admin Ajena")
    db.add(Customer(organization_id=org.id, legal_name="Cliente Ajeno QA", email="ajeno@example.com"))
    db.add(WarehouseItem(organization_id=org.id, name="Artículo Ajeno QA", sku="AJENO-1"))
    await db.commit()


async def main() -> None:
    _proteger()
    p = argparse.ArgumentParser()
    p.add_argument("--reiniciar", action="store_true", help="Borra toda la base local y la vuelve a crear")
    p.add_argument("--si-borrar-todo", action="store_true", help="Confirma el borrado de --reiniciar")
    args = p.parse_args()
    if args.reiniciar:
        if not args.si_borrar_todo:
            sys.exit("Para borrar la base agrega también --si-borrar-todo.")
        await _reiniciar_esquema()
        print("Base reiniciada y migraciones aplicadas.")

    async with AsyncSessionLocal() as db:
        permisos = await seed.seed_permission_catalog(db)
        await seed.seed_system_roles(db, permisos)
        await seed.seed_system_permission_modules(db, permisos)
        await seed.seed_demo_organization(db, permisos)
        await seed.seed_demo_users(db)
        await db.commit()
        await seed.seed_demo_programs(db)

        org = (await db.execute(select(Organization).where(Organization.name == ORG))).scalar_one()
        admin = (await db.execute(select(User).where(User.email == "admin@demo-org.com"))).scalar_one()
        tecnicos = await _tecnicos_y_vendedor(db, org)
        await _camionetas(db, org, admin, tecnicos)
        r = await _catalogo_y_lista(db, org, admin)
        await _org_ajena(db, permisos)
    print(f"Catálogo: {r.get('creados', 0)} creados, {r.get('actualizados', 0)} actualizados, "
          f"{len(r.get('errores', []))} errores. Técnicos: {len(tecnicos)}. Listo.")


if __name__ == "__main__":
    asyncio.run(main())
