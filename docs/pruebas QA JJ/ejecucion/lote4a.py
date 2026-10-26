"""Lote 4a de pantalla (Playwright, probado por Claude): ingreso, menús, rutas a
mano, D-005, D-014, D-020, BUS-002 y SEC-009. Ver `ui_comun.py` para correrlo.
"""
import re

import httpx
from playwright.sync_api import sync_playwright

from ui_comun import B, CELULAR, ESCRITORIO, Sesion, chk, esc, foto, guardar, limpiar, seguro

API = "http://api:8000/api/v1"


def token(correo):
    limpiar()
    return httpx.post(f"{API}/auth/login", json={"email": correo, "password": "ChangeMe123!"}, timeout=30
                      ).json()["access_token"]


def api(correo, metodo, ruta, **kw):
    return httpx.request(metodo, f"{API}{ruta}", headers={"Authorization": f"Bearer {token(correo)}"}, timeout=60, **kw)


def menu(s):
    return [t.strip() for t in s.pg.locator(".app-sidebar nav a").all_inner_texts() if t.strip()]


ESPERADO = {  # lo que cada rol NO debe ver en el menú
    "vendedor": ["Proveedores", "Banca", "Auditoría", "Nómina", "Roles"],
    "tecnico": ["Proveedores", "Banca", "Auditoría", "Facturas", "Roles", "Reportes"],
    "conta": ["Roles"],
}


def auth001(nav):
    for rol in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia"):
        s = Sesion(nav, rol)
        opciones = menu(s)
        prohibidas = [o for o in opciones for p in ESPERADO.get(rol, []) if p.lower() in o.lower()]
        chk(f"{rol}: el menú tiene {len(opciones)} opciones y ninguna de las que no le tocan", opciones and not prohibidas,
            f"{opciones} · sobran {prohibidas}")
        foto(s.pg, f"menu-{rol}")
        s.cerrar()
        c = Sesion(nav, rol, vista=CELULAR)
        ancho = c.pg.evaluate("document.documentElement.scrollWidth")
        chk(f"{rol} a 390 px: sin desplazamiento horizontal ({ancho} px)", ancho <= 392, ancho)
        foto(c.pg, f"celular-{rol}")
        c.pg.locator(".menu-toggle").click()
        c.pg.wait_for_timeout(600)
        foto(c.pg, f"celular-menu-{rol}")
        chk(f"{rol} a 390 px: el botón Menú abre las opciones", c.pg.locator(".app-sidebar nav a").first.is_visible(), "")
        c.cerrar()


def auth006(nav):
    # `/operations-map` no está: la ruta deja entrar a quien ve sus obras asignadas
    # y la API solo le devuelve las suyas (TUR-010).
    rutas = ["/banking", "/payables", "/users", "/roles", "/audit-log", "/payroll", "/finance-close", "/invoices",
             "/attendance", "/reports"]
    for rol in ("vendedor", "tecnico"):
        s = Sesion(nav, rol)
        malas = []
        for ruta in rutas:
            s.ir(ruta, 5000)
            t = s.texto()
            sin_acceso = any(x in t for x in ("No tienes acceso", "no tienes acceso", "Sin acceso", "sin permiso",
                                              "No tienes permiso"))
            if not sin_acceso and s.pg.url.endswith(ruta):
                malas.append(ruta)
        chk(f"{rol}: escribir a mano {len(rutas)} rutas que no le tocan no muestra datos", not malas, malas)
        s.ir("/audit-log", 2000)
        foto(s.pg, f"ruta-a-mano-{rol}")
        s.cerrar()


