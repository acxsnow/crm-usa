"""Escribe en los escenarios lo probado en pantalla por Claude (Playwright).

Uso: python registrar_pantalla.py <carpeta QA> <resultados.json> <decisiones.json>

A cada escenario le agrega la sección «Pantalla (probado por Claude)» con las
comprobaciones y las capturas, y en el índice pone el estado y, al principio de
las observaciones, «Pantalla: probado por Claude (<fecha>)», para que José sepa
qué le queda por revisar a mano. Las claves que empiezan por «D-» son defectos:
solo van al registro de defectos.
"""
import json
import re
import sys
from pathlib import Path

QA = Path(sys.argv[1])
RES = json.load(open(sys.argv[2], encoding="utf-8"))
DEC = json.load(open(sys.argv[3], encoding="utf-8"))
FECHA = DEC["_fecha"]


def capturas(eid):
    carpeta = QA / "evidencias" / "pantalla" / eid
    return sorted(f"evidencias/pantalla/{eid}/{p.name}" for p in carpeta.glob("*.jpg")) if carpeta.exists() else []


ind = QA / "00_INDICE_GENERAL.md"
indice = ind.read_text(encoding="utf-8")
for eid, d in DEC.items():
    if eid.startswith("_") or eid.startswith("D-"):
        continue
    p = next((QA / "escenarios").glob(f"{eid}_*.md"))
    s = p.read_text(encoding="utf-8")
    checks = RES.get(eid, []) + d.get("extra", [])
    lineas = "\n".join(f"  - {'✔' if c['ok'] else '✘'} {c['check']}" + (f" — `{c['dato'][:140]}`" if c.get("dato") else "")
                       for c in checks)
    fotos = "\n".join(f"  - [{Path(f).name}](../{f})" for f in capturas(eid)) or "  - (sin capturas)"
    bloque = (f"\n\n### Pantalla (probado por Claude, {FECHA}, Playwright)\n\n"
              f"- {d['que_paso']}\n- Comprobaciones ({sum(c['ok'] for c in checks)} de {len(checks)}):\n{lineas}\n"
              f"- Capturas:\n{fotos}\n- Pendiente: revisión de José en su propio equipo.\n")
    marca = "\n## 8. Evidencias"
    s = s.replace(marca, bloque + marca, 1) if marca in s else s + bloque
    s = re.sub(r"- \*\*Estado:\*\* .*", f"- **Estado:** {d['estado']}", s, count=1)
    if d["estado"] == "APROBADO":
        s = s.replace("- [ ] APROBADO", "- [x] APROBADO", 1).replace("- [x] FALLIDO", "- [ ] FALLIDO", 1)
    p.write_text(s, encoding="utf-8")
    m = re.search(rf"^\| {eid} \|.*$", indice, re.M)
    celdas = [x.strip() for x in m.group(0).strip("|").split("|")]
    celdas[6] = d["estado"]
    previo = re.sub(r"^Pantalla: probado por Claude \([^)]*\); ?", "", celdas[11])
    celdas[11] = f"Pantalla: probado por Claude ({FECHA}); {d.get('indice', previo)}".strip("; ")
    indice = indice[:m.start()] + "| " + " | ".join(celdas) + " |" + indice[m.end():]
ind.write_text(indice, encoding="utf-8")

reg = QA / "01_REGISTRO_DEFECTOS.md"
s = reg.read_text(encoding="utf-8")
for did, d in DEC.items():
    if not did.startswith("D-"):
        continue
    i = s.index(f"| {did} |")
    j = s.index("\n", i)
    s = s[:i] + re.sub(r"\| (Corregido[^|]*) \|", f"| {d['estado']} |", s[i:j], count=1) + s[j:]
    k = s.index(f"\n## {did} ")
    m2 = s.find("\n## ", k + 5)
    sec = s[k:m2].rstrip("\n") + f"\n- **Validación en pantalla ({FECHA}, Claude con Playwright):** {d['que_paso']} " \
                                  f"Capturas en `evidencias/pantalla/{did}/`.\n\n"
    s = s[:k] + sec + s[m2 + 1:]
reg.write_text(s, encoding="utf-8")
print("ok", len([k for k in DEC if not k.startswith("_")]))
