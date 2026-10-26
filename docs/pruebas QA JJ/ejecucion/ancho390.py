"""Qué se sale de los 390 px en una pantalla. Uso: python ancho390.py <rol> <ruta> [ruta…]"""
import sys

from playwright.sync_api import sync_playwright

from ui_comun import CELULAR, Sesion

JS = """() => [...document.querySelectorAll('body *')]
  .filter(e => e.getBoundingClientRect().right > 392)
  .map(e => `${e.tagName}.${String(e.className || '').slice(0, 40)} w=${Math.round(e.getBoundingClientRect().width)}`
       + ` l=${Math.round(e.getBoundingClientRect().left)} «${(e.innerText || '').slice(0, 30).replace(/\\s+/g, ' ')}»`)
  .slice(0, 12)"""

with sync_playwright() as p:
    nav = p.chromium.launch()
    s = Sesion(nav, sys.argv[1], vista=CELULAR)
    for ruta in sys.argv[2:]:
        s.ir(ruta, 3000)
        print(ruta, s.pg.evaluate("document.documentElement.scrollWidth"))
        for x in s.pg.evaluate(JS):
            print("   ", x)
