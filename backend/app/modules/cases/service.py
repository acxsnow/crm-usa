"""Reglas de negocio del expediente.

**Este es el único archivo del proyecto que puede escribir `stage_code`.** Hay
un test que recorre `app/` y lo verifica (`test_cases_service.py`). La razón: si
un endpoint asignara la etapa directo, `case_stage_events` quedaría incompleto,
y ese historial es la única fuente de los reportes del PDF §7 —días por etapa,
tiempo hasta aprobación, tasa de rechazo, productividad por zona—. A diferencia
de casi todo lo demás, **no se puede reconstruir después**.

Cada cadena registra sus propias guardas con `stages.register_guard()` desde su
paquete; nadie edita el archivo de otro.
"""
import inspect
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases import stages
from app.modules.cases.models import Case, CaseStageEvent
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.shared.normalize import normalize_address


async def _next_case_number(db: AsyncSession, organization_id: uuid.UUID) -> str:
    """`CASE-AAAA-NNNN`, correlativo por organización y año.

    Se cuenta sobre los expedientes de esa organización y ese año en vez de
    llevar un contador aparte: una tabla de secuencias más es una tabla más que
    puede desincronizarse. Con la restricción única
    (`organization_id`, `case_number`), dos creaciones simultáneas hacen que una
    falle con `IntegrityError` —que el manejador global traduce a 409— en vez de
    duplicar el número en silencio."""
    anio = datetime.now(timezone.utc).year
    prefijo = f"CASE-{anio}-"
    usados = (
        await db.execute(
            select(func.count(Case.id)).where(
                Case.organization_id == organization_id,
                Case.case_number.like(f"{prefijo}%"),
            )
        )
    ).scalar_one()
    return f"{prefijo}{usados + 1:04d}"


def _record_event(
    db: AsyncSession,
    *,
    case: Case,
    from_stage: str | None,
    to_stage: str,
    from_substatus: str | None,
    to_substatus: str | None,
    reason: str | None,
    actor_id: uuid.UUID | None,
) -> None:
    db.add(
        CaseStageEvent(
            organization_id=case.organization_id,
            case_id=case.id,
            from_stage_code=from_stage,
            to_stage_code=to_stage,
            from_substatus_code=from_substatus,
            to_substatus_code=to_substatus,
            reason=reason,
            actor_user_id=actor_id,
            occurred_at=datetime.now(timezone.utc),
        )
    )


def _require_stage_permission(
    *,
    to_stage: str,
    actor_id: uuid.UUID | None,
    actor_permissions: frozenset[str] | set[str],
    case: Case,
    required: str | None = None,
) -> None:
    """Dos controles, y los dos faltaban (SEG-07).

    1. **Separación de funciones**: cada etapa exige su permiso. Antes la ruta
       admitía a quien tuviera *cualquiera* de los permisos del expediente y
       después aceptaba cualquier transición del mapa, así que un vendedor
       aprobaba el suyo.
    2. **Dueño**: quien solo puede ver los propios (`cases.read_own`) tampoco
       puede mover los ajenos. La consulta ya lo comprobaba; el cambio de etapa
       no.
    """
    # Primero que la etapa exista: `to_stage` llega del cliente y una etapa
    # inventada haría estallar el mapa de permisos con un 500 en vez de decir
    # que el dato es inválido.
    if to_stage not in stages.STAGES:
        raise InvalidInputError(
            f"La etapa «{to_stage}» no existe.", code="unknown_stage"
        )

    if actor_permissions == stages.SYSTEM_ACTOR:
        return

    requerido = required or stages.permission_for(to_stage)
    if requerido not in actor_permissions:
        raise ForbiddenError(
            f"No tienes permiso para pasar un expediente a "
            f"«{stages.STAGE_LABELS[to_stage]}».",
            code="stage_not_allowed_for_role",
        )

    if "cases.read_all" not in actor_permissions and case.assigned_salesperson_id != actor_id:
        # 404 y no 403: confirmar que existe ya sería revelar de más, igual que
        # en la consulta.
        raise NotFoundError("El expediente no existe.", code="case_not_found")


