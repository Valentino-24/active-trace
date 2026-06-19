"""add equipos:gestionar permission

Adds the equipos:gestionar permission for bulk team management
operations and assigns it to COORDINADOR and ADMIN roles.

Revision ID: 007
Revises: 006
Create Date: 2026-06-18

"""

from collections.abc import Sequence
from uuid import uuid5, NAMESPACE_DNS

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def upgrade() -> None:
    conn = op.get_bind()

    # Get all tenant IDs
    tenants = conn.execute(sa.text("SELECT id FROM tenant")).fetchall()

    perms_t = sa.table("permission",
                       sa.column("id"), sa.column("tenant_id"),
                       sa.column("codigo"), sa.column("descripcion"))
    rp_t = sa.table("role_permission",
                    sa.column("id"), sa.column("role_id"),
                    sa.column("permission_id"))

    for (tid,) in tenants:
        # Add equipos:gestionar permission
        perm_id = _perm_id("equipos:gestionar")
        # Use INSERT ... ON CONFLICT DO NOTHING for idempotency
        conn.execute(
            sa.text(
                "INSERT INTO permission (id, tenant_id, codigo, descripcion) "
                "VALUES (:id, :tid, :codigo, :descripcion) "
                "ON CONFLICT (id, tenant_id) DO NOTHING"
            ),
            {
                "id": perm_id,
                "tid": tid,
                "codigo": "equipos:gestionar",
                "descripcion": "Gestionar equipos docentes (operaciones masivas)",
            }
        )

        # Assign to COORDINADOR
        coord_role_id = _role_id("COORDINADOR")
        rp_coord_id = _rp_id("COORDINADOR", "equipos:gestionar")
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
        rp_admin_id = _rp_id("ADMIN", "equipos:gestionar")
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
    conn = op.get_bind()
    perm_id = _perm_id("equipos:gestionar")

    # Remove role_permission assignments
    conn.execute(
        sa.text("DELETE FROM role_permission WHERE permission_id = :pid"),
        {"pid": perm_id},
    )
    # Remove permission
    conn.execute(
        sa.text(
            "DELETE FROM permission WHERE codigo = 'equipos:gestionar'"
        ),
    )
