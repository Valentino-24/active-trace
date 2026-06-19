"""create mensaje table

Revision ID: 018
Revises: 017
Create Date: 2026-06-19
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("mensaje",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("remitente_id", sa.UUID(), nullable=False),
        sa.Column("destinatario_id", sa.UUID(), nullable=False),
        sa.Column("asunto", sa.String(255), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("leido", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("leido_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["remitente_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destinatario_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("mensaje")
