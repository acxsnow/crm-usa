import threading, httpx, redis
from app.core.config import get_settings
R = redis.Redis.from_url(get_settings().REDIS_URL)
B = "http://localhost:8000/api/v1"
def h(c):
    [R.delete(k) for k in R.scan_iter("ratelimit:*")]
    return {"Authorization": "Bearer " + httpx.post(B + "/auth/login", json={"email": c, "password": "ChangeMe123!"}).json()["access_token"]}
adm, admin = h("administracion@demo-org.com"), h("admin@demo-org.com")
item = httpx.get(B + "/warehouse/items", params={"q": "3496"}, headers=adm).json()[0]
dobles = []
for i in range(10):
    o = httpx.post(B + "/warehouse/releases", json={"lines": [{"item_id": item["id"], "quantity": "1"}]}, headers=adm).json()
    httpx.post(B + f"/warehouse/releases/{o['id']}/submit", headers=adm)
    res = [None, None]
    def ap(j): res[j] = httpx.post(B + f"/warehouse/releases/{o['id']}/approve", headers=admin, timeout=60).status_code
    t = [threading.Thread(target=ap, args=(j,)) for j in range(2)]; [x.start() for x in t]; [x.join() for x in t]
    dobles.append(res)
    httpx.post(B + f"/warehouse/releases/{o['id']}/reject", json={"reason": "QA carrera CON-001"}, headers=adm)
print(dobles, "ambas 200:", sum(1 for d in dobles if d == [200, 200]))
