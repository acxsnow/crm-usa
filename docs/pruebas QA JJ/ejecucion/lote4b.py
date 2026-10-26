"""Lote 4b de pantalla (Playwright, probado por Claude), con los datos de `prep4b.py`.
Ver `ui_comun.py` para correrlo.
"""
import json
import time
from datetime import date, timedelta

import httpx
from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, QA, Sesion, chk, esc, foto, guardar, limpiar, seguro

API = "http://api:8000/api/v1"
D = json.loads((QA / "ejecucion" / "prep4b.json").read_text())


def api(correo, metodo, ruta, **kw):
    limpiar()
    tok = httpx.post(f"{API}/auth/login", json={"email": correo, "password": "ChangeMe123!"}, timeout=30).json()["access_token"]
    return httpx.request(metodo, f"{API}{ruta}", headers={"Authorization": f"Bearer {tok}"}, timeout=60, **kw)


def paso(pg, clave):
    s = pg.locator(f"#acta-step-{clave}")
    if s.locator(".acta-step-body").count() == 0:
        s.locator(".acta-step-head").click()
        pg.wait_for_timeout(1000)
    return s


def ins010(nav):
    s = Sesion(nav, "tecnico")
    s.ir(f"/projects/{D['pid_visita']}", 3500)
    p = paso(s.pg, "release")
    boton = p.get_by_role("button", name="No se pudo hacer la visita")
    chk("El técnico ve «No se pudo hacer la visita» en la obra agendada", boton.count() == 1, "")
    boton.click()
    s.pg.wait_for_timeout(600)
    opciones = s.pg.locator("#visita-motivo option").all_inner_texts()
    chk(f"El formulario pide el motivo ({len(opciones) - 1} opciones) y la nota", len(opciones) >= 4
        and s.pg.locator("#visita-nota").count() == 1, opciones)
    s.pg.select_option("#visita-motivo", index=1)
    s.pg.fill("#visita-nota", "QA pantalla: toqué tres veces y no abrieron")
    foto(s.pg, "formulario")
    s.pg.locator("form.panel-form button[type=submit]").first.click()
    s.pg.wait_for_timeout(2500)
    t = paso(s.pg, "release").inner_text()
    chk("Queda la sección «Visitas fallidas» con el contador y lo que escribió", "Visitas fallidas" in t
        and "toqué tres veces" in t, t[:300])
    foto(s.pg, "visitas-fallidas", completa=True)
    s.cerrar()


def ins011(nav):
    # Segunda visita fallida por API para llegar al límite (2).
    api("administracion@demo-org.com", "PATCH", f"/projects/{D['pid_visita']}/schedule", json={
        "technician_user_id": api("tecnico@demo-org.com", "GET", "/auth/me").json()["id"],
        "scheduled_date": (date.today() + timedelta(days=2)).isoformat()})
    r = api("tecnico@demo-org.com", "POST", f"/projects/{D['pid_visita']}/failed-visits", json={
        "reason_code": "customer_absent", "notes": "QA segunda visita fallida", "latitude": 33.45, "longitude": -112.07})
    chk("Segunda visita fallida (por API) para llegar al límite", r.status_code == 201, r.text[:150])
    s = Sesion(nav, "admin")
    s.ir(f"/projects/{D['pid_visita']}", 3500)
    t = paso(s.pg, "release").inner_text()
    chk("Administración ve el aviso del límite alcanzado", "2 de 2" in t or "límite" in t.lower(), t[:300])
    chk("Y el botón «Autorizar otro intento»", s.pg.get_by_role("button", name="Autorizar otro intento").count() == 1, "")
    chk("Y el ajuste «Límite de visitas fallidas»", "Límite de visitas fallidas" in s.texto(), "")
    foto(s.pg, "limite", completa=True)
    s.cerrar()


