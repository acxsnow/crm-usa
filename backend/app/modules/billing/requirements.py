"""Requisitos para radicar un cobro (spec D6.2 y §5).

El checklist de cada programa sale del proceso real de Delta HVAC (definido
con Mateo el 28 de septiembre): documentos → cliente → T&C → aprobación →
instalación programada → instalación → información de los técnicos →
confirmación → factura y papeleo → cobro, "solo si todo está bien".

Dos tipos:
- `auto`: el sistema lo comprueba con datos que ya existen (expediente,
  acta del módulo 5, permisos, inspección, factura). Su regla vive en
  `AUTO_RULES` y se evalúa en `evaluate_requirements()`.
- `manual`: una persona lo confirma en cada cobro (queda quién y cuándo).
  Documentos y T&C son manuales hasta que la Cadena A termine los módulos 2 y
  3; entonces pasan a automáticos sin cambiar el checklist de nadie.
"""

# Reglas automáticas disponibles: código → etiqueta por defecto.
AUTO_RULES: dict[str, str] = {
    "client_captured": "Cliente captado",
    "program_approved": "Aprobación del programa con código",
    "installation_scheduled": "Instalación programada",
    "installation_done": "Instalación realizada (acta cerrada)",
    "technician_info_complete": "Información de los técnicos completa",
    "technician_info_confirmed": "Información técnica recibida y confirmada",
    "permit_filed": "Permiso municipal radicado",
    "permit_approved": "Permiso municipal aprobado",
    "inspection_passed": "Inspección aprobada con firma del inspector",
    "gas_to_electric": "Evidencia de reemplazo de gas por eléctrico",
    "invoice_issued": "Factura emitida",
}

# El checklist con el que nace cada programa, en el orden del proceso real.
# `inspection_passed` va activado por defecto: TECH puede desactivarlo e ir
# solo con el número de permiso (así funcionó el año pasado).
DEFAULT_REQUIREMENTS: list[dict] = [
    {"code": "benefit_documents", "label": "Documentos del beneficio y demás documentos del cliente", "kind": "manual"},
    {"code": "client_captured", "kind": "auto"},
    {"code": "terms_signed", "label": "Términos y condiciones firmados", "kind": "manual"},
    {"code": "program_approved", "kind": "auto"},
    {"code": "installation_scheduled", "kind": "auto"},
    {"code": "installation_done", "kind": "auto"},
    {"code": "technician_info_complete", "kind": "auto"},
    {"code": "technician_info_confirmed", "kind": "auto"},
    {"code": "permit_approved", "kind": "auto"},
    {"code": "inspection_passed", "kind": "auto"},
    {"code": "invoice_issued", "kind": "auto"},
    {"code": "program_paperwork", "label": "Papeleo propio del programa", "kind": "manual"},
]


def default_requirements() -> list[dict]:
    """El checklist por defecto, con etiquetas y orden resueltos."""
    return [
        {
            "code": r["code"],
            "label": r.get("label") or AUTO_RULES[r["code"]],
            "kind": r["kind"],
            "sort_order": orden,
        }
        for orden, r in enumerate(DEFAULT_REQUIREMENTS)
    ]


# ---------------------------------------------------------------------------
# Evaluación: qué requisitos del programa cumple un cobro, hoy
# ---------------------------------------------------------------------------

async def _auto_results(db, *, claim, project, case, today) -> dict[str, tuple[bool, str | None]]:
    """Resultado de cada regla automática: (se cumple, detalle si no)."""
    from sqlalchemy import select

    from app.modules.field_ops.inspections import has_signed_permit, latest_result
    from app.modules.field_ops.installation import installation_gaps
    from app.modules.field_ops.models import Evidence, ProjectStatus
    from app.modules.field_ops.permits import all_cleared, permits_of

    permisos = await permits_of(db, project.id)
    ultima = await latest_result(db, project.id)
    cerrada = project.status == ProjectStatus.completed
    faltan = await installation_gaps(db, project=project)
    foto_gas = (
        await db.execute(
            select(Evidence.id).where(Evidence.project_id == project.id, Evidence.category == "gas_removal",
                                      Evidence.deleted_at.is_(None)).limit(1)
        )
    ).first() is not None
    factura = claim.invoice
    return {
        "client_captured": (bool(project.customer_id), "El expediente no tiene cliente."),
        "program_approved": (
            bool(case and case.approved_at and case.approval_code),
            "Falta la aprobación del programa con su código.",
        ),
        "installation_scheduled": (
            bool(project.primary_technician_user_id and project.scheduled_date),
            "La orden no tiene técnico y fecha.",
        ),
        "installation_done": (cerrada, "El técnico no ha cerrado el acta."),
        "technician_info_complete": (not faltan, "; ".join(faltan) or None),
        "technician_info_confirmed": (
            project.technician_info_confirmed, "Administración no ha confirmado el acta.",
        ),
        "permit_filed": (any(p.permit_number for p in permisos), "No hay permiso con número."),
        "permit_approved": (all_cleared(permisos, today), "Hay permisos sin aprobar o vencidos."),
        "inspection_passed": (
            ultima == "passed" and await has_signed_permit(db, project.id),
            "Falta la inspección aprobada con el permiso firmado por el inspector.",
        ),
        "gas_to_electric": (
            "gas_equipment_removed" in (project.installation_conditions or []) and foto_gas,
            "Falta marcar que se retiró el equipo de gas y su foto.",
        ),
        "invoice_issued": (
            factura is not None and factura.document_status == "issued", "La factura no está emitida.",
        ),
    }


async def evaluate_requirements(db, *, claim, project, case, requirements, today) -> list[dict]:
    """El checklist del cobro: cada requisito activo del programa con si se
    cumple. Los automáticos se calculan con los datos de hoy; los manuales,
    con la confirmación guardada en el cobro."""
    autos = await _auto_results(db, claim=claim, project=project, case=case, today=today)
    confirmados = {c.code: c for c in claim.checks}
    resultado = []
    for req in requirements:
        if not req.active:
            continue
        if req.kind == "auto":
            cumple, detalle = autos.get(req.code, (False, "Regla desconocida."))
            check = None
        else:
            check = confirmados.get(req.code)
            cumple, detalle = check is not None, None
        resultado.append({
            "code": req.code, "label": req.label, "kind": req.kind, "met": bool(cumple),
            "detail": None if cumple else detalle,
            "confirmed_by_user_id": check.confirmed_by_user_id if check else None,
            "confirmed_at": check.created_at if check else None,
            "note": check.note if check else None,
        })
    return resultado
