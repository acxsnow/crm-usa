"""Caché en disco de lo extraído de CompanyCam (`~/companycam_export/`).

La extracción (red, lenta, con límite de ritmo) y la carga (base de datos) se
separan: la carga se puede repetir y probar sin volver a llamar a la API."""
import json
import os
from pathlib import Path
from typing import Any, Iterator

DEFAULT_ROOT = Path.home() / "companycam_export"
SUBRESOURCES = ("photos", "comments", "documents", "checklists", "labels")


class ExportCache:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    @property
    def reports_dir(self) -> Path:
        d = self.root / "reports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def project_dir(self, project_id: str) -> Path:
        d = self.root / "p" / str(project_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def read_json(self, path: Path, default: Any = None) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    # --- proyectos -----------------------------------------------------------
    @property
    def projects_file(self) -> Path:
        return self.root / "projects.jsonl"

    def write_projects(self, projects: list[dict]) -> None:
        with self.projects_file.open("w", encoding="utf-8") as f:
            for p in projects:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

    def projects(self) -> list[dict]:
        try:
            return [json.loads(x) for x in self.projects_file.read_text(encoding="utf-8").splitlines() if x.strip()]
        except OSError:
            return []

    def iter_projects(self, only: set[str] | None = None, limit: int | None = None) -> Iterator[dict]:
        n = 0
        for p in self.projects():
            if only and str(p.get("id")) not in only:
                continue
            if limit is not None and n >= limit:
                return
            n += 1
            yield p

    def is_done(self, project_id: str) -> bool:
        return (self.root / "p" / str(project_id) / ".done").exists()

    def mark_done(self, project_id: str) -> None:
        (self.project_dir(project_id) / ".done").write_text("1")

    def project_data(self, project_id: str) -> dict[str, list]:
        d = self.root / "p" / str(project_id)
        return {k: self.read_json(d / f"{k}.json", []) or [] for k in SUBRESOURCES}

    # --- globales ------------------------------------------------------------
    def users(self) -> list[dict]:
        return self.read_json(self.root / "users.json", []) or []

    def tag_photos(self) -> dict[str, list[str]]:
        return self.read_json(self.root / "tag_photos.json", {}) or {}
