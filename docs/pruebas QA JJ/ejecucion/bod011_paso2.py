"""BOD-011, paso 2: en otra salida, entregar un serial que ya salió (D-007).
Corre dentro del contenedor api después del lote 2: PYTHONPATH=/app python /tmp/bod011_paso2.py"""
import json

import httpx
import redis

from app.core.config import get_settings

R = redis.Redis.from_url(get_settings().REDIS_URL)
B = "http://localhost:8000/api/v1"


def h(correo):
    [R.delete(k) for k in R.scan_iter("ratelimit:*")]
    r = httpx.post(B + "/auth/login", json={"email": correo, "password": "ChangeMe123!"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


adm, admin = h("administracion@demo-org.com"), h("admin@demo-org.com")
salidos = httpx.get(B + "/warehouse/serials", params={"status": "delivered"}, headers=adm).json()
equipo = next(s for s in salidos if s["sku"] == "85980")
checks = []
r = httpx.post(B + "/warehouse/movements", json={"item_id": equipo["item_id"], "movement_type": "entrada",
                                                 "quantity": "1", "reference": "QA BOD-011"}, headers=adm)
checks.append({"check": "Entrada de 1 unidad más del 85980 (sin serial: se anota al entregar)",
               "ok": r.status_code == 201, "dato": str(r.status_code)})
o = httpx.post(B + "/warehouse/releases", json={"lines": [{"item_id": equipo["item_id"], "quantity": "1"}]},
               headers=adm).json()
httpx.post(B + f"/warehouse/releases/{o['id']}/submit", headers=adm)
o = httpx.post(B + f"/warehouse/releases/{o['id']}/approve", headers=admin).json()
linea = o["lines"][0]["id"]
r = httpx.post(B + f"/warehouse/releases/{o['id']}/deliver", headers=adm,
               json={"lines": [{"line_id": linea, "quantity": "1", "serials": [equipo["serial"]]}]})
checks.append({"check": f"Entregar en otra salida el serial {equipo['serial']} que ya salió → 409 serial_not_in_stock",
               "ok": r.status_code == 409 and r.json().get("code") == "serial_not_in_stock",
               "dato": f"{r.status_code} {r.json().get('detail')}"})
r = httpx.post(B + f"/warehouse/releases/{o['id']}/deliver", headers=adm,
               json={"lines": [{"line_id": linea, "quantity": "1", "serials": ["  "]}]})
checks.append({"check": "Con el serial vacío → 400 serial_empty",
               "ok": r.status_code == 400 and r.json().get("code") == "serial_empty",
               "dato": f"{r.status_code} {r.json().get('detail')}"})
r = httpx.post(B + f"/warehouse/releases/{o['id']}/deliver", headers=adm,
               json={"lines": [{"line_id": linea, "quantity": "1", "serials": ["QA-BOD011-NUEVO"]}]})
checks.append({"check": "Con un serial nuevo sí sale y queda registrado",
               "ok": r.status_code == 200 and r.json()["lines"][0]["serials"] == ["QA-BOD011-NUEVO"],
               "dato": str(r.status_code)})
print(json.dumps(checks, ensure_ascii=False))
