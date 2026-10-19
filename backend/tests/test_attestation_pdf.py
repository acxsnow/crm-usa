"""PDF del acta (spec 2026-10-18-firmas-del-acta): título del documento con el
nombre real de la organización, expediente y equipos instalados, y las firmas
en la misma hoja que el texto de conformidad."""
import base64
import re
import zlib

from tests.field_helpers import add_equipment_directly, headers_for, ready_to_install_case
from tests.test_cases_intake import firma_png


def _texto(pdf: bytes) -> bytes:
    """Lo que se lee del PDF: ReportLab comprime cada página (ASCII85 + Flate)."""
    partes = [pdf]
    for cuerpo in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            partes.append(zlib.decompress(base64.a85decode(cuerpo.strip(), adobe=False).rstrip(b"~>")))
        except Exception:
            try:
                partes.append(zlib.decompress(base64.a85decode(cuerpo.strip().removesuffix(b"~>"))))
            except Exception:
                pass
    return b"\n".join(partes)


async def test_the_acta_pdf_is_titled_and_fits_on_one_page(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    await add_equipment_directly(db, project)
    h = await headers_for(app_client, "tech@acme-demo.com")
    base = f"/api/v1/projects/{project.id}/attestation"
    await app_client.post(f"{base}/technician-sign", json={"signature_base64": firma_png()}, headers=h)
    acta = (await app_client.post(f"{base}/customer-sign",
                                  json={"customer_name": "Marge Simpson", "signature_base64": firma_png()}, headers=h)).json()

    pdf = (await app_client.get(f"/api/v1/attestations/{acta['id']}/pdf", headers=h)).content
    texto = _texto(pdf)
    assert b"Firma del cliente" in texto, "no se pudo leer el contenido del PDF"
    assert b"CRM Field Ops" not in texto
    assert b"Acta de instalaci" in texto                    # título del documento
    assert seeded_org["org"].name.encode() in texto         # la organización real
    assert project.case_number.encode() in texto            # el expediente
    assert b"SN-0001" in texto                              # el serial del equipo instalado
    assert b"Marge Simpson" in texto                        # quien firmó
    paginas = len(re.findall(rb"/Type /Page[^s]", pdf))
    assert paginas == 1, f"el acta ocupa {paginas} páginas"
