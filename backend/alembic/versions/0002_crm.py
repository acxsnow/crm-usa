"""CRM: customers, contacts, leads, pipeline stages, opportunities, activities, quotes

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("customer_type", sa.Enum("individual", "business", name="customer_type"), nullable=False, server_default="individual"),
        sa.Column("main_phone", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("website", sa.String(255)),
        sa.Column("billing_address", sa.String(500)),
        sa.Column("status", sa.Enum("active", "inactive", name="customer_status"), nullable=False, server_default="active"),
        sa.Column("tags", postgresql.JSON),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_customers_organization_id", "customers", ["organization_id"])

    op.create_table(
        "customer_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role_title", sa.String(150)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(32)),
        sa.Column("preferred_contact_method", sa.String(50)),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address_street", sa.String(255)),
        sa.Column("address_unit", sa.String(50)),
        sa.Column("address_city", sa.String(120)),
        sa.Column("address_state", sa.String(2)),
        sa.Column("address_zip", sa.String(10)),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255)),
        sa.Column("phone", sa.String(32)),
        sa.Column("phone_normalized", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("email_normalized", sa.String(255)),
        sa.Column("source", sa.String(100)),
        sa.Column("benefit_type", sa.String(100)),
        sa.Column("funder_program", sa.String(100)),
        sa.Column("interested_service", sa.String(255)),
        sa.Column("assigned_owner_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.Enum("new", "contacted", "qualified", "disqualified", "converted", name="lead_status"), nullable=False, server_default="new"),
        sa.Column("notes", sa.Text),
        sa.Column("converted_customer_id", postgresql.UUID(as_uuid=True)),
        sa.Column("converted_opportunity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_leads_organization_id", "leads", ["organization_id"])
    op.create_index("ix_leads_phone_normalized", "leads", ["phone_normalized"])
    op.create_index("ix_leads_email_normalized", "leads", ["email_normalized"])
    op.create_index("ix_leads_assigned_owner_user_id", "leads", ["assigned_owner_user_id"])

    op.create_table(
        "pipeline_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_won", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_lost", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", "code", name="uq_pipeline_stage_org_code"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pipeline_stages_organization_id", "pipeline_stages", ["organization_id"])

    op.create_table(
        "funder_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("organization_id", "code", name="uq_funder_status_org_code"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_funder_statuses_organization_id", "funder_statuses", ["organization_id"])

    op.create_table(
        "opportunities",
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
        sa.Column("primary_contact_id", postgresql.UUID(as_uuid=True)),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("estimated_amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("probability", sa.Integer),
        sa.Column("expected_close_date", sa.Date),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_stages.id"), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("loss_reason", sa.String(255)),
        sa.Column("benefit_type", sa.String(100)),
        sa.Column("funder_program", sa.String(100)),
        sa.Column("application_number", sa.String(100)),
        sa.Column("approval_code", sa.String(100)),
        sa.Column("funder_status_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("funder_statuses.id")),
        sa.Column("utility_account_number", sa.String(100)),
        sa.Column("meter_number", sa.String(100)),
        sa.Column("unit_type", sa.String(100)),
        sa.Column("scheduled_install_date", sa.Date),
        sa.Column("source_lead_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_opportunities_organization_id", "opportunities", ["organization_id"])
    op.create_index("ix_opportunities_customer_id", "opportunities", ["customer_id"])
    op.create_index("ix_opportunities_stage_id", "opportunities", ["stage_id"])
    op.create_index("ix_opportunities_owner_user_id", "opportunities", ["owner_user_id"])
    op.create_index("ix_opportunities_funder_status_id", "opportunities", ["funder_status_id"])

    op.create_table(
        "activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Enum("call", "email", "meeting", "note", "task", "follow_up", name="activity_type"), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("reminder_at", sa.DateTime(timezone=True)),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True)),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_activities_organization_id", "activities", ["organization_id"])
    op.create_index("ix_activities_owner_user_id", "activities", ["owner_user_id"])
    op.create_index("ix_activities_customer_id", "activities", ["customer_id"])
    op.create_index("ix_activities_opportunity_id", "activities", ["opportunity_id"])

    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_number", sa.String(50), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("project_description", sa.Text),
        sa.Column("issue_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.Enum("draft", "sent", "accepted", "rejected", "expired", name="quote_status"), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_quotes_organization_id", "quotes", ["organization_id"])
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"])
    op.create_index("ix_quotes_opportunity_id", "quotes", ["opportunity_id"])

    op.create_table(
        "quote_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_quote_line_items_quote_id", "quote_line_items", ["quote_id"])


def downgrade() -> None:
    op.drop_table("quote_line_items")
    op.drop_table("quotes")
    op.drop_table("activities")
    op.drop_table("opportunities")
    op.drop_table("funder_statuses")
    op.drop_table("pipeline_stages")
    op.drop_table("leads")
    op.drop_table("customer_contacts")
    op.drop_table("customers")
    for enum_name in ["quote_status", "activity_type", "lead_status", "customer_status", "customer_type"]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
