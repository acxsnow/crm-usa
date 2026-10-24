"""Diario de obra (punto 4 del cuestionario del 19 de octubre).

«Los trabajos fuera de rebate duran varios días, con técnicos distintos cada
día», y lo que se quiere ver es, día por día, qué se gastó, qué se hizo, qué
material faltó, hasta dónde se avanzó y qué llevar al día siguiente.

Tres reglas sostienen el archivo:

- **El técnico vive en la jornada, no en el proyecto.** La misma obra tiene un
  técnico distinto cada día; por eso `technician_user_id` está acá y no en
  `projects`. Una obra con más de una jornada es una obra de varios días.
- **Los gastos del día no se capturan acá.** Se leen de `expenses` por fecha,
  que es donde ya están cargados: volver a escribirlos sería contarlos dos veces.
- **El material que salió de la camioneta no se edita ni se borra.** Registrar
  la jornada descuenta la existencia con un movimiento de bodega, y el libro de
  movimientos no se toca; para corregir se registra el movimiento contrario. Las
  líneas que no movieron existencia (texto libre) sí se editan.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.finance.models import Expense
from app.modules.users.models import User
from app.modules.warehouse import service as wh
from app.modules.warehouse.budgets import get_project
from app.modules.warehouse.catalogs import ITEM_UNITS, LocationKind, MovementType
from app.modules.warehouse.models import ProjectDayLog, ProjectDayLogHelper, ProjectDayLogMaterial
from app.shared.decimals import to_quantity
from app.shared.audit import record_audit_event
from app.shared.errors import ForbiddenError, InvalidInputError, NotFoundError

Q2 = Decimal("0.01")

# La clave del movimiento que descuenta la camioneta: repetir el guardado de la
# misma jornada no descuenta dos veces.
DAY_LOG_SOURCE_PREFIX = "day-log:"

# Un gasto que cuenta es uno aprobado o ya reembolsado; el que está por revisar
# o rechazado todavía no es plata puesta.
COUNTED_EXPENSES = ("approved", "reimbursed")

MAX_NOTE = 4000


def _q(value) -> Decimal:
    return to_quantity(value)


def _texto(value, *, maximo: int = MAX_NOTE) -> str | None:
    limpio = (value or "").strip()
    if not limpio:
        return None
    if len(limpio) > maximo:
        raise InvalidInputError(f"El texto no puede pasar de {maximo} caracteres.", code="day_log_text_too_long")
    return limpio


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

async def get_day_log(db: AsyncSession, organization_id, log_id) -> ProjectDayLog:
    fila = await db.get(ProjectDayLog, log_id)
    if fila is None or fila.organization_id != organization_id:
        raise NotFoundError("La jornada no existe.", code="day_log_not_found")
    return fila


def day_logs_stmt(organization_id, *, project_id=None, date_from: date | None = None,
                  date_to: date | None = None):
    stmt = select(ProjectDayLog).where(ProjectDayLog.organization_id == organization_id)
    if project_id:
        stmt = stmt.where(ProjectDayLog.project_id == project_id)
    if date_from:
        stmt = stmt.where(ProjectDayLog.log_date >= date_from)
    if date_to:
        stmt = stmt.where(ProjectDayLog.log_date <= date_to)
    # El diario se lee del último día al primero: lo reciente es lo que se mira.
    return stmt.order_by(ProjectDayLog.log_date.desc(), ProjectDayLog.created_at.desc())


async def materials_of(db: AsyncSession, organization_id, log_ids) -> dict:
    """Material de varias jornadas, agrupado. Se lee aparte porque la relación
    está en `lazy="raise"`."""
    ids = list(log_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(ProjectDayLogMaterial).where(
        ProjectDayLogMaterial.organization_id == organization_id,
        ProjectDayLogMaterial.day_log_id.in_(ids),
    ).order_by(ProjectDayLogMaterial.sort_order, ProjectDayLogMaterial.created_at))).scalars().all()
    agrupados: dict = {}
    for linea in filas:
        agrupados.setdefault(linea.day_log_id, []).append(linea)
    return agrupados


async def day_count_by_project(db: AsyncSession, organization_id, project_ids) -> dict:
    """Cuántas jornadas tiene cada obra. Más de una = obra de varios días, que
    es lo que la Agenda marca."""
    ids = list(project_ids)
    if not ids:
        return {}
    filas = (await db.execute(
        select(ProjectDayLog.project_id, func.count(ProjectDayLog.id))
        .where(ProjectDayLog.organization_id == organization_id, ProjectDayLog.project_id.in_(ids))
        .group_by(ProjectDayLog.project_id))).all()
    return {project_id: int(cuantas) for project_id, cuantas in filas}


async def expenses_by_date(db: AsyncSession, organization_id, *, project_id, fechas) -> dict:
    """Los gastos de la obra agrupados por fecha. Solo se leen: los gastos ya
    están capturados en `expenses` y el diario no los vuelve a pedir."""
    dias = list(fechas)
    if not dias:
        return {}
    filas = (await db.execute(
        select(Expense.expense_date, func.count(Expense.id), func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.organization_id == organization_id, Expense.project_id == project_id,
               Expense.expense_date.in_(dias), Expense.status.in_(COUNTED_EXPENSES))
        .group_by(Expense.expense_date))).all()
    return {fecha: {"count": int(cuantos), "amount": to_money(monto)} for fecha, cuantos, monto in filas}


async def _names(db: AsyncSession, organization_id, *, item_ids, location_ids, user_ids) -> dict:
    """Nombres de artículos, ubicaciones y usuarios en tres consultas sueltas:
    el diario se lee de a páginas, así que no vale la pena más."""
    nombres: dict = {"items": {}, "locations": {}, "users": {}}
    if item_ids:
        filas = (await db.execute(select(wh.WarehouseItem.id, wh.WarehouseItem.name, wh.WarehouseItem.sku,
                                         wh.WarehouseItem.unit)
                                  .where(wh.WarehouseItem.organization_id == organization_id,
                                         wh.WarehouseItem.id.in_(list(item_ids))))).all()
        nombres["items"] = {i: {"name": n, "sku": s, "unit": u} for i, n, s, u in filas}
    if location_ids:
        filas = (await db.execute(select(wh.WarehouseLocation.id, wh.WarehouseLocation.name)
                                  .where(wh.WarehouseLocation.organization_id == organization_id,
                                         wh.WarehouseLocation.id.in_(list(location_ids))))).all()
        nombres["locations"] = dict(filas)
    if user_ids:
        filas = (await db.execute(select(User.id, User.full_name)
                                  .where(User.id.in_(list(user_ids))))).all()
        nombres["users"] = dict(filas)
    return nombres


# ---------------------------------------------------------------------------
# Guardar
# ---------------------------------------------------------------------------

def _check_truck(ubicacion, usuario, descripcion: str) -> None:
    """El material del día descuenta de lo que la camioneta llevó. Sacarlo de la
    bodega es una orden de salida, que pasa por autorización; y el técnico solo
    descuenta de su propia camioneta. Bodega (`warehouse.manage`) puede corregir."""
    from app.api.deps import get_effective_permissions

    if "warehouse.manage" in get_effective_permissions(usuario):
        return
    if ubicacion.kind != LocationKind.TRUCK or ubicacion.technician_user_id != usuario.id:
        raise InvalidInputError(
            f"«{descripcion}» solo puede salir de tu camioneta; lo de bodega se pide con una orden de salida.",
            code="day_log_location_not_own_truck")


async def _material_de_linea(db, organization_id, *, log, usuario, linea: ProjectDayLogMaterial, datos: dict,
                             posicion: int) -> None:
    """Deja la línea lista y, si salió de una ubicación, descuenta la existencia.

    El movimiento lleva el `project_id`, así que el material usado en la jornada
    cuenta como costo de la obra; y lleva `source_key` por línea, así que
    guardar dos veces la misma jornada no baja el saldo dos veces.
    """
    item = await wh.get_item(db, organization_id, datos["item_id"]) if datos.get("item_id") else None
    descripcion = _texto(datos.get("description"), maximo=255) or (item.name if item else None)
    if not descripcion:
        raise InvalidInputError("Todo material del día necesita una descripción.",
                                code="day_log_material_description_required")
    cantidad = _q(datos.get("quantity") or Decimal("1"))
    if cantidad <= ZERO:
        raise InvalidInputError(f"«{descripcion}» necesita una cantidad mayor que cero.",
                                code="invalid_day_log_quantity")

    ubicacion_id = datos.get("location_id")
    if ubicacion_id and item is None:
        raise InvalidInputError(f"«{descripcion}» no es un artículo del catálogo: no puede salir de una ubicación.",
                                code="day_log_material_item_required")

    linea.item_id = item.id if item else None
    linea.description = descripcion
    linea.quantity = cantidad
    linea.unit = datos.get("unit") or (item.unit if item else "unit")
    linea.notes = _texto(datos.get("notes"))
    linea.sort_order = posicion
    # Sin artículo ni ubicación la línea es solo la anotación del día: no mueve
    # nada (es el caso del material comprado directo a la obra).
    linea.location_id = None
    if item is None or not ubicacion_id:
        return

    ubicacion = await wh.get_location(db, organization_id, ubicacion_id)
    _check_truck(ubicacion, usuario, descripcion)
    movimiento = await wh.record_movement(
        db, organization_id=organization_id, user=usuario, item_id=item.id, location_id=ubicacion.id,
        movement_type=MovementType.SALIDA, quantity=cantidad,
        unit_cost=item.unit_cost if item.unit_cost is not None else ZERO,
        reference=f"Diario de obra {log.log_date.isoformat()}",
        note=f"Usado en la jornada del {log.log_date.isoformat()}: {descripcion}",
        project_id=log.project_id, movement_date=log.log_date,
        source_key=f"{DAY_LOG_SOURCE_PREFIX}{log.id}:line:{linea.id}", commit=False)
    linea.location_id = ubicacion.id
    linea.movement_id = movimiento.id


def _cambios_rechazados(linea: ProjectDayLogMaterial, datos: dict) -> bool:
    """Si la línea ya movió existencia, sus datos quedaron congelados: el
    movimiento que la descontó no se puede editar."""
    enviado = datos.get("item_id")
    return (str(linea.item_id) if linea.item_id else None) != (str(enviado) if enviado else None) \
        or _q(datos.get("quantity") or Decimal("1")) != _q(linea.quantity)


async def _check_active_user(db, organization_id, user_id) -> None:
    """El técnico del día o el ayudante: una persona activa de la organización."""
    from app.modules.users.models import UserStatus

    persona = await db.get(User, user_id)
    if persona is None or persona.organization_id != organization_id or persona.status != UserStatus.active:
        raise InvalidInputError("El técnico no existe o no está activo.", code="invalid_technician")


async def helpers_of(db, organization_id, log_ids) -> dict:
    """Los ayudantes de cada jornada, con su nombre."""
    ids = list(log_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(ProjectDayLogHelper.day_log_id, User.id, User.full_name)
                              .join(User, User.id == ProjectDayLogHelper.user_id)
                              .where(ProjectDayLogHelper.organization_id == organization_id,
                                     ProjectDayLogHelper.day_log_id.in_(ids))
                              .order_by(User.full_name))).all()
    agrupados: dict = {}
    for log_id, uid, nombre in filas:
        agrupados.setdefault(log_id, []).append({"user_id": str(uid), "name": nombre})
    return agrupados


async def save_day_log(db: AsyncSession, *, organization_id, user, project_id, data: dict,
                       log_id=None) -> ProjectDayLog:
    """Registra o corrige una jornada.

    La fecha y el técnico se cambian libremente; el material que ya movió
    existencia, no. Un día por obra: registrar dos veces la misma fecha se
    rechaza en vez de dejar dos renglones para el mismo día.
    """
    project = await get_project(db, organization_id, project_id)
    fecha = data.get("log_date")
    if not fecha:
        raise InvalidInputError("El diario necesita la fecha del día.", code="day_log_date_required")

    from app.modules.field_ops.access import _sees_all

    oficina = _sees_all(user)
    if log_id is not None:
        log = await get_day_log(db, organization_id, log_id)
        if log.project_id != project.id:
            raise NotFoundError("La jornada no existe.", code="day_log_not_found")
        # Cada jornada es de quien la registró: el técnico que sigue la obra la
        # lee pero no la cambia (el personal rota; fase 5). La oficina corrige.
        if not oficina and log.created_by_user_id != user.id:
            raise ForbiddenError("Esa jornada la registró otro técnico: la ves en solo lectura.",
                                 code="day_log_by_other")
        log.updated_by_user_id = user.id
    else:
        log = ProjectDayLog(organization_id=organization_id, project_id=project.id,
                            created_by_user_id=user.id)

    repetida = (await db.execute(select(ProjectDayLog.id).where(
        ProjectDayLog.organization_id == organization_id, ProjectDayLog.project_id == project.id,
        ProjectDayLog.log_date == fecha,
        *([ProjectDayLog.id != log.id] if log_id is not None else [])))).first()
    if repetida is not None:
        raise InvalidInputError("Esa obra ya tiene una jornada de ese día.",
                                code="day_log_date_taken")

    # El técnico registra su propia jornada; a nombre de otro, solo la oficina.
    tecnico_id = data.get("technician_user_id") or (None if oficina else user.id)
    if tecnico_id and tecnico_id != user.id:
        if not oficina:
            raise ForbiddenError("La jornada queda a tu nombre: no puedes registrarla por otro técnico.",
                                 code="day_log_for_other")
        await _check_active_user(db, organization_id, tecnico_id)
    ayudantes = []
    for ayudante in dict.fromkeys(data.get("helper_user_ids") or []):
        if ayudante == tecnico_id:
            continue  # el responsable del día no es su propio ayudante
        await _check_active_user(db, organization_id, ayudante)
        ayudantes.append(ayudante)

    log.log_date = fecha
    log.technician_user_id = tecnico_id
    log.crew = _texto(data.get("crew"), maximo=255)
    log.hours = None if data.get("hours") in (None, "") else _q(data["hours"])
    log.work_done = _texto(data.get("work_done"))
    log.progress_note = _texto(data.get("progress_note"), maximo=255)
    log.missing_materials = _texto(data.get("missing_materials"))
    log.next_day_plan = _texto(data.get("next_day_plan"))
    log.incidents = _texto(data.get("incidents"))
    if log_id is None:
        db.add(log)
    await db.flush()

    # Los ayudantes se reemplazan completos: la jornada dice quiénes fueron.
    previos = {h.user_id: h for h in (await db.execute(select(ProjectDayLogHelper).where(
        ProjectDayLogHelper.day_log_id == log.id))).scalars().all()}
    for uid, fila in previos.items():
        if uid not in ayudantes:
            await db.delete(fila)
    for uid in ayudantes:
        if uid not in previos:
            db.add(ProjectDayLogHelper(organization_id=organization_id, day_log_id=log.id, user_id=uid))
    await db.flush()

    anteriores = {linea.id: linea for linea in (await materials_of(db, organization_id, [log.id])).get(log.id, [])}
    enviadas = data.get("materials") or []
    por_id = {linea.get("id"): linea for linea in enviadas if linea.get("id")}

    # Lo que ya no viene en la lista se borra, salvo que haya movido existencia.
    for linea_id, linea in anteriores.items():
        if linea_id not in por_id:
            if linea.movement_id is not None:
                raise InvalidInputError(
                    f"«{linea.description}» ya descontó la camioneta y no se puede quitar del día. "
                    "Registra la devolución a bodega si fue un error.",
                    code="day_log_line_locked")
            await db.delete(linea)

    for posicion, datos in enumerate(enviadas):
        linea_id = datos.get("id")
        if linea_id and linea_id in anteriores:
            linea = anteriores[linea_id]
            if linea.movement_id is not None:
                if _cambios_rechazados(linea, datos):
                    raise InvalidInputError(
                        f"«{linea.description}» ya descontó la camioneta y no se puede corregir desde el diario.",
                        code="day_log_line_locked")
                continue
            await _material_de_linea(db, organization_id, log=log, usuario=user, linea=linea,
                                     datos=datos, posicion=posicion)
            continue
        if linea_id:
            raise NotFoundError("Esa línea del diario no existe.", code="day_log_line_not_found")
        # El id se pone acá porque la línea todavía no está en la sesión (le
        # falta la descripción, que es obligatoria) y el movimiento la necesita
        # para su `source_key`. Se agrega al final, ya completa.
        linea = ProjectDayLogMaterial(id=uuid.uuid4(), organization_id=organization_id, day_log_id=log.id)
        await _material_de_linea(db, organization_id, log=log, usuario=user, linea=linea, datos=datos,
                                 posicion=posicion)
        db.add(linea)

    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.day_log_saved", entity_type="project_day_log",
                             entity_id=str(log.id),
                             after_data={"project_id": str(project.id), "log_date": fecha.isoformat(),
                                         "materials": len(enviadas)})
    await db.commit()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Salidas para las pantallas
# ---------------------------------------------------------------------------

def material_out(linea: ProjectDayLogMaterial, *, nombres: dict) -> dict:
    item = nombres["items"].get(linea.item_id) or {}
    return {
        "id": str(linea.id), "item_id": str(linea.item_id) if linea.item_id else None,
        "item_name": item.get("name"), "sku": item.get("sku"),
        "description": linea.description, "quantity": str(_q(linea.quantity)),
        "unit": linea.unit, "unit_label": ITEM_UNITS.get(linea.unit, linea.unit),
        "location_id": str(linea.location_id) if linea.location_id else None,
        "location_name": nombres["locations"].get(linea.location_id),
        "movement_id": str(linea.movement_id) if linea.movement_id else None,
        "descontada": linea.movement_id is not None,
        "notes": linea.notes,
    }


def day_log_out(log: ProjectDayLog, *, lineas: list[ProjectDayLogMaterial], nombres: dict,
                gastos: dict | None = None, ayudantes: list | None = None) -> dict:
    return {
        "created_by_user_id": str(log.created_by_user_id) if log.created_by_user_id else None,
        "helpers": ayudantes or [],
        "id": str(log.id), "project_id": str(log.project_id),
        "log_date": log.log_date.isoformat() if log.log_date else None,
        "technician_user_id": str(log.technician_user_id) if log.technician_user_id else None,
        "technician_name": nombres["users"].get(log.technician_user_id),
        "crew": log.crew, "hours": None if log.hours is None else str(_q(log.hours)),
        "work_done": log.work_done, "progress_note": log.progress_note,
        "missing_materials": log.missing_materials, "next_day_plan": log.next_day_plan,
        "incidents": log.incidents,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "materials": [material_out(linea, nombres=nombres) for linea in lineas],
        "expenses": {"count": (gastos or {}).get("count", 0),
                     "amount": str(to_money((gastos or {}).get("amount", ZERO)))},
    }


async def day_logs_out(db: AsyncSession, organization_id, logs) -> list[dict]:
    """Las jornadas con su material, los nombres resueltos y los gastos del día."""
    filas = list(logs)
    if not filas:
        return []
    por_jornada = await materials_of(db, organization_id, [log.id for log in filas])
    lineas = [linea for grupo in por_jornada.values() for linea in grupo]
    nombres = await _names(
        db, organization_id,
        item_ids={linea.item_id for linea in lineas if linea.item_id},
        location_ids={linea.location_id for linea in lineas if linea.location_id},
        user_ids={log.technician_user_id for log in filas if log.technician_user_id},
    )
    gastos = await expenses_by_date(db, organization_id, project_id=filas[0].project_id,
                                    fechas={log.log_date for log in filas})
    ayudantes = await helpers_of(db, organization_id, [log.id for log in filas])
    return [day_log_out(log, lineas=por_jornada.get(log.id, []), nombres=nombres,
                        gastos=gastos.get(log.log_date), ayudantes=ayudantes.get(log.id)) for log in filas]


# ---------------------------------------------------------------------------
# Calendario de obras (plan bodega-cierre, fase 5)
# ---------------------------------------------------------------------------

# Un calendario de más de dos meses ya es un reporte.
CALENDAR_MAX_DAYS = 62


async def calendar(db: AsyncSession, organization_id, user, *, date_from: date, date_to: date,
                   technician_id=None) -> dict:
    """Lo que pasó y pasa en las obras, día por día: el turno de cada
    responsable (de cuándo a cuándo estuvo en la obra) y cada jornada
    registrada, con su técnico, sus ayudantes y hasta dónde se avanzó.

    La oficina ve todo y puede filtrar por técnico; el técnico ve solo lo suyo:
    sus turnos y las jornadas donde fue responsable o ayudante.
    """
    from sqlalchemy import and_, or_

    from app.modules.field_ops.access import _sees_all
    from app.modules.field_ops.models import Project, ProjectTechnicianAssignment

    if date_to < date_from:
        raise InvalidInputError("La fecha final va después de la inicial.", code="calendar_range_invalid")
    if (date_to - date_from).days > CALENDAR_MAX_DAYS:
        raise InvalidInputError(f"El calendario muestra hasta {CALENDAR_MAX_DAYS} días.",
                                code="calendar_range_too_long")
    persona = technician_id if _sees_all(user) else user.id

    turnos_stmt = (select(ProjectTechnicianAssignment, Project.title, Project.status)
                   .join(Project, Project.id == ProjectTechnicianAssignment.project_id)
                   .where(ProjectTechnicianAssignment.organization_id == organization_id,
                          ProjectTechnicianAssignment.started_on <= date_to,
                          or_(ProjectTechnicianAssignment.ended_on.is_(None),
                              ProjectTechnicianAssignment.ended_on >= date_from)))
    if persona:
        turnos_stmt = turnos_stmt.where(ProjectTechnicianAssignment.technician_user_id == persona)
    turnos = (await db.execute(turnos_stmt.order_by(ProjectTechnicianAssignment.started_on))).all()

    jornadas_stmt = (select(ProjectDayLog, Project.title)
                     .join(Project, Project.id == ProjectDayLog.project_id)
                     .where(ProjectDayLog.organization_id == organization_id,
                            ProjectDayLog.log_date >= date_from, ProjectDayLog.log_date <= date_to))
    if persona:
        de_ayudante = select(ProjectDayLogHelper.day_log_id).where(ProjectDayLogHelper.user_id == persona)
        jornadas_stmt = jornadas_stmt.where(or_(ProjectDayLog.technician_user_id == persona,
                                                ProjectDayLog.id.in_(de_ayudante)))
    jornadas = (await db.execute(jornadas_stmt.order_by(ProjectDayLog.log_date, Project.title))).all()

    ayudantes = await helpers_of(db, organization_id, [log.id for log, _ in jornadas])
    usuarios = {t.technician_user_id for t, _, _ in turnos} | {log.technician_user_id for log, _ in jornadas
                                                              if log.technician_user_id}
    nombres = {u.id: u.full_name for u in (await db.execute(select(User).where(
        User.id.in_(usuarios)))).scalars().all()} if usuarios else {}
    return {
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "assignments": [{
            "project_id": str(t.project_id), "project_title": titulo, "project_status": getattr(estado, "value", estado),
            "technician_user_id": str(t.technician_user_id), "technician_name": nombres.get(t.technician_user_id),
            "started_on": t.started_on.isoformat(), "ended_on": t.ended_on.isoformat() if t.ended_on else None,
        } for t, titulo, estado in turnos],
        "day_logs": [{
            "id": str(log.id), "project_id": str(log.project_id), "project_title": titulo,
            "log_date": log.log_date.isoformat(),
            "technician_user_id": str(log.technician_user_id) if log.technician_user_id else None,
            "technician_name": nombres.get(log.technician_user_id),
            "helpers": ayudantes.get(log.id, []), "progress_note": log.progress_note,
            "work_done": log.work_done, "next_day_plan": log.next_day_plan,
        } for log, titulo in jornadas],
    }
