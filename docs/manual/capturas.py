"""Capturas anotadas del manual de usuario (docs/Manual_Usuario_CRM_Delta_HVAC.docx).

Entra con cada rol a la app real, abre cada pantalla, dibuja recuadros, números
y flechas sobre los elementos que explica el manual y guarda la imagen en
`docs/manual/img/`. La leyenda de cada número queda en `docs/manual/img/capturas.json`,
que lee `docs/manual/manual.js` al armar el Word.

Necesita la app arriba con los datos de `backend/scripts/manual_demo.py`
(ids en `docs/manual/demo.json`). Se corre con la imagen de Playwright:

    docker run --rm --network crm-usa_default -v "<repo>/docs/manual:/m" \
      mcr.microsoft.com/playwright/python:v1.47.0-jammy \
      sh -c "pip install -q playwright==1.47.0 redis && python /m/pantallas.py [clave ...]"
"""
import json
import sys
from pathlib import Path

import redis
from playwright.sync_api import sync_playwright

B = "http://localhost:5173"
CLAVE = "ChangeMe123!"
USUARIOS = {"admin": "admin@demo-org.com", "adm": "administracion@demo-org.com", "vendedor": "vendedor@demo-org.com",
            "tecnico": "tecnico@demo-org.com", "conta": "contabilidad@demo-org.com", "gerencia": "gerencia@demo-org.com"}
ESCRITORIO = {"width": 1280, "height": 800}
CELULAR = {"width": 390, "height": 844}
AQUI = Path(__file__).parent
IMG = AQUI / "img"
DEMO = json.loads((AQUI / "demo.json").read_text())

# Dibuja sobre la pantalla: recuadro rojo en cada elemento, un círculo numerado
# al costado y una flecha del círculo al recuadro. Coordenadas de la ventana.
ANOTAR_JS = """
(items) => {
  document.getElementById('__anot')?.remove();
  const W = innerWidth, H = innerHeight, NS = 'http://www.w3.org/2000/svg';
  const capa = document.createElement('div');
  capa.id = '__anot';
  capa.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  svg.style.cssText = 'position:absolute;inset:0';
  svg.innerHTML = '<defs><marker id="pt" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#E11D48"/></marker></defs>';
  capa.appendChild(svg);
  const R = 15, D = 46;
  for (const it of items) {
    const x = it.x - 4, y = it.y - 4, w = it.w + 8, h = it.h + 8;
    const caja = document.createElement('div');
    caja.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;border:3px solid #E11D48;border-radius:8px;box-shadow:0 0 0 2px rgba(255,255,255,.85)`;
    capa.appendChild(caja);
    // Las cajas más grandes que la pantalla se ubican por su parte visible.
    const vx = Math.max(x, 0), vy = Math.max(y, 0), vx2 = Math.min(x + w, W), vy2 = Math.min(y + h, H);
    const cx = (vx + vx2) / 2, cy = (vy + vy2) / 2;
    let bx, by, ax, ay;
    const lado = it.side || 'left';
    if (lado === 'left')   { bx = x - D; by = cy; ax = x; ay = cy; }
    if (lado === 'right')  { bx = x + w + D; by = cy; ax = x + w; ay = cy; }
    if (lado === 'top')    { bx = cx; by = y - D; ax = cx; ay = y; }
    if (lado === 'bottom') { bx = cx; by = y + h + D; ax = cx; ay = y + h; }
    // «inside»: si a la derecha hay lugar, el número va ahí con flecha corta; si no, dentro.
    if (lado === 'inside' && W - (x + w) >= 2 * R + 14) { bx = x + w + R + 8; by = cy; ax = x + w; ay = cy; }
    else if (lado === 'inside') { bx = vx2 - R - 6; by = vy + R + 6; ax = null; }
    bx = Math.min(Math.max(bx, R + 3), W - R - 3); by = Math.min(Math.max(by, R + 3), H - R - 3);
    if (ax !== null) {
      const l = document.createElementNS(NS, 'line');
      const dx = ax - bx, dy = ay - by, len = Math.hypot(dx, dy) || 1;
      l.setAttribute('x1', bx + dx / len * R); l.setAttribute('y1', by + dy / len * R);
      l.setAttribute('x2', ax); l.setAttribute('y2', ay);
      l.setAttribute('stroke', '#E11D48'); l.setAttribute('stroke-width', '3'); l.setAttribute('marker-end', 'url(#pt)');
      svg.appendChild(l);
    }
    const c = document.createElement('div');
    c.textContent = it.n;
    c.style.cssText = `position:absolute;left:${bx - R}px;top:${by - R}px;width:${2 * R}px;height:${2 * R}px;border-radius:50%;background:#E11D48;color:#fff;font:700 16px/30px Arial,sans-serif;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.35);border:2px solid #fff`;
    capa.appendChild(c);
  }
  document.body.appendChild(capa);
}
"""


class Sesion:
    def __init__(self, navegador, rol: str | None, vista: dict):
        self.ctx = navegador.new_context(viewport=vista, device_scale_factor=2, locale="es-CO",
                                         timezone_id="America/Bogota")  # la zona de la organización demo
        self.pg = self.ctx.new_page()
        if rol:
            redis.Redis(host="redis").delete(*(redis.Redis(host="redis").scan_iter("ratelimit:*")) or ["_"])
            self.pg.goto(B + "/login")
            self.pg.fill("input[type=email]", USUARIOS[rol])
            self.pg.fill(".password-field input", CLAVE)
            self.pg.click("button[type=submit]")
            self.pg.wait_for_url(lambda u: "/login" not in u, timeout=30000)
            self.pg.wait_for_timeout(1500)

    def ir(self, ruta: str, espera: int = 2500):
        self.pg.goto(B + ruta)
        self.pg.wait_for_timeout(espera)

    def cerrar(self):
        self.ctx.close()


def anotar_y_guardar(pg, clave: str, puntos: list, ancla=None):
    """puntos: [(locator, texto de la leyenda, lado)]. Guarda la imagen y devuelve la leyenda."""
    if ancla is not None:
        ancla.first.evaluate("e => e.scrollIntoView({block: 'start'})")
        pg.evaluate("window.scrollBy(0, -90)")
        pg.wait_for_timeout(400)
    pg.evaluate("document.querySelectorAll('.table-wrap').forEach(e => e.scrollLeft = 0)")
    items, leyenda = [], []
    for n, (loc, texto, lado) in enumerate(puntos, start=1):
        try:
            caja = loc.first.bounding_box(timeout=4000)
        except Exception:
            caja = None
        if not caja:
            print(f"  ! {clave} #{n} no encontrado: {texto[:50]}")
            continue
        items.append({"n": len(items) + 1, "x": caja["x"], "y": caja["y"], "w": caja["width"], "h": caja["height"], "side": lado})
        leyenda.append(texto)
    pg.evaluate(ANOTAR_JS, items)
    pg.wait_for_timeout(200)
    # Se recorta un poco después de la última marca: sin espacio vacío abajo.
    vista = pg.viewport_size
    fondo = max((i["y"] + i["h"] for i in items), default=vista["height"])
    alto_util = int(min(vista["height"], max(fondo + 160, 480)))
    pg.screenshot(path=str(IMG / f"{clave}.png"), clip={"x": 0, "y": 0, "width": vista["width"], "height": alto_util})
    pg.evaluate("document.getElementById('__anot')?.remove()")
    print(f"  ✓ {clave}: {len(items)} marcas")
    return leyenda
