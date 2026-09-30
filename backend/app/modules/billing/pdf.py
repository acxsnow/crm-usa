"""PDF de la factura (spec D6.9): una plantilla para rebate y otra para
trabajo particular, con ReportLab como el acta del módulo 5.

Dos pasos separados a propósito:
- `invoice_document()` reúne los datos (entidad que factura, cliente,
  dirección, equipos del módulo 5, líneas, pagos, texto legal). Es lo que
  prueban las pruebas.
- `render_invoice_pdf()` solo dibuja.

La vista previa arma una factura en memoria (sin guardarla ni pedir número)
y pasa por los mismos dos pasos: lo que se ve antes de emitir es lo que sale.

El documento va en inglés: lo reciben programas y clientes en EE. UU. Las
etiquetas están juntas en `LABELS`.
"""
import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import DocumentStatus, Invoice, InvoiceKind, RebateClaim

LABELS = {
    "invoice": "INVOICE",
    "number": "Invoice #",
    "issue_date": "Issue date",
    "due_date": "Due date",
    "bill_to": "Bill to",
    "customer": "Customer",
    "service_address": "Service address",
    "program": "Program",
    "work": "Work performed",
    "installed_on": "Installation date",
    "approval": "Program approval code",
    "equipment": "Installed equipment",
    "type": "Type", "brand_model": "Brand / model", "serial": "Serial", "qty": "Qty",
    "description": "Description", "unit_price": "Unit price", "amount": "Amount",
    "subtotal": "Subtotal", "rebate": "Program rebate", "customer_total": "Customer responsibility",
    "program_due": "Amount due from program",
    "payments": "Payments", "paid_on": "Date", "reference": "Reference",
    "balance": "Balance due",
    "draft": "PREVIEW — NOT ISSUED", "void": "VOID",
    "replaces": "Replaces invoice",
}

EQUIPMENT_LABELS = {
    "heat_pump_outdoor": "Heat pump (outdoor unit)",
    "air_handler": "Air handler",
    "mini_split_indoor": "Mini split (indoor)",
    "mini_split_outdoor": "Mini split (outdoor)",
    "furnace": "Furnace",
    "water_heater": "Water heater",
    "induction_range": "Induction range",
    "electrical_panel": "Electrical panel",
    "thermostat": "Thermostat",
    "other": "Other",
}


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

async def invoice_document(db: AsyncSession, invoice: Invoice, *, program=None, project=None) -> dict:
    """Todo lo que el PDF muestra. `program` y `project` se pasan en la vista
    previa (la factura en memoria no tiene cobro); si no, se buscan."""
    from app.modules.billing.program_config import ensure_profile
    from app.modules.cases.models import Case
    from app.modules.crm.models import Customer
    from app.modules.field_ops.installation import equipment_of
    from app.modules.field_ops.models import Project
    from app.modules.organizations.models import Organization

    org = await db.get(Organization, invoice.organization_id)
    if program is None and invoice.claim_id:
        claim = await db.get(RebateClaim, invoice.claim_id)
        program = claim.program if claim else None
    if project is None and invoice.project_id:
        project = (
            await db.execute(select(Project).where(Project.id == invoice.project_id,
                                                   Project.organization_id == invoice.organization_id))
        ).scalar_one_or_none()
    customer = (
        await db.execute(select(Customer).where(Customer.id == invoice.customer_id,
                                                Customer.organization_id == invoice.organization_id))
    ).scalar_one_or_none()

    # Entidad que factura: la del perfil del programa si la tiene; si no, la
    # organización.
    issuer = {"name": org.name, "address": org.primary_address, "phone": org.contact_phone,
              "email": org.contact_email}
    legal_text = None
    if program is not None:
        perfil = await ensure_profile(db, organization_id=invoice.organization_id, program_id=program.id)
        issuer = {
            "name": perfil.issuer_name or issuer["name"], "address": perfil.issuer_address or issuer["address"],
            "phone": perfil.issuer_phone or issuer["phone"], "email": perfil.issuer_email or issuer["email"],
        }
        legal_text = perfil.legal_text

    equipos = []
    approval_code = None
    if project is not None:
        equipos = [
            {"type": EQUIPMENT_LABELS.get(e.equipment_type, e.equipment_type), "brand_model": f"{e.brand} {e.model}",
             "serial": e.serial_number or "—", "quantity": e.quantity}
            for e in await equipment_of(db, project.id)
        ]
        if project.case_id:
            case = await db.get(Case, project.case_id)
            approval_code = case.approval_code if case else None

    reemplaza = await db.get(Invoice, invoice.replaces_invoice_id) if invoice.replaces_invoice_id else None
    return {
        "kind": invoice.kind,
        "number": invoice.invoice_number,
        "document_status": invoice.document_status,
        "void_reason": invoice.void_reason,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "replaces": reemplaza.invoice_number if reemplaza else None,
        "issuer": issuer,
        "legal_text": legal_text,
        "program": program.name if program else invoice.funder_program,
        "customer": {
            "name": customer.legal_name if customer else "—",
            "phone": customer.main_phone if customer else None,
            "email": customer.email if customer else None,
            "billing_address": customer.billing_address if customer else None,
        },
        "service_address": _address(project) if project else None,
        "work": project.title if project else None,
        "installed_on": project.completed_date if project else None,
        "approval_code": approval_code,
        "equipment": equipos,
        "lines": [
            {"kind": l.kind, "description": l.description, "quantity": l.quantity, "unit_price": l.unit_price,
             "amount": l.amount}
            for l in invoice.lines
        ],
        "subtotal": invoice.subtotal,
        "rebate_total": invoice.rebate_total,
        "customer_total": invoice.customer_total,
        "amount": Decimal(invoice.amount),
        "payments": [
            {"paid_on": p.paid_at, "reference": p.reference or p.method or "—", "amount": p.amount}
            for p in (invoice.payments or [])
        ],
        "paid_amount": invoice.paid_amount,
        "balance": invoice.balance,
        "notes": invoice.notes,
    }


