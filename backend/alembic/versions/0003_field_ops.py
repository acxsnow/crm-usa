"""Field operations: projects, checklists, tasks, evidence, attestation

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address_street", sa.String(255)),
        sa.Column("address_unit", sa.String(50)),
        sa.Column("address_city", sa.String(120)),
        sa.Column("address_state", sa.String(2)),
        sa.Column("address_zip", sa.String(10)),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("opportunities.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("project_type", sa.String(100)),
        sa.Column("status", sa.Enum("planning", "scheduled", "in_progress", "completed", "cancelled", name="project_status"), nullable=False, server_default="planning"),
        sa.Column("scheduled_date", sa.Date),
        sa.Column("completed_date", sa.Date),
        sa.Column("primary_technician_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_customer_id", "projects", ["customer_id"])
    op.create_index("ix_projects_opportunity_id", "projects", ["opportunity_id"])
    op.create_index("ix_projects_primary_technician_user_id", "projects", ["primary_technician_user_id"])

    op.create_table(
        "checklist_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("project_type", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_checklist_templates_organization_id", "checklist_templates", ["organization_id"])

    op.create_table(
        "checklist_template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("requires_evidence", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_checklist_template_items_template_id", "checklist_template_items", ["template_id"])

    op.create_table(
        "project_checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_template_item_id", postgresql.UUID(as_uuid=True)),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("requires_evidence", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_checklist_items_project_id", "project_checklist_items", ["project_id"])

    op.create_table(
        "field_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.Enum("pending", "in_progress", "done", name="task_status"), nullable=False, server_default="pending"),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_field_tasks_organization_id", "field_tasks", ["organization_id"])
    op.create_index("ix_field_tasks_project_id", "field_tasks", ["project_id"])
    op.create_index("ix_field_tasks_assigned_user_id", "field_tasks", ["assigned_user_id"])

    op.create_table(
        "task_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("field_tasks.id")),
        sa.Column("checklist_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_checklist_items.id")),
        sa.Column("category", sa.Enum("before", "during", "after", "damage", "other", name="evidence_category"), nullable=False, server_default="other"),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("watermarked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_evidence_organization_id", "evidence", ["organization_id"])
    op.create_index("ix_evidence_project_id", "evidence", ["project_id"])
    op.create_index("ix_evidence_task_id", "evidence", ["task_id"])

    op.create_table(
        "attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("technician_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("technician_signature_path", sa.String(500)),
        sa.Column("technician_signed_at", sa.DateTime(timezone=True)),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("customer_signature_path", sa.String(500)),
        sa.Column("customer_signed_at", sa.DateTime(timezone=True)),
        sa.Column("pdf_path", sa.String(500)),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_attestation_project"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_attestations_organization_id", "attestations", ["organization_id"])
    op.create_index("ix_attestations_project_id", "attestations", ["project_id"])


def downgrade() -> None:
    op.drop_table("attestations")
    op.drop_table("evidence")
    op.drop_table("task_comments")
    op.drop_table("field_tasks")
    op.drop_table("project_checklist_items")
    op.drop_table("checklist_template_items")
    op.drop_table("checklist_templates")
    op.drop_table("projects")
    for enum_name in ["evidence_category", "task_status", "project_status"]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
