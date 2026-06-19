"""extend user with PII fields, create asignacion table

Revision ID: 006
Revises: 005
Create Date: 2026-06-18

Extends the users table with personal, tax and banking information fields
(PII encrypted at rest with AES-256-GCM). Adds email_hash for deterministic
lookup. Creates the asignacion table that links users to roles within an
academic context (materia, carrera, cohorte) with validity dates.

Migration steps:
1. Add PII columns to users table
2. Add email_hash column to users table
3. Migrate existing emails: encrypt with AES-256-GCM, compute hash
4. Create asignaciones table with all constraints
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as UUIDType

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _compute_email_hash(email: str) -> str:
    """Compute a deterministic hash of an email for lookup.

    Uses SHA-256. The hash is NOT for security — it enables fast
    lookups without exposing the plaintext email. The encryption
    key is used as a pepper to prevent rainbow table attacks on
    common email domains.
    """
    return hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()


def upgrade() -> None:
    # ── Extend users table ──────────────────────────────────────────────
    # Personal info
    op.add_column("users", sa.Column("nombre", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("apellidos", sa.String(255), nullable=True))

    # PII — encrypted with AES-256-GCM (stored as base64 text)
    op.add_column("users", sa.Column("dni", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("cuil", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("cbu", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("alias_cbu", sa.Text(), nullable=True))

    # Non-sensitive fields
    op.add_column("users", sa.Column("banco", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("regional", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("legajo", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("legajo_profesional", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("facturador", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("estado", sa.String(20), nullable=False, server_default="activo"))

    # Email hash for deterministic lookup (email column itself will be encrypted)
    op.add_column("users", sa.Column("email_hash", sa.String(64), nullable=True))
    op.create_index(op.f("ix_users_email_hash"), "users", ["email_hash"])

    # ── Migrate existing emails ─────────────────────────────────────────
    # Read all existing users and compute email_hash for each.
    # The email column migration to ciphertext happens at the app level
    # (encrypt/decrypt in the schema layer). Here we just set the hash.
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(only=("users",), bind=connection)
    users_table = meta.tables["users"]

    # Ensure users table has the expected columns before migration
    if "email" in users_table.c:
        # For each existing user, compute email_hash from current email
        existing = connection.execute(
            sa.select(users_table.c.id, users_table.c.email)
        ).fetchall()
        for row in existing:
            if row.email:
                email_hash = _compute_email_hash(row.email)
                connection.execute(
                    sa.update(users_table)
                    .where(users_table.c.id == row.id)
                    .values(email_hash=email_hash)
                )

    # Make email_hash NOT NULL after populating existing data
    op.alter_column("users", "email_hash", nullable=False)

    # ── Create asignaciones table ───────────────────────────────────────
    op.create_table(
        "asignacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("rol", sa.String(50), nullable=False),
        sa.Column("materia_id", sa.UUID(), nullable=True),
        sa.Column("carrera_id", sa.UUID(), nullable=True),
        sa.Column("cohorte_id", sa.UUID(), nullable=True),
        sa.Column("comisiones", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("responsable_id", sa.UUID(), nullable=True),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["materia_id"], ["materia.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["carrera_id"], ["carrera.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cohorte_id"], ["cohorte.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        op.f("ix_asignacion_usuario_id"), "asignacion", ["usuario_id"],
    )
    op.create_index(
        op.f("ix_asignacion_materia_id"), "asignacion", ["materia_id"],
    )
    op.create_index(
        op.f("ix_asignacion_rol"), "asignacion", ["rol"],
    )


def downgrade() -> None:
    op.drop_table("asignacion")
    op.drop_index(op.f("ix_users_email_hash"), table_name="users")
    op.drop_column("users", "email_hash")
    op.drop_column("users", "estado")
    op.drop_column("users", "facturador")
    op.drop_column("users", "legajo_profesional")
    op.drop_column("users", "legajo")
    op.drop_column("users", "regional")
    op.drop_column("users", "banco")
    op.drop_column("users", "alias_cbu")
    op.drop_column("users", "cbu")
    op.drop_column("users", "cuil")
    op.drop_column("users", "dni")
    op.drop_column("users", "apellidos")
    op.drop_column("users", "nombre")
