"""Base de las pruebas de pantalla (lote 4) con Playwright: las hace Claude y José
las revisa después. Corre con la imagen de Playwright en la red del contenedor
del frontend, para que `localhost:5173` sea la app de verdad (Vite rechaza el
nombre del servicio):

    docker run --rm --network container:crm-usa-frontend-1 \
      -v "<repo>/docs/pruebas QA JJ:/q" mcr.microsoft.com/playwright/python:v1.47.0-jammy \
      sh -c "pip install -q playwright==1.47.0 redis && cd /q/ejecucion && python lote4a.py"

Cada comprobación cae en el escenario activo y las capturas quedan en
`evidencias/pantalla/<escenario>/`, para mirarlas.
"""
import json
from pathlib import Path

import redis

B = "http://localhost:5173"
CLAVE = "ChangeMe123!"
USUARIOS = {"admin": "admin@demo-org.com", "adm": "administracion@demo-org.com", "vendedor": "vendedor@demo-org.com",
            "tecnico": "tecnico@demo-org.com", "conta": "contabilidad@demo-org.com", "gerencia": "gerencia@demo-org.com",
            "carlos": "tecnico03@demo-org.com", "luis": "tecnico04@demo-org.com"}
ESCRITORIO = {"width": 1280, "height": 860}
CELULAR = {"width": 390, "height": 844}
QA = Path(__file__).resolve().parents[1]
EVID = QA / "evidencias" / "pantalla"
OUT: dict[str, list] = {}
ACTUAL = ["_prep"]
R = redis.Redis(host="redis")


def limpiar():
    for k in R.scan_iter("ratelimit:*"):
        R.delete(k)


def esc(eid):
    ACTUAL[0] = eid


def chk(nombre, ok, dato=""):
    OUT.setdefault(ACTUAL[0], []).append({"check": nombre, "ok": bool(ok), "dato": str(dato)[:300]})
    print(("  ✓ " if ok else "  ✗ ") + nombre + ("" if ok else f" — {str(dato)[:200]}"))


def foto(pg, nombre, completa=False):
    carpeta = EVID / ACTUAL[0]
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.jpg"
    pg.screenshot(path=str(ruta), type="jpeg", quality=70, full_page=completa)
    return f"evidencias/pantalla/{ACTUAL[0]}/{nombre}.jpg"


class Sesion:
    def __init__(self, navegador, rol=None, vista=ESCRITORIO, correo=None, clave=CLAVE, **ctx):
        self.ctx = navegador.new_context(viewport=vista, locale="es-CO", timezone_id="America/Bogota",
                                         permissions=["geolocation"], geolocation={"latitude": 33.4484,
                                                                                    "longitude": -112.074}, **ctx)
        self.pg = self.ctx.new_page()
        self.errores: list[str] = []
        self.pg.on("pageerror", lambda e: self.errores.append(str(e)[:200]))
        if rol or correo:
            limpiar()
            self.pg.goto(B + "/login")
            self.pg.fill("input[type=email]", correo or USUARIOS[rol])
            self.pg.fill(".password-field input", clave)
            self.pg.click("button[type=submit]")
            self.pg.wait_for_url(lambda u: "/login" not in u, timeout=30000)
            self.pg.wait_for_timeout(1500)

    def ir(self, ruta, espera=2500):
        self.pg.goto(B + ruta)
        self.pg.wait_for_timeout(espera)
        return self.pg

    def texto(self):
        return self.pg.locator("body").inner_text()

    def cerrar(self):
        self.ctx.close()


def seguro(eid, fn, *a, **kw):
    esc(eid)
    try:
        return fn(*a, **kw)
    except Exception as ex:  # noqa: BLE001
        chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
        return None


def guardar(nombre):
    OUT.pop("_prep", None)
    (QA / "ejecucion" / nombre).write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
