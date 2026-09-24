"""Local-disk evidence/report storage.

The spec (section 12) calls for S3 with signed upload/download URLs in
production. Until AWS infrastructure is wired up (see README "Known
follow-ups"), this module stores files on local disk under
`settings.STORAGE_DIR`, organized per organization so tenants never share a
path. Swapping this for S3 later only means changing `save_bytes` /
`read_bytes` / `build_download_url` — callers never touch the filesystem
directly.
"""
import uuid
from pathlib import Path, PurePosixPath

from app.core.config import get_settings
from app.shared.errors import InvalidInputError

settings = get_settings()


def _storage_root() -> Path:
    root = Path(settings.STORAGE_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sanitize_filename(filename: str | None) -> str:
    """Strips any directory components / traversal sequences from a
    caller-supplied filename (OWASP path traversal, CWE-22). A browser
    always sends just a filename, but nothing stops a crafted multipart
    request from sending "../../etc/passwd" or an absolute path, and
    Path's "/" operator happily follows a "/"-containing string right out
    of the intended directory, so this must run before the name ever
    touches a Path."""
    name = PurePosixPath(Path(filename or "file").name).name
    return name.lstrip(".") or "file"


def save_bytes(*, organization_id: uuid.UUID, subfolder: str, filename: str, data: bytes) -> str:
    """Saves bytes under storage/<org_id>/<subfolder>/<uuid>_<filename> and
    returns the storage-relative path (what we persist in the DB)."""
    root = _storage_root()
    org_dir = (root / str(organization_id) / subfolder).resolve()
    if root not in org_dir.parents and org_dir != root:
        # Un intento de salir del directorio de la organización es una
        # petición inválida, no un fallo del servidor: con ValueError salía
        # como 500 y quedaba invisible entre los errores genéricos.
        raise InvalidInputError(
            "La ruta de almacenamiento no es válida.", code="invalid_storage_path"
        )
    org_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{_sanitize_filename(filename)}"
    path = org_dir / safe_name
    path.write_bytes(data)
    return str(path.relative_to(root))


def _resolve_within_root(relative_path: str) -> Path:
    root = _storage_root()
    path = (root / relative_path).resolve()
    if root != path and root not in path.parents:
        raise InvalidInputError(
            "La ruta de almacenamiento no es válida.", code="invalid_storage_path"
        )
    return path


def read_bytes(relative_path: str) -> bytes:
    return _resolve_within_root(relative_path).read_bytes()


def absolute_path(relative_path: str) -> Path:
    return _resolve_within_root(relative_path)
