"""Catálogos que cada organización recibe al crearse.

`DEFAULT_PIPELINE_STAGES` se retiró con el modelo anterior: las etapas del
expediente viven en `app/modules/cases/stages.py`, en código y con sus
transiciones validadas, no como filas editables.
"""

# Funder/program approval status (org-configurable catalog, confirmed with
# Mateo Sept 2026 — mirrors the status column used across the current
# spreadsheets for CARE/MEDICAL/CALFRESH/HEEHRA/LADWP applications). This is
# separate from the case stage: la etapa del expediente dice en qué va
# *nuestro* proceso; funder_status es lo que el programa reporta de vuelta.
DEFAULT_FUNDER_STATUSES: list[dict] = [
    {"code": "not_submitted", "name": "No enviado", "sort_order": 0},
    {"code": "pending", "name": "Pendiente", "sort_order": 1},
    {"code": "under_review", "name": "En revisión", "sort_order": 2},
    {"code": "approved", "name": "Aprobado", "sort_order": 3},
    {"code": "installed", "name": "Instalado", "sort_order": 4},
    {"code": "rejected", "name": "Rechazado", "sort_order": 5},
    {"code": "on_hold", "name": "En espera", "sort_order": 6},
]
