"""create salario_base, salario_plus, liquidacion, factura + alter materia grupo_plus

Revision ID: 016
Revises: 015
Create Date: 2026-06-19

Part of C-18 — Liquidaciones y Honorarios (Epica 10).
Seeds 3 permisos: liquidaciones:ver, liquidaciones:gestionar, liquidaciones:configurar-salarios
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))

def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))

def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed_permisos() -> None:
    conn = op.get_bind()
    try:
        row = conn.execute(sa.text("SELECT id FROM tenant LIMIT 1")).fetchone()
    except Exception:
        return
    if row is None:
        return
    tid = row[0]

    perms_t = sa.table("permission", sa.column("id"), sa.column("tenant_id"),
                        sa.column("codigo"), sa.column("descripcion"))
    rp_t = sa.table("role_permission", sa.column("id"), sa.column("role_id"),
                     sa.column("permission_id"))

    new_perms = [
        ("liquidaciones:ver", "Ver liquidaciones e historial"),
        ("liquidaciones:gestionar", "Calcular, cerrar y gestionar liquidaciones y facturas"),
        ("liquidaciones:configurar-salarios", "Administrar grilla salarial base y plus"),
    ]

    existing_codes = set()
    rows = conn.execute(sa.text("SELECT codigo FROM permission")).fetchall()
    for r in rows:
        existing_codes.add(r[0])

    inserts = []
    for code, desc in new_perms:
        if code not in existing_codes:
            inserts.append({"id": _perm_id(code), "tenant_id": tid, "codigo": code, "descripcion": desc})

    if inserts:
        op.bulk_insert(perms_t, inserts)
        for pi in inserts:
            existing_codes.add(pi["codigo"])

    rp_matrix = {
        "liquidaciones:ver": ["FINANZAS", "ADMIN"],
        "liquidaciones:gestionar": ["FINANZAS"],
        "liquidaciones:configurar-salarios": ["FINANZAS"],
    }

    existing_rp = set()
    rp_rows = conn.execute(sa.text("SELECT rp.role_id, rp.permission_id FROM role_permission rp")).fetchall()
    for r in rp_rows:
        existing_rp.add((str(r[0]), str(r[1])))

    rp_inserts = []
    for perm_code, role_codes in rp_matrix.items():
        pid = _perm_id(perm_code)
        for role_code in role_codes:
            rid = _role_id(role_code)
            if (rid, pid) not in existing_rp:
                rp_inserts.append({"id": _rp_id(role_code, perm_code), "role_id": rid, "permission_id": pid})

    if rp_inserts:
        op.bulk_insert(rp_t, rp_inserts)


def upgrade() -> None:
    # salario_base
    op.create_table("salario_base",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("rol", sa.String(50), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )

    # salario_plus
    op.create_table("salario_plus",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("grupo", sa.String(50), nullable=False),
        sa.Column("rol", sa.String(50), nullable=False),
        sa.Column("descripcion", sa.String(255), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )

    # liquidacion
    op.create_table("liquidacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("cohorte_id", sa.UUID(), nullable=False),
        sa.Column("periodo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("rol", sa.String(50), nullable=False),
        sa.Column("monto_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_plus", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("es_nexo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("excluido_por_factura", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("estado", sa.String(20), nullable=False, server_default=sa.text("'Abierta'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
    )

    # factura
    op.create_table("factura",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("periodo", sa.String(20), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("referencia_archivo", sa.String(500), nullable=True),
        sa.Column("tamano_kb", sa.Numeric(10, 2), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False, server_default=sa.text("'Pendiente'")),
        sa.Column("cargada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abonada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
    )

    # alter materia: add grupo_plus
    op.add_column("materia", sa.Column("grupo_plus", sa.String(50), nullable=True))

    _seed_permisos()


def downgrade() -> None:
    op.drop_column("materia", "grupo_plus")
    op.drop_table("factura")
    op.drop_table("liquidacion")
    op.drop_table("salario_plus")
    op.drop_table("salario_base")