async def create_case(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    stage_code: str,
    source: str = "visit",
    address_street: str | None = None,
    address_unit: str | None = None,
    address_city: str | None = None,
    address_state: str | None = None,
    address_zip: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    customer_id: uuid.UUID | None = None,
    program_id: uuid.UUID | None = None,
    assigned_salesperson_id: uuid.UUID | None = None,
) -> Case:
    """Abre un expediente para una puerta.

    `stage_code` tiene que ser una de las cuatro etapas iniciales: el resultado
    del primer toque. Nacer en mitad del flujo saltaría todo el historial y no
    habría forma de saber cuándo se envió ni quién lo aprobó."""
    if stage_code not in stages.INITIAL_STAGES:
        raise InvalidInputError(
            f"Un expediente solo puede abrirse en: "
            f"{', '.join(sorted(stages.INITIAL_STAGES))}.",
            code="invalid_initial_stage",
        )

    ahora = datetime.now(timezone.utc)
    case = Case(
        organization_id=organization_id,
        case_number=await _next_case_number(db, organization_id),
        source=source,
        stage_code=stage_code,
        address_street=address_street,
        address_unit=address_unit,
        address_city=address_city,
        address_state=address_state,
        address_zip=address_zip,
        latitude=latitude,
        longitude=longitude,
        normalized_address=normalize_address(address_street, address_unit, address_city, address_zip),
        customer_id=customer_id,
        program_id=program_id,
        assigned_salesperson_id=assigned_salesperson_id or actor_id,
        # Si alguien abrió la puerta, ya hubo contacto.
        first_contact_at=ahora if stage_code != "no_contact" else None,
    )
    db.add(case)
    await db.flush()

    _record_event(
        db,
        case=case,
        from_stage=None,
        to_stage=stage_code,
        from_substatus=None,
        to_substatus=None,
        reason=None,
        actor_id=actor_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_id,
        action="cases.created",
        entity_type="case",
        entity_id=str(case.id),
        after_data={"case_number": case.case_number, "stage_code": stage_code},
    )
    await db.commit()
    await db.refresh(case)
    domain_events.emit(
        "case.created",
        {"case_id": str(case.id), "organization_id": str(organization_id), "stage": stage_code},
    )
    return case


async def transition(
    db: AsyncSession,
    *,
    case: Case,
    to_stage: str,
    actor_id: uuid.UUID | None,
    actor_permissions: frozenset[str] | set[str],
    reason: str | None = None,
    substatus: str | None = None,
) -> Case:
    """Mueve el expediente de etapa. **La única puerta de entrada.**

    En orden: comprueba que quien actúa pueda entrar a esa etapa y que el
    expediente sea suyo, valida contra el mapa, corre las guardas, cambia la
    etapa, escribe la fecha hito, inserta el historial, audita y emite el
    evento. Si algo falla antes del `commit`, no queda nada a medias.

    `actor_permissions` es obligatorio a propósito: era opcional y eso dejaba
    que cualquier llamador lo olvidara y se saltara el control sin enterarse
    (hallazgo SEG-07). Para migraciones y tareas del sistema se pasa
    `stages.SYSTEM_ACTOR`."""
    desde = case.stage_code
    _require_stage_permission(
        to_stage=to_stage, actor_id=actor_id, actor_permissions=actor_permissions, case=case
    )
    if not stages.is_allowed(desde, to_stage):
        raise InvalidInputError(
            f"No se puede pasar de «{stages.STAGE_LABELS[desde]}» a "
            f"«{stages.STAGE_LABELS[to_stage]}».",
            code="invalid_transition",
        )

    for guard in stages.guards_for(desde, to_stage):
        # Las guardas pueden ser `async`: las del tramo de campo consultan la
        # base (checklist completo, permisos vigentes) y con una sesión
        # asíncrona no hay otra forma. Las síncronas siguen igual (COD-08).
        resultado = guard(db=db, case=case, actor_id=actor_id, reason=reason)
        if inspect.isawaitable(resultado):
            await resultado

    if substatus is not None and substatus not in stages.SUBSTATUSES.get(to_stage, set()):
        raise InvalidInputError(
            f"El sub-estado «{substatus}» no pertenece a «{stages.STAGE_LABELS[to_stage]}».",
            code="invalid_substatus",
        )

    substatus_anterior = case.substatus_code
    case.stage_code = to_stage
    # El sub-estado no sobrevive al cambio de etapa: un expediente aprobado y
    # «devuelto» a la vez no significa nada.
    case.substatus_code = substatus
    case.stage_reason = reason

    campo_fecha = stages.STAGE_MILESTONE.get(to_stage)
    if campo_fecha and getattr(case, campo_fecha) is None:
        setattr(case, campo_fecha, datetime.now(timezone.utc))

    # Los efectos corren con la etapa ya cambiada y antes del commit: ven el
    # hecho consumado, y si alguno falla nada queda a medias.
    for effect in stages.effects_for(desde, to_stage):
        await effect(db=db, case=case, actor_id=actor_id, reason=reason)

    _record_event(
        db,
        case=case,
        from_stage=desde,
        to_stage=to_stage,
        from_substatus=substatus_anterior,
        to_substatus=substatus,
        reason=reason,
        actor_id=actor_id,
    )
    await record_audit_event(
        db,
        organization_id=case.organization_id,
        actor_user_id=actor_id,
        action="cases.stage_changed",
        entity_type="case",
        entity_id=str(case.id),
        before_data={"stage_code": desde, "substatus_code": substatus_anterior},
        after_data={"stage_code": to_stage, "substatus_code": substatus, "reason": reason},
    )
    await db.commit()
    await db.refresh(case)

    domain_events.emit(
        "case.stage_changed",
        {
            "case_id": str(case.id),
            "organization_id": str(case.organization_id),
            "case_number": case.case_number,
            "from_stage": desde,
            "to_stage": to_stage,
            "reason": reason,
        },
    )
    return case


