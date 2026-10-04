"""Plantillas del sistema (spec D1.7): el catálogo canónico de campos y los
flujos iniciales de Eficiencia de Arizona y TECH Clean California.

Viven en código, como los roles por defecto; `service.install_defaults` los
copia a cada organización y no pisa lo que ya exista, así que correrlo dos
veces no duplica nada y no deshace lo que el administrador ajustó.

Fuentes: requerimientos §2.5–§2.6 (catálogo y opciones), Anexo A (qué usa cada
programa), §4.5 y §5.5 (documentos y requisitos técnicos) y el PDF §2.3–§2.4
(ID y auditoría técnica del vendedor). Lo que el cliente todavía no confirma
(D7, preguntas 8–10 y 14) va con valores provisionales: es configuración, no
código, y se ajusta desde la pantalla.
"""


def _opts(*pares: str) -> list[dict]:
    """"valor=Etiqueta" → {"value", "label"}."""
    return [{"value": p.split("=", 1)[0], "label": p.split("=", 1)[1]} for p in pares]


SI_NO = _opts("yes=Sí", "no=No")

# (key, etiqueta, tipo, sección, extras)
CATALOG: list[tuple] = [
    # --- Cliente (§3.1) ------------------------------------------------------
    ("customer.full_name", "Nombre completo", "text", "Cliente",
     {"binding": "customer.legal_name", "validation": {"min_length": 3, "max_length": 255}}),
    ("customer.phone", "Teléfono", "phone", "Cliente", {"binding": "customer.main_phone"}),
    ("customer.email", "Correo electrónico", "email", "Cliente", {"binding": "customer.email"}),
    ("customer.address_street", "Dirección", "text", "Cliente", {"binding": "case.address_street"}),
    ("customer.address_city", "Ciudad", "text", "Cliente", {"binding": "case.address_city"}),
    ("customer.address_state", "Estado", "single_select", "Cliente",
     {"binding": "case.address_state", "options": _opts("CA=California", "AZ=Arizona", "NV=Nevada")}),
    ("customer.address_zip", "ZIP", "text", "Cliente",
     {"binding": "case.address_zip", "validation": {"format": "zip"}}),
    ("customer.contact_preference", "Hora conveniente para contactarle", "single_select", "Cliente",
     {"options": _opts("morning=Mañana", "afternoon=Tarde", "anytime=Cualquier hora")}),
    ("customer.id_photo", "Foto del documento de identidad", "photo", "Cliente",
     {"help": "Verifica el ID en persona y tómale una foto legible.", "sensitive": True}),
    # --- Vivienda (§3.2) -----------------------------------------------------
    ("home.is_homeowner", "¿Es propietario de la vivienda?", "single_select", "Vivienda", {"options": SI_NO}),
    ("home.residence_type", "Tipo de vivienda", "single_select", "Vivienda",
     {"options": _opts("single_family_home=Casa", "mobile_home=Casa móvil (mobile home)",
                       "condominium=Condominio", "duplex=Dúplex")}),
    ("home.unit_number", "Número de unidad o espacio", "text", "Vivienda", {"binding": "case.address_unit"}),
    ("home.bedrooms", "Número de habitaciones", "integer", "Vivienda", {"validation": {"min": 0, "max": 20}}),
    ("home.bathrooms", "Número de baños", "integer", "Vivienda", {"validation": {"min": 0, "max": 20}}),
    # --- Hogar (§3.4; datos sensibles §17.3) ----------------------------------
    ("home.household_members", "Número de miembros del hogar", "integer", "Hogar",
     {"validation": {"min": 1, "max": 30}}),
    ("home.education_level", "Nivel de educación del cliente", "single_select", "Hogar",
     {"options": _opts("primary_secondary=Primaria / Secundaria", "high_school=Preparatoria / High School",
                       "technical_associate=Educación técnica / Associate Degree",
                       "bachelors=Licenciatura / Universidad", "graduate=Posgrado / Maestría",
                       "prefer_not_to_answer=Prefiero no responder")}),
    ("home.has_disability_or_chronic_condition", "¿Algún miembro tiene discapacidad o condición médica crónica?",
     "single_select", "Hogar",
     {"sensitive": True, "options": _opts("yes=Sí", "no=No", "prefer_not_to_answer=Prefiero no responder")}),
    ("home.disability_or_condition_detail", "Especificar la condición", "textarea", "Hogar", {"sensitive": True}),
    ("home.gas_type", "Tipo de suministro de gas", "single_select", "Hogar",
     {"options": _opts("natural_gas=Gas natural", "lp_propane=Gas LP / Propano", "no_gas=No tienen gas")}),
    ("home.gas_company", "Compañía de gas natural", "text", "Hogar", {}),
    ("home.notes", "Notas del hogar", "textarea", "Hogar", {}),
    # --- Elegibilidad (§3.3) -------------------------------------------------
    ("eligibility.programs_az", "Programas de beneficio del hogar (Arizona)", "multi_select", "Elegibilidad",
     {"sensitive": True, "validation": {"exclusive": ["none"]},
      "options": _opts("alice=ALICE", "hip=Housing Improvement Program (HIP)",
                       "hopwa=Housing Opportunities for Persons with AIDS", "fdpir=FDPIR", "head_start=Head Start",
                       "lifeline=Lifeline Support for Communications", "liheap=LIHEAP",
                       "medicaid_ahcccs=Medicaid / AHCCCS", "public_housing=Public Housing",
                       "nslp=National School Lunch Program (NSLP)", "snap=SNAP", "ssi=SSI",
                       "other_government_nonprofit=Programa gubernamental o sin ánimo de lucro acreditado",
                       "none=Ninguno de los anteriores")}),
    ("eligibility.programs_tech", "Programas de beneficio del hogar (TECH Clean)", "multi_select", "Elegibilidad",
     {"sensitive": True, "validation": {"exclusive": ["none"]},
      "options": _opts("care=CARE", "fera=FERA", "medi_cal=Medi-Cal", "calfresh=CalFresh (SNAP)", "wic=WIC",
                       "calworks=CalWORKS", "ssi=SSI", "none=Ninguno")}),
    ("eligibility.other_program", "Otro programa o documento aceptado", "text", "Elegibilidad", {}),
    ("eligibility.benefit_document", "Documento que demuestra el beneficio", "document", "Elegibilidad",
     {"sensitive": True}),
    ("eligibility.tax_return", "Declaración de impuestos (si no tiene beneficio)", "document", "Elegibilidad",
     {"sensitive": True, "help": "Vía alterna de elegibilidad por ingresos (PDF §2.2). Provisional."}),
    # --- Auditoría técnica preliminar del vendedor (PDF §2.4, provisional D7) --
    ("tech.panel_amperage", "Amperaje del panel eléctrico", "single_select", "Auditoría técnica",
     {"options": _opts("100=100 A", "125=125 A", "150=150 A", "200=200 A", "other=Otro / no se sabe")}),
    ("tech.existing_hvac", "Climatización existente", "single_select", "Auditoría técnica",
     {"options": _opts("none=Ninguna", "mini_split=Mini split", "central=Central", "window=Ventana / portátil")}),
    ("tech.induction_cooktop", "¿Tiene cocina de inducción?", "single_select", "Auditoría técnica",
     {"options": SI_NO}),
    ("tech.water_heater", "Calentador de agua", "single_select", "Auditoría técnica",
     {"options": _opts("gas=De gas", "electric=Eléctrico", "none=No tiene")}),
    ("tech.electrical_viability", "Diagnóstico de viabilidad eléctrica", "single_select", "Auditoría técnica",
     {"options": _opts("adequate=Adecuada", "needs_upgrade=Requiere adecuación", "not_viable=No viable")}),
    ("tech.garbage_disposal", "Triturador de basura (cantidad y ubicación)", "text", "Auditoría técnica", {}),
    ("tech.fans", "Ventiladores (cantidad y ubicación)", "text", "Auditoría técnica", {}),
    ("tech.exhaust", "Extractores (cantidad y ubicación)", "text", "Auditoría técnica", {}),
    ("tech.dishwasher", "¿Tiene lavaplatos?", "single_select", "Auditoría técnica", {"options": SI_NO}),
    ("tech.access_notes", "Acceso, mascotas, estacionamiento y condiciones especiales", "textarea",
     "Auditoría técnica", {}),
    # --- Documentos y fotos para el instalador (§4.5, §5.5) -----------------
    ("docs.electric_bill", "Factura reciente de electricidad", "document", "Documentos", {}),
    ("docs.panel_photo", "Foto del panel o subpanel", "photo", "Documentos", {}),
    ("docs.furnace_photo", "Foto del furnace existente", "photo", "Documentos", {}),
    ("docs.hvac_photos", "Fotos del HVAC existente (interior y exterior)", "photo", "Documentos", {}),
    ("docs.pedestal_photo", "Foto del pedestal", "photo", "Documentos", {}),
    ("docs.mobile_home_title", "Título de la mobile home", "document", "Documentos", {}),
    ("docs.mobile_home_decal", "Decal de la mobile home", "photo", "Documentos", {}),
    ("docs.additional_photos", "Fotos adicionales para el instalador", "photo", "Documentos", {}),
    # --- Autorización (§3.5) ------------------------------------------------
    ("authorization.customer_name", "Nombre del cliente", "text", "Autorización", {}),
    ("authorization.terms_accepted", "Acepto la autorización y los términos y condiciones", "terms_checkbox",
     "Autorización", {}),
    ("authorization.signature", "Firma del cliente", "signature", "Autorización", {}),
    ("authorization.signed_at", "Fecha y hora de firma", "system_datetime", "Autorización", {}),
    # --- Uso interno (§3.6) -------------------------------------------------
    ("internal.salesperson", "Vendedor", "system_user", "Uso interno", {"internal": True}),
    ("internal.result", "Resultado preliminar", "single_select", "Uso interno",
     {"internal": True, "options": _opts("preapproved=Preaprobado", "pending=Pendiente",
                                         "does_not_qualify=No califica")}),
    ("internal.notes", "Observaciones internas", "textarea", "Uso interno", {"internal": True}),
]

