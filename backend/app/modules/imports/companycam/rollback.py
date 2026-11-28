"""Reversa de la importación: borra lo importado que nadie ha tocado.

Un expediente importado se borra solo si sigue intacto: sin historial propio
(eventos no importados), sin respuestas de formulario, sin obra, sin cobros ni
documentos de facturación, sin archivos subidos por personas y sin programa.
Lo que alguien ya trabajó se deja y se anota en `rollback_bloqueados.csv`.
Después se borran los clientes importados que quedaron sin nada y los usuarios
inactivos creados por la importación sin ningún otro vínculo."""
import csv
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.modules.cases.models import Case, CaseFile, CaseNote, CaseStageEvent
from app.modules.crm.models import Customer
from app.modules.imports.companycam.cache import ExportCache
from app.modules.imports.models import ImportItem
from app.modules.users.models import User, UserStatus
from app.shared.audit import record_audit_event

SOURCE = "companycam"
# Tablas que cuelgan del expediente y se borran con él (se revisan aparte o no bloquean).
# `data_consents` NO está aquí: una constancia de autorización es evidencia y bloquea.
_SIN_BLOQUEO = {"case_notes", "import_items", "case_stage_events", "case_files"}
_CLIENTE_SIN_BLOQUEO = {"customer_contacts", "cases"}


def _refs_by_column(column: str, skip: set[str]) -> list[tuple[str, str]]:
    """(tabla, columna) de TODA tabla con esa columna, tenga o no clave foránea
    (`Activity.customer_id`, `MarketingConsent`, `CampaignRecipient`,
    `EmailMarketingConsent`… son UUID sueltos que una FK no vería)."""
    return [(t.name, column) for t in Base.metadata.tables.values()
            if column in t.c and t.name not in skip]


def _fks_to(table_name: str) -> list[tuple[str, str]]:
    """(tabla, columna) de todas las claves foráneas hacia `table_name.id`."""
    out = []
    for t in Base.metadata.tables.values():
        for fk in t.foreign_keys:
            if fk.column.table.name == table_name and fk.column.name == "id":
                out.append((t.name, fk.parent.name))
    return out


async def _count(db: AsyncSession, table: str, column: str, value) -> int:
    t = Base.metadata.tables[table]
    return (await db.execute(select(func.count()).select_from(t).where(t.c[column] == value))).scalar_one()


async def case_blockers(db: AsyncSession, case: Case) -> list[str]:
    motivos: list[str] = []
    if case.program_id is not None:
        motivos.append("tiene programa asignado")
    if (await db.execute(select(func.count(CaseStageEvent.id)).where(
            CaseStageEvent.case_id == case.id, CaseStageEvent.imported.is_(False)))).scalar_one():
        motivos.append("tiene historial de etapas propio")
    if (await db.execute(select(func.count(CaseFile.id)).where(
            CaseFile.case_id == case.id, (CaseFile.uploaded_by_user_id.is_not(None))
            | (~CaseFile.field_key.like("companycam\\_%", escape="\\"))))).scalar_one():
        motivos.append("tiene archivos subidos por personas")
    # Un expediente que alguien tocó después (reasignado, editado) ya no es el de la importación.
    if case.updated_at != case.created_at:
        motivos.append("fue modificado después de importarlo")
    for tabla, col in sorted(set(_fks_to("cases")) | set(_refs_by_column("case_id", set()))):
        if tabla in _SIN_BLOQUEO:
            continue
        if await _count(db, tabla, col, case.id):
            motivos.append(f"tiene registros en {tabla}")
    return motivos


async def rollback_import(db: AsyncSession, organization_id: uuid.UUID, cache: ExportCache, *, log=print) -> dict:
    resumen = {"cases_deleted": 0, "cases_blocked": 0, "customers_deleted": 0, "users_deleted": 0}
    bloqueados: list[dict] = []
    casos = (await db.execute(select(Case).where(
        Case.organization_id == organization_id, Case.source == SOURCE))).scalars().all()
    for c in casos:
        motivos = await case_blockers(db, c)
        if motivos:
            bloqueados.append({"tipo": "expediente", "id": str(c.id), "ref": c.case_number, "motivo": "; ".join(motivos)})
            resumen["cases_blocked"] += 1
            continue
        # Los hijos se borran a mano: en la base real caen por cascada, pero así
        # no se depende de ella (SQLite de pruebas no la aplica).
        for modelo in (CaseNote, ImportItem, CaseFile, CaseStageEvent):
            await db.execute(delete(modelo).where(modelo.case_id == c.id))
        await db.delete(c)
        resumen["cases_deleted"] += 1
    await db.flush()

    clientes = (await db.execute(select(Customer).where(
        Customer.organization_id == organization_id, Customer.source == SOURCE))).scalars().all()
    for cl in clientes:
        motivos = []
        if cl.updated_at and cl.created_at and cl.updated_at > cl.created_at:
            motivos.append("fue modificado después de importarlo")
        for tabla, col in sorted(set(_fks_to("customers")) | set(_refs_by_column("customer_id", set()))):
            if tabla in _CLIENTE_SIN_BLOQUEO:
                continue
            if await _count(db, tabla, col, cl.id):
                motivos.append(f"usado en {tabla}")
        if await _count(db, "cases", "customer_id", cl.id):
            motivos.append("tiene expedientes")
        if motivos:
            bloqueados.append({"tipo": "cliente", "id": str(cl.id), "ref": cl.external_ref or "",
                               "motivo": "; ".join(motivos)})
            continue
        await db.delete(cl)
        resumen["customers_deleted"] += 1
    await db.flush()

    usuarios = (await db.execute(select(User).where(
        User.organization_id == organization_id, User.source == SOURCE, User.status == UserStatus.inactive))
    ).scalars().all()
    for u in usuarios:
        motivos = []
        if await _count(db, "cases", "assigned_salesperson_id", u.id):
            motivos.append("vendedor de expedientes")
        for tabla, col in _fks_to("users"):
            if tabla == "user_roles":
                continue
            if await _count(db, tabla, col, u.id):
                motivos.append(f"referenciado en {tabla}")
        if motivos:
            bloqueados.append({"tipo": "usuario", "id": str(u.id), "ref": u.external_ref or "",
                               "motivo": "; ".join(motivos)})
            continue
        await db.delete(u)
        resumen["users_deleted"] += 1

    await record_audit_event(db, organization_id=organization_id, actor_user_id=None,
                             action="imports.rolled_back", entity_type="import", entity_id=SOURCE,
                             after_data=resumen)
    await db.commit()
    if bloqueados:
        ruta = cache.reports_dir / "rollback_bloqueados.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["tipo", "id", "ref", "motivo"])
            w.writeheader()
            w.writerows(bloqueados)
        log(f"{len(bloqueados)} elementos bloqueados → {ruta}")
    return resumen
