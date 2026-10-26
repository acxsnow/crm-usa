"""Saca del log del api (modo consola) el último enlace de cada correo.

Uso, desde el equipo:
  docker compose logs api --since <inicio> | python enlaces.py > links.json
Con EMAIL_PROVIDER=smtp los enlaces no se escriben en el log (a propósito).
"""
import json
import re
import sys

CORREOS = {"gerencia@demo-org.com": "gerencia", "tecnico16@demo-org.com": "tecnico16", "sinrol@demo-org.com": "sinrol"}
enlaces = {"todos": []}
for linea in sys.stdin:
    if "email.send" not in linea:
        continue
    m = re.search(r"(\{.*\})\s*$", linea)
    if not m:
        continue
    try:
        evento = json.loads(m.group(1))
    except ValueError:
        continue
    clave = CORREOS.get(evento.get("to"))
    for url in (evento.get("dev_links") or {}).values():
        token = re.search(r"token=([^&\s\"]+)", url)
        if token:
            enlaces["todos"].append({"to": evento.get("to"), "template": evento.get("template"),
                                     "token": token.group(1)})
        if clave and token:
            enlaces[clave] = token.group(1)
print(json.dumps(enlaces))