R, O, C = "required", "optional", "conditional"
MOBILE = {"field": "home.residence_type", "eq": "mobile_home"}

# Flujo: [(paso, título, [(key, requisito, condición)])]. Fase única: Vendedor.
_COMMON_START = [
    ("customer", "Cliente", [
        ("customer.full_name", R, None), ("customer.phone", R, None), ("customer.email", R, None),
        ("customer.address_street", R, None), ("home.unit_number", O, None), ("customer.address_city", R, None),
        ("customer.address_state", R, None), ("customer.address_zip", R, None),
        ("customer.contact_preference", O, None), ("customer.id_photo", R, None),
    ]),
]
_TECH_AUDIT = ("technical", "Auditoría técnica", [
    ("tech.panel_amperage", R, None), ("tech.existing_hvac", R, None), ("home.bedrooms", R, None),
    ("home.bathrooms", O, None), ("tech.induction_cooktop", R, None), ("tech.water_heater", R, None),
    ("tech.electrical_viability", R, None), ("tech.access_notes", O, None),
])
_AUTH_END = [
    ("authorization", "Autorización y firma", [
        ("authorization.customer_name", R, None), ("authorization.terms_accepted", R, None),
        ("authorization.signature", R, None), ("authorization.signed_at", O, None),
    ]),
    ("internal", "Uso interno", [
        ("internal.salesperson", O, None), ("internal.result", R, None), ("internal.notes", O, None),
    ]),
]