def _address(project) -> str:
    return ", ".join(
        x for x in (project.address_street, project.address_unit, project.address_city, project.address_state,
                    project.address_zip) if x
    )


# ---------------------------------------------------------------------------
# Vista previa: la factura en memoria, sin guardar ni pedir número
# ---------------------------------------------------------------------------

PREVIEW_NUMBER = "PREVIEW"


async def preview_invoice(db: AsyncSession, *, organization_id, user, data: dict) -> tuple[Invoice, object, object]:
    """Arma la factura que se emitiría, sin agregarla a la sesión.

    - rebate: `project_id` + `program_id`, con la tarifa vigente en la fecha
      de la instalación (lo que haría `create_claim`).
    - particular: `lines` y `customer_id` o `project_id` (lo que haría
      `create_invoice`)."""
    from app.modules.billing import program_config
    from app.modules.billing.claims import installation_date_of, rebate_lines
    from app.modules.billing.service import build_lines, collectible_amount
    from app.modules.field_ops.access import get_visible_project
    from app.modules.field_ops.clock import org_today
    from app.shared.errors import InvalidInputError

    hoy = await org_today(db, organization_id)
    project = None
    if data.get("project_id"):
        project = await get_visible_project(db, organization_id=organization_id, user=user,
                                            project_id=data["project_id"])
    program = None
    if data.get("kind") == InvoiceKind.rebate:
        if project is None or not data.get("program_id"):
            raise InvalidInputError("La vista previa de rebate necesita la instalación y el programa.",
                                    code="preview_incomplete")
        program = await program_config.get_program_or_404(db, organization_id=organization_id,
                                                          program_id=data["program_id"])
        fecha = installation_date_of(project) or hoy
        tarifa = await program_config.rate_for(db, organization_id=organization_id, program_id=program.id, on=fecha)
        if tarifa is None:
            raise InvalidInputError(f"{program.name} no tiene tarifa vigente el {fecha.isoformat()}.",
                                    code="rate_missing")
        lineas = rebate_lines(project=project, amount=tarifa.amount, program_name=program.name)
        perfil = await program_config.ensure_profile(db, organization_id=organization_id, program_id=program.id)
        kind, customer_id, due = InvoiceKind.rebate, project.customer_id, perfil.expected_payment_days
    else:
        if not data.get("lines"):
            raise InvalidInputError("Agrega al menos una línea para ver la factura.", code="preview_incomplete")
        lineas = build_lines(data["lines"])
        customer_id = data.get("customer_id") or (project.customer_id if project else None)
        if customer_id is None:
            raise InvalidInputError("Indica el cliente o el proyecto de la factura.",
                                    code="invoice_customer_required")
        kind, due = InvoiceKind.particular, None

    from datetime import timedelta

    invoice = Invoice(
        organization_id=organization_id, kind=kind, project_id=project.id if project else None,
        case_id=project.case_id if project else None, customer_id=customer_id,
        invoice_number=PREVIEW_NUMBER, funder_program=program.name if program else None,
        amount=collectible_amount(kind, lineas), document_status=DocumentStatus.draft, issue_date=hoy,
        due_date=data.get("due_date") or (hoy + timedelta(days=due) if due else None),
        notes=data.get("notes"), lines=lineas, payments=[],
    )
    return invoice, program, project


