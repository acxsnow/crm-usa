"""Migración CompanyCam → CRM (uso único, temporal).

    python -m scripts.companycam_import extract [--only id1,id2] [--limit N]
    python -m scripts.companycam_import load --org <uuid> [--dry-run] [--only id1,id2] [--limit N]
    python -m scripts.companycam_import rollback --confirm --org <uuid>

`extract` solo lee CompanyCam y escribe en `~/companycam_export/`. `load` lee
esa caché y escribe en la base de `DATABASE_URL`. El token sale de la variable
`COMPANYCAM_TOKEN` o de `~/.companycam.env`; nunca se imprime.
No importa `app.main`: usa los modelos y servicios del backend."""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import all_models as _all_models  # noqa: E402,F401
from app.db.session import worker_session  # noqa: E402
from app.modules.imports.companycam.cache import ExportCache  # noqa: E402
from app.modules.imports.companycam.client import CompanyCamClient, resolve_token  # noqa: E402
from app.modules.imports.companycam.extract import extract  # noqa: E402
from app.modules.imports.companycam.loader import ImportAborted, Loader  # noqa: E402
from app.modules.imports.companycam.rollback import rollback_import  # noqa: E402


def _ids(texto: str | None) -> set[str] | None:
    return {x.strip() for x in texto.split(",") if x.strip()} if texto else None


async def _extract(args) -> int:
    token = resolve_token()
    if not token:
        print("Falta COMPANYCAM_TOKEN (variable de entorno o ~/.companycam.env).")
        return 2
    async with CompanyCamClient(token) as client:
        r = await extract(client, ExportCache(args.cache), only=_ids(args.only), limit=args.limit)
    print("Extracción:", r)
    return 0


async def _load(args) -> int:
    cache = ExportCache(args.cache)
    async with worker_session() as db:
        try:
            r = await Loader(db, uuid.UUID(args.org), cache, dry_run=args.dry_run).run(
                only=_ids(args.only), limit=args.limit)
        except ImportAborted as exc:
            print(f"Abortado: {exc}")
            return 1
    print(("SIMULACIÓN (no se guardó nada). " if args.dry_run else "Carga lista. ") + "Conteos:")
    for k in sorted(r):
        print(f"  {k}: {r[k]}")
    print(f"Informes en {cache.reports_dir}")
    return 0


async def _rollback(args) -> int:
    if not args.confirm:
        print("Falta --confirm: la reversa borra datos.")
        return 2
    cache = ExportCache(args.cache)
    async with worker_session() as db:
        r = await rollback_import(db, uuid.UUID(args.org), cache)
    print("Reversa:", r)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=None, help="carpeta de la caché (por defecto ~/companycam_export)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--only")
    e.add_argument("--limit", type=int)
    c = sub.add_parser("load")
    c.add_argument("--org", required=True)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--only")
    c.add_argument("--limit", type=int)
    r = sub.add_parser("rollback")
    r.add_argument("--org", required=True)
    r.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    return asyncio.run({"extract": _extract, "load": _load, "rollback": _rollback}[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
