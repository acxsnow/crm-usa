"""Un asiento se reversa una sola vez, también con dos peticiones simultáneas.

Revision ID: 0049
Revises: 0048
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_journal_entries_reversal_of_id", "journal_entries", ["reversal_of_id"])


def downgrade() -> None:
    op.drop_constraint("uq_journal_entries_reversal_of_id", "journal_entries", type_="unique")
