"""Lote 3, fase A: seguridad y acceso por API.

SEC-003 (permiso por ruta), SEC-005 (subida de archivos), SEC-006 (enlaces de
archivos), SEC-007 (asignación masiva), SEC-008 (autorización de datos, parte
API), API-006 (transiciones del expediente), AUTH-005 (renovar y salir, parte
API) y AUTH-008 (quitar un permiso con la sesión abierta). Además pide los
enlaces de AUTH-003, AUTH-004 y AUTH-007, que solo quedan en el log del api:
la fase B (`lote3b.py`) los usa.

Corre dentro del contenedor api, con la base QA recién cargada:
PYTHONPATH=/app:/tmp python /tmp/lote3a.py → /tmp/lote3a.json y /tmp/lote3_estado.json
"""
import json
import re
import uuid
from datetime import timedelta

import httpx
from fastapi.routing import APIRoute

from qa_comun import (API, aprobar_rapido, bearer, chk, cliente, e, esc, guardar, limpiar, login, prep_p03,
                      seguro, sql)

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "luis", "carlos", "ajeno")}
admin, adm, v, tec, conta, ger = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"], c["gerencia"]
ESTADO: dict = {}


# ===========================================================================
# SEC-003: cada ruta con su permiso, para los 6 roles
# ===========================================================================
def _requisitos(dependant) -> list[set]:
    """Los permisos que exige la ruta, leídos de `require_permission` y
    `require_any_permission` (cada uno es un conjunto: basta uno de ellos)."""
    reqs = []
    for d in dependant.dependencies:
        nombre = getattr(d.call, "__qualname__", "")
        if nombre.startswith(("require_permission.<locals>", "require_any_permission.<locals>")):
            for celda in d.call.__closure__ or []:
                valor = celda.cell_contents
                if isinstance(valor, str):
                    reqs.append({valor})
                elif isinstance(valor, tuple):
                    reqs.append(set(valor))
        reqs += _requisitos(d)
    return reqs


def _ruta(path: str) -> str:
    def poner(m):
        nombre = m.group(1)
        return "qa-inexistente" if nombre in ("code", "token", "key", "slug") else str(uuid.uuid4())
    return re.sub(r"\{([^}:]+)(:[^}]*)?\}", poner, path)


def sec003():
    from app.main import app
    from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS

    roles = {"admin": "organization_admin", "adm": "admin_staff", "vendedor": "salesperson",
             "tecnico": "field_technician", "conta": "accounting", "gerencia": "management"}
    permisos = {k: set(c[k].me.get("permissions") or []) for k in roles}
    for k, codigo in roles.items():
        esperado = set(DEFAULT_ROLE_PERMISSIONS.get(codigo, []))
        chk(f"{codigo}: los permisos que trae la sesión son los de la matriz ({len(esperado)})",
            permisos[k] == esperado,
            f"faltan {sorted(esperado - permisos[k])} · sobran {sorted(permisos[k] - esperado)}")

    rutas, sin_permiso = [], []
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/v1"):
            continue
        reqs = _requisitos(r.dependant)
        for metodo in sorted(r.methods - {"HEAD", "OPTIONS"}):
            if reqs:
                rutas.append((metodo, r.path, reqs))
            else:
                sin_permiso.append(f"{metodo} {r.path}")
    chk(f"Rutas con permiso declarado: {len(rutas)}", len(rutas) > 300, len(rutas))
    publicas = ("/api/v1/auth/", "/api/v1/public/", "/api/v1/privacy/", "/api/v1/health", "/api/v1/webhooks/")
    otras = [s for s in sin_permiso if not s.split(" ", 1)[1].startswith(publicas)]
    chk(f"Rutas sin `require_permission` ({len(sin_permiso)}): las públicas y de sesión, y estas otras para revisar "
        f"a mano ({len(otras)})", True, "; ".join(otras)[:1500])

    for k in roles:
        prohibidas = malas_403 = permitidas = malas_ok = 0
        detalle = []
        for metodo, path, reqs in rutas:
            permitido = all(req & permisos[k] for req in reqs)
            url = _ruta(path).replace("/api/v1", "", 1)
            if not permitido:
                prohibidas += 1
                r = c[k].call(metodo, url, json={} if metodo != "GET" else None)
                if r.status_code != 403:
                    malas_403 += 1
                    detalle.append(f"{metodo} {path} → {r.status_code}")
            elif metodo == "GET":
                permitidas += 1
                r = c[k].call(metodo, url)
                if r.status_code in (401, 403) or r.status_code >= 500:
                    malas_ok += 1
                    detalle.append(f"GET {path} → {r.status_code}")
        chk(f"{roles[k]}: {prohibidas} rutas sin su permiso responden 403", malas_403 == 0,
            "; ".join(d for d in detalle if not d.startswith("GET ") or "→ 403" not in d)[:1200] or "todas 403")
        chk(f"{roles[k]}: {permitidas} lecturas con su permiso responden sin 401/403/5xx", malas_ok == 0,
            "; ".join(d for d in detalle if d.startswith("GET "))[:1200] or "ninguna falla")
    r = httpx.get(f"{API}/cases", timeout=30)
    chk("Sin sesión → 401", r.status_code == 401, r.status_code)


