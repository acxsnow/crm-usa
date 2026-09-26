"""El mapa de etapas del expediente.

`ALLOWED_TRANSITIONS` contiene **todas** las transiciones desde el día uno,
incluidas las de la Cadena B: así Mateo no tiene que editar este archivo para
que sus etapas funcionen, y el mapa completo del flujo está a la vista.

Estos tests son de lógica pura, sin base de datos: si el mapa se rompe, fallan
en un segundo y no hay que levantar nada."""
import pytest

from app.modules.cases import stages


def test_the_fifteen_stages_of_the_pdf_flow_exist():
    assert stages.STAGES == (
        "no_contact",
        "not_interested",
        "not_eligible",
        "new_prospect",
        "pending_approval",
        "approved",
        "rejected",
        "on_hold",
        "permit_in_progress",
        "ready_to_install",
        "installed",
        "inspection_pending",
        "billing_in_progress",
        "paid",
        "closed",
    )


def test_every_stage_has_a_label_in_spanish():
    for code in stages.STAGES:
        assert stages.STAGE_LABELS[code], f"la etapa {code} no tiene etiqueta"


def test_the_transition_map_only_mentions_real_stages():
    for origin, destinations in stages.ALLOWED_TRANSITIONS.items():
        assert origin in stages.STAGES, f"origen desconocido: {origin}"
        for destination in destinations:
            assert destination in stages.STAGES, f"destino desconocido: {destination}"


def test_a_case_can_be_born_in_any_of_the_four_first_stages():
    """La puerta puede terminar en el primer toque: no abrió, no le interesa o
    no califica. Solo si abre y le interesa sigue a `new_prospect`."""
    assert stages.INITIAL_STAGES == {
        "no_contact",
        "not_interested",
        "not_eligible",
        "new_prospect",
    }


def test_early_closures_can_be_reopened():
    """Volver al parque y encontrar a alguien es lo normal, así que las tres
    salidas tempranas reabren a `new_prospect`."""
    for code in ("no_contact", "not_interested", "not_eligible"):
        assert "new_prospect" in stages.ALLOWED_TRANSITIONS[code]


def test_knocking_again_without_an_answer_stays_in_no_contact():
    assert "no_contact" in stages.ALLOWED_TRANSITIONS["no_contact"]


def test_the_salesperson_path_up_to_review():
    assert "pending_approval" in stages.ALLOWED_TRANSITIONS["new_prospect"]
    assert "not_interested" in stages.ALLOWED_TRANSITIONS["new_prospect"]
    assert "not_eligible" in stages.ALLOWED_TRANSITIONS["new_prospect"]


def test_a_returned_case_does_not_go_back_a_stage():
    """La devolución NO cambia la etapa: el vendedor corrige dentro de
    `pending_approval` y el sub-estado vuelve a `pending_review`. Si retrocediera
    a `new_prospect`, el contador de días de aprobación se reiniciaría y el
    reporte de tiempos del PDF §7 mentiría."""
    assert "new_prospect" not in stages.ALLOWED_TRANSITIONS["pending_approval"]
    assert "returned" in stages.SUBSTATUSES["pending_approval"]


def test_the_admin_path():
    assert stages.ALLOWED_TRANSITIONS["pending_approval"] >= {"approved", "rejected", "on_hold"}
    assert stages.ALLOWED_TRANSITIONS["on_hold"] >= {"approved", "rejected"}
    assert "pending_approval" in stages.ALLOWED_TRANSITIONS["rejected"]


def test_the_field_path():
    assert "permit_in_progress" in stages.ALLOWED_TRANSITIONS["approved"]
    assert "ready_to_install" in stages.ALLOWED_TRANSITIONS["permit_in_progress"]
    assert "installed" in stages.ALLOWED_TRANSITIONS["ready_to_install"]
    assert "inspection_pending" in stages.ALLOWED_TRANSITIONS["installed"]


def test_a_failed_inspection_goes_back_to_install():
    """Provisional: el cliente todavía no dice qué pasa cuando la inspección
    falla. Ver `docs/contratos/case.md`, pendientes."""
    assert "ready_to_install" in stages.ALLOWED_TRANSITIONS["inspection_pending"]


def test_the_billing_path():
    assert "billing_in_progress" in stages.ALLOWED_TRANSITIONS["inspection_pending"]
    assert "paid" in stages.ALLOWED_TRANSITIONS["billing_in_progress"]
    assert "closed" in stages.ALLOWED_TRANSITIONS["paid"]


def test_any_stage_can_be_closed_administratively():
    """Cualquier etapa cierra con motivo; el permiso `cases.close_admin` lo
    restringe, no el mapa."""
    for code in stages.STAGES:
        if code == "closed":
            continue
        assert "closed" in stages.ALLOWED_TRANSITIONS[code], f"{code} no puede cerrarse"


def test_a_closed_case_is_the_end_of_the_line():
    assert stages.ALLOWED_TRANSITIONS["closed"] == set()


def test_milestone_dates_belong_to_specific_stages():
    """Cada fecha hito la escribe la entrada a UNA etapa. Si dos etapas
    escribieran la misma, el dato dependería del orden y nadie sabría cuál ganó."""
    assert stages.STAGE_MILESTONE["pending_approval"] == "submitted_at"
    assert stages.STAGE_MILESTONE["approved"] == "approved_at"
    assert stages.STAGE_MILESTONE["installed"] == "completed_at"
    assert stages.STAGE_MILESTONE["closed"] == "closed_at"
    assert len(set(stages.STAGE_MILESTONE.values())) == len(stages.STAGE_MILESTONE)


def test_substatuses_only_hang_from_real_stages():
    for code in stages.SUBSTATUSES:
        assert code in stages.STAGES


def test_is_allowed_answers_the_map():
    assert stages.is_allowed("new_prospect", "pending_approval") is True
    assert stages.is_allowed("new_prospect", "paid") is False
    assert stages.is_allowed("closed", "new_prospect") is False


def test_an_unknown_stage_is_rejected_instead_of_silently_false():
    """Devolver `False` ante una etapa inventada escondería el error de
    escritura: parecería una transición prohibida y no un código inexistente."""
    with pytest.raises(KeyError):
        stages.is_allowed("etapa_inventada", "closed")
