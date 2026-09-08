import json


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_csv_import_creates_leads_and_skips_duplicates(app_client, active_admin_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        "NOMBRE,DIRECCION,TELEFONO,EMAIL,BENEFICIO\n"
        "Rosa Gutierrez,106 S Colombo Ln Tustin CA 92780,7142320526,rosa@example.com,CARE\n"
        "Miguel Vargas,1500 Warren St Spc 101 Santa Ana CA 92705,7142776702,miguel@example.com,CALFRESH\n"
        "Rosa Gutierrez Duplicate,106 S Colombo Ln Tustin CA 92780,7142320526,other@example.com,CARE\n"
        ",Missing name row,7141112222,noname@example.com,CARE\n"
    )
    mapping = json.dumps({"full_name": "NOMBRE", "address_street": "DIRECCION", "phone": "TELEFONO", "email": "EMAIL", "benefit_type": "BENEFICIO"})

    resp = await app_client.post(
        "/api/v1/leads/import",
        files={"file": ("leads.csv", csv_content, "text/csv")},
        data={"column_mapping": mapping},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rows"] == 4
    assert body["created"] == 2
    assert body["skipped_duplicates"] == 2  # duplicate phone row + missing-name row

    list_resp = await app_client.get("/api/v1/leads", headers=headers)
    assert len(list_resp.json()) == 2
