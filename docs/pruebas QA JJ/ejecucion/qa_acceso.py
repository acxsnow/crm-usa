"""Ataque a acceso, usuarios y roles (10 nov 2026).

Lo que puede pasar: alguien que se intenta dar más permisos, un usuario
desactivado que sigue entrando, una sesión que no se cierra, adivinar
correos con el «olvidé mi clave», borrar roles del sistema, y un
administrador de otra empresa tocando nuestro equipo.

PYTHONPATH=/app:/tmp python /tmp/qa_acceso.py → /tmp/qa_acceso.json
"""
import httpx

from qa_comun import API, chk, cliente, e, esc, guardar, limpiar, login

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "ajeno")}
admin, adm, v, tec, ajeno = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["ajeno"]
RUN = e.RUN
CLAVE = e.PASSWORD


def roles_de(user_id):
    perfil = admin.get(f"/users/{user_id}/profile").json()
    return sorted(r.get("code") if isinstance(r, dict) else r for r in perfil.get("roles", []))


# ===========================================================================
esc("ACC-01 Ingreso")
# ===========================================================================
limpiar()
r = httpx.post(f"{API}/auth/login", json={"email": "vendedor@demo-org.com", "password": "mala"}, timeout=30)
chk("Clave equivocada → 401 sin decir si el correo existe", r.status_code == 401, r.status_code)
r2 = httpx.post(f"{API}/auth/login", json={"email": f"noexiste{RUN}@demo-org.com", "password": "mala"}, timeout=30)
chk("Correo que no existe → la misma respuesta", (r2.status_code, r2.json().get("detail")) ==
    (r.status_code, r.json().get("detail")), f"{r.json().get('detail')} / {r2.json().get('detail')}")
for cuerpo in ({}, {"email": "x"}, {"email": "' OR 1=1 --", "password": "' OR 1=1 --"},
               {"email": "a" * 5000 + "@x.com", "password": "b" * 5000}):
    limpiar()
    r = httpx.post(f"{API}/auth/login", json=cuerpo, timeout=30)
    chk(f"Ingreso con datos raros ({str(cuerpo)[:30]}…) no entra ni da 500", r.status_code in (400, 401, 422),
        r.status_code)
limpiar()
bloqueo = [httpx.post(f"{API}/auth/login", json={"email": "gerencia@demo-org.com", "password": f"mala{i}"},
                      timeout=30).status_code for i in range(12)]
chk(f"Muchos intentos seguidos se frenan (límite) {bloqueo}", 429 in bloqueo or 423 in bloqueo, bloqueo)
limpiar()

# ===========================================================================
esc("ACC-02 Sesión")
# ===========================================================================
s = httpx.Client(base_url=API, timeout=30)
r = s.post("/auth/login", json={"email": "contabilidad@demo-org.com", "password": CLAVE})
token = r.json().get("access_token")
chk("Entra y recibe la sesión larga en cookie (no en el cuerpo)",
    r.status_code == 200 and "refresh_token" not in r.json() and any("refresh" in k for k in s.cookies.keys()),
    list(s.cookies.keys()))
r = s.post("/auth/refresh")
chk("Renueva la sesión con la cookie", r.status_code == 200, r.status_code)
s.post("/auth/logout", headers={"Authorization": f"Bearer {r.json().get('access_token', token)}"})
r = s.post("/auth/refresh")
chk("Después de salir, la cookie ya no renueva", r.status_code == 401, r.status_code)
r = httpx.get(f"{API}/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIn0."}, timeout=30)
chk("Un token falso (alg none) no entra", r.status_code == 401, r.status_code)
r = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token[:-4]}abcd"}, timeout=30)
chk("Un token alterado no entra", r.status_code == 401, r.status_code)

# ===========================================================================
esc("ACC-03 Nadie se da más permisos de los que tiene")
# ===========================================================================
r = v.patch("/auth/me", json={"full_name": "Vicky Vendedora", "email": "jefe@demo-org.com", "roles": ["organization_admin"],
                              "is_platform_super_admin": True, "status": "active"})
yo = v.get("/auth/me").json()
chk("Mi perfil solo cambia el nombre: ni correo, ni rol, ni superadmin",
    yo.get("email") == "vendedor@demo-org.com" and not yo.get("is_platform_super_admin")
    and "organization_admin" not in str(yo.get("roles")), str(yo)[:200])
r = adm.patch(f"/users/{adm.me['id']}/roles", json={"role_codes": ["organization_admin"]})
chk("Administración no se pone el rol de Administrador", r.status_code == 403, r.status_code)
r = v.post("/users", json={"email": f"qa.colado{RUN}@demo-org.com", "full_name": "Colado", "role_codes": ["organization_admin"]})
chk("El vendedor no crea usuarios", r.status_code == 403, r.status_code)
r = v.post("/roles", json={"code": f"qa_super_{RUN}", "name": "Súper", "permissions": ["users.manage"]})
chk("El vendedor no crea roles", r.status_code == 403, r.status_code)
r = adm.get("/audit-events")
chk(f"Administración y el vendedor ven la auditoría solo si tienen el permiso ({r.status_code})",
    v.get("/audit-events").status_code == 403, v.get("/audit-events").status_code)
r = v.patch("/organization/settings", json={"name": "Hackeada"})
chk("El vendedor no cambia la organización", r.status_code == 403, r.status_code)

# ===========================================================================
esc("ACC-04 Usuarios: crear, desactivar y lo que no se debe")
# ===========================================================================
nuevo = e.expect("Administrador invita a un técnico nuevo", admin.post("/users", json={
    "email": f"qa.tec.{RUN}@demo-org.com", "full_name": f"QA Técnico {RUN}", "role_codes": ["field_technician"]}),
    201) or {}
