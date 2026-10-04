"""Motor del formulario (módulo 1, spec D1.4): sin base de datos."""
from app.modules.programs.engine import check_condition, condition_met, evaluate, validate_value

GAS = {"key": "home.gas_type", "label": "Tipo de gas", "type": "single_select", "requirement": "required",
       "options": [{"value": "natural_gas", "label": "Gas natural"}, {"value": "no_gas", "label": "No tienen gas"}]}
COMPANIA = {"key": "home.gas_company", "label": "Compañía de gas", "type": "text", "requirement": "conditional",
            "condition": {"field": "home.gas_type", "eq": "natural_gas"}}
PROGRAMAS = {"key": "eligibility.programs", "label": "Programas", "type": "multi_select", "requirement": "required",
             "options": [{"value": "snap", "label": "SNAP"}, {"value": "ssi", "label": "SSI"},
                         {"value": "none", "label": "Ninguno"}],
             "validation": {"exclusive": ["none"]}}
NOTAS = {"key": "internal.notes", "label": "Observaciones", "type": "textarea", "requirement": "optional",
         "internal": True}
TERMINOS = {"key": "authorization.terms_accepted", "label": "Acepto", "type": "terms_checkbox",
            "requirement": "required"}
DEF = {"steps": [{"code": "home", "title": "Vivienda", "fields": [GAS, COMPANIA]},
                 {"code": "eligibility", "title": "Elegibilidad", "fields": [PROGRAMAS, NOTAS, TERMINOS]}]}


def test_a_conditional_field_appears_only_when_its_condition_is_met():
    sin_gas = evaluate(DEF, {"home.gas_type": "no_gas"})
    assert [f["key"] for f in sin_gas["steps"][0]["fields"]] == ["home.gas_type"]
    con_gas = evaluate(DEF, {"home.gas_type": "natural_gas"})
    assert [f["key"] for f in con_gas["steps"][0]["fields"]] == ["home.gas_type", "home.gas_company"]
    assert {"step": "home", "key": "home.gas_company", "label": "Compañía de gas"} in con_gas["missing"]


def test_required_fields_block_submitting_and_say_what_is_missing():
    r = evaluate(DEF, {})
    assert r["can_submit"] is False
    assert [m["key"] for m in r["missing"]] == ["home.gas_type", "eligibility.programs", "authorization.terms_accepted"]
    completo = evaluate(DEF, {"home.gas_type": "no_gas", "eligibility.programs": ["snap"],
                              "authorization.terms_accepted": True})
    assert completo["can_submit"] is True and all(s["complete"] for s in completo["steps"])


def test_none_cannot_be_combined_with_other_programs():
    r = evaluate(DEF, {"eligibility.programs": ["none", "snap"]})
    assert r["errors"]["eligibility.programs"] == "«Ninguno» no se combina con otras opciones."
    assert r["can_submit"] is False


def test_internal_fields_are_hidden_from_the_customer_view():
    r = evaluate(DEF, {}, include_internal=False)
    assert "internal.notes" not in [f["key"] for s in r["steps"] for f in s["fields"]]


def test_formats_and_ranges():
    assert validate_value({"type": "email"}, "marge@") == "No es un correo válido."
    assert validate_value({"type": "phone"}, "602-555-0100") is None
    assert validate_value({"type": "text", "validation": {"format": "zip"}}, "8500") == "El ZIP debe tener 5 dígitos."
    assert validate_value({"type": "integer", "validation": {"min": 1}}, 0) == "Debe ser al menos 1."
    assert validate_value({"type": "integer"}, "2.5") == "Debe ser un número entero."
    assert validate_value(GAS, "propane") == "Elige una de las opciones."
    assert validate_value({"type": "date"}, "2026-13-01") == "No es una fecha válida."


def test_conditions_are_checked_for_shape():
    assert check_condition({"field": "a", "eq": "x"}) is None
    assert check_condition({"eq": "x"}) is not None
    assert check_condition({"field": "a", "eq": "x", "in": ["y"]}) is not None
    assert condition_met({"field": "p", "in": ["ssi"]}, {"p": ["snap", "ssi"]}) is True
    assert condition_met({"field": "p", "not_empty": True}, {"p": ""}) is False
