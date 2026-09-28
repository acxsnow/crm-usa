"""Plantilla de checklist por defecto de cada organización.

Sale de los requerimientos §8 (checklist técnico del instalador). Se usa cuando
el programa del expediente no tiene plantilla propia (spec D5.3).

- No pide la firma del cliente: §8 aclara que el cliente firma con el vendedor,
  durante la aplicación, no con el técnico.
- Los ítems con `condition_code` solo son obligatorios si esa condición aplica a
  la casa (§8.3): la desconexión del gas solo se exige si se retira un equipo de
  gas.
- `allows_not_applicable` va en lo que puede no existir en la casa (panel,
  equipo previo, alguna de las dos etiquetas), siempre con motivo.
"""

_GENERAL = "Requisitos generales"
_CIERRE = "Instalación y cierre"

# El nombre es la identidad de la plantilla (`get_or_create_default_checklist_template`
# busca por nombre). Es distinto al de la plantilla anterior al módulo 5
# ("Instalación HVAC — Programa de Aires Gratis") a propósito: las
# organizaciones que ya la tenían reciben esta en su próximo proyecto, y los
# proyectos anteriores conservan su copia. Cambiar el contenido sin cambiar el
# nombre dejaría a esas organizaciones con la vieja para siempre.
DEFAULT_CHECKLIST_TEMPLATE = {
    "name": "Checklist técnico del instalador (requerimientos §8)",
    "project_type": "hvac_install",
    "items": [
        {"label": "Verificar orden y dirección", "section": _GENERAL,
         "is_required": True, "requires_evidence": False},
        {"label": "Confirmar distribución de la vivienda (habitaciones, cocina y sala)", "section": _GENERAL,
         "is_required": True, "requires_evidence": False},
        {"label": "Foto de la fachada", "section": _GENERAL,
         "is_required": True, "requires_evidence": True, "evidence_category": "facade"},
        {"label": "Foto del pedestal", "section": _GENERAL,
         "is_required": True, "requires_evidence": True, "evidence_category": "pedestal",
         "condition_code": "pedestal_required"},
        {"label": "Título o decal de la casa móvil", "section": _GENERAL,
         "is_required": True, "requires_evidence": True, "evidence_category": "additional_photo",
         "condition_code": "title_decal_required"},
        {"label": "Registrar el equipo existente (furnace y sistema HVAC)", "section": _GENERAL,
         "is_required": True, "requires_evidence": True, "evidence_category": "existing_furnace",
         "allows_not_applicable": True},
        {"label": "Foto del panel eléctrico", "section": _GENERAL,
         "is_required": True, "requires_evidence": True, "evidence_category": "electrical_panel",
         "allows_not_applicable": True},
        {"label": "Foto de cada unidad nueva instalada", "section": _CIERRE,
         "is_required": True, "requires_evidence": True, "evidence_category": "new_equipment"},
        {"label": "Etiqueta interior con modelo y serial visibles", "section": _CIERRE,
         "is_required": True, "requires_evidence": True, "evidence_category": "indoor_label",
         "allows_not_applicable": True},
        {"label": "Etiqueta exterior con modelo y serial visibles", "section": _CIERRE,
         "is_required": True, "requires_evidence": True, "evidence_category": "outdoor_label",
         "allows_not_applicable": True},
        {"label": "Conductos y cableado eléctrico", "section": _CIERRE,
         "is_required": True, "requires_evidence": True, "evidence_category": "ducts_wiring",
         "condition_code": "electrical_upgrade"},
        {"label": "Proceso de gas: estado anterior y desconexión segura", "section": _CIERRE,
         "is_required": True, "requires_evidence": True, "evidence_category": "gas_removal",
         "condition_code": "gas_equipment_removed"},
        {"label": "Prueba de funcionamiento", "section": _CIERRE,
         "is_required": True, "requires_evidence": False},
        {"label": "Explicar al cliente el uso y la garantía", "section": _CIERRE,
         "is_required": True, "requires_evidence": False},
    ],
}

# El orden de la lista es el orden en pantalla.
for _orden, _item in enumerate(DEFAULT_CHECKLIST_TEMPLATE["items"]):
    _item["sort_order"] = _orden
