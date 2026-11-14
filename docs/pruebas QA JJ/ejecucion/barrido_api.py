"""Barrido de toda la API (10 nov 2026): cada ruta, con cada rol y sin sesión.

Busca tres clases de fallas en todos los módulos a la vez:
1. Errores 500: ninguna entrada, por absurda que sea, debe tumbar el servidor.
2. Rutas abiertas: sin sesión, todo lo que no es público responde 401.
3. Fugas entre organizaciones: un usuario de otra empresa pide los registros
   reales de la nuestra por su id y no debe recibir nada.

Los ids de las rutas en (1) y (2) son aleatorios, así que no toca datos reales.
Corre en el contenedor api:
    PYTHONPATH=/app:/tmp python /tmp/barrido_api.py → /tmp/barrido_api.json
"""
import json
import re
import uuid
from collections import Counter

import httpx

from app.main import app
from qa_comun import API, chk, cliente, esc, guardar, limpiar, sql

BASE = API.rsplit("/api/v1", 1)[0]
ROLES = ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "ajeno")
c = {k: cliente(k) for k in ROLES}
# Lo que no pide sesión, a propósito (sección 9 del artefacto).
PUBLICAS = re.compile(r"^/api/v1/(auth/(login|refresh|logout|forgot-password|reset-password|accept-invitation|"
                      r"invitation)|public/|unsubscribe|webhooks/|privacy/consent-notice|payment-links/public|"
                      r"health)")
BASURA = [None, {}, {"x": "y"}, {"amount": "abc", "id": "no-uuid", "date": "ayer", "quantity": -1e308},
          [1, 2, 3], "texto"]


def rutas():
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/v1/"):
            continue
        for metodo in sorted((getattr(r, "methods", None) or set()) - {"HEAD", "OPTIONS"}):
            yield metodo, path


def armar(path):
    def valor(m):
        nombre = m.group(1)
        return str(uuid.uuid4()) if nombre.endswith("id") or nombre in ("id",) else "qa-x"
    return re.sub(r"\{([^}:]+)(?::[^}]+)?\}", valor, path)


def llamar(cli_headers, metodo, url, cuerpo):
    kw = {"headers": cli_headers, "timeout": 30}
    if metodo in ("POST", "PUT", "PATCH") and cuerpo is not None:
        if isinstance(cuerpo, str):
            kw["content"] = cuerpo
            kw["headers"] = {**cli_headers, "content-type": "application/json"}
        else:
            kw["json"] = cuerpo
    return httpx.request(metodo, BASE + url, **kw)


todas = list(rutas())
esc("BAR-0 Inventario")
chk(f"Rutas de la API recorridas: {len(todas)}", len(todas) > 400, len(todas))

# ---------------------------------------------------------------------------
esc("BAR-1 Ninguna entrada tumba el servidor (500)")
quinientos = []
cuenta = Counter()
for n, (metodo, path) in enumerate(todas):
    if n % 60 == 0:
        limpiar()
        # El token corto vence: se vuelve a entrar cada tanto para no confundir un 401 con un permiso.
        c = {k: cliente(k) for k in ROLES}
    if "logout" in path or "sessions" in path:
        continue  # cerraría la sesión de los usuarios de prueba
    url = armar(path)
    for rol in ROLES:
        cuerpos = BASURA if metodo in ("POST", "PUT", "PATCH") else [None]
        for cuerpo in cuerpos:
            try:
                r = llamar(c[rol].h, metodo, url, cuerpo)
            except httpx.HTTPError as ex:
                quinientos.append((metodo, path, rol, repr(cuerpo)[:40], f"sin respuesta: {ex!r}"[:120]))
                continue
            cuenta[r.status_code // 100] += 1
            if r.status_code >= 500:
                quinientos.append((metodo, path, rol, repr(cuerpo)[:40], r.text[:160]))
chk(f"Ninguna de {sum(cuenta.values())} llamadas da 500 ({dict(cuenta)})", not quinientos,
    json.dumps(quinientos[:25], ensure_ascii=False))

# ---------------------------------------------------------------------------
esc("BAR-2 Sin sesión, solo lo público responde")
abiertas = []
for n, (metodo, path) in enumerate(todas):
    if PUBLICAS.match(path):
        continue
    r = llamar({}, metodo, armar(path), {} if metodo in ("POST", "PUT", "PATCH") else None)
    if r.status_code not in (401, 403):
        abiertas.append((metodo, path, r.status_code))
chk(f"Todas las rutas privadas piden sesión ({len(todas)} revisadas)", not abiertas, json.dumps(abiertas[:30]))

# ---------------------------------------------------------------------------
esc("BAR-3 Otra organización no lee nuestros registros")
org_ajena = c["ajeno"].me.get("organization_id")
tablas = {  # parámetro de ruta → tabla de donde sacar ids reales de nuestra organización
    "case_id": "cases", "project_id": "projects", "customer_id": "customers", "invoice_id": "invoices",
    "claim_id": "rebate_claims", "quote_id": "quotes", "permit_id": "permits", "inspection_id": "inspections",
    "expense_id": "expenses", "supplier_id": "suppliers", "item_id": "warehouse_items",
    "release_id": "warehouse_releases", "kit_id": "warehouse_kits", "user_id": "users", "program_id": "programs",
    "campaign_id": "campaigns", "evidence_id": "evidence", "task_id": "project_tasks",
    "location_id": "warehouse_locations", "entry_id": "time_entries", "shift_id": "work_shifts",
    "account_id": "accounting_accounts", "version_id": "program_versions", "zone_id": "program_zones",
}
ids = {}
for param, tabla in tablas.items():
    try:
        fila = sql(f"select id from {tabla} where organization_id <> '{org_ajena}' order by random() limit 1")
    except Exception:  # noqa: BLE001 - la tabla puede llamarse distinto; se informa abajo
        fila = ""
    if fila:
        ids[param] = fila.splitlines()[0]
chk(f"Ids reales de nuestra organización para {len(ids)} tipos de registro", len(ids) >= 15, sorted(ids))
fugas, probadas = [], 0
for metodo, path in todas:
    if metodo != "GET":
        continue
    params = re.findall(r"\{([^}:]+)", path)
    if not params or not all(p in ids for p in params):
        continue
    url = path
    for p in params:
        url = re.sub(r"\{" + p + r"(?::[^}]+)?\}", ids[p], url)
    r = llamar(c["ajeno"].h, "GET", url, None)
    probadas += 1
    if r.status_code == 200:
        cuerpo = r.text
        vacio = cuerpo in ("[]", "{}") or '"items":[]' in cuerpo.replace(" ", "") or '"rows":[]' in cuerpo.replace(" ", "")
        if not vacio:
            fugas.append((path, cuerpo[:160]))
chk(f"Ningún registro nuestro le llega a otra organización ({probadas} rutas con ids reales)", not fugas,
    json.dumps(fugas[:20], ensure_ascii=False))

guardar("/tmp/barrido_api.json")
