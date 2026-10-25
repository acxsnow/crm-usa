"""Lote 1 de QA por API: escenarios que no necesitan un flujo previo.
Corre dentro del contenedor api: python /tmp/lote1.py > /tmp/lote1.json"""
import json
import time
import uuid

import httpx
import redis

from app.core.config import get_settings

B = "http://localhost:8000/api/v1"
CLAVE = "ChangeMe123!"
R = redis.Redis.from_url(get_settings().REDIS_URL)
res: dict[str, list] = {}
cli = httpx.Client(timeout=30)


def limpiar():
    for k in R.scan_iter("ratelimit:*"):
        R.delete(k)


def chk(esc, nombre, ok, dato=""):
    res.setdefault(esc, []).append({"check": nombre, "ok": bool(ok), "dato": str(dato)[:400]})


def req(metodo, ruta, h=None, **kw):
    t = time.perf_counter()
    r = cli.request(metodo, B + ruta if ruta.startswith("/") else ruta, headers=h or {}, **kw)
    return r, round((time.perf_counter() - t) * 1000)


def login(correo, clave=CLAVE, limpia=True):
    if limpia:
        limpiar()
    r, _ = req("POST", "/auth/login", json={"email": correo, "password": clave})
    return r


def h(correo):
    r = login(correo)
    assert r.status_code == 200, (correo, r.text)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


ROLES = {"admin": "admin@demo-org.com", "administracion": "administracion@demo-org.com",
         "vendedor": "vendedor@demo-org.com", "tecnico": "tecnico@demo-org.com",
         "contabilidad": "contabilidad@demo-org.com", "gerencia": "gerencia@demo-org.com"}
H = {k: h(v) for k, v in ROLES.items()}
AJENO = h("admin@otra-org.com")

# --- AUTH-001 (parte API) ----------------------------------------------------
for rol, hh in H.items():
    r, ms = req("GET", "/auth/me", hh)
    d = r.json()
    chk("AUTH-001", f"{rol}: ingresa y /auth/me responde", r.status_code == 200,
        f"{d.get('full_name')} · roles={d.get('roles')} · permisos={len(d.get('permissions', []))} · {ms} ms")

# --- AUTH-002 ----------------------------------------------------------------
limpiar()
r1 = login("nadie@demo-org.com", limpia=False)
r2 = login("vendedor@demo-org.com", "Errada123!", limpia=False)
chk("AUTH-002", "correo inexistente y clave errada dan el mismo mensaje", r1.status_code == r2.status_code == 401
    and r1.json() == r2.json(), f"{r1.status_code} {r1.json()} | {r2.status_code} {r2.json()}")
limpiar()
codigos = [login("vendedor@demo-org.com", "Errada123!", limpia=False).status_code for _ in range(5)]
r6 = login("vendedor@demo-org.com", CLAVE, limpia=False)
chk("AUTH-002", "5 fallidos y el 6.º con la clave correcta se rechaza", r6.status_code == 429,
    f"intentos={codigos} sexto={r6.status_code} {r6.text}")
chk("AUTH-002", "el mensaje del bloqueo está en español", "Too many" not in r6.text, r6.text)
r7 = login("vendedor@demo-org.com")
chk("AUTH-002", "después de limpiar los contadores entra", r7.status_code == 200, r7.status_code)

# --- AUTH-006 (parte API) ----------------------------------------------------
RUTAS = {"/bank-feeds/transactions": "Banca", "/payables/invoices": "Proveedores", "/users": "Equipo",
         "/roles": "Roles", "/audit-events": "Auditoría", "/warehouse/stock/summary": "Bodega (saldos)",
         "/invoices": "Facturas", "/attendance/dashboard": "Asistencia",
         "/attendance/payroll/periods": "Nómina", "/reconciliation/summary": "Conciliación"}
for rol in ("vendedor", "tecnico"):
    for ruta, nombre in RUTAS.items():
        r, ms = req("GET", ruta, H[rol])
        chk("AUTH-006", f"{rol} → {nombre} ({ruta}) responde 403", r.status_code == 403, f"{r.status_code} · {ms} ms")

# --- SEC-002 -----------------------------------------------------------------
tok = H["admin"]["Authorization"]
alterado = {"Authorization": tok[:-3] + ("AAA" if not tok.endswith("AAA") else "BBB")}
for ruta in ("/cases", "/customers", "/warehouse/stock", "/invoices"):
    for nombre, hh in (("sin token", {}), ("token alterado", alterado), ("basura", {"Authorization": "Bearer x.y.z"})):
        r, _ = req("GET", ruta, hh)
        chk("SEC-002", f"{ruta} {nombre} → 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")
        chk("SEC-002", f"{ruta} {nombre} sin trazas internas", "Traceback" not in r.text and "sqlalchemy" not in r.text.lower(), "")
