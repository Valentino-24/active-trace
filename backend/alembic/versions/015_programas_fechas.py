"""create programa_materia and fecha_academica tables

Revision ID: 015
Revises: 014
Create Date: 2026-06-19

Part of C-17 — Programas y Fechas Academicas (F5.3, F5.4).
No new permiso seed — reuses estructura:gestionar from C-06.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── programa_materia ─────────────────────────────────────────────────
    op.create_table(
        "programa_materia",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("carrera_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("referencia_archivo", sa.String(500), nullable=True),
        sa.Column("cargado_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["carrera_id"], ["carrera.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_programa_materia_cohorte"),
        "programa_materia", ["materia_id", "cohorte_id"],
    )

    # ── fecha_academica ──────────────────────────────────────────────────
    op.create_table(
        "fecha_academica",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(50), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_fecha_academica_materia"),
        "fecha_academica", ["materia_id", "cohorte_id"],
    )
    op.create_index(
        op.f("ix_fecha_academica_periodo"),
        "fecha_academica", ["periodo"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_fecha_academica_periodo"), table_name="fecha_academica")
    op.drop_index(op.f("ix_fecha_academica_materia"), table_name="fecha_academica")
    op.drop_table("fecha_academica")
    op.drop_index(op.f("ix_programa_materia_cohorte"), table_name="programa_materia")
    op.drop_table("programa_materia")
