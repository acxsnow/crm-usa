"""Rutas de contabilidad. Leer exige `accounting.read`; registrar y cerrar,
`accounting.manage`; exportar, `accounting.export`. La organización sale del token."""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_permission
from app.db.session import get_db
from app.modules.accounting import ledger, posting
from app.modules.accounting.chart import ensure_chart, settings_of
from app.modules.field_ops.clock import org_today
from app.modules.users.models import User
from app.shared.pagination import paginate, pagination_params

router = APIRouter(prefix="/accounting", tags=["accounting"])
_read = require_permission("accounting.read")
_manage = require_permission("accounting.manage")
_export = require_permission("accounting.export")


class AccountIn(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name: str | None = Field(default=None, max_length=120)
    account_type: str | None = Field(default=None, pattern="^(asset|liability|equity|income|cogs|expense)$")
    tax_category: str | None = Field(default=None, max_length=80)
    active: bool | None = None


class EntryLineIn(BaseModel):
    account_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("999999999"))
    credit: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("999999999"))
    project_id: uuid.UUID | None = None
    memo: str | None = Field(default=None, max_length=255)


class EntryIn(BaseModel):
    entry_date: date
    memo: str = Field(min_length=1, max_length=500)
    lines: list[EntryLineIn] = Field(min_length=2, max_length=100)


class ReverseIn(BaseModel):
    entry_date: date | None = None
    reason: str = Field(min_length=1, max_length=400)


class LockIn(BaseModel):
    locked_through: date | None = None


def _csv(texto: str, nombre: str) -> Response:
    return Response(content=texto, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'})


@router.post("/sync")
async def sync_now(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_manage)) -> dict:
    """Trae ya lo que falte de los documentos (Celery lo hace cada hora)."""
    return await posting.sync(db, organization_id)


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_read)) -> dict:
    s = await settings_of(db, organization_id)
    await db.commit()
    return ledger.lock_out(s)


@router.put("/settings/lock")
async def set_lock(payload: LockIn, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_manage)) -> dict:
    return await ledger.set_lock(db, organization_id=organization_id, user=current_user, locked_through=payload.locked_through)


@router.get("/accounts")
async def list_accounts(response: Response, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pag: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_read)) -> list[dict]:
    await ensure_chart(db, organization_id)
    await db.commit()
    filas = await paginate(db, ledger.accounts_stmt(organization_id), limit=pag[0], offset=pag[1], response=response)
    return [ledger.account_out(a) for a in filas]


@router.post("/accounts", status_code=201)
async def create_account(payload: AccountIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    return ledger.account_out(await ledger.save_account(db, organization_id=organization_id, user=current_user,
                                                        data=payload.model_dump()))


@router.patch("/accounts/{account_id}")
async def update_account(account_id: uuid.UUID, payload: AccountIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    return ledger.account_out(await ledger.save_account(db, organization_id=organization_id, user=current_user,
                                                        data=payload.model_dump(exclude_unset=True), account_id=account_id))


@router.get("/accounts/{account_id}/ledger")
async def account_ledger(account_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None,
                         db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_read)) -> dict:
    await posting.sync(db, organization_id)
    return await ledger.account_ledger(db, organization_id, account_id, date_from, date_to)


@router.get("/entries")
async def list_entries(response: Response, date_from: date | None = None, date_to: date | None = None,
                       source: str | None = Query(default=None, pattern="^(manual|automatic)$"),
                       q: str | None = Query(default=None, max_length=80), db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_read)) -> list[dict]:
    await posting.sync(db, organization_id)
    filas = await paginate(db, ledger.entries_stmt(organization_id, date_from=date_from, date_to=date_to, source=source, q=q),
                           limit=pag[0], offset=pag[1], response=response)
    return await ledger.entries_out(db, organization_id, filas)


@router.post("/entries", status_code=201)
async def create_entry(payload: EntryIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)) -> dict:
    e = await ledger.create_manual_entry(db, organization_id=organization_id, user=current_user, on=payload.entry_date,
                                         memo=payload.memo, lines=[l.model_dump() for l in payload.lines])
    return (await ledger.entries_out(db, organization_id, [e]))[0]


