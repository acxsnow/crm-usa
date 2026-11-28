"""Descarga de fotos y documentos importados de CompanyCam.

    python -m scripts.companycam_download enqueue --org <uuid>          # encola la tarea de Celery (lotes de 10)
    python -m scripts.companycam_download run --org <uuid> [--limit N]  # procesa en línea, sin Celery
    python -m scripts.companycam_download status --org <uuid>
    python -m scripts.companycam_download retry-errors --org <uuid>
    python -m scripts.companycam_download purge --org <uuid> --confirm  # borra binarios de expedientes ya eliminados

En producción la descarga se lanza desde la Shell de Render con `enqueue`: el
trabajo lo hace el worker que ya corre dentro del servicio web, con el disco
de producción. `run` y `purge` escriben o borran en `STORAGE_DIR`, así que se
niegan a correr si no es `/app/storage` (el disco del servicio), para no
llenar por error el disco de un portátil o borrar archivos de otro sitio;
en local se habilitan con `--allow-local-storage`.
La descarga se detiene sola si quedan menos de `COMPANYCAM_MIN_FREE_GB` GB
libres (2 por defecto).
"""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db import all_models as _all_models  # noqa: E402,F401
from app.db.session import worker_session  # noqa: E402
from app.modules.imports.companycam import downloads  # noqa: E402
from app.modules.imports.companycam.client import CompanyCamClient, resolve_token  # noqa: E402

PROD_STORAGE = Path("/app/storage")


def storage_allowed(allow_local: bool) -> bool:
    return allow_local or Path(get_settings().STORAGE_DIR).resolve() == PROD_STORAGE


async def _run(org: uuid.UUID, limit: int | None) -> int:
    token = get_settings().COMPANYCAM_TOKEN or resolve_token()
    client = CompanyCamClient(token) if token else None
    hechos = 0
    try:
        async with worker_session() as db:
            while limit is None or hechos < limit:
                tam = downloads.BATCH_SIZE if limit is None else min(downloads.BATCH_SIZE, limit - hechos)
                r = await downloads.process_batch(db, org, client=client, size=tam)
                procesados = sum(v for k, v in r.items() if k not in ("remaining", "disk_full"))
                hechos += procesados
                print(f"lote: {r}")
                if r.get("disk_full"):
                    print("Disco casi lleno: cola detenida. Libera espacio y vuelve a correr.")
                    break
                if procesados == 0 or not r.get("remaining"):
                    break
    finally:
        if client is not None:
            await client.aclose()
    print(f"Procesados: {hechos}")
    return 0


async def _simple(cmd: str, org: uuid.UUID, confirm: bool) -> int:
    async with worker_session() as db:
        if cmd == "status":
            for kind, estados in sorted((await downloads.status(db, org)).items()):
                print(kind, estados)
        elif cmd == "retry-errors":
            print("Reencolados:", await downloads.retry_errors(db, org))
        elif cmd == "purge":
            if not confirm:
                print("Falta --confirm: purge borra archivos del disco.")
                return 2
            print("Archivos borrados:", await downloads.purge(db, org))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("enqueue", "run", "status", "retry-errors", "purge"):
        sp = sub.add_parser(nombre)
        sp.add_argument("--org", required=True)
        if nombre in ("run", "purge"):
            sp.add_argument("--allow-local-storage", action="store_true")
        if nombre == "run":
            sp.add_argument("--limit", type=int)
        if nombre == "purge":
            sp.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    org = uuid.UUID(args.org)
    if args.cmd in ("run", "purge") and not storage_allowed(args.allow_local_storage):
        print(f"Me niego: STORAGE_DIR no es {PROD_STORAGE}. Usa `enqueue` desde la Shell de Render, "
              "o --allow-local-storage si es a propósito (local).")
        return 2
    if args.cmd == "enqueue":
        from app.workers.tasks import companycam_download_batch_task

        print("Encolada:", companycam_download_batch_task.delay(str(org)).id)
        return 0
    if args.cmd == "run":
        return asyncio.run(_run(org, args.limit))
    return asyncio.run(_simple(args.cmd, org, getattr(args, "confirm", False)))


if __name__ == "__main__":
    sys.exit(main())
