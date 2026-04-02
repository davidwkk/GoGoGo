"""add message_type to messages

Revision ID: 002
Revises: 001
Create Date: 2026-04-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "message_type", sa.String(length=20), nullable=True, server_default=None
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "message_type")
