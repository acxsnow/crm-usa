"""Ayudas de las pruebas de la importación de CompanyCam: una caché falsa con
tres proyectos (activo con contacto, activo archivado, eliminado)."""
import json

from app.modules.imports.companycam.cache import ExportCache

T0 = 1_760_000_000


def project(pid, *, status="active", archived=False, contact=None, creator=("111", "Carla Creadora"),
            street="7722 Cleon Ave", unit=None, name=None, created=T0, notepad=None, photo_count=0):
    return {
        "id": str(pid), "creator_id": creator[0], "creator_type": "User", "creator_name": creator[1],
        "status": status, "archived": archived, "name": name,
        "address": {"street_address_1": street, "street_address_2": unit, "city": "Los Angeles", "state": "Ca",
                    "postal_code": "91352", "country": "US"},
        "coordinates": {"lat": 34.2, "lon": -118.3}, "primary_contact": contact, "created_at": created,
        "photo_count": photo_count, "notepad": notepad, "project_url": f"https://app.companycam.com/projects/{pid}",
    }


def photo(fid, pid, *, url=None, tags=None):
    return {"id": str(fid), "project_id": str(pid), "creator_name": "Carla Creadora", "captured_at": T0 + 5,
            "coordinates": {"lat": 34.2, "lon": -118.3}, "description": None,
            "uris": [{"type": "original", "uri": url or f"https://img.test/{fid}.jpg",
                      "url": url or f"https://img.test/{fid}.jpg"}]}


def make_cache(tmp_path, *, with_users=True) -> ExportCache:
    cache = ExportCache(tmp_path / "export")
    p1 = project(1001, contact={"id": "c1", "name": "Marge Simpson", "email": "Marge@Example.com",
                                "phone_number": "+1 (818) 555-0101"}, unit="Spc 14", name="Casa Marge",
                 notepad="Falta el permiso", photo_count=2)
    p2 = project(1002, archived=True, street="10 Archived Rd")
    p3 = project(1003, status="deleted", creator=("222", "Vic Vendedor"), street="99 Gone St")
    cache.write_projects([p1, p2, p3])
    users = [{"id": "111", "first_name": "Carla", "last_name": "Creadora", "email_address": "carla@cc.test",
              "status": "active", "user_role": "standard"},
             {"id": "222", "first_name": "Vic", "last_name": "Vendedor", "email_address": "vendedor@acme-demo.com",
              "status": "active", "user_role": "standard"}] if with_users else []
    cache.write_json(cache.root / "users.json", users)
    cache.write_json(cache.root / "tags.json", [{"id": "t1", "display_value": "Front Side"}])
    cache.write_json(cache.root / "tag_photos.json", {"501": ["Front Side"]})
    d = cache.project_dir("1001")
    cache.write_json(d / "photos.json", [photo(501, 1001), photo(502, 1001)])
    cache.write_json(d / "comments.json", [{"id": "9001", "content": "Llamar al cliente", "creator_name": "Mariana",
                                            "created_at": T0 + 10}])
    cache.write_json(d / "documents.json", [{"id": "7001", "name": "Doc.pdf", "content_type": "application/pdf",
                                             "url": "https://s3.test/doc.pdf", "creator_name": "Mariana",
                                             "created_at": T0 + 20}])
    cache.write_json(d / "checklists.json", [{"id": "c9", "name": "Revisión", "tasks": [
        {"name": "Foto del panel", "completed": True}, {"name": "Firma"}]}])
    for pid in ("1002", "1003"):
        dd = cache.project_dir(pid)
        for sub in ("photos", "comments", "documents", "checklists"):
            cache.write_json(dd / f"{sub}.json", [])
    return cache