limpiar()
rl = cli.post(B + "/auth/login", json={"email": ROLES["admin"], "password": CLAVE})
refresh = rl.cookies.get("refresh_token") or next((c.value for c in cli.cookies.jar if "refresh" in c.name), None)
if refresh:
    r, _ = req("GET", "/cases", {"Authorization": f"Bearer {refresh}"})
    chk("SEC-002", "el token de refresco no sirve como token de acceso", r.status_code == 401, r.status_code)
else:
    chk("SEC-002", "el token de refresco no sirve como token de acceso (no se pudo leer la cookie)", False,
        f"cookies={[c.name for c in cli.cookies.jar]}")

# --- BOD-001 -----------------------------------------------------------------
r, ms = req("GET", "/warehouse/stock/summary", H["administracion"])
chk("BOD-001", "resumen de bodega", r.status_code == 200, f"{r.json()} · {ms} ms")
r, _ = req("GET", "/warehouse/items", H["administracion"], params={"limit": 1})
chk("BOD-001", "artículos de la organización demo = 244 (el ajeno no se ve)", r.headers.get("x-total-count") == "244",
    r.headers.get("x-total-count"))
esperado = {"85980": None, "3496": None, "1578": None, "27948": None, "61052": None}
import csv  # noqa: E402
with open("/tmp/catalogo_ac_pro.csv", encoding="utf-8") as f:
    for fila in csv.DictReader(f, delimiter=";"):
        if fila["sku"] in esperado:
            esperado[fila["sku"]] = (fila["cantidad"], fila["costo"])
for sku, (cant, costo) in esperado.items():
    r, _ = req("GET", "/warehouse/stock", H["administracion"], params={"q": sku})
    filas = [x for x in r.json() if x.get("sku") == sku]
    total = sum(float(x.get("quantity") or x.get("on_hand") or 0) for x in filas)
    chk("BOD-001", f"SKU {sku}: existencia = CSV ({cant})", filas and abs(total - float(cant)) < 0.001,
        json.dumps(filas[:1])[:300])
    r, _ = req("GET", "/warehouse/items", H["administracion"], params={"q": sku})
    it = next((x for x in r.json() if x.get("sku") == sku), {})
    chk("BOD-001", f"SKU {sku}: costo = CSV ({costo})", it and float(it.get("unit_cost") or 0) == float(costo),
        it.get("unit_cost"))
    if it:
        r, _ = req("GET", "/warehouse/movements", H["administracion"], params={"item_id": it["id"]})
        chk("BOD-001", f"SKU {sku}: un solo movimiento de carga inicial", r.headers.get("x-total-count") == "1",
            r.headers.get("x-total-count"))
r, _ = req("GET", "/warehouse/items", H["administracion"], params={"q": "AJENO"})
chk("BOD-001", "«Artículo Ajeno QA» no aparece", r.json() == [], r.json())

# --- SEC-001 -----------------------------------------------------------------
import asyncio  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402


async def ids():
    async with AsyncSessionLocal() as db:
        q = lambda s: db.execute(text(s))  # noqa: E731
        ajeno_c = (await q("select id from customers where legal_name='Cliente Ajeno QA'")).scalar()
        ajeno_i = (await q("select id from warehouse_items where sku='AJENO-1'")).scalar()
        demo_org = (await q("select id from organizations where name='Demo Organization'")).scalar()
        demo_i = (await q(f"select id from warehouse_items where organization_id='{demo_org}' limit 1")).scalar()
        demo_u = (await q("select id from users where email='vendedor@demo-org.com'")).scalar()
        demo_kit = (await q(f"select id from warehouse_kit_templates where organization_id='{demo_org}' limit 1")).scalar()
        demo_prog = (await q(f"select id from programs where organization_id='{demo_org}' limit 1")).scalar()
        return ajeno_c, ajeno_i, demo_org, demo_i, demo_u, demo_kit, demo_prog
ajeno_c, ajeno_i, demo_org, demo_i, demo_u, demo_kit, demo_prog = asyncio.run(ids())
for nombre, ruta in (("artículo demo", f"/warehouse/items/{demo_i}"), ("usuario demo", f"/users/{demo_u}"),
                     ("lista demo", f"/warehouse/kits/{demo_kit}"), ("programa demo", f"/programs/{demo_prog}")):
    r, _ = req("GET", ruta, AJENO)
    chk("SEC-001", f"admin ajeno GET {nombre} → 404", r.status_code == 404, f"{r.status_code} {r.text[:100]}")
