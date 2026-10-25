"""Catálogos del trabajo de campo.

Viven en código, no en enums de Postgres, por la misma razón que las etapas del
expediente (`cases/stages.py`): agregar una categoría es cambiar un diccionario,
no escribir una migración con `ALTER TYPE`. La base guarda el código; la
etiqueta en español viaja en `GET /field-ops/catalogs` para que el frontend no
repita estas listas ni se desactualice.
"""
from enum import StrEnum

# Las 15 categorías mínimas de evidencia (requerimientos §7.1). El orden es el
# del documento del cliente y es el que ve el técnico al cargar.
EVIDENCE_CATEGORIES: dict[str, str] = {
    "facade": "Fachada",
    "pedestal": "Pedestal",
    "electrical_panel": "Panel o subpanel eléctrico",
    "existing_furnace": "Furnace o equipo existente",
    "central_ac": "A/C central",
    "window_ac": "A/C de ventana",
    "old_equipment": "Equipos viejos",
    "gas_process": "Proceso de gas",
    "ducts_wiring": "Conductos y cableado eléctrico",
    "new_equipment": "Equipos nuevos",
    "indoor_label": "Etiqueta interior",
    "outdoor_label": "Etiqueta exterior",
    "gas_removal": "Eliminación de equipo de gas",
    "additional_photo": "Fotos adicionales",
    "additional_video": "Video adicional",
    # La prueba de la inspección aprobada: el permiso con la firma del
    # inspector (módulo 6, spec D6.4). Sin esto no se cobra.
    "permit_signed": "Permiso firmado por el inspector",
}

# Condiciones de una instalación que vuelven obligatorios ciertos ítems del
# checklist (requerimientos §8.3). Las marca quien conoce la casa.
INSTALLATION_CONDITIONS: dict[str, str] = {
    "gas_equipment_removed": "Se retira equipo de gas",
    "electrical_upgrade": "Hay adecuación eléctrica",
    "pedestal_required": "El programa exige pedestal",
    "title_decal_required": "El programa exige título o decal de la casa móvil",
}

# Tipos de equipo instalado. Es lo que el cobro al programa necesita
# distinguir; "other" existe para no bloquear al técnico con un equipo raro.
EQUIPMENT_TYPES: dict[str, str] = {
    "heat_pump_outdoor": "Bomba de calor (unidad exterior)",
    "air_handler": "Manejadora de aire",
    "mini_split_indoor": "Mini split (unidad interior)",
    "mini_split_outdoor": "Mini split (unidad exterior)",
    "furnace": "Furnace",
    "water_heater": "Calentador de agua",
    "induction_range": "Estufa de inducción",
    "electrical_panel": "Panel eléctrico",
    "thermostat": "Termostato",
    "other": "Otro",
}

# Por qué no se pudo hacer una visita de instalación (D-001). La nota es
# obligatoria con cualquier motivo: el motivo clasifica, la nota explica.
VISIT_FAILURE_REASONS: dict[str, str] = {
    "customer_absent": "El cliente no estaba",
    "access_denied": "No dejaron entrar o el cliente no quiso",
    "unsafe_conditions": "Condiciones inseguras en la casa",
    "missing_material": "Faltó material o equipo",
    "weather": "Clima",
    "other": "Otro",
}


class PermitStatus(StrEnum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    # No toda instalación exige permiso municipal. Lo que no se permite es
    # saltarse la etapa sin dejar constancia de por qué.
    not_required = "not_required"


PERMIT_STATUS_LABELS: dict[str, str] = {
    PermitStatus.submitted: "Radicado",
    PermitStatus.approved: "Aprobado",
    PermitStatus.rejected: "Rechazado",
    PermitStatus.not_required: "No requerido",
}


class InspectionResult(StrEnum):
    pending = "pending"
    passed = "passed"
    failed = "failed"


INSPECTION_RESULT_LABELS: dict[str, str] = {
    InspectionResult.pending: "Pendiente",
    InspectionResult.passed: "Aprobada",
    InspectionResult.failed: "Fallida",
}


def default_evidence_category(mime_type: str | None) -> str:
    """La categoría cuando nadie la indica: la genérica que corresponde al tipo
    de archivo, en vez de una que diga algo falso sobre la foto."""
    if mime_type and mime_type.startswith("video/"):
        return "additional_video"
    return "additional_photo"
