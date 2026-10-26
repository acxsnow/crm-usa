"""Lote 3, fase B: AUTH-003 (olvido de clave), AUTH-004 (invitación) y AUTH-007
(rol sin permisos), con los enlaces que la fase A pidió.

Los enlaces solo quedan en el log del api (modo consola). Antes de correr esto,
desde el equipo: `docker compose logs api | grep email.send` → /tmp/links.json
({"gerencia": token, "tecnico16": token, "sinrol": token}).

PYTHONPATH=/app:/tmp python /tmp/lote3b.py → /tmp/lote3b.json
"""
import json

import httpx

from qa_comun import API, R, bearer, chk, cliente, e, esc, guardar, limpiar, login, seguro, sql

ENLACES = json.load(open("/tmp/links.json"))
ESTADO = json.load(open("/tmp/lote3_estado.json"))
CLAVE_NUEVA = "NuevaClave123!"
admin = cliente("admin")


def auth003():
    token = ENLACES["gerencia"]
    r = httpx.post(f"{API}/auth/password-reset/confirm", json={"token": token, "new_password": "Corta1!"}, timeout=30)
    chk("Una clave de menos de 12 caracteres se rechaza", r.status_code == 422, r.status_code)
    r = httpx.post(f"{API}/auth/password-reset/confirm", json={"token": token, "new_password": CLAVE_NUEVA}, timeout=30)
    chk("Abrir el enlace y poner la clave nueva", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    chk("Entra con la clave nueva", login("gerencia@demo-org.com", CLAVE_NUEVA).status_code == 200, "")
    chk("Con la clave anterior ya no entra", login("gerencia@demo-org.com", e.PASSWORD).status_code == 401, "")
    r = httpx.get(f"{API}/auth/me", headers=bearer(ESTADO["token_gerencia_viejo"]), timeout=30)
    chk("La sesión que estaba abierta queda cerrada", r.status_code == 401, r.status_code)
    r = httpx.post(f"{API}/auth/password-reset/confirm", json={"token": token, "new_password": "OtraClave1234!"},
                   timeout=30)
    chk("El mismo enlace otra vez responde que ya no es válido", r.status_code in (400, 401, 404, 410)
        and r.json().get("detail"), f"{r.status_code} {r.text[:150]}")
    antes = sql("select count(*) from password_reset_tokens t join users u on u.id = t.user_id "
                "where u.email = 'gerencia@demo-org.com' and t.created_at > now() - interval '1 hour'")
    codigos = [httpx.post(f"{API}/auth/password-reset/request", json={"email": "gerencia@demo-org.com"},
                          timeout=30).status_code for _ in range(4)]
    despues = sql("select count(*) from password_reset_tokens t join users u on u.id = t.user_id "
                  "where u.email = 'gerencia@demo-org.com' and t.created_at > now() - interval '1 hour'")
    chk("4 pedidos seguidos: no se crean más de 3 enlaces en la hora", int(despues) <= 3,
        f"respuestas={codigos} enlaces en la hora: {antes} → {despues}")
    # Para dejar la clave como estaba (fase C) se limpia el tope de la hora.
    for k in R.scan_iter("ratelimit:pwreset:*"):
        R.delete(k)
    r = httpx.post(f"{API}/auth/password-reset/request", json={"email": "gerencia@demo-org.com"}, timeout=30)
    chk("Pedir un enlace nuevo para dejar la clave en ChangeMe123! (fase C)", r.status_code == 200, r.status_code)


def auth004():
    token = ENLACES["tecnico16"]
    r = httpx.post(f"{API}/auth/invitations/accept", json={"token": token, "password": e.PASSWORD}, timeout=30)
    chk("Abrir la invitación y crear la clave", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    r = login("tecnico16@demo-org.com")
    chk("Entra como tecnico16", r.status_code == 200, r.status_code)
    tok = r.json().get("access_token") if r.status_code == 200 else ""
    me = httpx.get(f"{API}/auth/me", headers=bearer(tok), timeout=30).json() if tok else {}
    chk("La cuenta quedó con el rol Técnico", me.get("roles") == ["field_technician"], me.get("roles"))
    r = httpx.post(f"{API}/auth/invitations/accept", json={"token": token, "password": "OtraClave1234!"}, timeout=30)
    chk("La misma invitación no se usa dos veces", r.status_code in (400, 401, 404, 409, 410), r.status_code)
    e.expect("Admin desactiva a «Técnico Dieciséis»", admin.post(f"/users/{ESTADO['tecnico16_id']}/deactivate"), 200)
    chk("Desactivado, no puede entrar", login("tecnico16@demo-org.com").status_code == 401, "")
    r = httpx.get(f"{API}/auth/me", headers=bearer(tok), timeout=30)
    chk("Su sesión abierta deja de funcionar", r.status_code == 401, r.status_code)


def auth007():
    token = ENLACES["sinrol"]
    r = httpx.post(f"{API}/auth/invitations/accept", json={"token": token, "password": e.PASSWORD}, timeout=30)
    chk("Aceptar la invitación de sinrol", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    r = login("sinrol@demo-org.com")
    tok = r.json().get("access_token") if r.status_code == 200 else ""
    me = httpx.get(f"{API}/auth/me", headers=bearer(tok), timeout=30).json() if tok else {}
    chk("Sin permisos: la sesión no trae permisos ni módulos", me.get("permissions") == [] and not me.get("modules"),
        f"{me.get('permissions')} {me.get('modules')}")
    rutas = ["/cases", "/projects", "/invoices", "/customers", "/warehouse/items", "/payables/suppliers"]
    codigos = {p: httpx.get(f"{API}{p}", headers=bearer(tok), timeout=30).status_code for p in rutas}
    chk("Expedientes, obras, facturas, clientes, bodega y proveedores → 403", set(codigos.values()) == {403}, codigos)
    e.expect("Admin le da al rol solo «Ver clientes»", admin.patch("/roles/qa_sin_permisos", json={
        "permissions": ["customers.read"]}), 200)
    me = httpx.get(f"{API}/auth/me", headers=bearer(tok), timeout=30).json()
    chk("Ahora la sesión trae solo customers.read", me.get("permissions") == ["customers.read"], me.get("permissions"))
    chk("Y el menú solo el módulo de clientes", me.get("modules") in (["crm"], ["customers"]) or len(me.get("modules") or []) == 1,
        me.get("modules"))
    codigos = {p: httpx.get(f"{API}{p}", headers=bearer(tok), timeout=30).status_code for p in rutas}
    chk("Clientes abre (200) y lo demás sigue en 403", codigos["/customers"] == 200
        and all(v == 403 for p, v in codigos.items() if p != "/customers"), codigos)


def sec006_reejecucion():
    """Tras corregir D-013: la foto de Carlos, ahora como Luis."""
    ev = sql("select e.id from evidence e join users u on u.id = e.uploaded_by_user_id "
             "where u.email = 'tecnico03@demo-org.com' and e.original_filename = 'foto.jpg' "
             "order by e.created_at desc limit 1")
    luis, carlos, ajeno = cliente("luis"), cliente("carlos"), cliente("ajeno")
    chk("Reejecución D-013: sin sesión → 401", httpx.get(f"{API}/evidence/{ev}/file", timeout=30).status_code == 401, "")
    r = luis.get(f"/evidence/{ev}/file")
    chk("Reejecución D-013: Luis (técnico de otra obra) → 404", r.status_code == 404, r.status_code)
    chk("Reejecución D-013: admin ajeno → 404", ajeno.get(f"/evidence/{ev}/file").status_code == 404, "")
    chk("Reejecución D-013: Carlos sí la abre", carlos.get(f"/evidence/{ev}/file").status_code == 200, "")
    chk("Reejecución D-013: Administración (ve todas las obras) sí la abre",
        cliente("adm").get(f"/evidence/{ev}/file").status_code == 200, "")


def sec005_pdf():
    """El PDF va en los documentos del expediente, no en las evidencias de obra (son fotos y videos)."""
    v = cliente("vendedor")
    p = e.persona(334, "AZ")
    caso = e.abrir_puerta(v, p, "AZ_EFFICIENCY", "opened").get("case") or {}
    ruta = f"/cases/{caso.get('id')}/documents"
    r = v.post(ruta, data={"label": "QA recibo"}, files={"file": ("recibo.pdf", e.pdf_doc("QA recibo"), "application/pdf")})
    chk("Un PDF real se acepta en los documentos del expediente", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    r = v.post(ruta, data={"label": "QA falso"}, files={"file": ("recibo.pdf", b"MZ\x90\x00" + b"\x00" * 512,
                                                                   "application/pdf")})
    chk("Un .exe con nombre .pdf se rechaza", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:150]}")
    r = v.post(ruta, data={"label": "QA svg"}, files={"file": ("x.svg", b"<svg><script>alert(1)</script></svg>",
                                                              "image/svg+xml")})
    chk("Un .svg con script se rechaza en documentos", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:150]}")


def auth005_agenda():
    limpiar()
    s = httpx.Client(base_url=API, timeout=30)
    s.post("/auth/login", json={"email": e.USERS["tecnico"], "password": e.PASSWORD})
    tok = s.post("/auth/refresh").json().get("access_token")
    r = s.get("/dispatch/agenda", headers=bearer(tok), params={
        "date_from": e.HOY.isoformat(), "date_to": e.HOY.isoformat()})
    chk("Con el token renovado la Agenda carga", r.status_code == 200, r.status_code)


def auth008_permiso_correcto():
    """Crear proveedores exige suppliers.manage (o payables.approve), no payables.manage."""
    conta = cliente("conta")
    rol = next(x for x in admin.get("/roles").json() if x["code"] == "accounting")
    originales = list(rol["permissions"])
    quitar = {"suppliers.manage", "payables.approve"} & set(originales)
    chk(f"Contabilidad crea proveedores con {sorted(quitar)}", bool(quitar), originales)
    e.expect("Admin quita esos permisos a Contabilidad", admin.patch("/roles/accounting", json={
        "permissions": [p for p in originales if p not in quitar]}), 200)
    r = conta.post("/payables/suppliers", json={"name": f"QA {e.RUN} Sin permiso"})
    chk("Con la misma sesión, crear un proveedor → 403 en la siguiente acción", r.status_code == 403, r.status_code)
    e.expect("Admin devuelve los permisos", admin.patch("/roles/accounting", json={"permissions": originales}), 200)
    r = conta.post("/payables/suppliers", json={"name": f"QA {e.RUN} Con permiso"})
    chk("Vuelve a funcionar sin volver a entrar", r.status_code == 201, f"{r.status_code} {r.text[:120]}")


import sys  # noqa: E402

if "--solo-pdf" in sys.argv:
    seguro("SEC-005", sec005_pdf)
else:
    seguro("SEC-006", sec006_reejecucion)
    seguro("SEC-005", sec005_pdf)
    seguro("AUTH-005", auth005_agenda)
    seguro("AUTH-008", auth008_permiso_correcto)
    seguro("AUTH-003", auth003)
    seguro("AUTH-004", auth004)
    seguro("AUTH-007", auth007)
limpiar()
guardar("/tmp/lote3b_pdf.json" if "--solo-pdf" in sys.argv else "/tmp/lote3b.json")
print("ok")
