"""create version_padron and entrada_padron tables, seed padron:importar
                                                                                
Revision ID: 008
Revises: 007
Create Date: 2026-06-18

Creates the versioned padron import system:
- version_padron: each import creates a new version with activa flag
- entrada_padron: individual student entries linked to a version

Seeds the padron:importar permission for PROFESOR, COORDINADOR and ADMIN roles.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def upgrade() -> None:
    # ── version_padron ────────────────────────────────────────────────────
    op.create_table(
        "version_padron",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("cargado_por", sa.UUID(), nullable=False),
        sa.Column("cargado_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("modo", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cargado_por"], ["users.id"],
                                ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_version_padron_materia_cohorte_activa"),
        "version_padron", ["materia_id", "cohorte_id", "activa"],
    )

    # ── entrada_padron ────────────────────────────────────────────────────
    op.create_table(
        "entrada_padron",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("apellidos", sa.String(255), nullable=False),
        sa.Column("email_cifrado", sa.Text(), nullable=True),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("comision", sa.String(50), nullable=True),
        sa.Column("regional", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["version_id"], ["version_padron.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"],
                                ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_entrada_padron_version_id"),
        "entrada_padron", ["version_id"],
    )

    # ── Seed padron:importar permission per tenant ───────────────────────
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM tenant")).fetchall()

    for (tid,) in tenants:
        perm_id = _perm_id("padron:importar")
        conn.execute(
            sa.text(
                "INSERT INTO permission (id, tenant_id, codigo, descripcion) "
                "VALUES (:id, :tid, :codigo, :descripcion) "
                "ON CONFLICT (id, tenant_id) DO NOTHING"
            ),
            {
                "id": perm_id,
                "tid": tid,
                "codigo": "padron:importar",
                "descripcion": "Importar padrón de alumnos (Moodle WS / archivo) y vaciar materia",
            }
        )

        # Assign to PROFESOR
        profe_role_id = _role_id("PROFESOR")
        rp_profe_id = _rp_id("PROFESOR", "padron:importar")
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": rp_profe_id,
                "role_id": profe_role_id,
                "perm_id": perm_id,
            }
        )

        # Assign to COORDINADOR
        coord_role_id = _role_id("COORDINADOR")
        rp_coord_id = _rp_id("COORDINADOR", "padron:importar")
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": rp_coord_id,
                "role_id": coord_role_id,
                "perm_id": perm_id,
            }
        )

        # Assign to ADMIN
        admin_role_id = _role_id("ADMIN")
        rp_admin_id = _rp_id("ADMIN", "padron:importar")
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": rp_admin_id,
                "role_id": admin_role_id,
                "perm_id": perm_id,
            }
        )


def downgrade() -> None:
    perm_id = _perm_id("padron:importar")

    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM role_permission WHERE permission_id = :pid"),
        {"pid": perm_id},
    )
    conn.execute(
        sa.text("DELETE FROM permission WHERE codigo = 'padron:importar'"),
    )

    op.drop_index(op.f("ix_entrada_padron_version_id"),
                  table_name="entrada_padron")
    op.drop_table("entrada_padron")
    op.drop_index(op.f("ix_version_padron_materia_cohorte_activa"),
                  table_name="version_padron")
    op.drop_table("version_padron")
