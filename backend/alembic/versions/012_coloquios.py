"""create evaluacion, reserva_evaluacion, resultado_evaluacion tables

Revision ID: 012
Revises: 011
Create Date: 2026-06-19

Creates three new tables for Coloquios module (Epic 7).
Also seeds the nuevos permisos coloquios:gestionar and coloquios:ver.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed_permisos() -> None:
    """Seed permisos coloquios:gestionar and coloquios:ver if not exist."""
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
        ("coloquios:gestionar", "Gestionar convocatorias de coloquios"),
        ("coloquios:ver", "Consultar coloquios, métricas y registro"),
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

    # Role-Permission matrix for coloquios
    # PROFESOR, COORDINADOR, ADMIN → both gestionar and ver
    rp_matrix = {
        "coloquios:gestionar": ["PROFESOR", "COORDINADOR", "ADMIN"],
        "coloquios:ver": ["PROFESOR", "COORDINADOR", "ADMIN"],
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
    # ── evaluacion table ────────────────────────────────────────────────
    op.create_table(
        "evaluacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("instancia", sa.Text(), nullable=False),
        sa.Column("dias_disponibles", sa.Integer(), nullable=False,
                  server_default=sa.text("30")),
        sa.Column("activa", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
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
        op.f("ix_evaluacion_activa"),
        "evaluacion", ["tenant_id", "activa"],
    )
    op.create_index(
        op.f("ix_evaluacion_materia"),
        "evaluacion", ["tenant_id", "materia_id"],
    )

    # ── reserva_evaluacion table ────────────────────────────────────────
    op.create_table(
        "reserva_evaluacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("evaluacion_id", sa.UUID(), nullable=False),
        sa.Column("alumno_id", sa.UUID(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False,
                  server_default=sa.text("'Activa'")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluacion_id"], ["evaluacion.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alumno_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_reserva_evaluacion"),
        "reserva_evaluacion", ["evaluacion_id"],
    )
    op.create_index(
        op.f("ix_reserva_alumno"),
        "reserva_evaluacion", ["alumno_id"],
    )
    op.create_index(
        op.f("ix_reserva_activa"),
        "reserva_evaluacion", ["tenant_id", "estado"],
    )

    # ── resultado_evaluacion table ──────────────────────────────────────
    op.create_table(
        "resultado_evaluacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("evaluacion_id", sa.UUID(), nullable=False),
        sa.Column("alumno_id", sa.UUID(), nullable=False),
        sa.Column("nota_final", sa.String(50), nullable=True),
        sa.Column("registrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluacion_id"], ["evaluacion.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alumno_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_resultado_evaluacion"),
        "resultado_evaluacion", ["evaluacion_id"],
    )
    op.create_index(
        op.f("ix_resultado_alumno"),
        "resultado_evaluacion", ["alumno_id"],
    )

    # ── Seed permisos ───────────────────────────────────────────────────
    _seed_permisos()


def downgrade() -> None:
    op.drop_index(op.f("ix_resultado_alumno"), table_name="resultado_evaluacion")
    op.drop_index(op.f("ix_resultado_evaluacion"), table_name="resultado_evaluacion")
    op.drop_table("resultado_evaluacion")
    op.drop_index(op.f("ix_reserva_activa"), table_name="reserva_evaluacion")
    op.drop_index(op.f("ix_reserva_alumno"), table_name="reserva_evaluacion")
    op.drop_index(op.f("ix_reserva_evaluacion"), table_name="reserva_evaluacion")
    op.drop_table("reserva_evaluacion")
    op.drop_index(op.f("ix_evaluacion_materia"), table_name="evaluacion")
    op.drop_index(op.f("ix_evaluacion_activa"), table_name="evaluacion")
    op.drop_table("evaluacion")
