"""create comunicacion table

Revision ID: 010
Revises: 009
Create Date: 2026-06-19

Creates the comunicacion table for outbound communications with
state machine, encrypted recipient, batch grouping, and approval fields.

Permissions comunicacion:enviar and comunicacion:aprobar were already
seeded in migration 003 — no reseed needed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── comunicacion table ──────────────────────────────────────────────
    op.create_table(
        "comunicacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("enviado_por", sa.UUID(), nullable=False),
        sa.Column("aprobado_por", sa.UUID(), nullable=True),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("destinatario", sa.Text(), nullable=False),
        sa.Column("asunto", sa.Text(), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default=sa.text("'Pendiente'")),
        sa.Column("lote_id", sa.UUID(), nullable=True),
        sa.Column("fecha_aprobacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enviado_por"], ["users.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["aprobado_por"], ["users.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"],
                                ondelete="CASCADE"),
    )

    # ── Indexes ─────────────────────────────────────────────────────────
    op.create_index(
        op.f("ix_comunicacion_lote"),
        "comunicacion", ["lote_id"],
    )
    op.create_index(
        op.f("ix_comunicacion_estado"),
        "comunicacion", ["tenant_id", "estado"],
    )
    op.create_index(
        op.f("ix_comunicacion_materia"),
        "comunicacion", ["tenant_id", "materia_id"],
    )

    # ── Permissions check ──────────────────────────────────────────────
    # comunicacion:enviar and comunicacion:aprobar were seeded in
    # migration 003 (003_crear_rbac.py). Do NOT reseed.
    # Verify they exist:
    conn = op.get_bind()
    from uuid import NAMESPACE_DNS, uuid5

    def _perm_id(code: str) -> str:
        return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))

    for perm_code in ["comunicacion:enviar", "comunicacion:aprobar"]:
        pid = _perm_id(perm_code)
        existing = conn.execute(
            sa.text(
                "SELECT id FROM permission WHERE id = :pid"
            ),
            {"pid": pid},
        ).fetchone()
        if existing is None:
            # This is a safety check: if somehow the permissions were
            # not seeded (e.g., running migration 010 on a fresh DB
            # without running 003 first), seed them now.
            from uuid import uuid5 as _u5

            # We need a tenant — take the first one
            row = conn.execute(
                sa.text("SELECT id FROM tenant LIMIT 1")
            ).fetchone()
            if row is not None:
                tid = row[0]
                desc = (
                    "Enviar comunicaciones a alumnos"
                    if perm_code == "comunicacion:enviar"
                    else "Aprobar comunicaciones masivas"
                )
                conn.execute(
                    sa.text(
                        "INSERT INTO permission (id, tenant_id, codigo, descripcion) "
                        "VALUES (:id, :tid, :codigo, :descripcion) "
                        "ON CONFLICT (id, tenant_id) DO NOTHING"
                    ),
                    {
                        "id": pid,
                        "tid": tid,
                        "codigo": perm_code,
                        "descripcion": desc,
                    }
                )


def downgrade() -> None:
    op.drop_index(op.f("ix_comunicacion_materia"), table_name="comunicacion")
    op.drop_index(op.f("ix_comunicacion_estado"), table_name="comunicacion")
    op.drop_index(op.f("ix_comunicacion_lote"), table_name="comunicacion")
    op.drop_table("comunicacion")
