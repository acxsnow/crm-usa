"""Default pipeline stages seeded per organization (spec 7.2 default stages,
adapted to the confirmed funder-program workflow)."""

DEFAULT_PIPELINE_STAGES: list[dict] = [
    {"code": "new", "name": "Nueva", "sort_order": 0, "is_won": False, "is_lost": False},
    {"code": "contacted", "name": "Contactada", "sort_order": 1, "is_won": False, "is_lost": False},
    {"code": "application_sent", "name": "Solicitud enviada", "sort_order": 2, "is_won": False, "is_lost": False},
    {"code": "under_review", "name": "En revisión", "sort_order": 3, "is_won": False, "is_lost": False},
    {"code": "approved", "name": "Aprobada", "sort_order": 4, "is_won": False, "is_lost": False},
    {"code": "installation", "name": "Instalación", "sort_order": 5, "is_won": False, "is_lost": False},
    {"code": "won", "name": "Ganada", "sort_order": 6, "is_won": True, "is_lost": False},
    {"code": "waitlisted", "name": "Lista de espera", "sort_order": 7, "is_won": False, "is_lost": False},
    {"code": "rejected", "name": "Rechazada", "sort_order": 8, "is_won": False, "is_lost": True},
    {"code": "lost", "name": "Perdida", "sort_order": 9, "is_won": False, "is_lost": True},
]

# Funder/program approval status (org-configurable catalog, confirmed with
# Mateo Sept 2026 — mirrors the status column used across the current
# spreadsheets for CARE/MEDICAL/CALFRESH/HEEHRA/LADWP applications). This is
# separate from PipelineStage: the pipeline stage tracks where the deal is in
# *our* process, funder_status tracks what the funder itself reports back.
DEFAULT_FUNDER_STATUSES: list[dict] = [
    {"code": "not_submitted", "name": "No enviado", "sort_order": 0},
    {"code": "pending", "name": "Pendiente", "sort_order": 1},
    {"code": "under_review", "name": "En revisión", "sort_order": 2},
    {"code": "approved", "name": "Aprobado", "sort_order": 3},
    {"code": "installed", "name": "Instalado", "sort_order": 4},
    {"code": "rejected", "name": "Rechazado", "sort_order": 5},
    {"code": "on_hold", "name": "En espera", "sort_order": 6},
]