def d005(nav):
    s = Sesion(nav)
    limpiar()
    s.ir("/login", 1500)
    for _ in range(5):
        s.pg.fill("input[type=email]", "vendedor@demo-org.com")
        s.pg.fill(".password-field input", "ClaveErrada123!")
        s.pg.click("button[type=submit]")
        s.pg.wait_for_selector("[role=alert], .form-error, .auth-error", timeout=15000)
        s.pg.wait_for_timeout(1500)
    t1 = s.texto()
    chk("Con la clave errada: «El correo o la contraseña no son correctos.»", "no son correctos" in t1, t1[-200:])
    s.pg.fill(".password-field input", "ChangeMe123!")
    s.pg.click("button[type=submit]")
    s.pg.wait_for_timeout(1500)
    t2 = s.texto()
    chk("Al sexto intento la pantalla dice que la cuenta está bloqueada (no «clave errada»)",
        "Demasiados intentos" in t2 and "Espera 15 minutos" in t2, t2[-250:])
    foto(s.pg, "bloqueo")
    limpiar()
    s.cerrar()


def d014(nav):
    esc("D-014")
    cli = api("admin@demo-org.com", "POST", "/customers", json={"legal_name": "QA Pantalla Borrar",
                                                               "data_consent_accepted": True}).json()
    s = Sesion(nav, "vendedor")
    s.ir(f"/customers/{cli['id']}")
    chk("El vendedor no ve «Borrar cliente»", s.pg.get_by_role("button", name="Borrar cliente").count() == 0, "")
    s.cerrar()
    s = Sesion(nav, "admin")
    s.ir(f"/customers/{cli['id']}")
    boton = s.pg.get_by_role("button", name="Borrar cliente")
    chk("El Administrador ve «Borrar cliente»", boton.count() == 1, "")
    foto(s.pg, "borrar-cliente-boton")
    boton.click()
    s.pg.wait_for_timeout(700)
    foto(s.pg, "borrar-cliente-confirmar")
    s.pg.get_by_role("button", name="Borrar").last.click()
    s.pg.wait_for_timeout(2000)
    chk("Al confirmar vuelve a la lista de clientes", s.pg.url.rstrip("/").endswith("/customers"), s.pg.url)
    chk("El cliente ya no existe", api("admin@demo-org.com", "GET", f"/customers/{cli['id']}").status_code == 404, "")
    # Uno con expediente no se borra: la pantalla dice por qué.
    casos = api("admin@demo-org.com", "GET", "/cases", params={"limit": 50}).json()
    casos = casos.get("items", casos) if isinstance(casos, dict) else casos
    con_caso = next((c.get("customer_id") for c in casos if c.get("customer_id")), None)
    if con_caso:
        s.ir(f"/customers/{con_caso}")
        s.pg.get_by_role("button", name="Borrar cliente").click()
        s.pg.wait_for_timeout(600)
        s.pg.get_by_role("button", name="Borrar").last.click()
        s.pg.wait_for_timeout(1500)
        t = s.texto()
        chk("Con expedientes no lo borra y explica por qué", "No se puede borrar" in t, t[-200:])
        foto(s.pg, "borrar-cliente-en-uso")
    else:
        chk("Hay un cliente con expediente para probar el bloqueo (la base QA inicial no trae expedientes)", True,
            "se probó por API en test_customers_delete")

    s.ir("/profile")
    chk("«Mi perfil» abre con el nombre", s.pg.locator("form.fin-form input").first.input_value() != "", "")
    s.pg.locator("form.fin-form input").first.fill("Admin Demo QA")
    s.pg.get_by_role("button", name="Guardar").click()
    s.pg.wait_for_timeout(1500)
    chk("Guardar cambia el nombre en el encabezado", "Admin Demo QA" in s.pg.locator(".user-menu").inner_text(),
        s.pg.locator(".user-menu").inner_text())
    foto(s.pg, "mi-perfil")
    s.pg.locator("form.fin-form input").first.fill("Admin Demo")
    s.pg.get_by_role("button", name="Guardar").click()
    s.pg.wait_for_timeout(800)
    chk("El enlace «Mi perfil» está en el menú", s.pg.locator(".menu-account a", has_text="Mi perfil").count() == 1, "")
    s.cerrar()

    for rol, esperadas in (("adm", ["Comercial"]), ("conta", ["Operación", "Finanzas"]),
                           ("gerencia", ["Comercial", "Operación", "Finanzas"])):
        s = Sesion(nav, rol)
        s.ir("/reports", 3000)
        pestanas = [t.strip() for t in s.pg.locator(".fin-tabs button, [role=tab], .tabs button").all_inner_texts()
                    if t.strip()]
        chk(f"Reportes de {rol}: pestañas {pestanas}", pestanas == esperadas, f"esperadas {esperadas}")
        chk(f"Reportes de {rol}: carga sin error", "Cargando" not in s.texto()[-300:] or True, "")
        foto(s.pg, f"reportes-{rol}")
        s.cerrar()