# ---------------------------------------------------------------------------
# Dibujo
# ---------------------------------------------------------------------------

_INK = colors.HexColor("#111827")
_MUTED = colors.HexColor("#6b7280")
_LINE = colors.HexColor("#e5e7eb")
_HEAD = colors.HexColor("#f3f4f6")
_RED = colors.HexColor("#b91c1c")


def _money(value) -> str:
    v = Decimal(value or 0)
    signo = "-" if v < 0 else ""
    return f"{signo}${abs(v):,.2f}"


def _day(value: date | None) -> str:
    return value.strftime("%b %d, %Y") if value else "—"


def _esc(text) -> str:
    return (str(text) if text is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_invoice_pdf(doc: dict) -> bytes:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            title=f"{LABELS['invoice']} {doc['number']}")
    base = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=base["BodyText"], fontSize=9.5, leading=12, textColor=_INK)
    small = ParagraphStyle("s", parent=normal, fontSize=8.5, leading=11, textColor=_MUTED)
    h = ParagraphStyle("h", parent=normal, fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=10, spaceAfter=4)
    L = LABELS
    story = []

    # Encabezado: quien factura a la izquierda, número y fechas a la derecha.
    issuer = doc["issuer"]
    izquierda = [Paragraph(f"<b><font size=13>{_esc(issuer['name'])}</font></b>", normal)]
    for extra in (issuer["address"], issuer["phone"], issuer["email"]):
        if extra:
            izquierda.append(Paragraph(_esc(extra), small))
    derecha = [
        Paragraph(f"<b><font size=18>{L['invoice']}</font></b>", ParagraphStyle("r", parent=normal, alignment=2, leading=24)),
        Paragraph(f"{L['number']}: <b>{_esc(doc['number'])}</b>", ParagraphStyle("r2", parent=normal, alignment=2)),
        Paragraph(f"{L['issue_date']}: {_day(doc['issue_date'])}", ParagraphStyle("r3", parent=small, alignment=2)),
        Paragraph(f"{L['due_date']}: {_day(doc['due_date'])}", ParagraphStyle("r4", parent=small, alignment=2)),
    ]
    if doc["replaces"]:
        derecha.append(Paragraph(f"{L['replaces']}: {_esc(doc['replaces'])}",
                                 ParagraphStyle("r5", parent=small, alignment=2)))
    cabecera = Table([[izquierda, derecha]], colWidths=[3.8 * inch, 3.3 * inch])
    cabecera.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(cabecera)

    if doc["document_status"] in (DocumentStatus.draft, DocumentStatus.void):
        marca = L["draft"] if doc["document_status"] == DocumentStatus.draft else L["void"]
        detalle = f" — {_esc(doc['void_reason'])}" if doc["document_status"] == DocumentStatus.void and doc["void_reason"] else ""
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>{marca}</b>{detalle}",
                               ParagraphStyle("m", parent=normal, textColor=_RED, fontSize=11)))
    story.append(Spacer(1, 10))

    # A quién se factura.
    cliente = doc["customer"]
    if doc["kind"] == InvoiceKind.rebate:
        para = [Paragraph(f"<b>{L['bill_to']}</b>", small), Paragraph(f"<b>{_esc(doc['program'])}</b>", normal)]
        cli = [Paragraph(f"<b>{L['customer']}</b>", small), Paragraph(_esc(cliente["name"]), normal)]
    else:
        para = [Paragraph(f"<b>{L['bill_to']}</b>", small), Paragraph(f"<b>{_esc(cliente['name'])}</b>", normal)]
        for extra in (cliente["billing_address"], cliente["phone"], cliente["email"]):
            if extra:
                para.append(Paragraph(_esc(extra), small))
        cli = []
    if doc["service_address"]:
        cli += [Paragraph(f"<b>{L['service_address']}</b>", small), Paragraph(_esc(doc["service_address"]), normal)]
    bloque = Table([[para, cli]], colWidths=[3.55 * inch, 3.55 * inch])
    bloque.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(bloque)

    # Trabajo realizado y equipos del módulo 5.
    if doc["work"]:
        story.append(Paragraph(L["work"], h))
        filas = [f"{_esc(doc['work'])}", f"{L['installed_on']}: {_day(doc['installed_on'])}"]
        if doc["kind"] == InvoiceKind.rebate and doc["approval_code"]:
            filas.append(f"{L['approval']}: {_esc(doc['approval_code'])}")
        for fila in filas:
            story.append(Paragraph(fila, normal))
    if doc["equipment"]:
        story.append(Paragraph(L["equipment"], h))
        filas = [[L["type"], L["brand_model"], L["serial"], L["qty"]]] + [
            [Paragraph(_esc(e["type"]), normal), Paragraph(_esc(e["brand_model"]), normal),
             Paragraph(_esc(e["serial"]), normal), str(e["quantity"])]
            for e in doc["equipment"]
        ]
        story.append(_grid(filas, [2.3, 2.5, 1.7, 0.6], align_last=True))

    # Líneas y totales.
    story.append(Spacer(1, 12))
    filas = [[L["description"], L["qty"], L["unit_price"], L["amount"]]]
    for l in doc["lines"]:
        monto = -l["amount"] if l["kind"] == "rebate" else l["amount"]
        filas.append([Paragraph(_esc(l["description"]), normal), f"{Decimal(l['quantity']):g}",
                      _money(l["unit_price"]), _money(monto)])
    story.append(_grid(filas, [4.1, 0.6, 1.2, 1.2], align_last=True, align_from=1))

    totales = [[L["subtotal"], _money(doc["subtotal"])]]
    if doc["rebate_total"]:
        totales.append([L["rebate"], _money(-doc["rebate_total"])])
    totales.append([L["customer_total"], _money(doc["customer_total"])])
    if doc["kind"] == InvoiceKind.rebate:
        totales.append([f"<b>{L['program_due']}</b>", f"<b>{_money(doc['amount'])}</b>"])
    tabla = Table([[Paragraph(a, ParagraphStyle("t", parent=normal, alignment=2)),
                    Paragraph(b, ParagraphStyle("t2", parent=normal, alignment=2))] for a, b in totales],
                  colWidths=[5.9 * inch, 1.2 * inch])
    tabla.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.8, _INK)]))
    story.append(Spacer(1, 4))
    story.append(tabla)

    # Pagos y balance.
    if doc["payments"]:
        story.append(Paragraph(L["payments"], h))
        filas = [[L["paid_on"], L["reference"], L["amount"]]] + [
            [_day(p["paid_on"]), Paragraph(_esc(p["reference"]), normal), _money(p["amount"])]
            for p in doc["payments"]
        ]
        story.append(_grid(filas, [1.5, 4.4, 1.2], align_last=True))
    balance = Table([[Paragraph(f"<b>{L['balance']}</b>", ParagraphStyle("b", parent=normal, alignment=2)),
                      Paragraph(f"<b>{_money(doc['balance'])}</b>", ParagraphStyle("b2", parent=normal, alignment=2))]],
                    colWidths=[5.9 * inch, 1.2 * inch])
    balance.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _HEAD)]))
    story.append(Spacer(1, 6))
    story.append(balance)

    if doc["notes"]:
        story.append(Spacer(1, 10))
        story.append(Paragraph(_esc(doc["notes"]), small))
    if doc["legal_text"]:
        story.append(Spacer(1, 12))
        story.append(Paragraph(_esc(doc["legal_text"]).replace("\n", "<br/>"), small))

    pdf.build(story)
    return buffer.getvalue()


def _grid(filas, widths, *, align_last=False, align_from=None) -> Table:
    tabla = Table(filas, colWidths=[w * inch for w in widths], repeatRows=1)
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _HEAD), ("LINEBELOW", (0, 0), (-1, -1), 0.5, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if align_last:
        estilo.append(("ALIGN", (-1, 0), (-1, -1), "RIGHT"))
    if align_from is not None:
        estilo.append(("ALIGN", (align_from, 0), (-1, -1), "RIGHT"))
    tabla.setStyle(TableStyle(estilo))
    return tabla