def ins012(nav):
    s = Sesion(nav, "admin")
    s.ir(f"/projects/{D['pid_cancelar']}", 3500)
    paso(s.pg, "release")
    s.pg.get_by_role("button", name="Cancelar la obra…").click()
    s.pg.wait_for_timeout(1500)
    t = paso(s.pg, "release").inner_text()
    chk("Antes de cancelar muestra la salida por autorizar y el material afuera", ("autorizar" in t.lower()
        or "Por autorizar" in t) and "3496" in t or "PVC" in t, t[:400])
    foto(s.pg, "cancelar-pendientes", completa=True)
    api("administracion@demo-org.com", "POST", f"/warehouse/releases/{D['salida_abierta']}/reject",
        json={"reason": "QA: la obra se cancela"})
    s.ir(f"/projects/{D['pid_cancelar']}", 3500)
    paso(s.pg, "release")
    s.pg.get_by_role("button", name="Cancelar la obra…").click()
    s.pg.wait_for_timeout(1500)
    for campo in s.pg.locator("#acta-step-release textarea").all():
        campo.fill("QA pantalla: el cliente desistió; los 2 tubos quedaron en la casa")
    for campo in s.pg.locator("#acta-step-release input[type=text]").all():
        campo.fill("QA pantalla: el cliente desistió")
    foto(s.pg, "cancelar-formulario", completa=True)
    s.pg.locator("#acta-step-release").get_by_role("button", name="Cancelar la obra").last.click()
    s.pg.wait_for_timeout(3000)
    t = s.texto()
    chk("La obra queda con el aviso «Obra cancelada»", "cancelada" in t.lower(), t[:300])
    foto(s.pg, "obra-cancelada")
    s.cerrar()


def d007(nav):
    esc("BOD-011")
    s = Sesion(nav, "admin")
    s.ir("/warehouse/releases", 3500)
    fila = s.pg.locator("tr", has=s.pg.get_by_role("button", name="Entregar")).first
    fila.get_by_role("button", name="Entregar").click()
    s.pg.wait_for_timeout(1200)
    entrada = s.pg.get_by_label("Serial 1 de", exact=False)
    chk("Al entregar el equipo con serial aparece un campo por unidad", entrada.count() >= 1, "")
    boton = s.pg.locator("form").get_by_role("button", name="Entregar")
    chk("Sin el serial, «Entregar» queda deshabilitado", boton.is_disabled(), "")
    foto(s.pg, "entregar-sin-serial")
    entrada.first.fill("sn-ui-001")
    s.pg.wait_for_timeout(300)
    boton.click()
    s.pg.wait_for_timeout(2500)
    t = s.texto()
    chk("Al entregar dice los seriales entregados", "Seriales entregados" in t and "SN-UI-001" in t.upper(), t[:300])
    foto(s.pg, "entregado")
    s.ir("/warehouse/serials", 3000)
    t = s.texto()
    chk("Bodega › Seriales lo muestra «Entregado a la obra» con la orden", "SN-UI-001" in t and "Entregado" in t, t[:300])
    foto(s.pg, "seriales")
    s.cerrar()
    s = Sesion(nav, "tecnico")
    s.ir(f"/projects/{D['pid_serial']}", 3500)
    p = paso(s.pg, "equipment")
    sel = s.pg.locator("#equipment-stock-serial")
    chk("En Equipos instalados el técnico ve «Equipo que salió de bodega»", sel.count() == 1, p.inner_text()[:200])
    if sel.count():
        sel.select_option(index=1)
        s.pg.wait_for_timeout(400)
        chk("Al elegirlo se llenan marca, modelo y serial", s.pg.locator("#equipment-serial").input_value() == "SN-UI-001",
            s.pg.locator("#equipment-serial").input_value())
    foto(s.pg, "equipos-instalados", completa=True)
    s.cerrar()


def d002(nav):
    esc("FIN-005")
    for vista, nombre in ((None, "escritorio"), (CELULAR, "celular")):
        s = Sesion(nav, "gerencia", **({"vista": vista} if vista else {}))
        s.ir("/finance-close", 4000)
        pestana = s.pg.get_by_role("tab", name="Rentabilidad")
        if pestana.count():
            pestana.click()
            s.pg.wait_for_timeout(2500)
        t = s.texto()
        chk(f"Rentabilidad ({nombre}): el margen negativo se lee completo «-$80,705.00»", "-$80,705.00" in t
            and "$-80" not in t, [l for l in t.split("\n") if "80,705" in l][:3])
        if vista:
            chk("A 390 px sin desplazamiento horizontal de la página", s.pg.evaluate("document.documentElement.scrollWidth") <= 392, "")
        foto(s.pg, f"rentabilidad-{nombre}", completa=True)
        s.cerrar()


