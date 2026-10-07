"""Falla si un componente llama un hook (`useX(...)`) después de un `return`
temprano. React exige el mismo número de hooks en cada render; si no, la
pantalla revienta con «Rendered more hooks than during the previous render»
(pasó en el detalle del cliente, 7 oct 2026). Suple la regla `rules-of-hooks`
de ESLint, que no está instalado en el proyecto.

Uso: python3 frontend/scripts/check_hooks.py   (lo corre la integración continua)
"""
import pathlib
import re
import sys

raiz = pathlib.Path(__file__).resolve().parents[1] / "src"
malos = []
for f in raiz.rglob("*.tsx"):
    lineas = f.read_text(encoding="utf-8").splitlines()
    comp = temprano = None
    for i, l in enumerate(lineas):
        m = re.match(r"^(export )?function ([A-Z]\w*)\(", l)
        if m:
            comp, temprano = m.group(2), None
            continue
        if comp is None:
            continue
        if l.startswith("}"):
            comp = None
            continue
        if re.match(r"^  if \(.*\) return\b", l) or (
                re.match(r"^  if \(.*\) \{$", l) and i + 1 < len(lineas) and re.match(r"^    return\b", lineas[i + 1])):
            temprano = temprano or i + 1
        if temprano and re.match(r"^  (const|let) .*\buse[A-Z]\w*\(", l):
            malos.append(f"{f.relative_to(raiz.parent)}:{i + 1} {comp}: hook después del return de la línea {temprano}")
if malos:
    print("\n".join(malos))
    sys.exit(1)
print("OK: ningún hook después de un return temprano")