for nombre, ruta in (("cliente ajeno", f"/customers/{ajeno_c}"), ("artículo ajeno", f"/warehouse/items/{ajeno_i}")):
    r, _ = req("GET", ruta, H["admin"])
    chk("SEC-001", f"admin demo GET {nombre} → 404", r.status_code == 404, r.status_code)
    r, _ = req("PATCH", ruta, H["admin"], json={"notes": "intrusión"})
    chk("SEC-001", f"admin demo PATCH {nombre} → 404/405", r.status_code in (404, 405), r.status_code)
    r, _ = req("PUT", ruta, H["admin"], json={"name": "intrusión"})
    chk("SEC-001", f"admin demo PUT {nombre} → 404/405/422", r.status_code in (404, 405, 422), r.status_code)
    r, _ = req("DELETE", ruta, H["admin"])
    chk("SEC-001", f"admin demo DELETE {nombre} → 404/405", r.status_code in (404, 405), r.status_code)
r, _ = req("GET", "/customers", AJENO, params={"limit": 500})
chk("SEC-001", "la lista de clientes del ajeno solo trae lo suyo", all(c.get("legal_name") == "Cliente Ajeno QA"
    for c in r.json()), [c.get("legal_name") for c in r.json()])
r, _ = req("GET", "/warehouse/items", AJENO, params={"limit": 500})
chk("SEC-001", "la lista de artículos del ajeno solo trae el suyo", r.headers.get("x-total-count") == "1",
    r.headers.get("x-total-count"))
r, _ = req("GET", "/users", AJENO, params={"limit": 500})
usuarios = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
chk("SEC-001", "la lista de usuarios del ajeno solo trae los suyos",
    r.status_code == 200 and all("otra-org" in u.get("email", "") for u in usuarios),
    f"{r.status_code} {[u.get('email') for u in usuarios] if usuarios else r.text[:200]}")
r, _ = req("POST", "/customers", AJENO, json={"legal_name": "QA Intruso", "organization_id": str(demo_org),
                                             "privacy_consent": True, "data_consent": True})
creado = r.json() if r.status_code in (200, 201) else {}
chk("SEC-001", "crear cliente mandando organization_id ajeno no lo deja en la demo",
    r.status_code in (200, 201, 400, 422) and str(creado.get("organization_id", "")) != str(demo_org),
    f"{r.status_code} org={creado.get('organization_id')} {r.text[:200]}")

# --- API-001 -----------------------------------------------------------------
A = H["administracion"]
r, ms = req("GET", "/warehouse/items", A)
chk("API-001", "sin parámetros: 100 filas y X-Total-Count", len(r.json()) == 100 and r.headers.get("x-total-count") == "244",
    f"filas={len(r.json())} total={r.headers.get('x-total-count')} · {ms} ms")
for lim, ok in (("500", 200), ("501", 422), ("0", 422), ("-1", 422)):
    r, _ = req("GET", "/warehouse/items", A, params={"limit": lim})
    chk("API-001", f"limit={lim} → {ok}", r.status_code == ok, f"{r.status_code} filas={len(r.json()) if r.status_code == 200 else '-'}")
r, _ = req("GET", "/warehouse/items", A, params={"offset": 200, "limit": 100})
chk("API-001", "offset=200 trae las 44 restantes", len(r.json()) == 44, len(r.json()))
r, _ = req("GET", "/warehouse/items", A, params={"offset": 10000})
chk("API-001", "offset=10000 trae lista vacía", r.status_code == 200 and r.json() == [], r.status_code)
paginas = []
for off in (0, 100, 200):
    paginas += [x["id"] for x in req("GET", "/warehouse/items", A, params={"offset": off, "limit": 100})[0].json()]
chk("API-001", "recorrer las páginas: 244 ids sin repetir", len(paginas) == 244 == len(set(paginas)), f"{len(paginas)}/{len(set(paginas))}")

# --- API-002 -----------------------------------------------------------------
ids_m = []
off = 0
while True:
    r, _ = req("GET", "/warehouse/movements", A, params={"offset": off, "limit": 50})
    if not r.json():
        break
    ids_m += [x["id"] for x in r.json()]
    off += 50
chk("API-002", "movimientos en páginas de 50: 244 ids distintos", len(ids_m) == 244 == len(set(ids_m)),
    f"{len(ids_m)} filas, {len(set(ids_m))} distintas")

