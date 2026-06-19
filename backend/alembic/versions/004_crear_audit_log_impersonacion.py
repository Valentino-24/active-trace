"""create audit_log table, impersonacion:usar permission

Revision ID: 004
Revises: 003
Create Date: 2026-06-18

Creates the immutable append-only audit_log table and seeds the
impersonacion:usar permission for the ADMIN role.

Applies DB-level REVOKE on UPDATE/DELETE to enforce append-only
semantics at the database level (defence in depth).

"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid5, NAMESPACE_DNS

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def upgrade() -> None:
    # ── audit_log ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False, index=True),
        sa.Column("impersonado_id", sa.UUID(), nullable=True),
        sa.Column("materia_id", sa.UUID(), nullable=True),
        sa.Column("accion", sa.String(64), nullable=False, index=True),
        sa.Column("detalle", sa.JSON(), nullable=True),
        sa.Column("filas_afectadas", sa.Integer(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        op.f("ix_audit_log_tenant_accion"),
        "audit_log", ["tenant_id", "accion"],
    )
    op.create_index(
        op.f("ix_audit_log_tenant_fecha"),
        "audit_log", ["tenant_id", "fecha_hora"],
    )

    # ── DB-level append-only guard (defence in depth) ───────────────────
    # The application layer already blocks UPDATE/DELETE in the repository.
    # This REVOKE ensures that even direct SQL modifications to audit_log
    # are impossible from the application role.
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC")
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM activia_trace_app")

    # ── Seed impersonacion:usar permission ──────────────────────────────
    conn = op.get_bind()
    try:
        row = conn.execute(sa.text("SELECT id FROM tenant LIMIT 1")).fetchone()
    except Exception:
        return
    if row is None:
        return
    tid = row[0]

    perms_t = sa.table(
        "permission",
        sa.column("id"), sa.column("tenant_id"),
        sa.column("codigo"), sa.column("descripcion"),
        sa.column("created_at"), sa.column("updated_at"),
    )
    rp_t = sa.table(
        "role_permission",
        sa.column("id"), sa.column("role_id"),
        sa.column("permission_id"),
        sa.column("created_at"), sa.column("updated_at"),
    )

    now = sa.func.now()

    # Insert the permission (idempotent via ON CONFLICT DO NOTHING)
    perm_id_val = _perm_id("impersonacion:usar")
    op.execute(
        sa.text(
            "INSERT INTO permission (id, tenant_id, codigo, descripcion, "
            "created_at, updated_at) "
            "VALUES (:id, :tid, 'impersonacion:usar', "
            "'Iniciar sesión de impersonación sobre otros usuarios', "
            "NOW(), NOW()) "
            "ON CONFLICT (tenant_id, codigo) DO NOTHING"
        ).bindparams(id=perm_id_val, tid=tid)
    )

    # Link to ADMIN role (idempotent)
    role_id_val = str(uuid5(NAMESPACE_DNS, "role:ADMIN"))
    rp_id_val = _rp_id("ADMIN", "impersonacion:usar")

    op.execute(
        sa.text(
            "INSERT INTO role_permission (id, role_id, permission_id, "
            "created_at, updated_at) "
            "VALUES (:id, :role_id, :perm_id, NOW(), NOW()) "
            "ON CONFLICT (role_id, permission_id) DO NOTHING"
        ).bindparams(id=rp_id_val, role_id=role_id_val, perm_id=perm_id_val)
    )


def downgrade() -> None:
    # Remove REVOKE first
    op.execute("GRANT UPDATE, DELETE ON audit_log TO PUBLIC")
    op.execute("GRANT UPDATE, DELETE ON audit_log TO activia_trace_app")

    op.drop_index(op.f("ix_audit_log_tenant_fecha"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_tenant_accion"), table_name="audit_log")
    op.drop_table("audit_log")

    # Remove the permission (CASCADE removes role_permission link)
    op.execute(
        sa.delete(sa.table("permission")).where(
            sa.column("codigo") == "impersonacion:usar"
        )
    )
