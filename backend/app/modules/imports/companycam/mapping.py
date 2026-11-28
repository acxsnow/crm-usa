"""Traducción pura (sin base de datos ni red) de lo que devuelve CompanyCam a
lo que guarda el CRM, y la regla para reconocer clientes que ya existen."""
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.shared.normalize import normalize_address, normalize_email, normalize_phone

SOURCE = "companycam"
# Un correo o teléfono que aparece en más de este número de contactos distintos
# es de la empresa o de una inmobiliaria, no de una persona: no sirve para unir.
MAX_SHARED_CONTACT_USES = 3

_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def to_dt(epoch: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def fold(text: str | None) -> str:
    """Minúsculas, sin acentos y con espacios colapsados: para comparar nombres."""
    if not text:
        return ""
    sin = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin).strip().lower()


def state_code(value: str | None) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    if len(v) == 2:
        return v.upper()
    return _STATES.get(v.lower())


def clean(value: Any, limit: int | None = None) -> str | None:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", str(value)).strip()
    if not v:
        return None
    return v[:limit] if limit else v


# «6545 Wilbur Ave Spc 104»: en los parques de casas móviles el espacio viene
# pegado a la calle. El CRM lo guarda aparte (`address_unit`), y sin unidad no
# hay unión de clientes por dirección.
_UNIT_TAIL = re.compile(r"^(?P<street>.+?)[\s,]+(?P<unit>(?:spc|space|sp|unit|apt|lot|trlr|trailer|#)\.?\s*#?\s*[\w-]+)$",
                        re.IGNORECASE)


def split_unit(street: str | None, unit: str | None) -> tuple[str | None, str | None]:
    if unit or not street:
        return street, unit
    m = _UNIT_TAIL.match(street.strip())
    return (m.group("street").strip(), m.group("unit").strip()) if m else (street, unit)


def map_address(project: dict) -> dict:
    a = project.get("address") or {}
    calle, unidad = split_unit(clean(a.get("street_address_1")), clean(a.get("street_address_2")))
    coords = project.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    if not lat and not lon:  # CompanyCam manda 0,0 cuando no hay ubicación
        lat = lon = None
    return {
        "address_street": clean(calle, 255),
        "address_unit": clean(unidad, 50),
        "address_city": clean(a.get("city"), 120),
        "address_state": state_code(a.get("state")),
        "address_zip": clean(a.get("postal_code"), 10),
        "latitude": lat,
        "longitude": lon,
    }


def map_stage(project: dict) -> tuple[str, str]:
    """(etapa, motivo) del expediente importado."""
    if project.get("status") == "deleted":
        return "closed", "Importado de CompanyCam: el proyecto estaba eliminado en CompanyCam"
    if project.get("archived"):
        return "closed", "Importado de CompanyCam: el proyecto estaba archivado en CompanyCam"
    return "on_hold", "Importado de CompanyCam: proyecto activo, pendiente de que Administración elija programa"


def address_line(addr: dict) -> str:
    return ", ".join(p for p in (addr.get("address_street"), addr.get("address_unit"), addr.get("address_city"),
                                 addr.get("address_state"), addr.get("address_zip")) if p)


def customer_name(project: dict, addr: dict) -> str:
    contacto = project.get("primary_contact") or {}
    return (clean(contacto.get("name"), 255) or clean(project.get("name"), 255)
            or clean(address_line(addr), 255) or f"Proyecto CompanyCam {project.get('id')}")


def customer_ref(project: dict) -> str:
    contacto = project.get("primary_contact") or {}
    if contacto.get("id"):
        return f"contact:{contacto['id']}"
    return f"project:{project.get('id')}"


def notepad_body(project: dict) -> str:
    cabecera = (f"Proyecto CompanyCam: {project.get('name') or project.get('id')} · "
                f"creado por {project.get('creator_name') or 'desconocido'}")
    texto = (project.get("notepad") or "").strip()
    return f"{cabecera}\n\n{texto}" if texto else cabecera


def comment_body(comment: dict) -> str:
    return (comment.get("content") or "").strip()


