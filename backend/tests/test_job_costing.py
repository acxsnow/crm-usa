"""Costo del trabajo: estimado contra real (spec 2026-10-22, fases 1 y 2).

Lo que se protege aquí es lo que Aldo hoy mira en Housecall Pro al cerrar un
trabajo: **cuánto esperaba ganar, cuánto ganó y en qué se fue la diferencia**,
sin volver a capturar lo que el sistema ya sabe. Las cifras son las reales que
dio el cliente para el pedestal de rebate (4.200 USD).
"""
import pytest

from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


# ---------------------------------------------------------------------------
# Conceptos del tablero
# ---------------------------------------------------------------------------

async def test_las_categorias_nuevas_y_los_conceptos_cubren_todo():
    from app.modules.warehouse.catalogs import BUDGET_CATEGORIES, CONCEPT_OF_CATEGORY, JOB_CONCEPTS
    from app.modules.warehouse.costing import ACTUAL_LABELS

    assert BUDGET_CATEGORIES["sales_rep"] == "Representante"
    assert BUDGET_CATEGORIES["consumables"] == "Consumibles"
    assert list(JOB_CONCEPTS) == ["sales_rep", "permits", "materials", "labor", "other"]
    # Toda categoría que puede tener costo real cae en un concepto del tablero.
    assert set(ACTUAL_LABELS) <= set(CONCEPT_OF_CATEGORY)
    assert set(CONCEPT_OF_CATEGORY.values()) <= set(JOB_CONCEPTS)
