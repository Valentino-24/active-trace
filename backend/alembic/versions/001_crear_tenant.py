"""create tenant table

Revision ID: 001
Revises:
Create Date: 2026-06-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("codigo", sa.String(50), nullable=False),
        sa.Column("configuracion", sa.JSON(), nullable=True),
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default="activo",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_tenant_codigo"),
    )
    op.create_index(
        op.f("ix_tenant_codigo"), "tenant", ["codigo"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tenant_codigo"), table_name="tenant")
    op.drop_table("tenant")
