"""Validación común de archivos subidos (cierra SEG-01 y SEG-02).

- **Tamaño mientras se recibe** (SEG-01): `read_limited` lee por partes y corta
  apenas se pasa del límite. Antes se leía el archivo entero en memoria y
  después se medía: un envío enorme agotaba la memoria antes del rechazo.
- **Tipo real por contenido** (SEG-02): `sniff_mime` reconoce el formato por
  sus primeros bytes ("número mágico"). El tipo que declara el navegador no
  basta: un ejecutable renombrado `foto.jpg` llega como `image/jpeg`.
  `check_type` exige que el tipo declarado esté permitido **y** que el
  contenido sea de esa familia.

Lo usan todos los puntos de subida: evidencias de campo, archivos del
expediente y adjuntos de factura.
"""
from fastapi import UploadFile

from app.shared.errors import InvalidInputError

CHUNK = 1024 * 1024

# Familias: tipos declarados que comparten formato real.
_FAMILY = {
    "image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png", "image/webp": "webp",
    "image/heic": "heic", "image/heif": "heic", "application/pdf": "pdf",
    "video/mp4": "mp4", "video/quicktime": "mp4", "video/webm": "webm",
}


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Lee el archivo sin pasar de `max_bytes`; si lo supera, corta y avisa."""
    partes, total = [], 0
    while True:
        parte = await file.read(CHUNK)
        if not parte:
            break
        total += len(parte)
        if total > max_bytes:
            raise InvalidInputError(f"El archivo supera el límite de {max_bytes // (1024 * 1024)} MB.",
                                    code="file_too_large")
        partes.append(parte)
    if total == 0:
        raise InvalidInputError("El archivo está vacío.", code="file_empty")
    return b"".join(partes)


def sniff_mime(data: bytes) -> str | None:
    """La familia del archivo según su contenido, o None si no se reconoce."""
    cabeza = data[:32]
    if cabeza.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if cabeza.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabeza[:4] == b"RIFF" and cabeza[8:12] == b"WEBP":
        return "webp"
    if cabeza.startswith(b"%PDF-"):
        return "pdf"
    if cabeza[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if cabeza[4:8] == b"ftyp":
        marca = cabeza[8:12]
        if marca in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"):
            return "heic"
        return "mp4"  # isom, mp41, mp42, qt (QuickTime), M4V…
    return None


def check_type(data: bytes, declared: str | None, allowed: set[str]) -> str:
    """Devuelve el tipo declarado (en minúsculas) si está permitido y el
    contenido corresponde; si no, rechaza con un mensaje claro."""
    tipo = (declared or "").lower().strip()
    if tipo not in allowed:
        raise InvalidInputError("Tipo de archivo no permitido para este campo.", code="invalid_file_type")
    esperado = _FAMILY.get(tipo)
    if esperado and sniff_mime(data) != esperado:
        raise InvalidInputError("El contenido del archivo no corresponde a su tipo. Sube una foto, video o PDF real.",
                                code="file_content_mismatch")
    return tipo
