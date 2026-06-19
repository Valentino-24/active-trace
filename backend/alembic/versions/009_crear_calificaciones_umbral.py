"""create calificacion and umbral_materia tables, seed calificaciones:ver

Revision ID: 009
Revises: 008
Create Date: 2026-06-19

Creates the grade and threshold system:
- calificacion: individual grade records linked to entrada_padron
- umbral_materia: passing threshold configuration per asignacion

Seeds the calificaciones:ver permission for PROFESOR, COORDINADOR and ADMIN roles.
calificaciones:importar was already seeded in migration 003.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def upgrade() -> None:
    # ── calificacion ──────────────────────────────────────────────────────
    op.create_table(
        "calificacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entrada_padron_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("asignacion_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("actividad_nombre", sa.String(255), nullable=False),
        sa.Column("nota", sa.Float(), nullable=True),
        sa.Column("nota_textual", sa.String(100), nullable=True),
        sa.Column("aprobado", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("periodo", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entrada_padron_id"], ["entrada_padron.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asignacion_id"], ["asignacion.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"],
                                ondelete="SET NULL"),
        sa.CheckConstraint("origen IN ('Importado', 'Manual')",
                           name="ck_calificacion_origen"),
    )
    op.create_index(
        op.f("ix_calificacion_materia_cohorte"),
        "calificacion", ["materia_id", "cohorte_id"],
    )
    op.create_index(
        op.f("ix_calificacion_asignacion"),
        "calificacion", ["asignacion_id"],
    )

    # ── umbral_materia ────────────────────────────────────────────────────
    op.create_table(
        "umbral_materia",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("asignacion_id", sa.UUID(), nullable=True),
        sa.Column("umbral_pct", sa.Float(), nullable=False,
                  server_default=sa.text("0.600")),
        sa.Column("valores_aprobatorios", sa.ARRAY(sa.String(100)),
                  nullable=True),
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
        sa.ForeignKeyConstraint(["asignacion_id"], ["asignacion.id"],
                                ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "materia_id", "cohorte_id",
                            "asignacion_id",
                            name="uq_umbral_materia_asignacion"),
        sa.CheckConstraint("umbral_pct >= 0 AND umbral_pct <= 1",
                           name="ck_umbral_materia_pct"),
    )
    op.create_index(
        op.f("ix_umbral_materia_materia_cohorte"),
        "umbral_materia", ["materia_id", "cohorte_id"],
    )

    # ── Seed calificaciones:ver permission per tenant ──────────────────────
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM tenant")).fetchall()

    for (tid,) in tenants:
        # calificaciones:ver
        perm_ver_id = _perm_id("calificaciones:ver")
        conn.execute(
            sa.text(
                "INSERT INTO permission (id, tenant_id, codigo, descripcion) "
                "VALUES (:id, :tid, :codigo, :descripcion) "
                "ON CONFLICT (id, tenant_id) DO NOTHING"
            ),
            {
                "id": perm_ver_id,
                "tid": tid,
                "codigo": "calificaciones:ver",
                "descripcion": "Consultar calificaciones y umbrales",
            }
        )

        # Assign calificaciones:ver to PROFESOR
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": _rp_id("PROFESOR", "calificaciones:ver"),
                "role_id": _role_id("PROFESOR"),
                "perm_id": perm_ver_id,
            }
        )

        # Assign calificaciones:ver to COORDINADOR
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": _rp_id("COORDINADOR", "calificaciones:ver"),
                "role_id": _role_id("COORDINADOR"),
                "perm_id": perm_ver_id,
            }
        )

        # Assign calificaciones:ver to ADMIN
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (id, role_id, permission_id) "
                "VALUES (:id, :role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {
                "id": _rp_id("ADMIN", "calificaciones:ver"),
                "role_id": _role_id("ADMIN"),
                "perm_id": perm_ver_id,
            }
        )

        # calificaciones:importar was already seeded in migration 003
        # Verify it exists, but DO NOT re-insert
        perm_importar_id = _perm_id("calificaciones:importar")
        existing = conn.execute(
            sa.text("SELECT id FROM permission WHERE id = :pid AND tenant_id = :tid"),
            {"pid": perm_importar_id, "tid": tid},
        ).fetchone()

        if existing is None:
            # Not seeded yet — seed it (defensive, though 003 should have done it)
            conn.execute(
                sa.text(
                    "INSERT INTO permission (id, tenant_id, codigo, descripcion) "
                    "VALUES (:id, :tid, :codigo, :descripcion) "
                    "ON CONFLICT (id, tenant_id) DO NOTHING"
                ),
                {
                    "id": perm_importar_id,
                    "tid": tid,
                    "codigo": "calificaciones:importar",
                    "descripcion": "Importar calificaciones y configurar umbrales",
                }
            )

            # Assign to PROFESOR
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (id, role_id, permission_id) "
                    "VALUES (:id, :role_id, :perm_id) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ),
                {
                    "id": _rp_id("PROFESOR", "calificaciones:importar"),
                    "role_id": _role_id("PROFESOR"),
                    "perm_id": perm_importar_id,
                }
            )

            # Assign to COORDINADOR
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (id, role_id, permission_id) "
                    "VALUES (:id, :role_id, :perm_id) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ),
                {
                    "id": _rp_id("COORDINADOR", "calificaciones:importar"),
                    "role_id": _role_id("COORDINADOR"),
                    "perm_id": perm_importar_id,
                }
            )

            # Assign to ADMIN
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (id, role_id, permission_id) "
                    "VALUES (:id, :role_id, :perm_id) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ),
                {
                    "id": _rp_id("ADMIN", "calificaciones:importar"),
                    "role_id": _role_id("ADMIN"),
                    "perm_id": perm_importar_id,
                }
            )


def downgrade() -> None:
    perm_ver_id = _perm_id("calificaciones:ver")
    perm_importar_id = _perm_id("calificaciones:importar")

    conn = op.get_bind()

    # Remove role_permission entries for both permissions
    conn.execute(
        sa.text("DELETE FROM role_permission WHERE permission_id = :pid"),
        {"pid": perm_ver_id},
    )
    conn.execute(
        sa.text("DELETE FROM role_permission WHERE permission_id = :pid"),
        {"pid": perm_importar_id},
    )

    # Remove permission entries
    conn.execute(
        sa.text("DELETE FROM permission WHERE codigo = 'calificaciones:ver'"),
    )

    # Drop tables
    op.drop_index(op.f("ix_umbral_materia_materia_cohorte"),
                  table_name="umbral_materia")
    op.drop_table("umbral_materia")
    op.drop_index(op.f("ix_calificacion_asignacion"),
                  table_name="calificacion")
    op.drop_index(op.f("ix_calificacion_materia_cohorte"),
                  table_name="calificacion")
    op.drop_table("calificacion")
