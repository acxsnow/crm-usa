"""La orden de instalación: equipos, materiales, agenda y cierre (spec D5.7–D5.9).

- Agendar la orden (técnico y fecha) marca `install_scheduled` en el expediente
  y emite `installation.scheduled`: es la "orden liberada" del cronograma.
- Cerrar la instalación exige el checklist completo y al menos un equipo
  registrado; mueve el expediente a `installed` y congela lo registrado.
- Equipos y materiales no se modifican con la instalación cerrada: es lo que se
  inspecciona y lo que se cobra al programa.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_effective_permissions
from app.modules.cases.models import Case
from app.modules.cases.stages import STAGE_LABELS
from app.modules.field_ops.access import get_visible_project, get_workable_project
from app.modules.field_ops.case_flow import advance_case, case_for_project, mark_substatus
from app.modules.field_ops.catalogs import EQUIPMENT_TYPES
from app.modules.field_ops.checklist import checklist_gaps, ensure_installation_open
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import InstalledEquipment, Project, ProjectMaterial, ProjectStatus
from app.modules.field_ops.reviews import was_reopened_for_correction
from app.modules.users.models import User, UserRole, UserStatus
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

# Una agenda más larga que dos meses no es una agenda: es un reporte, y sin
# límite la consulta crece con la historia de la empresa.
MAX_AGENDA_DAYS = 62
# El historial se consulta en rangos más largos: es lectura de lo cerrado.
MAX_HISTORY_DAYS = 366
# Vistas de la agenda (spec 2026-10-16-agenda-pendientes-historial).
CLOSED_STATUSES = (ProjectStatus.completed, ProjectStatus.cancelled)


# ---------------------------------------------------------------------------
# Equipos instalados
# ---------------------------------------------------------------------------

async def equipment_of(db: AsyncSession, project_id: uuid.UUID) -> list[InstalledEquipment]:
    return list(
        (
            await db.execute(
                select(InstalledEquipment)
                .where(InstalledEquipment.project_id == project_id)
                .order_by(InstalledEquipment.created_at)
            )
        ).scalars().all()
    )


async def list_equipment(db, *, organization_id, user, project_id) -> list[InstalledEquipment]:
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    equipos = await equipment_of(db, project_id)
    from app.modules.warehouse import serials as serial_svc

    cruzados = await serial_svc.linked_to_equipment(db, organization_id, [e.id for e in equipos])
    for equipo in equipos:
        equipo.warehouse_serial_id = cruzados.get(equipo.id)
    return equipos


async def add_equipment(db, *, organization_id, user, project_id, data: dict) -> InstalledEquipment:
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    if data["equipment_type"] not in EQUIPMENT_TYPES:
        raise InvalidInputError(
            f"El tipo de equipo «{data['equipment_type']}» no existe.", code="unknown_equipment_type"
        )
    datos = dict(data)
    serial_id = datos.pop("warehouse_serial_id", None)
    equipo = InstalledEquipment(
        organization_id=organization_id, project_id=project.id, recorded_by_user_id=user.id, **datos
    )
    db.add(equipo)
    _unconfirm(project)
    await db.flush()
    # D-007: el serial se cruza con lo que salió de bodega para esta obra.
    from app.modules.warehouse import serials as serial_svc

    cruzado = await serial_svc.install(db, organization_id=organization_id, user=user, project=project,
                                       equipment=equipo, serial_id=serial_id)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="equipment.recorded", entity_type="InstalledEquipment", entity_id=str(equipo.id),
        after_data={"project_id": str(project.id), "equipment_type": equipo.equipment_type,
                    "brand": equipo.brand, "model": equipo.model, "serial_number": equipo.serial_number},
    )
    await db.commit()
    await db.refresh(equipo)
    equipo.warehouse_serial_id = cruzado.id if cruzado else None
    return equipo


async def delete_equipment(db, *, organization_id, user, equipment_id) -> None:
    equipo = await _owned(db, InstalledEquipment, equipment_id, organization_id, "El equipo no existe.", "equipment_not_found")
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=equipo.project_id)
    ensure_installation_open(project)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="equipment.deleted", entity_type="InstalledEquipment", entity_id=str(equipo.id),
        before_data={"serial_number": equipo.serial_number, "model": equipo.model},
    )
    from app.modules.warehouse import serials as serial_svc

    await serial_svc.uninstall(db, organization_id=organization_id, equipment_id=equipo.id)
    await db.delete(equipo)
    _unconfirm(project)
    await db.commit()


def _unconfirm(project: Project) -> None:
    """La lista cambió: hay que volver a guardarla."""
    project.equipment_confirmed_at = None
    project.equipment_confirmed_by_user_id = None


async def confirm_equipment(db, *, organization_id, user, project_id) -> Project:
    """«Guardar equipos instalados»: el técnico da por terminada la lista."""
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    equipos = await equipment_of(db, project.id)
    if not equipos:
        raise InvalidInputError("Registra al menos un equipo antes de guardar la lista.", code="no_equipment")
    project.equipment_confirmed_at = datetime.now(timezone.utc)
    project.equipment_confirmed_by_user_id = user.id
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="equipment.confirmed", entity_type="Project", entity_id=str(project.id),
        after_data={"equipment_count": len(equipos)},
    )
    await db.commit()
    await db.refresh(project)
    return project


# ---------------------------------------------------------------------------
# Materiales de la orden
# ---------------------------------------------------------------------------

async def list_materials(db, *, organization_id, user, project_id) -> list[ProjectMaterial]:
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return list(
        (
            await db.execute(
                select(ProjectMaterial)
                .where(ProjectMaterial.project_id == project_id)
                .order_by(ProjectMaterial.created_at)
            )
        ).scalars().all()
    )


async def add_material(db, *, organization_id, user, project_id, data: dict) -> ProjectMaterial:
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    material = ProjectMaterial(organization_id=organization_id, project_id=project.id, **data)
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


async def delete_material(db, *, organization_id, user, material_id) -> None:
    material = await _owned(db, ProjectMaterial, material_id, organization_id, "El material no existe.", "material_not_found")
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=material.project_id)
    ensure_installation_open(project)
    # Lo que entregó bodega queda: es el rastro de la salida y el costo real de
    # la obra. Si sobró, se registra la devolución a bodega.
    if material.warehouse_release_line_id is not None:
        raise ConflictError("Ese material lo entregó bodega: no se quita de la orden. Si sobró, regístralo como "
                            "devolución a bodega.", code="material_from_warehouse")
    await db.delete(material)
    await db.commit()


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

async def _record_assignment(db, *, project: Project, technician_id: uuid.UUID, starts_on: date, user) -> None:
    """Historial de responsables (plan bodega-cierre, fase 5). Cambiar de
    técnico cierra el turno del anterior el día que empieza el nuevo: el
    anterior conserva la obra en solo lectura. Volver a liberar con el mismo
    técnico solo mueve la fecha de inicio de su turno."""
    from sqlalchemy import select

    from app.modules.field_ops.models import ProjectTechnicianAssignment

    abierto = (await db.execute(select(ProjectTechnicianAssignment).where(
        ProjectTechnicianAssignment.project_id == project.id,
        ProjectTechnicianAssignment.ended_on.is_(None)))).scalars().first()
    if abierto is not None and abierto.technician_user_id == technician_id:
        if not await db.scalar(select(ProjectTechnicianAssignment.id).where(
                ProjectTechnicianAssignment.project_id == project.id,
                ProjectTechnicianAssignment.id != abierto.id)):
            abierto.started_on = starts_on  # todavía no rotó: se corrige la fecha
        return
    if abierto is not None:
        if starts_on < abierto.started_on:
            # Se rota antes de que empezara el turno del anterior: no alcanzó a
            # trabajarla. Su turno se corre al día del cambio para que no
            # termine después de que empieza el nuevo (D-011); conserva la fila
            # y con ella la obra en solo lectura.
            abierto.started_on = starts_on
        abierto.ended_on = max(starts_on, abierto.started_on)
    db.add(ProjectTechnicianAssignment(organization_id=project.organization_id, project_id=project.id,
                                       technician_user_id=technician_id, started_on=starts_on,
                                       assigned_by_user_id=user.id))


async def assignments_of(db, *, organization_id, project_id) -> list[dict]:
    """Quién fue responsable de la obra, del primero al de hoy, con su nombre."""
    from sqlalchemy import select

    from app.modules.field_ops.models import ProjectTechnicianAssignment

    filas = (await db.execute(select(ProjectTechnicianAssignment, User.full_name)
                              .join(User, User.id == ProjectTechnicianAssignment.technician_user_id)
                              .where(ProjectTechnicianAssignment.organization_id == organization_id,
                                     ProjectTechnicianAssignment.project_id == project_id)
                              .order_by(ProjectTechnicianAssignment.started_on,
                                        ProjectTechnicianAssignment.created_at))).all()
    return [{"technician_user_id": str(a.technician_user_id), "technician_name": nombre,
             "started_on": a.started_on.isoformat(), "ended_on": a.ended_on.isoformat() if a.ended_on else None,
             "current": a.ended_on is None} for a, nombre in filas]


def require_assign_permission(user) -> None:
    """Asignar o cambiar el técnico de una obra exige `projects.assign`
    (D-014: el permiso existía y no hacía nada); mover solo la fecha, no."""
    if "projects.assign" not in get_effective_permissions(user):
        raise ForbiddenError("No tienes permiso para asignar técnicos a las obras.", code="assign_not_allowed")


async def schedule_installation(
    db, *, organization_id, user, project_id, technician_id: uuid.UUID, scheduled_date: date
) -> Project:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    # Con el límite de visitas fallidas alcanzado decide Administración (D-001).
    from app.modules.field_ops.visits import ensure_can_reschedule

    await ensure_can_reschedule(db, project)
    if scheduled_date < await org_today(db, organization_id):
        raise InvalidInputError("No se puede agendar una instalación en una fecha pasada.", code="schedule_in_past")
    await _require_installer(db, organization_id=organization_id, technician_id=technician_id)
    if project.primary_technician_user_id != technician_id:
        require_assign_permission(user)

    antes = {"technician": str(project.primary_technician_user_id) if project.primary_technician_user_id else None,
             "scheduled_date": project.scheduled_date.isoformat() if project.scheduled_date else None}
    await _record_assignment(db, project=project, technician_id=technician_id, starts_on=scheduled_date, user=user)
    project.primary_technician_user_id = technician_id
    project.scheduled_date = scheduled_date
    if project.status in (ProjectStatus.planning, ProjectStatus.scheduled):
        project.status = ProjectStatus.scheduled
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.installation_scheduled", entity_type="Project", entity_id=str(project.id),
        before_data=antes,
        after_data={"technician": str(technician_id), "scheduled_date": scheduled_date.isoformat()},
    )
    project_id_, org_ = project.id, project.organization_id
    # Se puede instalar antes de tener el permiso (así se trabaja en la
    # práctica, spec D6.4). Si el mapa de etapas ya tiene Aprobado → Listo
    # para instalar (pedido a José), liberar la orden lleva el expediente ahí;
    # si no, `advance_case` no hace nada y el permiso sigue siendo el camino.
    await advance_case(db, project=project, to_stage="ready_to_install", user=user,
                       reason="Orden liberada antes del permiso municipal")
    await mark_substatus(db, project=project, stage="ready_to_install", substatus="install_scheduled",
                         user=user, reason=f"Instalación agendada para el {scheduled_date.isoformat()}")
    await db.commit()
    domain_events.emit(
        "installation.scheduled",
        {"project_id": str(project_id_), "organization_id": str(org_),
         "technician_user_id": str(technician_id), "scheduled_date": scheduled_date.isoformat()},
    )
    return await _reload(db, project_id_)


def _validar_rango(date_from: date | None, date_to: date | None, maximo: int) -> None:
    if date_from is None or date_to is None:
        raise InvalidInputError("Indica la fecha inicial y la final.", code="agenda_range_required")
    if date_to < date_from:
        raise InvalidInputError("La fecha final es anterior a la inicial.", code="agenda_range_inverted")
    if (date_to - date_from) > timedelta(days=maximo):
        raise InvalidInputError(f"La agenda se consulta en rangos de hasta {maximo} días.",
                                code="agenda_range_too_long")


def agenda_query(*, organization_id, user, date_from: date | None, date_to: date | None,
                 technician_id: uuid.UUID | None, view: str | None = None):
    """La consulta de la agenda, para paginarla en la base.

    - `pending`: lo que falta por hacer hasta `date_to`, **sin límite hacia
      atrás** (una orden atrasada sin cerrar sale aunque sea de hace semanas),
      de la más vieja a la más nueva.
    - `history`: lo cerrado o cancelado en el rango, de lo más nuevo a lo más viejo.
    - Sin `view`: el rango de siempre (hasta 62 días, todos los estados).
    """
    stmt = select(Project, Case).outerjoin(Case, Case.id == Project.case_id).where(
        Project.organization_id == organization_id, Project.scheduled_date.is_not(None))
    if view == "pending":
        if date_to is None:
            raise InvalidInputError("Indica hasta qué fecha ver lo pendiente.", code="agenda_range_required")
        stmt = stmt.where(Project.status.not_in(CLOSED_STATUSES), Project.scheduled_date <= date_to) \
            .order_by(Project.scheduled_date, Project.created_at, Project.id)
    elif view == "history":
        _validar_rango(date_from, date_to, MAX_HISTORY_DAYS)
        stmt = stmt.where(Project.status.in_(CLOSED_STATUSES), Project.scheduled_date >= date_from,
                          Project.scheduled_date <= date_to) \
            .order_by(Project.scheduled_date.desc(), Project.created_at.desc(), Project.id)
    elif view is None:
        _validar_rango(date_from, date_to, MAX_AGENDA_DAYS)
        stmt = stmt.where(Project.scheduled_date >= date_from, Project.scheduled_date <= date_to) \
            .order_by(Project.scheduled_date, Project.created_at, Project.id)
    else:
        raise InvalidInputError("La vista de la agenda es «pending» o «history».", code="agenda_unknown_view")
    if "dispatch.manage" not in get_effective_permissions(user):
        # El técnico ve su agenda, y solo la suya, pida el filtro que pida.
        stmt = stmt.where(Project.primary_technician_user_id == user.id)
    elif technician_id is not None:
        stmt = stmt.where(Project.primary_technician_user_id == technician_id)
    return stmt


def days_late(project: Project, today: date) -> int | None:
    """Días de atraso de una orden sin cerrar con fecha anterior a hoy."""
    if project.status in CLOSED_STATUSES or project.scheduled_date is None or project.scheduled_date >= today:
        return None
    return (today - project.scheduled_date).days


# ---------------------------------------------------------------------------
# Cierre
# ---------------------------------------------------------------------------

async def installation_gaps(db: AsyncSession, *, project: Project) -> list[str]:
    """Todo lo que falta para cerrar, en palabras del técnico."""
    faltan = await checklist_gaps(db, project=project)
    if not await equipment_of(db, project.id):
        faltan.append("Registrar al menos un equipo instalado (marca, modelo y serial)")
    elif project.equipment_confirmed_at is None:
        faltan.append("Guardar la lista de equipos instalados")
    return faltan


def mark_project_completed(project: Project, today: date) -> None:
    project.status = ProjectStatus.completed
    project.completed_date = project.completed_date or today


async def close_installation(db, *, organization_id, user, project_id, observations: str | None) -> Project:
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)

    faltan = await installation_gaps(db, project=project)
    if faltan:
        raise InvalidInputError(
            "No se puede cerrar la instalación. Falta: " + "; ".join(faltan) + ".",
            code="installation_incomplete",
        )

    case = await case_for_project(db, project)
    # Un acta devuelta al técnico (o reabierta por una inspección fallida) se
    # vuelve a cerrar aunque el expediente esté más adelante: se corrige el
    # acta, no la etapa (módulo 6, spec D6.6).
    corrigiendo = was_reopened_for_correction(project) and case is not None and case.stage_code != "ready_to_install"
    if case is not None and case.stage_code != "ready_to_install" and not corrigiendo:
        raise ConflictError(
            f"El expediente está en «{STAGE_LABELS[case.stage_code]}»; la instalación se "
            "cierra cuando está en «Listo para instalar».",
            code="case_not_ready_to_install",
        )

    if observations:
        project.notes = (project.notes + "\n\n" if project.notes else "") + f"Cierre: {observations.strip()}"
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.installation_closed", entity_type="Project", entity_id=str(project.id),
        after_data={"case_id": str(case.id) if case else None},
    )
    project_id_ = project.id
    if case is None or corrigiendo:
        # Proyecto heredado sin expediente, o corrección de un acta devuelta:
        # el expediente no se mueve.
        mark_project_completed(project, await org_today(db, organization_id))
    else:
        # El efecto de `installed` marca el proyecto como completado, así el
        # camino manual y este terminan igual.
        await advance_case(db, project=project, to_stage="installed", user=user,
                           reason="Instalación cerrada por el técnico")
    await db.commit()
    domain_events.emit(
        "installation.closed",
        {"project_id": str(project_id_), "organization_id": str(organization_id),
         "closed_by_user_id": str(user.id)},
    )
    return await _reload(db, project_id_)


async def on_installed(*, db, case, actor_id, reason=None) -> None:
    """Efecto al entrar a `installed`, venga del comando o del camino manual."""
    project = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalar_one_or_none()
    if project is not None:
        mark_project_completed(project, await org_today(db, case.organization_id))


# ---------------------------------------------------------------------------

# Quién puede recibir una orden: marca el checklist en campo y tiene agenda
# propia. Administración también marca checklists, pero no sale a instalar.
INSTALLER_PERMISSIONS = {"checklists.complete", "dispatch.read_own"}


def _can_install(user) -> bool:
    return INSTALLER_PERMISSIONS <= get_effective_permissions(user)


async def list_installers(db, *, organization_id) -> list[User]:
    usuarios = (
        await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.organization_id == organization_id, User.status == UserStatus.active)
            .order_by(User.full_name)
        )
    ).scalars().all()
    return [u for u in usuarios if _can_install(u)]


async def _require_installer(db, *, organization_id, technician_id) -> None:
    tecnico = (
        await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == technician_id, User.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if tecnico is None or tecnico.status != UserStatus.active:
        raise InvalidInputError("El técnico no existe o no está activo.", code="technician_not_found")
    if not _can_install(tecnico):
        raise InvalidInputError(
            f"{tecnico.full_name} no tiene un rol que pueda ejecutar instalaciones.",
            code="user_cannot_install",
        )


async def _owned(db, model, obj_id, organization_id, message, code):
    obj = (
        await db.execute(select(model).where(model.id == obj_id, model.organization_id == organization_id))
    ).scalar_one_or_none()
    if obj is None:
        raise NotFoundError(message, code=code)
    return obj


async def _reload(db, project_id) -> Project:
    db.expire_all()
    return (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
