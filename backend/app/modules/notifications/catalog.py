"""Qué avisa el sistema, a quién y con qué texto por defecto (módulo 7).

Cada aviso tiene un código propio (`case.returned`, no `case.substatus_changed`):
el mismo evento de dominio produce avisos distintos según lo que cambió, y la
organización edita la plantilla de cada uno por separado.

Los textos usan variables `{{nombre}}`; una variable sin valor queda vacía.
"""

# código → (descripción para la pantalla de plantillas, permiso de quien lo
# recibe o "salesperson"/"technician" si va a una persona concreta)
NOTICES: dict[str, dict] = {
    "case.submitted": {
        "label": "Expediente enviado a revisión", "audience": "Administración (cases.review)",
        "title": "Expediente por revisar: {{expediente}}",
        "body": "{{vendedor}} envió el expediente {{expediente}} de {{cliente}} ({{programa}}).",
    },
    "case.returned": {
        "label": "Expediente devuelto al vendedor", "audience": "Vendedor del expediente",
        "title": "Expediente devuelto: {{expediente}}",
        "body": "Administración devolvió el expediente de {{cliente}}: {{motivo}}. Corrígelo y vuelve a enviarlo.",
    },
    "case.approved": {
        "label": "Expediente aprobado", "audience": "Vendedor del expediente",
        "title": "Expediente aprobado: {{expediente}}",
        "body": "El expediente de {{cliente}} fue aprobado. {{motivo}}",
    },
    "case.rejected": {
        "label": "Expediente rechazado", "audience": "Vendedor del expediente",
        "title": "Expediente rechazado: {{expediente}}",
        "body": "El expediente de {{cliente}} fue rechazado: {{motivo}}",
    },
    "case.on_hold": {
        "label": "Expediente en espera del programa", "audience": "Vendedor del expediente",
        "title": "Expediente en espera: {{expediente}}",
        "body": "El expediente de {{cliente}} quedó en espera del programa: {{motivo}}",
    },
    "installation.scheduled": {
        "label": "Instalación agendada", "audience": "Técnico asignado",
        "title": "Instalación agendada: {{fecha}}",
        "body": "Tienes una instalación el {{fecha}}: {{cliente}}, {{direccion}}.",
    },
    "project.returned_to_technician": {
        "label": "Acta devuelta al técnico", "audience": "Técnico del proyecto",
        "title": "Acta devuelta: {{proyecto}}",
        "body": "Administración devolvió el acta de {{proyecto}}: {{motivo}}",
    },
    "claim.rejected": {
        "label": "Cobro rechazado por el programa", "audience": "Cobro (billing.submit)",
        "title": "Cobro rechazado: {{proyecto}}",
        "body": "El programa rechazó el cobro de {{proyecto}}. Revísalo y vuelve a radicarlo.",
    },
    "claim.paid": {
        "label": "Cobro pagado", "audience": "Cobro (billing.submit)",
        "title": "Cobro pagado: {{proyecto}}",
        "body": "El programa pagó {{monto}} por {{proyecto}}.",
    },
    "case.approval_overdue": {
        "label": "Alerta: expediente sin aprobar", "audience": "Administración (cases.review)",
        "title": "Lleva {{dias}} días hábiles sin aprobar: {{expediente}}",
        "body": "El expediente {{expediente}} de {{cliente}} lleva {{dias}} días hábiles en «Pendiente de aprobación».",
    },
    "permit.expiring": {
        "label": "Alerta: permiso por vencer", "audience": "Permisos (permits.manage)",
        "title": "Permiso por vencer: {{proyecto}}",
        "body": "El permiso {{permiso}} de {{proyecto}} vence el {{fecha}}.",
    },
}

DEFAULT_PERMISSION = {
    "case.submitted": "cases.review",
    "case.approval_overdue": "cases.review",
    "claim.rejected": "billing.submit",
    "claim.paid": "billing.submit",
    "permit.expiring": "permits.manage",
}


def default_text(code: str, channel: str) -> tuple[str, str]:
    """(asunto o título, cuerpo) por defecto. El SMS va corto: solo el título."""
    n = NOTICES[code]
    if channel == "sms":
        return "", n["title"]
    return n["title"], n["body"]
