"""Plan de cuentas inicial, pensado para un contratista de HVAC en EE. UU. Se
crea solo la primera vez. Nombres y códigos se pueden ajustar; `tax_category` es
el renglón del resumen para impuestos y lo valida el contador."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.models import Account, AccountingSettings

# (código, nombre, tipo, llave del sistema, renglón de impuestos)
DEFAULT_CHART = [
    ("1000", "Banco operativo", "asset", "bank", None),
    ("1010", "Stripe por liquidar", "asset", "stripe_clearing", None),
    ("1020", "Fondos por depositar", "asset", "undeposited", None),
    ("1100", "Cuentas por cobrar", "asset", "ar", None),
    ("1200", "Inventario de bodega", "asset", "inventory", None),
    ("2000", "Cuentas por pagar", "liability", "ap", None),
    ("2100", "Tarjeta de crédito de la empresa", "liability", "credit_card", None),
    ("2200", "Reembolsos por pagar a empleados", "liability", "reimbursements", None),
    ("2300", "Nómina por pagar", "liability", "payroll_payable", None),
    ("3000", "Patrimonio inicial", "equity", "opening_equity", None),
    ("3900", "Utilidades retenidas", "equity", "retained", None),
    ("4000", "Ingresos por trabajo particular", "income", "income_particular", "Ingresos brutos"),
    ("4100", "Ingresos por programas de rebate", "income", "income_rebate", "Ingresos brutos"),
    ("4200", "Cobros adicionales en obra", "income", "income_extra", "Ingresos brutos"),
    ("5000", "Materiales", "cogs", "cogs_materials", "Costo de ventas: materiales"),
    ("5010", "Equipos", "cogs", "cogs_equipment", "Costo de ventas: materiales"),
    ("5020", "Contratistas", "cogs", "cogs_contractor", "Contratistas"),
    ("5030", "Permisos", "cogs", "cogs_permit", "Impuestos y licencias"),
    ("5040", "Servicios", "cogs", "cogs_services", "Costo de ventas: otros"),
    ("5050", "Mano de obra directa", "cogs", "cogs_labor", "Costo de ventas: mano de obra"),
    ("6100", "Gasolina", "expense", "exp_fuel", "Vehículos"),
    ("6110", "Viáticos", "expense", "exp_per_diem", "Viajes"),
    ("6120", "Hotel", "expense", "exp_lodging", "Viajes"),
    ("6130", "Comida", "expense", "exp_meals", "Comidas (deducción parcial)"),
    ("6140", "Peajes y parqueo", "expense", "exp_tolls", "Vehículos"),
    ("6150", "Material menor", "expense", "exp_small_materials", "Suministros"),
    ("6160", "Herramienta", "expense", "exp_tools", "Suministros"),
    ("6170", "Otros gastos", "expense", "exp_other", "Otros gastos"),
    ("6200", "Impuesto de ventas en compras", "expense", "exp_purchase_tax", "Impuestos y licencias"),
    ("6210", "Fletes y envíos", "expense", "exp_freight", "Otros gastos"),
    ("6300", "Comisiones de cobro en línea", "expense", "exp_merchant_fees", "Comisiones"),
    ("6400", "Ajustes de inventario", "expense", "exp_inventory_adjust", "Costo de ventas: otros"),
    ("6500", "Nómina administrativa", "expense", "exp_payroll", "Salarios"),
]


async def ensure_chart(db: AsyncSession, organization_id) -> None:
    """Crea las cuentas del sistema que falten, sin tocar las que ya existen."""
    filas = (await db.execute(select(Account.system_key, Account.code).where(
        Account.organization_id == organization_id))).all()
    llaves, codigos = {k for k, _ in filas}, {c for _, c in filas}
    for codigo, nombre, tipo, llave, renglon in DEFAULT_CHART:
        if llave in llaves:
            continue
        # Si el contador ya usó ese código en una cuenta propia, la del sistema toma otro.
        libre = codigo if codigo not in codigos else f"{codigo}-S"
        db.add(Account(organization_id=organization_id, code=libre, name=nombre, account_type=tipo, system_key=llave,
                       tax_category=renglon, active=True))
        codigos.add(libre)
    await db.flush()


async def settings_of(db: AsyncSession, organization_id) -> AccountingSettings:
    fila = (await db.execute(select(AccountingSettings).where(
        AccountingSettings.organization_id == organization_id))).scalar_one_or_none()
    if fila is None:
        fila = AccountingSettings(organization_id=organization_id)
        db.add(fila)
        await db.flush()
    return fila