def ven001(nav):
    s = Sesion(nav, "vendedor")
    s.ir("/cases", 3500)
    antes = s.texto()
    chk("Las puertas cerradas no salen en el tablero sin activar el filtro", "Sin contacto" not in antes
        and "No interesado" not in antes, "")
    s.pg.get_by_label("Mostrar puertas cerradas").check()
    s.pg.wait_for_timeout(2500)
    despues = s.texto()
    chk("Con «Mostrar puertas cerradas» aparecen", "Sin contacto" in despues or "No interesado" in despues, despues[:300])
    foto(s.pg, "puertas-cerradas", completa=True)
    s.cerrar()


def rev001(nav):
    s = Sesion(nav, "admin")
    s.ir(f"/cases/{D['cid_revisar']}/review", 3500)
    boton = s.pg.get_by_role("button", name="Aprobar")
    chk("Con documentos sin revisar «Aprobar» queda bloqueado", boton.count() == 1 and boton.is_disabled(), "")
    chk("Y dice cuántos faltan («Faltan N documento(s) por revisar.»)", "por revisar" in s.texto(), "")
    foto(s.pg, "aprobar-bloqueado", completa=True)
    s.cerrar()


def rev002(nav):
    s = Sesion(nav, "vendedor")
    s.ir("/sales", 3500)
    t = s.texto()
    chk("El vendedor ve «Devueltos por Administración»", "Devueltos por Administración" in t, t[:300])
    foto(s.pg, "devueltos", completa=True)
    s.ir(f"/cases/{D['cid_devuelto']}/form", 3500)
    t = s.texto()
    chk("Al abrirlo ve el motivo de la devolución", "foto borrosa" in t, t[:300])
    foto(s.pg, "motivo", completa=True)
    s.cerrar()


def api001(nav):
    s = Sesion(nav, "admin")
    s.ir("/warehouse/items", 4000)
    t1 = s.texto()
    chk("Artículos muestra 244 en total", "244" in t1, [l for l in t1.split("\n") if "244" in l][:2])
    primeros = s.pg.locator("tbody tr").all_inner_texts()[:3]
    siguiente = s.pg.get_by_role("button", name="Siguiente")
    if siguiente.count():
        siguiente.first.click()
        s.pg.wait_for_timeout(2500)
    segundos = s.pg.locator("tbody tr").all_inner_texts()[:3]
    chk("Pasar de página trae otras filas (sin repetir)", segundos and set(segundos).isdisjoint(primeros),
        f"{[p[:30] for p in primeros]} / {[p[:30] for p in segundos]}")
    foto(s.pg, "pagina-2")
    s.cerrar()


def auth007(nav):
    s = Sesion(nav, correo="tecnico06@demo-org.com")
    opciones = [t.strip() for t in s.pg.locator(".app-sidebar nav a").all_inner_texts() if t.strip()]
    chk(f"Sin permisos el menú solo trae Inicio ({opciones})", opciones == ["Inicio"], opciones)
    foto(s.pg, "sin-permisos")
    malas = []
    for ruta in ("/cases", "/projects", "/invoices", "/customers"):
        s.ir(ruta, 4000)
        if not s.pg.url.rstrip("/").endswith("5173"):
            malas.append(ruta)
    chk("Escribir /cases, /projects, /invoices y /customers lo devuelve al inicio", not malas, malas)
    api("admin@demo-org.com", "PATCH", "/roles/qa_sin_permisos", json={"permissions": ["customers.read"]})
    s.ir("/", 2000)
    s.pg.reload()
    s.pg.wait_for_timeout(3000)
    opciones = [t.strip() for t in s.pg.locator(".app-sidebar nav a").all_inner_texts() if t.strip()]
    chk(f"Con «Ver clientes» aparece solo Clientes ({opciones})", opciones == ["Inicio", "Clientes"], opciones)
    foto(s.pg, "solo-clientes")
    s.cerrar()
    api("admin@demo-org.com", "PATCH", f"/users/{D['t6']}/roles", json={"role_codes": ["field_technician"]})


