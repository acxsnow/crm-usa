"""Default checklist template seeded per organization: a generic HVAC
free-install checklist covering the steps confirmed with Mateo (inspection,
installation, evidence, signed attestation). Orgs can add more templates per
funder program (spec 18 item 1, still open) once the real intake PDFs are
reviewed in detail."""

DEFAULT_CHECKLIST_TEMPLATE = {
    "name": "Instalación HVAC — Programa de Aires Gratis",
    "project_type": "hvac_install",
    "items": [
        {"label": "Verificar elegibilidad y documentación del programa", "sort_order": 0, "is_required": True, "requires_evidence": False},
        {"label": "Foto de la unidad existente (antes)", "sort_order": 1, "is_required": True, "requires_evidence": True},
        {"label": "Foto del panel eléctrico / conexión", "sort_order": 2, "is_required": True, "requires_evidence": True},
        {"label": "Instalación de la nueva unidad", "sort_order": 3, "is_required": True, "requires_evidence": False},
        {"label": "Foto de la unidad instalada (después)", "sort_order": 4, "is_required": True, "requires_evidence": True},
        {"label": "Prueba de funcionamiento", "sort_order": 5, "is_required": True, "requires_evidence": False},
        {"label": "Explicación al cliente (uso y garantía)", "sort_order": 6, "is_required": True, "requires_evidence": False},
        {"label": "Firma de atestación (técnico y cliente)", "sort_order": 7, "is_required": True, "requires_evidence": False},
    ],
}
