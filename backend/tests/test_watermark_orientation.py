"""La marca de agua respeta la orientación de la foto del celular (29 oct 2026).

El celular guarda los píxeles «acostados» y anota en el EXIF cómo girarlos. Al
quemar la marca y volver a guardar sin aplicar ese giro, la foto tomada de
frente se veía de lado.
"""
import io
from datetime import datetime, timezone

from PIL import Image

from app.shared.files.watermark import apply_gps_watermark

ORIENTATION = 0x0112


def _foto_acostada(orientacion: int) -> bytes:
    """Como la guarda el celular: 400×200 en píxeles y el giro en el EXIF."""
    img = Image.new("RGB", (400, 200), (200, 40, 40))
    exif = Image.Exif()
    exif[ORIENTATION] = orientacion
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


def _marcar(datos: bytes) -> Image.Image:
    return Image.open(io.BytesIO(apply_gps_watermark(
        datos, latitude=33.45, longitude=-112.07, captured_at=datetime(2026, 10, 29, tzinfo=timezone.utc))))


def test_a_phone_photo_taken_upright_stays_upright():
    # 6 = girar 90° a la derecha: la foto real es vertical.
    assert _marcar(_foto_acostada(6)).size == (200, 400)
    # 8 = girar 90° a la izquierda.
    assert _marcar(_foto_acostada(8)).size == (200, 400)


def test_the_watermark_goes_at_the_bottom_of_the_upright_photo():
    marcada = _marcar(_foto_acostada(6))
    ancho, alto = marcada.size
    # Abajo va la franja oscura de la marca; arriba sigue el color de la foto.
    assert sum(marcada.getpixel((ancho // 2, alto - 3))) < sum(marcada.getpixel((ancho // 2, 10)))


def test_a_photo_without_orientation_is_not_rotated():
    img = Image.new("RGB", (400, 200), (200, 40, 40))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    assert _marcar(out.getvalue()).size == (400, 200)
