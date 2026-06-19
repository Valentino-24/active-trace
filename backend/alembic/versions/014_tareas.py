"""create tarea and comentario_tarea tables

Revision ID: 014
Revises: 013
Create Date: 2026-06-19

Creates two new tables for Tareas Internas module (Epica 8, F8.1–F8.3).
Also seeds the nuevo permiso tareas:gestionar for TUTOR, PROFESOR, COORDINADOR, ADMIN.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed_permisos() -> None:
    """Seed permiso tareas:gestionar if not exist."""
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
        ("tareas:gestionar", "Gestionar tareas internas del equipo docente"),
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

    # Role-Permission matrix for tareas
    rp_matrix = {
        "tareas:gestionar": ["TUTOR", "PROFESOR", "COORDINADOR", "ADMIN"],
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
    # ── tarea table ─────────────────────────────────────────────────────
    op.create_table(
        "tarea",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=True),
        sa.Column("asignado_a", sa.UUID(), nullable=False),
        sa.Column("asignado_por", sa.UUID(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default=sa.text("'Pendiente'")),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("contexto_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["asignado_a"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asignado_por"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_tarea_asignado"),
        "tarea", ["tenant_id", "asignado_a", "deleted_at"],
    )
    op.create_index(
        op.f("ix_tarea_estado"),
        "tarea", ["tenant_id", "estado"],
    )

    # ── comentario_tarea table ───────────────────────────────────────────
    op.create_table(
        "comentario_tarea",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tarea_id", sa.UUID(), nullable=False),
        sa.Column("autor_id", sa.UUID(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("creado_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tarea_id"], ["tarea.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["autor_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_comentario_tarea"),
        "comentario_tarea", ["tarea_id"],
    )

    # ── Seed permisos ─────────────────────────────────────────────────────
    _seed_permisos()


def downgrade() -> None:
    op.drop_index(op.f("ix_comentario_tarea"), table_name="comentario_tarea")
    op.drop_table("comentario_tarea")
    op.drop_index(op.f("ix_tarea_estado"), table_name="tarea")
    op.drop_index(op.f("ix_tarea_asignado"), table_name="tarea")
    op.drop_table("tarea")
