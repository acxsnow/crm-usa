"""El catálogo es la fuente de verdad de permisos, módulos y matriz de roles.

Estos tests evitan errores que solo se descubrirían en producción: un permiso
que no quedó en ningún módulo (no aparecería en ningún menú), un módulo que
lista un permiso inexistente, un rol con un permiso que no existe
(silenciosamente no hace nada), o un endpoint protegido con un código que
nadie declaró (nadie podría usarlo nunca)."""
import re
from pathlib import Path

from app.shared.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    DEFAULT_MODULES,
    PERMISSION_CATALOG,
    ROLE_LABELS,
    STANDALONE_PERMISSIONS,
    modules_for_permissions,
)

PDF_ROLES = {
    "organization_admin",
    "salesperson",
    "admin_staff",
    "field_technician",
    "accounting",
    "management",
}


def test_roles_are_the_ones_from_the_pdf():
    assert set(DEFAULT_ROLE_PERMISSIONS) == PDF_ROLES
    assert set(ROLE_LABELS) == PDF_ROLES


def test_permission_codes_are_unique_and_described():
    codes = [code for code, _ in PERMISSION_CATALOG]
    assert len(codes) == len(set(codes))
    for code, description in PERMISSION_CATALOG:
        assert description, f"{code} sin descripción"


def test_every_module_has_a_label_and_only_lists_real_permissions():
    catalog = {code for code, _ in PERMISSION_CATALOG}
    for key, module in DEFAULT_MODULES.items():
        assert module.label, f"módulo {key} sin etiqueta"
        assert module.permissions, f"módulo {key} sin permisos"
        unknown = set(module.permissions) - catalog
        assert not unknown, f"módulo {key} lista permisos inexistentes: {unknown}"


def test_every_permission_belongs_to_a_module_or_is_explicitly_standalone():
    """Un permiso fuera de todo módulo no enciende ningún ítem del menú. Eso es
    válido (`profile.manage`), pero tiene que ser una decisión declarada."""
    grouped = {code for module in DEFAULT_MODULES.values() for code in module.permissions}
    catalog = {code for code, _ in PERMISSION_CATALOG}
    orphans = catalog - grouped - STANDALONE_PERMISSIONS
    assert not orphans, f"permisos sin módulo y sin declarar como sueltos: {orphans}"


def test_a_permission_can_belong_to_several_modules():
    """La relación permiso ↔ módulo es de muchos a muchos: el mismo permiso
    puede encender más de un ítem del menú."""
    assert modules_for_permissions(["dashboards.finance"]) == {"billing", "reports"}
    assert modules_for_permissions(["programs.read"]) == {"cases", "config"}


def test_role_matrix_only_uses_catalog_codes():
    catalog = {code for code, _ in PERMISSION_CATALOG}
    for role, codes in DEFAULT_ROLE_PERMISSIONS.items():
        unknown = set(codes) - catalog
        assert not unknown, f"{role} usa códigos que no existen: {unknown}"


def test_organization_admin_has_every_permission():
    catalog = {code for code, _ in PERMISSION_CATALOG}
    assert set(DEFAULT_ROLE_PERMISSIONS["organization_admin"]) == catalog


def test_every_permission_required_by_an_endpoint_exists_in_the_catalog():
    """Busca require_permission("x") y require_any_permission("x", "y") en app/."""
    catalog = {code for code, _ in PERMISSION_CATALOG}
    app_dir = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r"require_(?:any_)?permission\(([^)]*)\)")
    used: set[str] = set()
    for path in app_dir.rglob("*.py"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            used.update(re.findall(r'"([^"]+)"', match.group(1)))
    missing = used - catalog
    assert not missing, f"endpoints exigen permisos que no están en el catálogo: {missing}"


def test_modules_for_permissions_maps_codes_to_modules():
    assert modules_for_permissions(["users.manage"]) == {"team"}
    assert modules_for_permissions(["profile.manage"]) == set()
    assert modules_for_permissions([]) == set()


def test_technician_matrix_opens_the_expected_modules():
    """La matriz inicial del técnico debe abrirle campo y gastos, y nada de
    facturación ni administración de usuarios."""
    modules = modules_for_permissions(DEFAULT_ROLE_PERMISSIONS["field_technician"])
    assert {"projects", "dispatch", "expenses", "customers"} <= modules
    assert "billing" not in modules
    assert "team" not in modules
    assert "config" not in modules
