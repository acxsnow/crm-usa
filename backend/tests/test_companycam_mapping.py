"""Mapeo puro de CompanyCam y la regla de reconocer clientes."""
from app.modules.imports.companycam import mapping as m
from tests.companycam_helpers import project


def test_estado_y_etapas():
    assert m.map_stage(project(1))[0] == "on_hold"
    assert m.map_stage(project(1, archived=True))[0] == "closed"
    etapa, motivo = m.map_stage(project(1, status="deleted"))
    assert etapa == "closed" and "eliminado" in motivo
    assert m.map_stage(project(1, status="deleted", archived=True))[0] == "closed"


def test_estado_a_codigo_de_dos_letras():
    assert m.state_code("Ca") == "CA" and m.state_code("California") == "CA" and m.state_code("nevada") == "NV"
    assert m.state_code("") is None and m.state_code("Atlantis") is None


def test_direccion_recorta_y_ignora_coordenadas_cero():
    p = project(1, unit="U" * 80)
    p["address"]["postal_code"] = "9" * 15
    p["coordinates"] = {"lat": 0.0, "lon": 0.0}
    a = m.map_address(p)
    assert len(a["address_unit"]) == 50 and len(a["address_zip"]) == 10 and a["address_state"] == "CA"
    assert a["latitude"] is None and a["address_street"] == "7722 Cleon Ave"


def test_nombre_del_cliente_con_alternativas():
    a = m.map_address(project(1))
    assert m.customer_name(project(1, contact={"id": "1", "name": "Ana"}), a) == "Ana"
    assert m.customer_name(project(1, name="Casa Verde"), a) == "Casa Verde"
    assert m.customer_name(project(1), a).startswith("7722 Cleon Ave")


def test_notas_y_checklists():
    p = project(1, name="Casa", notepad="Texto")
    assert m.notepad_body(p).startswith("Proyecto CompanyCam: Casa · creado por Carla Creadora")
    assert m.notepad_body(p).endswith("Texto")
    cuerpo = m.checklist_body({"name": "Lista", "tasks": [{"name": "A", "completed": True}, {"name": "B"}]})
    assert "[x] A" in cuerpo and "[ ] B" in cuerpo


def _cand(**k):
    base = dict(ref="contact:1", name="X", email=None, phone=None, address=None)
    return m.Candidate(**{**base, **k})


def test_match_por_contacto_previo():
    idx = m.MatchIndex()
    idx.add("c1", ref="contact:1")
    assert m.match_customer(_cand(), idx) == ("match", ["c1"])


def test_match_por_correo_telefono_y_direccion_con_unidad():
    idx = m.MatchIndex()
    idx.add("a", emails=["Ana@X.com "])
    idx.add("b", phones=["(818) 555-0101"])
    idx.add("c", address="1 main st spc 4 la 90001")
    assert m.match_customer(_cand(email="ana@x.com"), idx) == ("match", ["a"])
    assert m.match_customer(_cand(phone="8185550101"), idx) == ("match", ["b"])
    assert m.match_customer(_cand(address="1 main st spc 4 la 90001"), idx) == ("match", ["c"])
    # sin unidad el candidato no trae dirección: no hay unión por dirección
    p = project(1, street="1 Main St", unit=None)
    assert m.candidate_from_project(p).address is None
    assert m.candidate_from_project(project(1, unit="Spc 4")).address is not None


def test_ambiguo_y_nuevo():
    idx = m.MatchIndex()
    idx.add("a", emails=["x@x.com"])
    idx.add("b", emails=["x@x.com"])
    assert m.match_customer(_cand(email="x@x.com"), idx) == ("ambiguous", ["a", "b"])
    assert m.match_customer(_cand(email="otro@x.com"), idx) == ("new", [])


def test_valores_compartidos_se_ignoran():
    proyectos = [project(i, contact={"id": f"c{i}", "name": "N", "email": "inmo@x.com", "phone_number": "8180000000"})
                 for i in range(1, 6)]
    proyectos.append(project(9, contact={"id": "z", "name": "Z", "email": "solo@x.com"}))
    ign = m.shared_values(proyectos)
    assert "e:inmo@x.com" in ign and "t:8180000000" in ign and "e:solo@x.com" not in ign
    idx = m.MatchIndex(ignored=ign)
    idx.add("a", emails=["inmo@x.com"])
    assert m.match_customer(_cand(email="inmo@x.com"), idx) == ("new", [])


def test_unidad_pegada_a_la_calle_se_separa():
    assert m.split_unit("6545 Wilbur Ave Spc 104", None) == ("6545 Wilbur Ave", "Spc 104")
    assert m.split_unit("12 Park Rd #5", "") == ("12 Park Rd", "#5")
    assert m.split_unit("7722 Cleon Ave", None) == ("7722 Cleon Ave", None)
    assert m.split_unit("1 Main St", "Apt 2") == ("1 Main St", "Apt 2")  # lo explícito manda
    a = m.map_address(project(1, street="6545 Wilbur Ave Spc 104"))
    assert a["address_street"] == "6545 Wilbur Ave" and a["address_unit"] == "Spc 104"
    assert m.customer_name(project(1, contact={"id": "1", "name": "Walter A.  Rubio"}), a) == "Walter A. Rubio"