def checklist_body(checklist: dict) -> str:
    """Texto legible de una lista; el JSON crudo se guarda aparte en `payload`
    porque la forma exacta de las tareas no está garantizada."""
    titulo = clean(checklist.get("name") or checklist.get("title")) or "Lista de verificación"
    lineas = [titulo]

    def tareas(obj: Any, nivel: int = 0) -> None:
        if isinstance(obj, list):
            for t in obj:
                if isinstance(t, dict):
                    nombre = clean(t.get("name") or t.get("title") or t.get("description") or t.get("label"))
                    hecho = t.get("completed") or t.get("is_completed") or t.get("checked") \
                        or t.get("completed_at") or t.get("status") in ("completed", "complete", "done")
                    if nombre:
                        lineas.append(f"{'  ' * nivel}[{'x' if hecho else ' '}] {nombre}")
                    for k in ("tasks", "items", "sections", "children", "subtasks"):
                        if k in t:
                            tareas(t[k], nivel + 1)
        elif isinstance(obj, dict):
            for k in ("tasks", "items", "sections"):
                if k in obj:
                    tareas(obj[k], nivel)

    tareas(checklist)
    return "\n".join(lineas)


def photo_url(photo: dict) -> str | None:
    from app.modules.imports.companycam.client import original_uri

    return original_uri(photo)


def photo_web_url(photo: dict) -> str | None:
    """URL de la versión `web` (liviana) de la foto, para la miniatura."""
    for u in photo.get("uris") or []:
        if u.get("type") == "web" and (u.get("url") or u.get("uri")):
            return u.get("url") or u.get("uri")
    return None


# ---------------------------------------------------------------------------
# Reconocer clientes que ya existen
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    ref: str                      # contact:{id} | project:{id}
    name: str
    email: str | None             # normalizado
    phone: str | None             # normalizado
    address: str | None           # normalizada, solo si trae unidad


def candidate_from_project(project: dict) -> Candidate:
    addr = map_address(project)
    contacto = project.get("primary_contact") or {}
    unidad = addr["address_unit"]
    return Candidate(
        ref=customer_ref(project),
        name=customer_name(project, addr),
        email=normalize_email(clean(contacto.get("email"))),
        phone=normalize_phone(clean(contacto.get("phone_number"))),
        address=normalize_address(addr["address_street"], unidad, addr["address_city"], addr["address_zip"])
        if unidad else None,
    )


def shared_values(projects: list[dict]) -> set[str]:
    """Correos y teléfonos usados por más de 3 contactos distintos del
    export: se ignoran para unir clientes."""
    usos: dict[str, set[str]] = defaultdict(set)
    for p in projects:
        c = p.get("primary_contact") or {}
        ident = str(c.get("id") or f"p{p.get('id')}")
        e = normalize_email(clean(c.get("email")))
        t = normalize_phone(clean(c.get("phone_number")))
        if e:
            usos[f"e:{e}"].add(ident)
        if t:
            usos[f"t:{t}"].add(ident)
    return {k for k, v in usos.items() if len(v) > MAX_SHARED_CONTACT_USES}


@dataclass
class MatchIndex:
    """Lo que ya hay en el CRM, listo para consultar. Todo lo que se agrega
    es `customer_id -> clave`; una clave con varios clientes es ambigua."""
    ignored: set[str] = field(default_factory=set)
    by_ref: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    by_email: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    by_phone: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    by_address: dict[str, set] = field(default_factory=lambda: defaultdict(set))

    def add(self, customer_id, *, ref: str | None = None, emails=(), phones=(), address: str | None = None) -> None:
        if ref:
            self.by_ref[ref].add(customer_id)
        for e in emails:
            e = normalize_email(e)
            if e:
                self.by_email[e].add(customer_id)
        for t in phones:
            t = normalize_phone(t)
            if t:
                self.by_phone[t].add(customer_id)
        if address:
            self.by_address[address].add(customer_id)


def match_customer(cand: Candidate, index: MatchIndex) -> tuple[str, list]:
    """Aplica las reglas en orden y se queda con la primera que encuentre algo:

    a) mismo contacto de CompanyCam ya importado, b) correo, c) teléfono,
    d) dirección idéntica CON unidad (sin unidad no hay unión).

    Devuelve `("match", [id])`, `("ambiguous", [ids])` o `("new", [])`. Con más
    de un candidato en la regla que acierta no se adivina: cliente nuevo y se
    anota en `ambiguos.csv`."""
    pasos = [
        index.by_ref.get(cand.ref, set()),
        index.by_email.get(cand.email, set()) if cand.email and f"e:{cand.email}" not in index.ignored else set(),
        index.by_phone.get(cand.phone, set()) if cand.phone and f"t:{cand.phone}" not in index.ignored else set(),
        index.by_address.get(cand.address, set()) if cand.address else set(),
    ]
    for ids in pasos:
        if len(ids) == 1:
            return "match", list(ids)
        if len(ids) > 1:
            return "ambiguous", sorted(ids, key=str)
    return "new", []
