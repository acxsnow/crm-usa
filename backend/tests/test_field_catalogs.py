"""Catálogos de campo y la lógica pura de los modelos del módulo 5.

Sin base de datos: qué cuenta como obligatorio en el checklist, cuándo un ítem
está resuelto y cuándo un permiso deja avanzar.
"""
from datetime import date, timedelta

from app.modules.field_ops.catalogs import (
    EVIDENCE_CATEGORIES,
    PermitStatus,
    default_evidence_category,
)
from app.modules.field_ops.models import Permit, ProjectChecklistItem


def test_the_fifteen_evidence_categories_of_the_requirements_exist():
    assert len(EVIDENCE_CATEGORIES) == 15
    assert EVIDENCE_CATEGORIES["outdoor_label"] == "Etiqueta exterior"
    assert all(label for label in EVIDENCE_CATEGORIES.values())


def test_an_upload_without_category_gets_the_generic_one_for_its_type():
    assert default_evidence_category("video/mp4") == "additional_video"
    assert default_evidence_category("image/jpeg") == "additional_photo"
    assert default_evidence_category(None) == "additional_photo"


def _item(**kw):
    base = dict(label="Foto de la etiqueta", is_required=True, is_complete=False, not_applicable=False)
    base.update(kw)
    return ProjectChecklistItem(**base)


def test_a_required_item_without_condition_always_counts():
    assert _item().counts_as_required([]) is True


def test_a_conditional_item_counts_only_when_its_condition_applies():
    item = _item(condition_code="gas_equipment_removed")
    assert item.counts_as_required([]) is False
    assert item.counts_as_required(["gas_equipment_removed"]) is True


def test_an_optional_item_never_counts():
    assert _item(is_required=False).counts_as_required(["gas_equipment_removed"]) is False


def test_an_item_is_resolved_when_complete_or_not_applicable():
    assert _item(is_complete=True).is_resolved is True
    assert _item(not_applicable=True, not_applicable_reason="No hay furnace").is_resolved is True
    assert _item().is_resolved is False


def _permit(status, expires_on=None):
    return Permit(status=status, jurisdiction="Phoenix", expires_on=expires_on)


def test_an_approved_permit_in_force_is_cleared():
    assert _permit(PermitStatus.approved, date.today() + timedelta(days=30)).is_cleared is True
    assert _permit(PermitStatus.approved, None).is_cleared is True


def test_an_expired_permit_is_not_cleared():
    vencido = _permit(PermitStatus.approved, date.today() - timedelta(days=1))
    assert vencido.is_expired is True
    assert vencido.is_cleared is False


def test_a_permit_not_required_is_cleared_and_a_submitted_one_is_not():
    assert _permit(PermitStatus.not_required).is_cleared is True
    assert _permit(PermitStatus.submitted).is_cleared is False
    assert _permit(PermitStatus.rejected).is_cleared is False
