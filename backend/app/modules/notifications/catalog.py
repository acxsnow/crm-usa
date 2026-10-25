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
    "installation.closed": {
        "label": "Instalación cerrada: acta por confirmar", "audience": "Administración (checklists.approve)",
        "title": "Instalación cerrada: {{expediente}}",
        "body": "{{tecnico}} cerró la instalación de {{cliente}} ({{direccion}}). Revisa y confirma el acta.",
    },
    "installation.visit_failed": {
        "label": "Visita de instalación fallida", "audience": "Agenda (dispatch.manage)",
        "title": "Visita fallida: {{proyecto}}",
        "body": "{{tecnico}} no pudo instalar en {{direccion}} ({{fecha}}): {{motivo}}. Visitas fallidas: "
                "{{intentos}} de {{limite}}. {{siguiente}}",
    },
    "project.cancelled": {
        "label": "Obra cancelada", "audience": "Técnico del proyecto",
        "title": "Obra cancelada: {{proyecto}}",
        "body": "Administración canceló la obra {{proyecto}}: {{motivo}}",
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
    "expense.submitted": {
        "label": "Gasto de campo por revisar", "audience": "Quien aprueba gastos (expenses.approve)",
        "title": "Gasto por revisar: {{monto}}",
        "body": "{{persona}} registró un gasto de {{monto}} ({{categoria}}): {{descripcion}}.",
    },
    "expense.approved": {
        "label": "Gasto de campo aprobado", "audience": "Quien registró el gasto",
        "title": "Gasto aprobado: {{monto}}",
        "body": "Tu gasto de {{monto}} ({{categoria}}) fue aprobado.",
    },
    "expense.rejected": {
        "label": "Gasto de campo rechazado", "audience": "Quien registró el gasto",
        "title": "Gasto rechazado: {{monto}}",
        "body": "Tu gasto de {{monto}} ({{categoria}}) fue rechazado: {{motivo}}",
    },
    "payable.pending_approval": {
        "label": "Factura de proveedor por aprobar", "audience": "Quien aprueba pagos (payables.approve)",
        "title": "Factura por aprobar: {{proveedor}} {{factura}}",
        "body": "{{proveedor}} · factura {{factura}} por {{monto}}, vence el {{fecha}}.",
    },
    "payable.paid_now": {
        "label": "Factura de proveedor pagada al momento", "audience": "Quien aprueba pagos (payables.approve)",
        "title": "Pagada al momento: {{proveedor}} {{factura}}",
        "body": "{{persona}} registró la factura {{factura}} de {{proveedor}} por {{monto}} como pagada al momento.",
    },
    "supplier.bank_changed": {
        "label": "Cambiaron los datos bancarios de un proveedor", "audience": "Quien aprueba pagos (payables.approve)",
        "title": "Datos bancarios cambiados: {{proveedor}}",
        "body": "{{persona}} cambió los datos bancarios de {{proveedor}}. Confírmalo con el proveedor antes del próximo pago.",
    },
    "payable.due_soon": {
        "label": "Alerta: factura de proveedor por vencer", "audience": "Cuentas por pagar",
        "title": "Vence el {{fecha}}: {{proveedor}} {{factura}}",
        "body": "A la factura {{factura}} de {{proveedor}} le quedan {{monto}} por pagar y vence el {{fecha}}.",
    },
    "supplier.document_expiring": {
        "label": "Alerta: licencia o seguro de proveedor por vencer", "audience": "Proveedores (suppliers.manage)",
        "title": "{{documento}} de {{proveedor}} vence el {{fecha}}",
        "body": "Pide a {{proveedor}} la renovación de su {{documento}} (vence el {{fecha}}).",
    },
    "warehouse.release_pending": {
        "label": "Salida de bodega por autorizar",
        "audience": "Quien autoriza salidas (warehouse.approve_release)",
        "title": "Salida por autorizar: {{orden}}",
        "body": "{{solicitante}} pidió material de bodega para {{obra}} ({{lineas}} renglones). "
                "Apruébala o recházala.",
    },
    "warehouse.release_delivered": {
        "label": "Salida de bodega entregada", "audience": "Quien pidió la salida",
        "title": "Salida entregada: {{orden}}",
        "body": "Bodega entregó la orden {{orden}}. {{faltantes}}",
    },
    "warehouse.stock_low": {
        "label": "Alerta: artículo en su mínimo", "audience": "Bodega (warehouse.manage)",
        "title": "Por reponer: {{articulo}}",
        "body": "{{articulo}} quedó en {{existencia}} (mínimo {{minimo}}). Hay que reponerlo.",
    },
    "warehouse.count_due": {
        "label": "Alerta: toca el conteo mensual de bodega", "audience": "Bodega (warehouse.manage)",
        "title": "Toca contar la bodega",
        "body": "El último conteo físico fue el {{fecha}} (hace {{dias}} días). Toca el conteo mensual.",
    },
    # Pagos en línea (payments/, spec 2026-10-25-pagos-tarjeta)
    "payment.received": {
        "label": "Pago en línea recibido", "audience": "Quien registra pagos (invoices.record_payment)",
        "title": "Pago recibido: {{factura}} · {{monto}}",
        "body": "{{cliente}} pagó {{monto}} de la factura {{factura}} con {{metodo}}. Saldo: {{saldo}}.",
    },
    "payment.failed": {
        "label": "Pago en línea fallido", "audience": "Quien registra pagos (invoices.record_payment)",
        "title": "Pago fallido: {{factura}}",
        "body": "El pago de {{cliente}} por {{monto}} de la factura {{factura}} no se completó ({{metodo}}). Contacta al cliente.",
    },
    "payment.disputed": {
        "label": "Disputa de un pago con tarjeta", "audience": "Quien registra pagos (invoices.record_payment)",
        "title": "Disputa abierta: {{factura}} · {{monto}}",
        "body": "{{cliente}} abrió una disputa por {{monto}} en la factura {{factura}}. Responde en Stripe antes de la fecha límite.",
    },
}

DEFAULT_PERMISSION = {
    "case.submitted": "cases.review",
    "case.approval_overdue": "cases.review",
    "installation.closed": "checklists.approve",
    "installation.visit_failed": "dispatch.manage",
    "claim.rejected": "billing.submit",
    "claim.paid": "billing.submit",
    "permit.expiring": "permits.manage",
    "expense.submitted": "expenses.approve",
    "payable.pending_approval": "payables.approve",
    "payable.paid_now": "payables.approve",
    "supplier.bank_changed": "payables.approve",
    "supplier.document_expiring": "suppliers.manage",
    "warehouse.release_pending": "warehouse.approve_release",
    "warehouse.stock_low": "warehouse.manage",
    "warehouse.count_due": "warehouse.manage",
    "payment.received": "invoices.record_payment",
    "payment.failed": "invoices.record_payment",
    "payment.disputed": "invoices.record_payment",
}


def default_text(code: str, channel: str) -> tuple[str, str]:
    """(asunto o título, cuerpo) por defecto. El SMS va corto: solo el título."""
    n = NOTICES[code]
    if channel == "sms":
        return "", n["title"]
    return n["title"], n["body"]
