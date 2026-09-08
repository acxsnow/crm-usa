"""Generates the signed attestation PDF: project summary, checklist status,
and the technician + customer signatures embedded as images (confirmed
requirement — replaces the paper signature section on the current forms).
"""
import base64
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet


def decode_signature_png(signature_base64: str) -> bytes:
    """Accepts a data URL (data:image/png;base64,....) or bare base64 and
    returns raw PNG bytes."""
    if "," in signature_base64 and signature_base64.strip().startswith("data:"):
        signature_base64 = signature_base64.split(",", 1)[1]
    return base64.b64decode(signature_base64)


def build_attestation_pdf(
    *, project, customer, checklist_items: list, attestation, organization_name: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{organization_name}</b>", styles["Title"]))
    story.append(Paragraph("Acta de instalación y atestación de conformidad", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    address = ", ".join(
        filter(None, [project.address_street, project.address_unit, project.address_city, project.address_state, project.address_zip])
    )
    info_rows = [
        ["Cliente:", customer.legal_name],
        ["Dirección:", address or "—"],
        ["Proyecto:", project.title],
        ["Tipo:", project.project_type or "—"],
        ["Fecha de instalación:", str(project.completed_date or project.scheduled_date or "—")],
    ]
    info_table = Table(info_rows, colWidths=[1.8 * inch, 4.7 * inch])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Lista de verificación", styles["Heading3"]))
    checklist_rows = [["✓", "Elemento", "Requerido"]]
    for item in checklist_items:
        checklist_rows.append([
            "Sí" if item.is_complete else "No",
            item.label,
            "Sí" if item.is_required else "No",
        ])
    checklist_table = Table(checklist_rows, colWidths=[0.6 * inch, 4.8 * inch, 1.1 * inch])
    checklist_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(checklist_table)
    story.append(Spacer(1, 0.35 * inch))

    story.append(Paragraph(
        "El cliente confirma que la instalación fue realizada satisfactoriamente y que recibió "
        "explicación sobre el uso y garantía del equipo. Ambas firmas fueron capturadas "
        "electrónicamente dentro de la aplicación en el momento de la visita.",
        styles["BodyText"],
    ))
    story.append(Spacer(1, 0.3 * inch))

    sig_cells = []
    sig_labels = []
    for label, sig_path, signed_at in [
        ("Firma del técnico", attestation.technician_signature_path, attestation.technician_signed_at),
        ("Firma del cliente", attestation.customer_signature_path, attestation.customer_signed_at),
    ]:
        if sig_path:
            from app.modules.field_ops.storage import absolute_path
            img = RLImage(str(absolute_path(sig_path)), width=2.6 * inch, height=1.1 * inch)
            sig_cells.append(img)
        else:
            sig_cells.append(Paragraph("(sin firmar)", styles["BodyText"]))
        signed_str = signed_at.strftime("%Y-%m-%d %H:%M UTC") if signed_at else "—"
        sig_labels.append(Paragraph(f"<b>{label}</b><br/>Firmado electrónicamente: {signed_str}", styles["BodyText"]))

    sig_table = Table([sig_cells, sig_labels], colWidths=[3.1 * inch, 3.1 * inch])
    sig_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story.append(sig_table)

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"Documento generado el {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.",
        styles["BodyText"],
    ))

    doc.build(story)
    return buffer.getvalue()
