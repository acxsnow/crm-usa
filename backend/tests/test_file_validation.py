"""Validación común de archivos (cierra SEG-01 y SEG-02)."""
import io

import pytest
from starlette.datastructures import UploadFile

from app.shared.errors import InvalidInputError
from app.shared.files.validation import check_type, read_limited, sniff_mime
from tests.field_helpers import jpeg_bytes


async def test_reading_stops_as_soon_as_the_limit_is_passed():
    class Contador(io.BytesIO):
        leido = 0

        def read(self, n=-1):
            dato = super().read(n)
            Contador.leido += len(dato)
            return dato

    grande = UploadFile(file=Contador(b"x" * (5 * 1024 * 1024)), filename="big.bin")
    with pytest.raises(InvalidInputError, match="límite de 2 MB"):
        await read_limited(grande, 2 * 1024 * 1024)
    # Cortó al pasar el límite: no leyó los 5 MB.
    assert Contador.leido <= 3 * 1024 * 1024


async def test_an_empty_file_is_rejected():
    with pytest.raises(InvalidInputError, match="vacío"):
        await read_limited(UploadFile(file=io.BytesIO(b""), filename="x.jpg"), 1024)


def test_the_real_type_is_read_from_the_content():
    assert sniff_mime(jpeg_bytes()) == "jpeg"
    assert sniff_mime(b"%PDF-1.7 ...") == "pdf"
    assert sniff_mime(b"\x00\x00\x00\x18ftypmp42") == "mp4"
    assert sniff_mime(b"MZ\x90\x00") is None


def test_a_renamed_executable_is_not_a_photo():
    with pytest.raises(InvalidInputError, match="no corresponde"):
        check_type(b"MZ\x90\x00 programa", "image/jpeg", {"image/jpeg"})
    with pytest.raises(InvalidInputError, match="no permitido"):
        check_type(jpeg_bytes(), "application/x-msdownload", {"image/jpeg"})
    assert check_type(jpeg_bytes(), "IMAGE/JPEG", {"image/jpeg"}) == "image/jpeg"
    # Un tipo permitido sin firma conocida no pasa sin revisar el contenido.
    with pytest.raises(InvalidInputError, match="no corresponde"):
        check_type(b"MZ\x90\x00", "video/mpeg", {"video/mpeg"})
    with pytest.raises(InvalidInputError, match="no corresponde"):
        check_type(b"GIF89a", "image/gif", {"image/gif"})
    assert check_type(b"\x00\x00\x01\xba\x44", "video/mpeg", {"video/mpeg"}) == "video/mpeg"


async def test_evidence_rejects_a_disguised_file(app_client, active_admin_user, seeded_org):
    from tests.test_field_ops import _admin_headers, _create_customer_and_project

    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)
    files = {"file": ("foto.jpg", b"MZ\x90\x00 esto es un ejecutable", "image/jpeg")}
    r = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files,
                              data={"category": "additional_photo"}, headers=headers)
    assert r.status_code == 400 and "no corresponde" in r.json()["detail"]


# --- PDF completo (spec 2026-10-14-pdf-completo) ----------------------------

PDF_TIPOS = {"application/pdf"}


def test_a_real_pdf_passes():
    from tests.field_helpers import pdf_bytes

    assert check_type(pdf_bytes(), "application/pdf", PDF_TIPOS) == "application/pdf"
    assert check_type(pdf_bytes() + b"\r\n  \n", "application/pdf", PDF_TIPOS) == "application/pdf"


@pytest.mark.parametrize("contenido", [
    b"%PDF-1.4 QA documento\n%%EOF",   # el del script de QA: cabecera y fin, sin documento
    b"%PDF-1.7 x",                     # solo la cabecera
], ids=["falso-del-qa", "solo-cabecera"])
def test_a_fake_pdf_is_rejected(contenido):
    with pytest.raises(InvalidInputError) as err:
        check_type(contenido, "application/pdf", PDF_TIPOS)
    assert err.value.code == "pdf_incomplete"


def test_a_pdf_cut_in_half_is_rejected():
    """Se cae la señal a mitad de la subida: empieza bien pero no termina."""
    from tests.field_helpers import pdf_bytes

    real = pdf_bytes()
    with pytest.raises(InvalidInputError) as err:
        check_type(real[: len(real) // 2], "application/pdf", PDF_TIPOS)
    assert err.value.code == "pdf_incomplete"
    assert "incompleto" in err.value.message