# ===========================================================================
# Una obra de Carlos para SEC-005 y SEC-006
# ===========================================================================
def obra_de_carlos() -> str:
    _, pid = aprobar_rapido(v, adm, admin, 331)
    e.expect("Liberar la obra a Carlos", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": c["carlos"].me["id"],
        "scheduled_date": (e.HOY + timedelta(days=1)).isoformat()}), 200)
    return pid


def _subir(cli, pid, nombre, contenido, tipo):
    return cli.post(f"/projects/{pid}/evidence", data={"latitude": "34.28", "longitude": "-118.44"},
                    files={"file": (nombre, contenido, tipo)})


def sec005(pid):
    carlos = c["carlos"]
    exe = b"MZ\x90\x00" + b"\x00" * 2048
    r = _subir(carlos, pid, "foto.jpg", exe, "image/jpeg")
    chk("Un .exe renombrado .jpg se rechaza", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:150]}")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    r = _subir(carlos, pid, "dibujo.svg", svg, "image/svg+xml")
    chk("Un .svg con script se rechaza", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:150]}")
    grande = e.jpeg("QA grande") + b"\x00" * (30 * 1024 * 1024)
    r = _subir(carlos, pid, "grande.jpg", grande, "image/jpeg")
    chk("Un JPG de 30 MB se rechaza (anotar el tope)", r.status_code in (400, 413, 422), f"{r.status_code} {r.text[:200]}")
    r = _subir(carlos, pid, "../../etc/passwd.jpg", e.jpeg("QA ruta"), "image/jpeg")
    ok = r.status_code == 201
    ruta = sql(f"select file_path from evidence where id = '{r.json()['id']}'") if ok else ""
    chk("El nombre con ../ se guarda dentro de la carpeta de archivos", ok and ".." not in ruta and "etc/passwd" not in ruta,
        f"{r.status_code} ruta={ruta}")
    r = _subir(carlos, pid, "factura.pdf", e.pdf_doc("QA"), "application/pdf")
    chk("Un PDF real se acepta", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    r = _subir(carlos, pid, "foto.jpg", e.jpeg("QA foto de Carlos"), "image/jpeg")
    chk("Una foto real se acepta", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    if r.status_code == 201:
        f = carlos.get(f"/evidence/{r.json()['id']}/file")
        chk("La foto subida se abre", f.status_code == 200 and f.content[:2] == b"\xff\xd8", f.status_code)
        return r.json()["id"]
    return None


def sec006(ev_id):
    r = httpx.get(f"{API}/evidence/{ev_id}/file", timeout=30)
    chk("Sin sesión → 401", r.status_code == 401, r.status_code)
    r = c["luis"].get(f"/evidence/{ev_id}/file")
    chk("Luis (técnico de otra obra) → 404", r.status_code == 404, r.status_code)
    r = c["ajeno"].get(f"/evidence/{ev_id}/file")
    chk("El admin de otra organización → 404", r.status_code == 404, r.status_code)
    r = c["carlos"].get(f"/evidence/{ev_id}/file")
    chk("Carlos, el de la obra, sí la abre", r.status_code == 200, r.status_code)


# ===========================================================================
# SEC-007: campos que el cliente no puede fijar
# ===========================================================================
def sec007():
    p = e.persona(332, "AZ")
    r = e.abrir_puerta(v, p, "AZ_EFFICIENCY", "opened")
    cid = r.get("case_id") or (r.get("case") or {}).get("id")
    antes = admin.get(f"/cases/{cid}").json()["stage_code"]
    r = v.patch(f"/cases/{cid}", json={"stage_code": "paid"})
    chk("Vendedor: PATCH del expediente con stage_code=paid no existe (405)", r.status_code in (404, 405), r.status_code)
    r = v.post(f"/cases/{cid}/transition", json={"to_stage": "paid"})
    chk("Vendedor: pasar su expediente a «paid» se rechaza", r.status_code in (403, 409, 422), f"{r.status_code} {r.text[:150]}")
    chk("La etapa no cambió", admin.get(f"/cases/{cid}").json()["stage_code"] == antes, antes)

    yo = tec.me["id"]
    r = tec.patch(f"/users/{yo}", json={"full_name": "Tito QA", "role_codes": ["organization_admin"]})
    chk("Técnico: editarse con un rol de admin → 403", r.status_code == 403, r.status_code)
    r = tec.patch(f"/users/{yo}/roles", json={"role_codes": ["organization_admin"]})
    chk("Técnico: cambiarse el rol → 403", r.status_code == 403, r.status_code)
    me = tec.get("/auth/me").json()
    chk("Sigue siendo técnico, con los mismos permisos", me.get("roles") == ["field_technician"]
        and me.get("permissions") == tec.me.get("permissions"), me.get("roles"))

    cli = admin.post("/customers", json={"legal_name": f"QA {e.RUN} Particular SEC-007",
                                         "data_consent_accepted": True}).json()
    q = conta.post("/billing/quotes", json={"customer_id": cli["id"], "lines": [
        {"kind": "labor", "description": "QA revisión", "quantity": 1, "unit_price": 100}]}).json()
    conta.post(f"/billing/quotes/{q['id']}/send")
    fac = (conta.post(f"/billing/quotes/{q['id']}/accept").json() or {}).get("invoice") or {}
    r = conta.post(f"/invoices/{fac.get('id')}/issue", json={
        "due_date": (e.HOY + timedelta(days=30)).isoformat(), "invoice_number": "QA-HACK-1", "number": "QA-HACK-1"})
    numero = (r.json() or {}).get("invoice_number") if r.status_code == 200 else None
    chk("Contabilidad: emitir con el número fijado a mano lo ignora (lo pone la numeración)",
        r.status_code == 200 and numero and numero != "QA-HACK-1", f"{r.status_code} número={numero}")

    r = admin.post("/roles", json={"code": "qa_sistema", "name": "QA sistema", "permissions": [], "is_system": True})
    ok = r.status_code == 201 and not r.json().get("is_system")
    chk("Admin: crear un rol con is_system=true lo deja como rol normal", ok, f"{r.status_code} {r.text[:150]}")
    if r.status_code == 201:
        admin.delete("/roles/qa_sistema")
    r = v.post("/customers", json={"legal_name": f"QA {e.RUN} creado_por", "data_consent_accepted": True,
                                   "created_by_user_id": admin.me["id"], "organization_id": str(uuid.uuid4())})
    chk("Vendedor: crear cliente con dueño y organización ajenos los ignora", r.status_code == 201
        and r.json().get("organization_id") in (None, v.me.get("organization_id")), f"{r.status_code} {r.text[:150]}")
    return cid


# ===========================================================================
# SEC-008: autorización de datos (parte API)
# ===========================================================================
def sec008():
    e.flujo_consentimiento({"admin": admin, "vendedor": v})
    fuentes = sql("select source, count(*) from data_consents group by source order by source")
    chk("La firma de los T&C deja su constancia (fuente del expediente)", "case" in fuentes, fuentes.replace("\n", "; "))


# ===========================================================================
# API-006: solo las transiciones de stages.py
# ===========================================================================
def api006():
    p = e.persona(333, "AZ")
    r = e.abrir_puerta(v, p, "AZ_EFFICIENCY", "opened")
    cid = r.get("case_id") or (r.get("case") or {}).get("id")
    eventos = lambda: sql(f"select count(*) from case_stage_events where case_id = '{cid}'")  # noqa: E731
    antes, n0 = admin.get(f"/cases/{cid}").json()["stage_code"], eventos()
    chk("El expediente arranca en «Nuevo prospecto»", antes == "new_prospect", antes)
    for destino in ("paid", "approved"):
        r = admin.post(f"/cases/{cid}/transition", json={"to_stage": destino})
        chk(f"new_prospect → {destino} se rechaza con el motivo", r.status_code in (409, 422) and r.json().get("detail"),
            f"{r.status_code} {r.text[:150]}")
    r = admin.post(f"/cases/{cid}/transition", json={"to_stage": "inventado"})
    chk("Una etapa que no existe se rechaza", r.status_code in (400, 409, 422), f"{r.status_code} {r.text[:120]}")
    chk("Ni la etapa ni el historial cambiaron", admin.get(f"/cases/{cid}").json()["stage_code"] == antes
        and eventos() == n0, f"{eventos()} eventos")
    e.expect("Cierre administrativo con motivo", admin.post(f"/cases/{cid}/transition", json={
        "to_stage": "closed", "reason": "QA API-006"}), 200)
    for destino in ("submitted_to_program", "pending_approval", "new_prospect"):
        r = admin.post(f"/cases/{cid}/transition", json={"to_stage": destino})
        chk(f"closed → {destino} se rechaza", r.status_code in (409, 422), f"{r.status_code} {r.text[:120]}")
    chk("Sigue cerrado", admin.get(f"/cases/{cid}").json()["stage_code"] == "closed", "")
    r = ger.post(f"/cases/{cid}/transition", json={"to_stage": "closed"})
    chk("Gerencia (sin permiso de transición) → 403", r.status_code == 403, r.status_code)


# ===========================================================================
# AUTH-005: la sesión se renueva con la cookie y Salir la corta (parte API)
# ===========================================================================
def auth005():
    limpiar()
    s = httpx.Client(base_url=API, timeout=30)
    r = s.post("/auth/login", json={"email": e.USERS["tecnico"], "password": e.PASSWORD})
    chk("Ingreso del técnico con la cookie de sesión larga", r.status_code == 200 and "crm_refresh" in s.cookies, r.status_code)
    vieja = s.cookies.get("crm_refresh")
    r = s.post("/auth/refresh")
    chk("Renovar con la cookie da un token nuevo sin pedir clave", r.status_code == 200 and r.json().get("access_token"),
        r.status_code)
    nuevo = r.json().get("access_token")
    chk("Con el token renovado la Agenda carga", s.get("/dispatch/agenda", headers=bearer(nuevo)).status_code == 200, "")
    s2 = httpx.Client(base_url=API, timeout=30)
    s2.cookies.set("crm_refresh", vieja, path="/api/v1/auth")
    r = s2.post("/auth/refresh")
    chk("La cookie anterior (ya rotada) no sirve otra vez", r.status_code == 401, r.status_code)
    s.post("/auth/logout")
    r = s.post("/auth/refresh")
    chk("Después de Salir, renovar responde 401 (lleva al ingreso)", r.status_code == 401, r.status_code)


# ===========================================================================
# AUTH-008: quitar un permiso con la sesión abierta
# ===========================================================================
def auth008():
    r = conta.get("/payables/suppliers")
    chk("Contabilidad abre Proveedores y pagos", r.status_code == 200, r.status_code)
    rol = next(x for x in admin.get("/roles").json() if x["code"] == "accounting")
    originales = list(rol["permissions"])
    chk("El rol Contabilidad tiene payables.manage", "payables.manage" in originales, len(originales))
    e.expect("Admin quita payables.manage a Contabilidad", admin.patch("/roles/accounting", json={
        "permissions": [p for p in originales if p != "payables.manage"]}), 200)
    r = conta.post("/payables/suppliers", json={"name": f"QA {e.RUN} Proveedor sin permiso"})
    chk("Con la misma sesión, crear un proveedor → 403 en la siguiente acción", r.status_code == 403, r.status_code)
    e.expect("Admin devuelve el permiso", admin.patch("/roles/accounting", json={"permissions": originales}), 200)
    r = conta.post("/payables/suppliers", json={"name": f"QA {e.RUN} Proveedor con permiso"})
    chk("Vuelve a funcionar sin volver a entrar", r.status_code == 201, f"{r.status_code} {r.text[:120]}")


# ===========================================================================
# Pedidos de enlaces para la fase B (AUTH-003, AUTH-004, AUTH-007)
# ===========================================================================
def pedir_enlaces():
    esc("AUTH-003")
    ESTADO["token_gerencia_viejo"] = ger.h["Authorization"].split(" ", 1)[1]
    r = httpx.post(f"{API}/auth/password-reset/request", json={"email": "gerencia@demo-org.com"}, timeout=30)
    chk("¿Olvidaste tu contraseña? para gerencia responde con el mensaje genérico", r.status_code == 200
        and "Si hay una cuenta" in r.json().get("message", ""), r.text[:150])
    esc("AUTH-004")
    r = admin.post("/users", json={"email": "tecnico16@demo-org.com", "full_name": "Técnico Dieciséis",
                                   "role_codes": ["field_technician"]})
    chk("Admin invita a «Técnico Dieciséis» como Técnico", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    ESTADO["tecnico16_id"] = (r.json() or {}).get("id")
    esc("AUTH-007")
    r = admin.post("/roles", json={"code": "qa_sin_permisos", "name": "QA sin permisos", "permissions": []})
    chk("Crear el rol «QA sin permisos» sin marcar nada", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    r = admin.post("/users", json={"email": "sinrol@demo-org.com", "full_name": "QA Sin Rol",
                                   "role_codes": ["qa_sin_permisos"]})
    chk("Invitar a sinrol@demo-org.com con ese rol", r.status_code == 201, f"{r.status_code} {r.text[:150]}")


esc("_prep")
prep_p03(admin, v)
seguro("SEC-003", sec003)
pid_carlos = seguro("_prep", obra_de_carlos)
if pid_carlos:
    ev = seguro("SEC-005", sec005, pid_carlos)
    if ev:
        seguro("SEC-006", sec006, ev)
seguro("SEC-007", sec007)
seguro("SEC-008", sec008)
seguro("API-006", api006)
seguro("AUTH-005", auth005)
seguro("AUTH-008", auth008)
seguro("AUTH-003", pedir_enlaces)
guardar("/tmp/lote3a.json")
json.dump(ESTADO, open("/tmp/lote3_estado.json", "w"))
print("ok")
