"""create slot_encuentro, instancia_encuentro, guardia tables

Revision ID: 011
Revises: 010
Create Date: 2026-06-19

Creates three new tables for Encuentros and Guardias modules (Epic 6).
Also seeds the nuevos permisos encuentros:gestionar and guardias:gestionar
(since migration 003 already seeds them, we check exist first and skip if present).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed_permisos() -> None:
    """Seed permisos encuentros:gestionar and guardias:gestionar if not exist."""
    conn = op.get_bind()

    # Get tenant
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

    # Permissions already exist from migration 003 — check and skip if present
    new_perms = [
        ("encuentros:gestionar", "Gestionar encuentros"),
        ("guardias:gestionar", "Gestionar guardias"),

    # Note: The actual action for TUTOR is "registrar guardias" per KB,
    # but the permission is named guardias:gestionar for consistency
    # with encuentros:gestionar. Scope filtering handles the difference.
    ]

    existing_codes = set()
    rows = conn.execute(sa.text("SELECT codigo FROM permission")).fetchall()
    for r in rows:
        existing_codes.add(r[0])

    inserts = []
    perms_to_insert = []
    for code, desc in new_perms:
        if code not in existing_codes:
            pid = _perm_id(code)
            inserts.append({"id": pid, "tenant_id": tid, "codigo": code, "descripcion": desc})
            perms_to_insert.append(code)

    if inserts:
        op.bulk_insert(perms_t, inserts)
        for pi in inserts:
            existing_codes.add(pi["codigo"])

    # Role-Permission matrix for encuentros:gestionar and guardias:gestionar
    # Per design matrix: PROFESOR, COORDINADOR, ADMIN, NEXO → encuentros:gestionar
    #                    TUTOR, PROFESOR, COORDINADOR, ADMIN, NEXO → guardias:gestionar
    rp_matrix = {
        "encuentros:gestionar": ["PROFESOR", "COORDINADOR", "ADMIN", "NEXO"],
        "guardias:gestionar": ["TUTOR", "PROFESOR", "COORDINADOR", "ADMIN", "NEXO"],
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
    # ── slot_encuentro table ───────────────────────────────────────────
    op.create_table(
        "slot_encuentro",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("asignacion_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("hora", sa.String(10), nullable=False),
        sa.Column("dia_semana", sa.String(15), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("cant_semanas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fecha_unica", sa.Date(), nullable=True),
        sa.Column("meet_url", sa.String(1024), nullable=True),
        sa.Column("vig_desde", sa.Date(), nullable=True),
        sa.Column("vig_hasta", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asignacion_id"], ["asignacion.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_slot_encuentro_materia"),
        "slot_encuentro", ["tenant_id", "materia_id"],
    )

    # ── instancia_encuentro table ──────────────────────────────────────
    op.create_table(
        "instancia_encuentro",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slot_id", sa.UUID(), nullable=True),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora", sa.String(10), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default=sa.text("'Programado'")),
        sa.Column("meet_url", sa.String(1024), nullable=True),
        sa.Column("video_url", sa.String(1024), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slot_id"], ["slot_encuentro.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_instancia_materia"),
        "instancia_encuentro", ["tenant_id", "materia_id"],
    )
    op.create_index(
        op.f("ix_instancia_slot"),
        "instancia_encuentro", ["slot_id"],
    )
    op.create_index(
        op.f("ix_instancia_fecha"),
        "instancia_encuentro", ["tenant_id", "fecha"],
    )

    # ── guardia table ──────────────────────────────────────────────────
    op.create_table(
        "guardia",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("asignacion_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("carrera_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("dia", sa.String(15), nullable=False),
        sa.Column("horario", sa.String(20), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default=sa.text("'Pendiente'")),
        sa.Column("comentarios", sa.Text(), nullable=True),
        sa.Column("creada_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asignacion_id"], ["asignacion.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["carrera_id"], ["carrera.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_guardia_materia"),
        "guardia", ["tenant_id", "materia_id"],
    )
    op.create_index(
        op.f("ix_guardia_asignacion"),
        "guardia", ["asignacion_id"],
    )

    # ── Seed permisos ─────────────────────────────────────────────────
    _seed_permisos()


def downgrade() -> None:
    op.drop_index(op.f("ix_guardia_asignacion"), table_name="guardia")
    op.drop_index(op.f("ix_guardia_materia"), table_name="guardia")
    op.drop_table("guardia")
    op.drop_index(op.f("ix_instancia_fecha"), table_name="instancia_encuentro")
    op.drop_index(op.f("ix_instancia_slot"), table_name="instancia_encuentro")
    op.drop_index(op.f("ix_instancia_materia"), table_name="instancia_encuentro")
    op.drop_table("instancia_encuentro")
    op.drop_index(op.f("ix_slot_encuentro_materia"), table_name="slot_encuentro")
    op.drop_table("slot_encuentro")
