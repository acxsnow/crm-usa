"""Extracción: baja de CompanyCam a la caché en disco (solo lectura, sin base
de datos). Se puede interrumpir y repetir: los proyectos con `.done` se saltan."""
from datetime import datetime, timezone

from app.modules.imports.companycam.cache import SUBRESOURCES, ExportCache
from app.modules.imports.companycam.client import CompanyCamClient, CompanyCamNotFound


async def extract(client: CompanyCamClient, cache: ExportCache, *, only: set[str] | None = None,
                  limit: int | None = None, log=print) -> dict:
    resumen = {"projects": 0, "skipped_done": 0, "gone": [], "photos": 0, "documents": 0}

    cache.write_json(cache.root / "users.json", await client.list_all("/users"))
    tags = await client.list_all("/tags")
    cache.write_json(cache.root / "tags.json", tags)
    # foto -> etiquetas. CompanyCam no trae las etiquetas dentro de la foto; se
    # recorre cada etiqueta con el filtro de fotos.
    por_foto: dict[str, list[str]] = {}
    for t in tags:
        nombre = t.get("display_value") or t.get("value")
        async for foto in client.paginate("/photos", {"tag_ids[]": t["id"]}):
            por_foto.setdefault(str(foto["id"]), []).append(nombre)
    cache.write_json(cache.root / "tag_photos.json", por_foto)

    if only:
        proyectos = []
        for pid in sorted(only):
            try:
                proyectos.append(await client.project(pid))
            except CompanyCamNotFound:
                resumen["gone"].append(pid)
                log(f"proyecto {pid}: 404 (eliminado), se omite")
    else:
        proyectos = await client.list_all("/projects")
        # Guardar solo los proyectos pedidos con --limit mantiene la caché chica.
        if limit is not None:
            proyectos = proyectos[:limit]
    cache.write_projects(proyectos)

    for p in proyectos:
        pid = str(p["id"])
        if cache.is_done(pid):
            resumen["skipped_done"] += 1
            continue
        carpeta = cache.project_dir(pid)
        for sub in SUBRESOURCES:
            try:
                datos = await client.list_all(f"/projects/{pid}/{sub}")
            except CompanyCamNotFound:
                datos = []
                resumen["gone"].append(pid)
            cache.write_json(carpeta / f"{sub}.json", datos)
            if sub in ("photos", "documents"):
                resumen[sub] += len(datos)
        cache.mark_done(pid)
        resumen["projects"] += 1
        if resumen["projects"] % 25 == 0:
            log(f"{resumen['projects']} proyectos extraídos…")

    cache.write_json(cache.root / "manifest.json", {
        "extracted_at": datetime.now(timezone.utc).isoformat(), "projects": len(proyectos),
        "photos": resumen["photos"], "documents": resumen["documents"], "gone": resumen["gone"],
    })
    return resumen
