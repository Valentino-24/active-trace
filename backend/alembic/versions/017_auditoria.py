"""add audit index + seed auditoria:ver permiso

Revision ID: 017
Revises: 016
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))

def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))

def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _seed() -> None:
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

    existing_codes = {r[0] for r in conn.execute(sa.text("SELECT codigo FROM permission")).fetchall()}
    code = "auditoria:ver"
    if code not in existing_codes:
        op.bulk_insert(perms_t, [{"id": _perm_id(code), "tenant_id": tid, "codigo": code, "descripcion": "Ver panel de auditoria"}])


    existing_rp = {(str(r[0]), str(r[1])) for r in conn.execute(
        sa.text("SELECT role_id, permission_id FROM role_permission")).fetchall()}
    pid = _perm_id(code)
    rp_inserts = []
    for role_code in ("ADMIN", "COORDINADOR"):
        rid = _role_id(role_code)
        if (rid, pid) not in existing_rp:
            rp_inserts.append({"id": _rp_id(role_code, code), "role_id": rid, "permission_id": pid})
    if rp_inserts:
        op.bulk_insert(rp_t, rp_inserts)


def upgrade() -> None:
    op.create_index("ix_audit_log_fecha", "audit_log", ["fecha_hora"])
    _seed()


def downgrade() -> None:
    op.drop_index("ix_audit_log_fecha", table_name="audit_log")