PROGRAMS: list[dict] = [
    {
        "code": "AZ_EFFICIENCY",
        "name": "Eficiencia de Arizona",
        "customer_facing_name": "Arizona Efficiency Program",
        "funder_name": "Desert Alliance Properties LLC",
        "invoice_entity": "Desert Alliance Properties LLC",
        "authorization_text": "Autorizo el uso de esta información exclusivamente para verificar mi elegibilidad "
                              "en el programa de Eficiencia de Arizona. (Texto provisional: pendiente del cliente.)",
        "terms_title": "Autorización y términos del programa de Eficiencia de Arizona",
        "steps": _COMMON_START + [
            ("home", "Vivienda y hogar", [
                ("home.is_homeowner", R, None), ("home.residence_type", R, None),
                ("home.household_members", O, None), ("home.education_level", O, None),
                ("home.has_disability_or_chronic_condition", O, None),
                ("home.disability_or_condition_detail", C,
                 {"field": "home.has_disability_or_chronic_condition", "eq": "yes"}),
                ("home.gas_type", O, None), ("home.gas_company", C, {"field": "home.gas_type", "eq": "natural_gas"}),
                ("home.notes", O, None),
            ]),
            ("eligibility", "Elegibilidad", [
                ("eligibility.programs_az", R, None),
                ("eligibility.other_program", C,
                 {"field": "eligibility.programs_az", "eq": "other_government_nonprofit"}),
                ("eligibility.benefit_document", C, {"field": "eligibility.programs_az", "in": [
                    "alice", "hip", "hopwa", "fdpir", "head_start", "lifeline", "liheap", "medicaid_ahcccs",
                    "public_housing", "nslp", "snap", "ssi", "other_government_nonprofit"]}),
                ("eligibility.tax_return", C, {"field": "eligibility.programs_az", "eq": "none"}),
            ]),
            (_TECH_AUDIT[0], _TECH_AUDIT[1], _TECH_AUDIT[2] + [
                ("tech.garbage_disposal", O, None), ("tech.fans", O, None), ("tech.exhaust", O, None),
                ("tech.dishwasher", O, None),
            ]),
            ("documents", "Documentos y fotos", [
                ("docs.electric_bill", R, None), ("docs.panel_photo", R, None), ("docs.furnace_photo", R, None),
                ("docs.hvac_photos", R, None), ("docs.pedestal_photo", C, MOBILE),
                ("docs.mobile_home_title", C, MOBILE), ("docs.mobile_home_decal", C, MOBILE),
                ("docs.additional_photos", O, None),
            ]),
        ] + _AUTH_END,
    },
    {
        "code": "TECH_CLEAN_CA",
        "name": "TECH Clean California",
        "customer_facing_name": "TECH Clean California",
        "funder_name": "TECH Clean California",
        "invoice_entity": "Delta HVAC Service Inc.",
        "authorization_text": "Autorizo el uso de esta información exclusivamente para verificar mi posible "
                              "elegibilidad en TECH Clean California. (Texto provisional: pendiente del cliente.)",
        "terms_title": "Autorización y términos de TECH Clean California",
        "steps": _COMMON_START + [
            ("home", "Vivienda", [("home.is_homeowner", R, None), ("home.residence_type", R, None)]),
            ("eligibility", "Elegibilidad", [
                ("eligibility.programs_tech", R, None),
                ("eligibility.benefit_document", C, {"field": "eligibility.programs_tech", "in": [
                    "care", "fera", "medi_cal", "calfresh", "wic", "calworks", "ssi"]}),
                ("eligibility.tax_return", C, {"field": "eligibility.programs_tech", "eq": "none"}),
            ]),
            _TECH_AUDIT,
            ("documents", "Documentos y fotos", [
                ("docs.electric_bill", R, None), ("docs.panel_photo", R, None), ("docs.furnace_photo", O, None),
                ("docs.hvac_photos", R, None), ("docs.pedestal_photo", C, MOBILE),
                ("docs.mobile_home_title", C, MOBILE), ("docs.mobile_home_decal", C, MOBILE),
                ("docs.additional_photos", O, None),
            ]),
        ] + _AUTH_END,
    },
]
