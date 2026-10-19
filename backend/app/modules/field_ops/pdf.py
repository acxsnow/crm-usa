"""Generates the signed attestation PDF: project summary, checklist status,
installed equipment and the technician + customer signatures embedded as
images (confirmed requirement — replaces the paper signature section on the
current forms).
"""
import base64
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.field_ops.catalogs import EQUIPMENT_TYPES

TITULO = "Acta de instalación y conformidad"


def decode_signature_png(signature_base64: str) -> bytes:
    """Accepts a data URL (data:image/png;base64,....) or bare base64 and
    returns raw PNG bytes."""
    if "," in signature_base64 and signature_base64.strip().startswith("data:"):
        signature_base64 = signature_base64.split(",", 1)[1]
    return base64.b64decode(signature_base64)


def _tabla(filas, anchos, *, cabecera=True):
    tabla = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Filas bajas: con el checklist completo el acta cabe en una hoja.
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if cabecera:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                   ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    tabla.setStyle(TableStyle(estilo))
    return tabla


def build_attestation_pdf(
    *, project, customer, checklist_items: list, attestation, organization_name: str, equipment: list = (),
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            title=TITULO, author=organization_name)
    styles = getSampleStyleSheet()
    story = []

    # El título es el del documento; la empresa va debajo (antes decía «CRM Field Ops»).
    story.append(Paragraph(TITULO, styles["Title"]))
    if organization_name:
        story.append(Paragraph(organization_name, styles["Heading3"]))
    story.append(Spacer(1, 0.1 * inch))

    address = ", ".join(
        filter(None, [project.address_street, project.address_unit, project.address_city, project.address_state, project.address_zip])
    )
    info_rows = [
        ["Expediente:", project.case_number or "—"],
        ["Cliente:", customer.legal_name if customer else "—"],
        ["Dirección:", address or "—"],
        ["Proyecto:", project.title],
        ["Fecha de instalación:", str(project.completed_date or project.scheduled_date or "—")],
    ]
    info_table = Table(info_rows, colWidths=[1.8 * inch, 4.7 * inch])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
    ]))
    story.append(info_table)

    if equipment:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Equipos instalados", styles["Heading3"]))
        filas = [["Tipo", "Marca y modelo", "Serial", "Cant.", "Unidad"]]
        for e in equipment:
            filas.append([EQUIPMENT_TYPES.get(e.equipment_type, e.equipment_type), f"{e.brand} {e.model}",
                          e.serial_number or "—", str(e.quantity), e.unit_label or "—"])
        story.append(_tabla(filas, [1.9 * inch, 1.8 * inch, 1.2 * inch, 0.5 * inch, 1.1 * inch]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Lista de verificación", styles["Heading3"]))
    checklist_rows = [["Hecho", "Elemento", "Requerido"]]
    for item in checklist_items:
        hecho = "N/A" if getattr(item, "not_applicable", False) else ("Sí" if item.is_complete else "No")
        checklist_rows.append([hecho, item.label, "Sí" if item.is_required else "No"])
    story.append(_tabla(checklist_rows, [0.6 * inch, 4.8 * inch, 1.1 * inch]))
    story.append(Spacer(1, 0.15 * inch))

    sig_cells = []
    sig_labels = []
    for label, nombre, sig_path, signed_at in [
        ("Firma del técnico", None, attestation.technician_signature_path, attestation.technician_signed_at),
        ("Firma del cliente", attestation.customer_name, attestation.customer_signature_path, attestation.customer_signed_at),
    ]:
        if sig_path:
            from app.shared.files.storage import absolute_path
            sig_cells.append(RLImage(str(absolute_path(sig_path)), width=2.2 * inch, height=0.75 * inch))
        else:
            sig_cells.append(Paragraph("(sin firmar)", styles["BodyText"]))
        signed_str = signed_at.strftime("%Y-%m-%d %H:%M UTC") if signed_at else "—"
        quien = f"<br/>{nombre}" if nombre else ""
        sig_labels.append(Paragraph(f"<b>{label}</b>{quien}<br/>Firmado electrónicamente: {signed_str}", styles["BodyText"]))

    sig_table = Table([sig_cells, sig_labels], colWidths=[3.25 * inch, 3.25 * inch])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),  # las firmas, sobre la línea
        ("VALIGN", (0, 1), (-1, 1), "TOP"),     # los nombres, alineados arriba
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#9ca3af")),
    ]))
    # El texto de conformidad y las firmas van juntos: si no caben, pasan
    # juntos a la hoja siguiente en vez de dejar las firmas solas.
    story.append(KeepTogether([
        Paragraph(
            "El cliente confirma que la instalación fue realizada satisfactoriamente y que recibió "
            "explicación sobre el uso y garantía del equipo. Las firmas fueron capturadas "
            "electrónicamente en la aplicación.",
            styles["BodyText"],
        ),
        Spacer(1, 0.12 * inch),
        sig_table,
        Spacer(1, 0.12 * inch),
        Paragraph(
            f"Documento generado el {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
            styles["BodyText"],
        ),
    ]))

    doc.build(story)
    return buffer.getvalue()
