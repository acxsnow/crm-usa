"""Endpoints del expediente.

El reparto de visibilidad vive aquí, no en la pantalla: quien tiene
`cases.read_all` ve todos los expedientes de su organización; quien solo tiene
`cases.read_own` ve los que abrió. Esconder filas en el frontend no impediría
pedirlas por HTTP.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_effective_permissions,
    get_organization_id,
    require_any_permission,
    require_permission,
)
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case
from app.modules.cases.schemas import (
    CaseActivityItem,
    CaseCreateRequest,
    CaseResponse,
    CaseStageEventResponse,
    CaseSubstatusRequest,
    CaseTransitionRequest,
    StageCatalogResponse,
    StageInfo,
)
from app.modules.users.models import User
from app.shared.pagination import paginate, pagination_params

router = APIRouter(prefix="/cases", tags=["cases"])


def _to_response(case: Case) -> CaseResponse:
    return CaseResponse.model_validate(case, from_attributes=True)


# `/stages` va ANTES de `/{case_id}`: si no, FastAPI intentaría interpretar
# "stages" como un UUID y respondería 422.
@router.get("/stages", response_model=StageCatalogResponse)
async def stage_catalog(
    current_user: User = Depends(
        require_any_permission("cases.read_own", "cases.read_all", "cases.create")
    ),
):
    """El mapa del flujo, para que el frontend no duplique códigos ni etiquetas."""
    return StageCatalogResponse(
        stages=[
            StageInfo(
                code=code,
                label=stages.STAGE_LABELS[code],
                is_initial=code in stages.INITIAL_STAGES,
                substatuses=sorted(stages.SUBSTATUSES.get(code, set())),
                allowed_next=sorted(stages.ALLOWED_TRANSITIONS[code]),
            )
            for code in stages.STAGES
        ]
    )


# `/activity` también va antes de `/{case_id}`, por la misma razón que `/stages`.
@router.get("/activity", response_model=list[CaseActivityItem])
async def case_activity(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
    limit: int = Query(8, ge=1, le=50),
):
    """Actividad reciente para el Inicio: los últimos cambios de etapa que el
    usuario puede ver (el vendedor, los de sus expedientes)."""
    propios = None if "cases.read_all" in get_effective_permissions(current_user) else current_user.id
    return await case_service.recent_activity(
        db, organization_id=organization_id, only_salesperson_id=propios, limit=limit
    )


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    response: Response,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
    stage_code: str | None = Query(None),
    q: str | None = Query(None, description="Busca en la dirección o el número de expediente"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = (
        select(Case)
        .where(Case.organization_id == organization_id)
        .order_by(Case.created_at.desc())
    )

    # El filtro por dueño es parte de la consulta. `cases.read_all` lo levanta.
    if "cases.read_all" not in get_effective_permissions(current_user):
        stmt = stmt.where(Case.assigned_salesperson_id == current_user.id)

    if stage_code:
        stmt = stmt.where(Case.stage_code == stage_code)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Case.normalized_address.ilike(like) | Case.case_number.ilike(like)
        )

    limit, offset = pagination
    filas = await paginate(db, stmt, limit=limit, offset=offset, response=response)
    return [_to_response(c) for c in filas]


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    payload: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("cases.create")),
):
    """Abre el expediente de una puerta tocada."""
    case = await case_service.create_case(
        db,
        organization_id=organization_id,
        actor_id=current_user.id,
        **payload.model_dump(),
    )
    return _to_response(case)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
):
    case = await case_service.get_case_or_404(
        db, organization_id=organization_id, case_id=case_id
    )
    await _require_can_see(current_user, case)
    return _to_response(case)


@router.get("/{case_id}/events", response_model=list[CaseStageEventResponse])
async def list_case_events(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("cases.read_own", "cases.read_all")),
):
    """El historial completo de etapas de un expediente."""
    case = await case_service.get_case_or_404(
        db, organization_id=organization_id, case_id=case_id
    )
    await _require_can_see(current_user, case)
    return await case_service.list_stage_events(
        db, organization_id=organization_id, case_id=case.id
    )


@router.post("/{case_id}/transition", response_model=CaseResponse)
async def transition_case(
    case_id: uuid.UUID,
    payload: CaseTransitionRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(
        require_any_permission(
            "cases.create", "cases.submit", "cases.review", "cases.approve",
            "cases.close_admin", "permits.manage", "dispatch.manage",
            "checklists.complete", "inspections.manage", "billing.submit",
            "invoices.record_payment",
        )
    ),
):
    """Mueve el expediente de etapa.

    El permiso de aquí es solo la puerta gruesa: quién puede mover *algo*. Quién
    puede entrar a **esta** etapa lo decide `transition()` con el mapa
    `STAGE_PERMISSION`, que también comprueba que el expediente sea suyo. Antes
    la puerta gruesa era el único control y un vendedor aprobaba el propio
    (SEG-07)."""
    case = await case_service.get_case_or_404(
        db, organization_id=organization_id, case_id=case_id
    )
    # Primero el permiso (lo valida `transition()` con 403); el motivo solo se
    # le pide a quien sí puede cerrar o rechazar.
    from app.modules.cases import stages as _stages

    puede = _stages.STAGE_PERMISSION.get(payload.to_stage) in get_effective_permissions(current_user)
    if puede and payload.to_stage in ("closed", "rejected") and not (payload.reason or "").strip():
        # Cerrar o rechazar sin motivo deja el historial sin explicación: es lo
        # primero que se pregunta en un reclamo o en el reporte de rechazos.
        from app.shared.errors import InvalidInputError

        raise InvalidInputError("Escribe el motivo.", code="reason_required")
    if payload.to_stage == "approved":
        # Datos que entrega el programa al aprobar; se guardan con la misma
        # transacción del cambio de etapa (`transition()` hace el commit).
        if payload.approval_code:
            case.approval_code = payload.approval_code.strip()
        if payload.application_number:
            case.application_number = payload.application_number.strip()
    case = await case_service.transition(
        db,
        case=case,
        to_stage=payload.to_stage,
        actor_id=current_user.id,
        actor_permissions=get_effective_permissions(current_user),
        reason=payload.reason,
        substatus=payload.substatus,
    )
    return _to_response(case)


@router.post("/{case_id}/substatus", response_model=CaseResponse)
async def set_case_substatus(
    case_id: uuid.UUID,
    payload: CaseSubstatusRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(
        require_any_permission("cases.submit", "cases.review", "cases.approve")
    ),
):
    """Cambia el sub-estado sin mover de etapa. Es lo que usa la devolución."""
    case = await case_service.get_case_or_404(
        db, organization_id=organization_id, case_id=case_id
    )
    case = await case_service.set_substatus(
        db,
        case=case,
        substatus=payload.substatus,
        actor_id=current_user.id,
        actor_permissions=get_effective_permissions(current_user),
        reason=payload.reason,
    )
    return _to_response(case)


async def _require_can_see(current_user: User, case: Case) -> None:
    """404 —no 403— cuando alguien con `cases.read_own` pide uno ajeno.

    Un 403 confirmaría que ese expediente existe, que es justo lo que no debe
    saber: es la misma razón por la que un expediente de otra organización
    también responde 404."""
    from app.shared.errors import NotFoundError

    permisos = get_effective_permissions(current_user)
    if "cases.read_all" in permisos:
        return
    if case.assigned_salesperson_id != current_user.id:
        raise NotFoundError("El expediente no existe.", code="case_not_found")
