"""Recalcula «Resumen por módulo» y «Avance» del índice a partir de la tabla de
escenarios (estado y defectos de cada fila). Uso: python resumen.py <carpeta QA>"""
import re
import sys
from collections import OrderedDict
from pathlib import Path

ind = Path(sys.argv[1]) / "00_INDICE_GENERAL.md"
s = ind.read_text(encoding="utf-8")
filas = [[c.strip() for c in l.strip().strip("|").split("|")]
         for l in s.splitlines() if re.match(r"^\| [A-Z]{3,4}-\d{3} \|", l)]
mods = OrderedDict()
for f in filas:
    mods.setdefault(f[1], []).append(f)


def n(fs, cond):
    return sum(1 for f in fs if cond(f))


def defectos(fs):
    return len({d.strip() for f in fs for d in f[9].split(",") if d.strip()})


for mod, fs in mods.items():
    patron = re.compile(rf"^\| {re.escape(mod)} \| (.*)$", re.M)
    m = patron.search(s)
    c = [x.strip() for x in m.group(0).strip("|").split("|")]
    c[3] = str(n(fs, lambda f: f[6].upper().startswith("BLOQUEADO")))
    c[6] = str(n(fs, lambda f: f[6] == "APROBADO"))
    c[7] = str(n(fs, lambda f: f[6] == "FALLIDO"))
    c[8] = str(defectos(fs))
    s = s[:m.start()] + "| " + " | ".join(c) + " |" + s[m.end():]
tot = re.compile(r"^\| \*\*Total\*\* \| (.*)$", re.M)
m = tot.search(s)
c = [x.strip() for x in m.group(0).strip("|").split("|")]
c[3] = f"**{n(filas, lambda f: f[6].upper().startswith('BLOQUEADO'))}**"
c[6] = f"**{n(filas, lambda f: f[6] == 'APROBADO')}**"
c[7] = f"**{n(filas, lambda f: f[6] == 'FALLIDO')}**"
c[8] = f"**{defectos(filas)}**"
s = s[:m.start()] + "| " + " | ".join(c) + " |" + s[m.end():]
ejec = n(filas, lambda f: f[6] in ("APROBADO", "FALLIDO"))
curso = n(filas, lambda f: f[6] == "En ejecución")
avance = (f"## Avance\n\n- Ejecutados completos: {ejec} de {len(filas)} ({ejec * 100 // len(filas)} %). "
          f"En ejecución (parte hecha): {curso}.\n"
          f"- Aprobados: {n(filas, lambda f: f[6] == 'APROBADO')} · Fallidos: {n(filas, lambda f: f[6] == 'FALLIDO')} · "
          f"Bloqueados: {n(filas, lambda f: f[6].upper().startswith('BLOQUEADO'))} (faltan las llaves de prueba de Stripe/Plaid).\n"
          f"- Defectos: ver `01_REGISTRO_DEFECTOS.md`.\n")
s = re.sub(r"## Avance\n\n(?:- .*\n)+", avance, s, count=1)
ind.write_text(s, encoding="utf-8")
print(avance)
