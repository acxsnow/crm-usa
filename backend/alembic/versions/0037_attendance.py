"""Turnos, asistencia y mapa operativo (spec `2026-10-24-turnos-mapa-design.md`).

Crea la malla (`work_shifts`), las marcaciones y sus pausas, la bitácora de
eventos con ubicación, las novedades con su catálogo de motivos, la auditoría
de correcciones y los períodos de nómina. Agrega seis permisos, el módulo
«Turnos y asistencia» y la concesión inicial. Como en la 0027, solo inserta lo
que falta: no pisa una matriz de roles que un administrador ya editó.

La concesión va escrita aquí y no leída de `DEFAULT_ROLE_PERMISSIONS`, para que
la migración haga lo mismo aunque la matriz cambie después.

Revision ID: 0037
Revises: 0036
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID
MODULE_KEY = "attendance"
MODULE_LABEL = "Turnos y asistencia"

NEW_PERMISSIONS: dict[str, str] = {
    "attendance.clock": "Marcar el turno propio, pausas, desplazamientos y novedades",
    "shifts.manage": "Administrar la malla de turnos",
    "attendance.review": "Aprobar horas, novedades y correcciones de asistencia",
    "attendance.dashboard": "Ver el panel de asistencia y el reporte de nómina",
    "payroll.close": "Cerrar y reabrir períodos de nómina",
    "locations.view": "Ver la ubicación del personal y el mapa operativo",
}
MODULE_PERMISSIONS = list(NEW_PERMISSIONS)

GRANTS: dict[str, list[str]] = {
    "organization_admin": MODULE_PERMISSIONS,
    "salesperson": ["attendance.clock"],
    "admin_staff": ["attendance.clock", "shifts.manage", "attendance.review", "attendance.dashboard",
                    "locations.view"],
    "field_technician": ["attendance.clock"],
    "accounting": ["attendance.clock", "attendance.dashboard", "payroll.close"],
    "management": ["attendance.clock", "attendance.dashboard", "locations.view"],
}


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def _user(name: str, nullable: bool = True):
    return sa.Column(name, GUID(), sa.ForeignKey("users.id"), nullable=nullable)


def _grant(conn) -> None:
    for code, description in NEW_PERMISSIONS.items():
        conn.execute(sa.text(
            "INSERT INTO permissions (id, code, description)"
            " SELECT gen_random_uuid(), :code, :description"
            " WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ).bindparams(code=code, description=description))
    for role_code, codes in GRANTS.items():
        for code in codes:
            conn.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id)"
                " SELECT r.id, p.id FROM roles r, permissions p"
                " WHERE r.code = :role AND p.code = :perm"
                "   AND NOT EXISTS (SELECT 1 FROM role_permissions rp"
                "                   WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(role=role_code, perm=code))


def _create_module(conn) -> None:
    """El módulo como plantilla del sistema y como copia de cada organización
    (mismo patrón que la 0027, decisión D9)."""
    from app.shared.permissions import DEFAULT_MODULES

    orden = list(DEFAULT_MODULES).index(MODULE_KEY)
    permission_ids = {row[0]: row[1] for row in conn.execute(sa.text("SELECT code, id FROM permissions"))}
    organizaciones: list = [None] + [row[0] for row in conn.execute(sa.text("SELECT id FROM organizations"))]
    for organization_id in organizaciones:
        if organization_id is None:
            existente = conn.execute(sa.text(
                "SELECT id FROM permission_modules WHERE key = :key AND organization_id IS NULL"
            ).bindparams(key=MODULE_KEY)).scalar()
        else:
            existente = conn.execute(sa.text(
                "SELECT id FROM permission_modules WHERE key = :key AND organization_id = :org"
            ).bindparams(key=MODULE_KEY, org=organization_id)).scalar()
        if existente is None:
            existente = uuid.uuid4()
            conn.execute(sa.text(
                "INSERT INTO permission_modules"
                " (id, organization_id, key, label, sort_order, is_system, created_at, updated_at)"
                " VALUES (:id, :org, :key, :label, :sort, true, now(), now())"
            ).bindparams(id=existente, org=organization_id, key=MODULE_KEY, label=MODULE_LABEL, sort=orden))
        for posicion, code in enumerate(MODULE_PERMISSIONS):
            permission_id = permission_ids.get(code)
            if permission_id is None:
                continue
            conn.execute(sa.text(
                "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order)"
                " SELECT gen_random_uuid(), :module, :perm, :sort"
                " WHERE NOT EXISTS (SELECT 1 FROM permission_module_items"
                "                   WHERE module_id = :module AND permission_id = :perm)"
            ).bindparams(module=existente, perm=permission_id, sort=posicion))


def upgrade() -> None:
    op.create_table(
        "attendance_settings", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("late_tolerance_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("early_leave_tolerance_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("daily_overtime_after_minutes", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("weekly_overtime_after_minutes", sa.Integer(), nullable=False, server_default="2400"),
        sa.Column("tracking_interval_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("location_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("require_clock_in_for_field_work", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paid_pauses", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", name="uq_attendance_settings_org"),
    )
    op.create_table(
        "work_shifts", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("notes", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        _user("created_by_user_id"),
    )
    op.create_index("ix_work_shifts_org_date", "work_shifts", ["organization_id", "shift_date"])
    op.create_table(
        "time_entries", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("shift_id", GUID(), sa.ForeignKey("work_shifts.id"), index=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("clock_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_in_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_in_device_at", sa.DateTime(timezone=True)),
        sa.Column("clock_in_offline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("clock_out_at", sa.DateTime(timezone=True)),
        sa.Column("clock_out_received_at", sa.DateTime(timezone=True)),
        sa.Column("clock_out_device_at", sa.DateTime(timezone=True)),
        sa.Column("clock_out_offline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closed_by", sa.String(20)),
        sa.Column("notes", sa.Text()),
        sa.Column("approved_minutes", sa.Integer()),
        _user("approved_by_user_id"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_time_entries_one_open", "time_entries", ["organization_id", "user_id"], unique=True,
                    postgresql_where=sa.text("status = 'open'"))
    op.create_index("ix_time_entries_org_date", "time_entries", ["organization_id", "work_date"])
    op.create_table(
        "time_entry_pauses", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("time_entry_id", GUID(), sa.ForeignKey("time_entries.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(120)),
    )
    op.create_table(
        "attendance_events", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("time_entry_id", GUID(), sa.ForeignKey("time_entries.id", ondelete="SET NULL"), index=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), index=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("client_event_id", sa.String(64)),
        sa.Column("device_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()), sa.Column("accuracy_m", sa.Float()),
        sa.Column("location_status", sa.String(20), nullable=False, server_default="not_requested"),
        sa.Column("distance_km", sa.Float()), sa.Column("distance_source", sa.String(20)),
        sa.Column("note", sa.String(255)), sa.Column("result", sa.JSON()),
        sa.UniqueConstraint("organization_id", "user_id", "client_event_id", name="uq_attendance_event_client"),
    )
    op.create_index("ix_attendance_events_org_user_time", "attendance_events",
                    ["organization_id", "user_id", "received_at"])
    op.create_table(
        "novelty_reasons", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("organization_id", "code", name="uq_novelty_reason_code"),
    )
    op.create_table(
        "attendance_novelties", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("time_entry_id", GUID(), sa.ForeignKey("time_entries.id"), index=True),
        sa.Column("shift_id", GUID(), sa.ForeignKey("work_shifts.id"), index=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("reason_id", GUID(), sa.ForeignKey("novelty_reasons.id")),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("requested_clock_in_at", sa.DateTime(timezone=True)),
        sa.Column("requested_clock_out_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        _user("created_by_user_id"), _user("reviewed_by_user_id"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
    )
    op.create_table(
        "time_entry_corrections", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("time_entry_id", GUID(), sa.ForeignKey("time_entries.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("novelty_id", GUID(), sa.ForeignKey("attendance_novelties.id")),
        _user("corrected_by_user_id", nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=False),
        sa.Column("after_data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "payroll_periods", sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        _user("closed_by_user_id"), sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "start_date", "end_date", name="uq_payroll_period"),
    )
    op.create_table(
        "payroll_period_events", sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("period_id", GUID(), sa.ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("action", sa.String(20), nullable=False),
        _user("user_id", nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text()),
    )

    conn = op.get_bind()
    _grant(conn)
    _create_module(conn)


def downgrade() -> None:
    """Borra las tablas del módulo, y con ellas las marcaciones y ubicaciones.
    Antes de bajar en producción, exporta el reporte de nómina."""
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM permission_module_items WHERE module_id IN"
        " (SELECT id FROM permission_modules WHERE key = :key)").bindparams(key=MODULE_KEY))
    conn.execute(sa.text("DELETE FROM permission_modules WHERE key = :key").bindparams(key=MODULE_KEY))
    for code in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN"
                             " (SELECT id FROM permissions WHERE code = :code)").bindparams(code=code))
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    for tabla in ("payroll_period_events", "payroll_periods", "time_entry_corrections", "attendance_novelties",
                  "novelty_reasons", "attendance_events", "time_entry_pauses"):
        op.drop_table(tabla)
    op.drop_index("ix_time_entries_org_date", table_name="time_entries")
    op.drop_index("uq_time_entries_one_open", table_name="time_entries")
    op.drop_table("time_entries")
    op.drop_index("ix_work_shifts_org_date", table_name="work_shifts")
    op.drop_table("work_shifts")
    op.drop_table("attendance_settings")