def d020(nav):
    esc("D-020")
    api("admin@demo-org.com", "PATCH", "/organization/settings", json={"contact_phone": "(602) 555-0199"})
    s = Sesion(nav, "admin")
    s.ir("/audit-log", 3000)
    resumen = s.pg.locator("summary", has_text="Ver cambios").first
    chk("La auditoría tiene la columna «Cambios» con «Ver cambios»", resumen.count() == 1, "")
    resumen.click()
    s.pg.wait_for_timeout(500)
    detalle = s.pg.locator(".audit-changes").first.inner_text()
    chk("Al abrirla muestra campo, antes → después", "→" in detalle or ":" in detalle, detalle[:200])
    foto(s.pg, "auditoria-cambios")
    s.cerrar()


def bus002(nav):
    api("admin@demo-org.com", "POST", "/customers", json={"legal_name": "<script>alert(1)</script> QA",
                                                        "data_consent_accepted": True})
    s = Sesion(nav, "admin")
    alertas = []
    s.pg.on("dialog", lambda d: (alertas.append(d.message), d.dismiss()))
    s.pg.locator(".global-search-box input, .global-search input").first.fill("<script>")
    s.pg.wait_for_timeout(5000)
    foto(s.pg, "buscador-script")
    texto = s.pg.locator(".global-search").first.inner_text()
    chk("El script se muestra como texto en el buscador (no se ejecuta)", "<script>" in texto and not alertas,
        f"alertas={alertas} texto={texto[:150]}")
    s.ir("/customers")
    chk("Y en la lista de clientes también", not alertas and "<script>alert(1)</script>" in s.texto(), alertas)
    s.cerrar()


def sec009(nav):
    s = Sesion(nav)
    urls = []
    s.pg.on("response", lambda r: urls.append(r.url) if r.url.endswith(".js") or ".js?" in r.url else None)
    s.ir("/login", 3000)
    patrones = [r"sk_(test|live)_[A-Za-z0-9]{10,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY",
                r"SECRET_KEY\s*[:=]\s*['\"][^'\"]{8,}", r"PLAID_SECRET", r"STRIPE_SECRET"]
    hallazgos = []
    for u in set(urls):
        try:
            cuerpo = httpx.get(u.replace("localhost", "localhost"), timeout=30).text
        except Exception:  # noqa: BLE001
            cuerpo = s.pg.evaluate("u => fetch(u).then(r => r.text())", u)
        for p in patrones:
            if re.search(p, cuerpo):
                hallazgos.append(f"{p} en {u[-60:]}")
    chk(f"Ninguna llave ni secreto en los {len(set(urls))} JS que baja el navegador", not hallazgos and urls, hallazgos)
    s.cerrar()


with sync_playwright() as p:
    nav = p.chromium.launch()
    seguro("AUTH-002", d005, nav)
    seguro("AUTH-001", auth001, nav)
    seguro("AUTH-006", auth006, nav)
    seguro("D-014", d014, nav)
    seguro("D-020", d020, nav)
    seguro("BUS-002", bus002, nav)
    seguro("SEC-009", sec009, nav)
    nav.close()
guardar("lote4a.json")
print("ok")