r = admin.post("/users", json={"email": f"QA.TEC.{RUN}@DEMO-ORG.COM", "full_name": "Dup", "role_codes": ["field_technician"]})
chk("El mismo correo con mayúsculas no crea un duplicado", r.status_code in (400, 409), r.status_code)
r = admin.post("/users", json={"email": "no-es-correo", "full_name": "X", "role_codes": ["field_technician"]})
chk("Correo inválido se rechaza", r.status_code in (400, 422), r.status_code)
r = admin.post("/users", json={"email": f"qa.rol.{RUN}@demo-org.com", "full_name": "X", "role_codes": ["no_existe"]})
chk("Rol que no existe se rechaza", r.status_code in (400, 404, 422), r.status_code)
r = admin.post(f"/users/{admin.me['id']}/deactivate")
chk("El Administrador no se desactiva a sí mismo", r.status_code in (400, 409), r.status_code)
r = admin.patch(f"/users/{admin.me['id']}/roles", json={"role_codes": ["salesperson"]})
chk("El último Administrador no se quita su propio rol", r.status_code in (400, 403, 409), r.status_code)

# Un técnico activo al que se desactiva: su sesión abierta deja de servir.
tec_ses = login("tecnico03@demo-org.com")
tok = tec_ses.json().get("access_token") if tec_ses.status_code == 200 else None
carlos = next((u for u in admin.get("/users", params={"q": "tecnico03", "limit": 5}).json()["items"]
               if u.get("email") == "tecnico03@demo-org.com"), None)
if tok and carlos:
    e.expect("Se desactiva a Carlos", admin.post(f"/users/{carlos['id']}/deactivate"), 200)
    r = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    chk("Su sesión abierta deja de servir al desactivarlo", r.status_code in (401, 403), r.status_code)
    r = login("tecnico03@demo-org.com")
    chk("Desactivado, ya no puede entrar", r.status_code in (401, 403), r.status_code)
    e.expect("Se reactiva a Carlos", admin.post(f"/users/{carlos['id']}/activate"), 200)
    chk("Reactivado vuelve a entrar", login("tecnico03@demo-org.com").status_code == 200)
else:
    chk("Preparar al técnico 03", False, f"{tec_ses.status_code} {carlos}")

# ===========================================================================
esc("ACC-05 Roles")
# ===========================================================================
r = admin.delete("/roles/organization_admin")
chk("No se borra el rol de Administrador", r.status_code in (400, 403, 409), r.status_code)
r = admin.delete("/roles/salesperson")
chk("No se borra un rol del sistema en uso", r.status_code in (400, 403, 409), r.status_code)
r = admin.post("/roles", json={"code": f"qa_rol_{RUN}", "name": "QA rol", "permissions": ["no.existe"]})
chk("Un rol con un permiso inventado se rechaza", r.status_code in (400, 422), r.status_code)
rol = e.expect("Rol propio con dos permisos reales", admin.post("/roles", json={
    "code": f"qa_rol_{RUN}", "name": f"QA rol {RUN}", "permissions": ["customers.read", "cases.read_all"]}), 201)
r = admin.post("/roles", json={"code": f"qa_rol_{RUN}", "name": "Otra vez", "permissions": []})
chk("El mismo código de rol no se repite", r.status_code in (400, 409), r.status_code)

# ===========================================================================
esc("ACC-06 Otra organización no toca nuestro equipo")
# ===========================================================================
for metodo, ruta, cuerpo in (("GET", f"/users/{v.me['id']}/profile", None),
                             ("PATCH", f"/users/{v.me['id']}", {"full_name": "Robado"}),
                             ("PATCH", f"/users/{v.me['id']}/roles", {"role_codes": ["salesperson"]}),
                             ("POST", f"/users/{v.me['id']}/deactivate", None)):
    r = ajeno.call(metodo, ruta, json=cuerpo) if cuerpo is not None else ajeno.call(metodo, ruta)
    chk(f"Otra organización: {metodo} {ruta.split('/')[-1] or 'perfil'} → no", r.status_code in (403, 404), r.status_code)
lista = ajeno.get("/users", params={"q": "demo-org", "limit": 50}).json().get("items", [])
chk("En su lista de usuarios no aparece nadie nuestro",
    not any("demo-org.com" in (u.get("email") or "") for u in (lista if isinstance(lista, list) else [])),
    str(lista)[:150])
r = ajeno.get("/audit-events", params={"limit": 50})
eventos = r.json() if r.status_code == 200 else []
chk("Su auditoría no muestra lo nuestro",
    not any(v.me["id"] in str(ev) for ev in (eventos if isinstance(eventos, list) else [])), r.status_code)

# ===========================================================================
esc("ACC-07 Restablecer contraseña e invitaciones")
# ===========================================================================
limpiar()
r1 = httpx.post(f"{API}/auth/password-reset/request", json={"email": "vendedor@demo-org.com"}, timeout=30)
r2 = httpx.post(f"{API}/auth/password-reset/request", json={"email": f"nadie{RUN}@demo-org.com"}, timeout=30)
chk("Pedir el enlace responde igual exista o no el correo", (r1.status_code, r1.text) == (r2.status_code, r2.text),
    f"{r1.status_code} {r2.status_code}")
r = httpx.post(f"{API}/auth/password-reset/confirm", json={"token": "inventado", "new_password": "OtraClave123!"}, timeout=30)
chk("Un token de restablecer inventado no sirve", r.status_code in (400, 401, 404), r.status_code)
r = httpx.post(f"{API}/auth/invitations/accept", json={"token": "inventado", "password": "OtraClave123!"}, timeout=30)
chk("Una invitación inventada no sirve", r.status_code in (400, 401, 404, 422), r.status_code)

guardar("/tmp/qa_acceso.json")
print("FIN")