@router.post("/entries/{entry_id}/reverse", status_code=201)
async def reverse_entry(entry_id: uuid.UUID, payload: ReverseIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> dict:
    r = await ledger.reverse_manual(db, organization_id=organization_id, user=current_user, entry_id=entry_id,
                                    on=payload.entry_date, reason=payload.reason)
    return (await ledger.entries_out(db, organization_id, [r]))[0]


async def _as_of(db, organization_id, as_of: date | None) -> date:
    return as_of or await org_today(db, organization_id)


@router.get("/reports/trial-balance")
async def trial_balance(as_of: date | None = None, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)) -> dict:
    await posting.sync(db, organization_id)
    return await ledger.trial_balance(db, organization_id, await _as_of(db, organization_id, as_of))


@router.get("/reports/income-statement")
async def income_statement(date_from: date, date_to: date, project_id: uuid.UUID | None = None,
                           db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_read)) -> dict:
    await posting.sync(db, organization_id)
    return await ledger.income_statement(db, organization_id, date_from, date_to, project_id)


@router.get("/reports/balance-sheet")
async def balance_sheet(as_of: date | None = None, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)) -> dict:
    await posting.sync(db, organization_id)
    return await ledger.balance_sheet(db, organization_id, await _as_of(db, organization_id, as_of))


@router.get("/reports/tax-summary")
async def tax_summary(year: int = Query(ge=2000, le=2100), threshold: Decimal | None = Query(default=None, ge=0),
                      db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_read)) -> dict:
    await posting.sync(db, organization_id)
    return await ledger.tax_summary(db, organization_id, year, threshold,
                                    sensitive="accounting.export" in get_effective_permissions(current_user))


# --- Exportar para el contador ------------------------------------------------

@router.get("/export/income-statement.csv")
async def export_income(date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_export)) -> Response:
    await posting.sync(db, organization_id)
    r = await ledger.income_statement(db, organization_id, date_from, date_to)
    return _csv(ledger.statement_csv("Estado de resultados", f"{date_from} a {date_to}",
                                     [("Ingresos", r["income"]), ("Costo de ventas", r["cogs"]), ("Gastos", r["expenses"])],
                                     [("Utilidad bruta", r["gross_profit"]), ("Utilidad neta", r["net_income"])]),
                f"estado-de-resultados-{date_from}-{date_to}")


@router.get("/export/balance-sheet.csv")
async def export_balance(as_of: date | None = None, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_export)) -> Response:
    await posting.sync(db, organization_id)
    fecha = await _as_of(db, organization_id, as_of)
    r = await ledger.balance_sheet(db, organization_id, fecha)
    return _csv(ledger.statement_csv("Balance general", str(fecha),
                                     [("Activos", r["assets"]), ("Pasivos", r["liabilities"]), ("Patrimonio", r["equity"])],
                                     [("Total activos", r["total_assets"]), ("Utilidad acumulada", r["retained_earnings"]),
                                      ("Total pasivo y patrimonio", r["total_liabilities_equity"])]), f"balance-general-{fecha}")


@router.get("/export/journal.csv")
async def export_journal(date_from: date, date_to: date, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_export)) -> Response:
    await posting.sync(db, organization_id)
    filas = (await db.execute(ledger.entries_stmt(organization_id, date_from=date_from, date_to=date_to))).scalars().all()
    salida = [["Fecha", "Número", "Concepto", "Cuenta", "Nombre", "Débito", "Crédito"]]
    for e in await ledger.entries_out(db, organization_id, list(filas)):
        salida.extend([e["entry_date"], e["number"], e["memo"], l["account_code"], l["account_name"], l["debit"], l["credit"]]
                      for l in e["lines"])
    return _csv(ledger.to_csv(salida), f"libro-diario-{date_from}-{date_to}")


@router.get("/export/tax-summary.csv")
async def export_tax(year: int = Query(ge=2000, le=2100), db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_export)) -> Response:
    await posting.sync(db, organization_id)
    r = await ledger.tax_summary(db, organization_id, year, sensitive=True)
    salida = [[f"Resumen para impuestos {year}"], [], ["Grupo", "Renglón", "Valor", "Cuentas"]]
    salida.extend([f["group"], f["tax_category"], f["amount"], "; ".join(f["accounts"])] for f in r["lines"])
    salida += [[], ["Utilidad neta", "", r["net_income"]], [], [f"Proveedores para 1099-NEC (desde ${r['threshold_1099']})"],
               ["Nombre", "TIN", "Dirección", "Pagado", "Falta"]]
    salida.extend([c["name"], c["tax_id"], c["address"], c["total_paid"], ", ".join(c["missing"])] for c in r["contractors_1099"])
    return _csv(ledger.to_csv(salida), f"impuestos-{year}")