# --- API-003 -----------------------------------------------------------------
for params, nombre in (({"q": "cinta"}, "q=cinta"), ({"active": "false"}, "active=false"),
                       ({"q": "zzzz"}, "q sin coincidencias")):
    r, _ = req("GET", "/warehouse/items", A, params={**params, "limit": 500})
    chk("API-003", f"items {nombre}: total = filas", r.status_code == 200 and r.headers.get("x-total-count") == str(len(r.json())),
        f"{r.status_code} total={r.headers.get('x-total-count')} filas={len(r.json())}")
r, _ = req("GET", "/warehouse/stock", A, params={"low_only": "true", "limit": 500})
chk("API-003", "stock low_only: total = filas", r.status_code == 200 and r.headers.get("x-total-count") == str(len(r.json())),
    f"{r.status_code} total={r.headers.get('x-total-count')} filas={len(r.json())}")
r, _ = req("GET", "/warehouse/items", A, params={"active": "quizás"})
chk("API-003", "active=quizás → 422", r.status_code == 422, r.status_code)

# --- API-004 -----------------------------------------------------------------
for ruta in ("/warehouse/items/{}", "/customers/{}", "/projects/{}"):
    r, _ = req("GET", ruta.format(uuid.uuid4()), H["admin"])
    chk("API-004", f"{ruta}: id inexistente → 404", r.status_code == 404, f"{r.status_code} {r.json()}")
    r, _ = req("GET", ruta.format("abc"), H["admin"])
    chk("API-004", f"{ruta}: id mal formado → 422", r.status_code == 422, r.status_code)
for ruta in ("/warehouse/items", "/customers", "/warehouse/movements"):
    r, _ = req("POST", ruta, H["admin"], json={})
    chk("API-004", f"POST {ruta} cuerpo vacío → 422", r.status_code in (400, 422), f"{r.status_code} {r.text[:150]}")
    r, _ = req("POST", ruta, {**H["admin"], "Content-Type": "application/json"}, content=b"{roto")
    chk("API-004", f"POST {ruta} JSON roto → 400/422 (no 500)", r.status_code in (400, 422), r.status_code)
    chk("API-004", f"POST {ruta}: formato de error con detail", "detail" in r.json(), r.text[:150])

# --- BUS-002 y SEC-004 (filtros) ----------------------------------------------
total_admin = None
for termino in ("%", "_", "' OR 1=1 --", "<script>alert(1)</script>", "x" * 300, "🔧🔥", "Ñandú", "1; DROP TABLE cases; --"):
    r, ms = req("GET", "/search", H["admin"], params={"q": termino})
    n = sum(len(g.get("items", g.get("results", []))) for g in r.json().get("groups", [])) if r.status_code == 200 else "-"
    chk("BUS-002", f"buscador «{termino[:25]}» sin 500", r.status_code in (200, 422), f"{r.status_code} resultados={n} · {ms} ms")
    r2, _ = req("GET", "/warehouse/items", A, params={"q": termino})
    chk("SEC-004", f"filtro de artículos «{termino[:25]}» sin 500 y sin traer todo",
        r2.status_code in (200, 422) and (r2.status_code == 422 or int(r2.headers.get("x-total-count", "0")) < 244),
        f"{r2.status_code} total={r2.headers.get('x-total-count')}")
    r3, _ = req("GET", "/customers", H["admin"], params={"q": termino})
    chk("SEC-004", f"filtro de clientes «{termino[:25]}» sin 500", r3.status_code in (200, 422), r3.status_code)

# --- SEC-009 (parte API) --------------------------------------------------------
r = cli.get("http://localhost:8000/api/docs")
chk("SEC-009", "documentación de la API (/api/docs) — anotar si está abierta", True, f"{r.status_code} (abierta={r.status_code == 200})")
r = cli.options(B + "/cases", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
chk("SEC-009", "CORS no permite un origen ajeno", r.headers.get("access-control-allow-origin") not in ("*", "https://evil.example"),
    r.headers.get("access-control-allow-origin"))
r, _ = req("GET", "/auth/me", H["admin"])
chk("SEC-009", "/auth/me no devuelve hash de clave ni secretos", "password" not in r.text.lower() and "hash" not in r.text.lower(), "")

# --- API-005 -----------------------------------------------------------------
limpiar()
cods = [req("POST", "/auth/password-reset/request", json={"email": "gerencia@demo-org.com"})[0].status_code for _ in range(30)]
chk("API-005", "30 pedidos de olvido de clave: aparece 429", 429 in cods, cods)
r, _ = req("GET", "/auth/me", H["admin"])
chk("API-005", "la API sigue respondiendo a otros usuarios", r.status_code == 200, r.status_code)
limpiar()

print(json.dumps(res, ensure_ascii=False, indent=1))
