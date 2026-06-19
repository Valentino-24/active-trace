"""create aviso and acknowledgment_aviso tables

Revision ID: 013
Revises: 012
Create Date: 2026-06-19

Creates two new tables for Avisos module (F3.5).
Also seeds the nuevo permiso avisos:publicar for COORDINADOR and ADMIN.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed_permisos() -> None:
    """Seed permiso avisos:publicar if not exist."""
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
    )
    rp_t = sa.table(
        "role_permission",
        sa.column("id"), sa.column("role_id"), sa.column("permission_id"),
    )

    new_perms = [
        ("avisos:publicar", "Publicar y gestionar avisos institucionales"),
    ]

    existing_codes = set()
    rows = conn.execute(sa.text("SELECT codigo FROM permission")).fetchall()
    for r in rows:
        existing_codes.add(r[0])

    inserts = []
    for code, desc in new_perms:
        if code not in existing_codes:
            pid = _perm_id(code)
            inserts.append({"id": pid, "tenant_id": tid, "codigo": code, "descripcion": desc})

    if inserts:
        op.bulk_insert(perms_t, inserts)
        for pi in inserts:
            existing_codes.add(pi["codigo"])

    # Role-Permission matrix for avisos
    # COORDINADOR and ADMIN → avisos:publicar
    rp_matrix = {
        "avisos:publicar": ["COORDINADOR", "ADMIN"],
    }

    existing_rp = set()
    rp_rows = conn.execute(
        sa.text("SELECT rp.role_id, rp.permission_id FROM role_permission rp")
    ).fetchall()
    for r in rp_rows:
        existing_rp.add((str(r[0]), str(r[1])))

    rp_inserts = []
    for perm_code, role_codes in rp_matrix.items():
        pid = _perm_id(perm_code)
        for role_code in role_codes:
            rid = _role_id(role_code)
            if (rid, pid) not in existing_rp:
                rp_inserts.append({
                    "id": _rp_id(role_code, perm_code),
                    "role_id": rid,
                    "permission_id": pid,
                })

    if rp_inserts:
        op.bulk_insert(rp_t, rp_inserts)


def upgrade() -> None:
    # ── aviso table ──────────────────────────────────────────────────────
    op.create_table(
        "aviso",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("alcance", sa.String(20), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=True),
        sa.Column("cohorte_id", sa.UUID(), nullable=True),
        sa.Column("rol_destino", sa.String(50), nullable=True),
        sa.Column("severidad", sa.String(20), nullable=False),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("inicio_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requiere_ack", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        op.f("ix_aviso_activo_vigencia"),
        "aviso", ["tenant_id", "activo", "inicio_en", "fin_en"],
    )
    op.create_index(
        op.f("ix_aviso_alcance"),
        "aviso", ["tenant_id", "alcance"],
    )

    # ── acknowledgment_aviso table ───────────────────────────────────────
    op.create_table(
        "acknowledgment_aviso",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("aviso_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("confirmado_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["aviso_id"], ["aviso.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_ack_aviso"),
        "acknowledgment_aviso", ["aviso_id"],
    )
    op.create_index(
        op.f("ix_ack_usuario"),
        "acknowledgment_aviso", ["usuario_id"],
    )
    op.create_index(
        op.f("ix_ack_aviso_usuario"),
        "acknowledgment_aviso", ["aviso_id", "usuario_id"],
    )

    # ── Seed permisos ─────────────────────────────────────────────────────
    _seed_permisos()


def downgrade() -> None:
    op.drop_index(op.f("ix_ack_aviso_usuario"), table_name="acknowledgment_aviso")
    op.drop_index(op.f("ix_ack_usuario"), table_name="acknowledgment_aviso")
    op.drop_index(op.f("ix_ack_aviso"), table_name="acknowledgment_aviso")
    op.drop_table("acknowledgment_aviso")
    op.drop_index(op.f("ix_aviso_alcance"), table_name="aviso")
    op.drop_index(op.f("ix_aviso_activo_vigencia"), table_name="aviso")
    op.drop_table("aviso")