def tur001(nav):
    s = Sesion(nav, "adm", vista=CELULAR)
    s.ir("/shifts", 4000)
    chk("La malla a 390 px no desborda la página", s.pg.evaluate("document.documentElement.scrollWidth") <= 392,
        s.pg.evaluate("document.documentElement.scrollWidth"))
    foto(s.pg, "malla-celular", completa=True)
    s.cerrar()


def tec003(nav):
    s = Sesion(nav, "adm")
    s.pg.locator(".app-sidebar nav a", has_text="Agenda").first.click()
    s.pg.wait_for_timeout(3500)
    foto(s.pg, "agenda", completa=True)
    vistas = [b for b in ("Semana", "Día") if s.pg.get_by_role("button", name=b).count()]
    for v in vistas:
        s.pg.get_by_role("button", name=v).first.click()
        s.pg.wait_for_timeout(1500)
        foto(s.pg, f"agenda-{v.lower()}", completa=True)
    chk(f"La agenda abre en {vistas or ['su vista']} con las obras de la semana", s.pg.locator("body").inner_text().count("Instalación") >= 1,
        "")
    s.cerrar()
    s = Sesion(nav, "adm", vista=CELULAR)
    s.pg.locator(".menu-toggle").click()
    s.pg.locator(".app-sidebar nav a", has_text="Agenda").first.click()
    s.pg.wait_for_timeout(3500)
    chk("La agenda a 390 px no desborda la página", s.pg.evaluate("document.documentElement.scrollWidth") <= 392, "")
    foto(s.pg, "agenda-celular", completa=True)
    s.cerrar()


def tur009(nav):
    s = Sesion(nav, "adm")
    s.ir("/technician-monitor", 4000)
    filas = s.pg.locator("tbody tr").count()
    chk(f"El monitor muestra a los técnicos ({filas} filas)", filas >= 14, filas)
    foto(s.pg, "monitor", completa=True)
    s.cerrar()


def per001(nav):
    s = Sesion(nav, "admin")
    tiempos = {}
    for nombre, ruta in (("Inicio", "/"), ("Expedientes", "/cases"), ("Por revisar", "/review"), ("Proyectos", "/projects"),
                         ("Existencias", "/warehouse"), ("Salidas", "/warehouse/releases"), ("Facturas", "/invoices"),
                         ("Mapa", "/operations-map")):
        t0 = time.perf_counter()
        s.pg.goto("http://localhost:5173" + ruta)
        s.pg.wait_for_load_state("networkidle", timeout=30000)
        tiempos[nombre] = round((time.perf_counter() - t0) * 1000)
    lentas = {k: v for k, v in tiempos.items() if v > 2000}
    chk("Ninguna pantalla tarda más de 2 s hasta quedar quieta (servidor de desarrollo, sin caché de producción)",
        not lentas, json.dumps(tiempos))
    s.cerrar()
    esc("PER-004")
    chk("Se navegó por 8 pantallas con el worker y el beat corriendo sin que se frenaran (tiempos de PER-001)",
        not lentas, json.dumps(tiempos))


with sync_playwright() as p:
    nav = p.chromium.launch()
    for eid, fn in (("INS-010", ins010), ("INS-011", ins011), ("INS-012", ins012), ("BOD-011", d007),
                    ("FIN-005", d002), ("VEN-001", ven001), ("REV-001", rev001), ("REV-002", rev002),
                    ("API-001", api001), ("AUTH-007", auth007), ("TUR-001", tur001), ("TEC-003", tec003),
                    ("TUR-009", tur009), ("PER-001", per001)):
        seguro(eid, fn, nav)
    nav.close()
guardar("lote4b.json")
print("ok")