async def set_substatus(
    db: AsyncSession,
    *,
    case: Case,
    substatus: str,
    actor_id: uuid.UUID | None,
    actor_permissions: frozenset[str] | set[str],
    reason: str | None = None,
) -> Case:
    """Cambia el sub-estado sin mover de etapa.

    Es lo que usa la devolución: Administración devuelve el expediente al
    vendedor y el sub-estado pasa a `returned`, pero la etapa sigue siendo
    `pending_approval`. Si retrocediera de etapa, el contador de días de
    aprobación se reiniciaría y el reporte de tiempos mentiría."""
    _require_stage_permission(
        to_stage=case.stage_code,
        actor_id=actor_id,
        actor_permissions=actor_permissions,
        case=case,
        required=stages.substatus_permission(case.stage_code, substatus)
        if substatus in stages.SUBSTATUSES.get(case.stage_code, set()) else None,
    )
    permitidos = stages.SUBSTATUSES.get(case.stage_code, set())
    if substatus not in permitidos:
        raise InvalidInputError(
            f"El sub-estado «{substatus}» no pertenece a "
            f"«{stages.STAGE_LABELS[case.stage_code]}».",
            code="invalid_substatus",
        )

    anterior = case.substatus_code
    case.substatus_code = substatus
    if reason is not None:
        case.stage_reason = reason

    _record_event(
        db,
        case=case,
        from_stage=case.stage_code,
        to_stage=case.stage_code,
        from_substatus=anterior,
        to_substatus=substatus,
        reason=reason,
        actor_id=actor_id,
    )
    await record_audit_event(
        db,
        organization_id=case.organization_id,
        actor_user_id=actor_id,
        action="cases.substatus_changed",
        entity_type="case",
        entity_id=str(case.id),
        before_data={"substatus_code": anterior},
        after_data={"substatus_code": substatus, "reason": reason},
    )
    await db.commit()
    await db.refresh(case)

    domain_events.emit(
        "case.substatus_changed",
        {
            "case_id": str(case.id),
            "organization_id": str(case.organization_id),
            "stage": case.stage_code,
            "substatus": substatus,
        },
    )
    return case


async def get_case_or_404(
    db: AsyncSession, *, organization_id: uuid.UUID, case_id: uuid.UUID
) -> Case:
    """404 también cuando el expediente es de otra organización: responder algo
    distinto revelaría qué identificadores están en uso."""
    case = (
        await db.execute(
            select(Case).where(Case.id == case_id, Case.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if case is None:
        raise NotFoundError("El expediente no existe.", code="case_not_found")
    return case


async def recent_activity(
    db: AsyncSession, *, organization_id: uuid.UUID, only_salesperson_id: uuid.UUID | None, limit: int
) -> list[dict]:
    """Los últimos cambios de etapa de la organización, para el Inicio.

    Sale del historial (`case_stage_events`), el mismo que alimenta los
    reportes. `only_salesperson_id` deja solo los expedientes de ese vendedor:
    quien no tiene `cases.read_all` ve su actividad, no la de los demás."""
    from app.modules.crm.models import Customer
    from app.modules.users.models import User

    stmt = (
        select(CaseStageEvent, Case, Customer.legal_name, User.full_name)
        .join(Case, Case.id == CaseStageEvent.case_id)
        .outerjoin(Customer, Customer.id == Case.customer_id)
        .outerjoin(User, User.id == CaseStageEvent.actor_user_id)
        .where(CaseStageEvent.organization_id == organization_id, Case.organization_id == organization_id)
        .order_by(CaseStageEvent.occurred_at.desc(), CaseStageEvent.id.desc())
        .limit(limit)
    )
    if only_salesperson_id is not None:
        stmt = stmt.where(Case.assigned_salesperson_id == only_salesperson_id)
    filas = (await db.execute(stmt)).all()
    return [
        {
            "case_id": case.id,
            "case_number": case.case_number,
            "customer_name": cliente,
            "address": ", ".join(p for p in (case.address_street, case.address_unit) if p) or None,
            "to_stage_code": evento.to_stage_code,
            "label": stages.event_label(evento.to_stage_code, evento.to_substatus_code),
            "reason": evento.reason,
            "actor_name": actor,
            "occurred_at": evento.occurred_at,
        }
        for evento, case, cliente, actor in filas
    ]


async def list_stage_events(
    db: AsyncSession, *, organization_id: uuid.UUID, case_id: uuid.UUID
) -> list[CaseStageEvent]:
    return list(
        (
            await db.execute(
                select(CaseStageEvent)
                .where(
                    CaseStageEvent.case_id == case_id,
                    CaseStageEvent.organization_id == organization_id,
                )
                .order_by(CaseStageEvent.occurred_at, CaseStageEvent.id)
            )
        )
        .scalars()
        .all()
    )
