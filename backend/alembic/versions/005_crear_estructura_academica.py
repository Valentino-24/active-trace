"""create academic structure: carrera, cohorte, materia, dictado

Revision ID: 005
Revises: 004
Create Date: 2026-06-18

Creates the four core academic structure tables that form the foundation
for all academic modules: calificaciones, equipos docentes, encuentros,
coloquios, and comunicaciones.

- Carrera: degree programme (e.g. 'Técnico Universitario en Programación')
- Cohorte: a cohort within a carrera (e.g. '2026-A')
- Materia: subject catalogue (e.g. 'Programación I')
- Dictado: teaching instance of a materia in a carrera × cohorte

All tables inherit TenantScopedMixin + SoftDeleteMixin structure.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── carrera ───────────────────────────────────────────────────────────
    op.create_table(
        "carrera",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default="activa"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_carrera_tenant_codigo"),
    )

    # ── cohorte ───────────────────────────────────────────────────────────
    op.create_table(
        "cohorte",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("carrera_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("vig_desde", sa.Date(), nullable=False),
        sa.Column("vig_hasta", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default="activa"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["carrera_id"], ["carrera.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "tenant_id", "carrera_id", "nombre",
            name="uq_cohorte_tenant_carrera_nombre",
        ),
    )
    op.create_index(
        op.f("ix_cohorte_carrera_id"), "cohorte", ["carrera_id"],
    )

    # ── materia ───────────────────────────────────────────────────────────
    op.create_table(
        "materia",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default="activa"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_materia_tenant_codigo"),
    )

    # ── dictado ───────────────────────────────────────────────────────────
    op.create_table(
        "dictado",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("carrera_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default="activo"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["materia_id"], ["materia.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["carrera_id"], ["carrera.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cohorte_id"], ["cohorte.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "tenant_id", "materia_id", "carrera_id", "cohorte_id",
            name="uq_dictado_unique",
        ),
    )
    op.create_index(
        op.f("ix_dictado_materia_id"), "dictado", ["materia_id"],
    )
    op.create_index(
        op.f("ix_dictado_carrera_id"), "dictado", ["carrera_id"],
    )
    op.create_index(
        op.f("ix_dictado_cohorte_id"), "dictado", ["cohorte_id"],
    )


def downgrade() -> None:
    op.drop_table("dictado")
    op.drop_table("materia")
    op.drop_table("cohorte")
    op.drop_index(op.f("ix_cohorte_carrera_id"), table_name="cohorte")
    op.drop_table("carrera")
