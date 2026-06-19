"""create rbac tables: role, permission, role_permission, user_role

Revision ID: 003
Revises: 002
Create Date: 2026-06-18

"""

from collections.abc import Sequence
from uuid import uuid5, NAMESPACE_DNS

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _role_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"role:{code}"))


def _perm_id(code: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"perm:{code}"))


def _rp_id(role: str, perm: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"rp:{role}:{perm}"))


def _r(tid, codigo, nombre, descripcion):
    return {"id": _role_id(codigo), "tenant_id": tid,
            "codigo": codigo, "nombre": nombre, "descripcion": descripcion}


def _p(tid, codigo, descripcion):
    return {"id": _perm_id(codigo), "tenant_id": tid,
            "codigo": codigo, "descripcion": descripcion}


def _seed(ctx) -> None:
    """Seed initial roles, permissions, and role-permission matrix."""
    try:
        row = ctx.execute(sa.text("SELECT id FROM tenant LIMIT 1")).fetchone()
    except Exception:
        return
    if row is None:
        return
    tid = row[0]

    roles_t = sa.table("role", sa.column("id"), sa.column("tenant_id"),
                       sa.column("codigo"), sa.column("nombre"),
                       sa.column("descripcion"))
    perms_t = sa.table("permission", sa.column("id"), sa.column("tenant_id"),
                       sa.column("codigo"), sa.column("descripcion"))
    rp_t = sa.table("role_permission", sa.column("id"),
                    sa.column("role_id"), sa.column("permission_id"))

    roles = [
        _r(tid, "ALUMNO", "Alumno", "Estudiante que cursa materias"),
        _r(tid, "TUTOR", "Tutor", "Auxiliar o ayudante de cátedra"),
        _r(tid, "PROFESOR", "Profesor", "Docente a cargo de comisiones"),
        _r(tid, "COORDINADOR", "Coordinador", "Responsable de materias o cohorte"),
        _r(tid, "NEXO", "Nexo", "Rol de articulación o enlace transversal"),
        _r(tid, "ADMIN", "Admin", "Administrador del sistema dentro del tenant"),
        _r(tid, "FINANZAS", "Finanzas", "Responsable de liquidaciones y honorarios"),
    ]
    op.bulk_insert(roles_t, roles)

    perms = [
        _p(tid, "estado:ver_propio", "Ver estado académico propio"),
        _p(tid, "evaluacion:reservar", "Reservar instancia de evaluación"),
        _p(tid, "avisos:confirmar", "Confirmar avisos"),
        _p(tid, "calificaciones:importar", "Importar calificaciones"),
        _p(tid, "atrasados:ver", "Ver alumnos atrasados"),
        _p(tid, "entregas:detectar", "Detectar entregas sin corregir"),
        _p(tid, "comunicacion:enviar", "Enviar comunicaciones a alumnos"),
        _p(tid, "comunicacion:aprobar", "Aprobar comunicaciones masivas"),
        _p(tid, "encuentros:gestionar", "Gestionar encuentros"),
        _p(tid, "guardias:registrar", "Registrar guardias"),
        _p(tid, "tareas:gestionar", "Gestionar tareas internas"),
        _p(tid, "avisos:publicar", "Publicar avisos"),
        _p(tid, "equipos:asignar", "Gestionar equipos docentes"),
        _p(tid, "estructura:gestionar", "Gestionar estructura académica"),
        _p(tid, "usuarios:gestionar", "Gestionar usuarios del tenant"),
        _p(tid, "auditoria:ver", "Ver auditoría"),
        _p(tid, "salarios:operar", "Operar grilla salarial"),
        _p(tid, "liquidaciones:cerrar", "Calcular y cerrar liquidaciones"),
        _p(tid, "facturas:gestionar", "Gestionar facturas"),
        _p(tid, "tenant:configurar", "Configurar el tenant"),
    ]
    op.bulk_insert(perms_t, perms)

    # Role-Permission matrix per §3.3 of 03_actores_y_roles.md
    rp_data = [
        # ALUMNO
        _rp_id("ALUMNO", "estado:ver_propio"), _role_id("ALUMNO"), _perm_id("estado:ver_propio"),
        _rp_id("ALUMNO", "evaluacion:reservar"), _role_id("ALUMNO"), _perm_id("evaluacion:reservar"),
        _rp_id("ALUMNO", "avisos:confirmar"), _role_id("ALUMNO"), _perm_id("avisos:confirmar"),
        # TUTOR
        _rp_id("TUTOR", "avisos:confirmar"), _role_id("TUTOR"), _perm_id("avisos:confirmar"),
        _rp_id("TUTOR", "atrasados:ver"), _role_id("TUTOR"), _perm_id("atrasados:ver"),
        _rp_id("TUTOR", "entregas:detectar"), _role_id("TUTOR"), _perm_id("entregas:detectar"),
        _rp_id("TUTOR", "encuentros:gestionar"), _role_id("TUTOR"), _perm_id("encuentros:gestionar"),
        _rp_id("TUTOR", "guardias:registrar"), _role_id("TUTOR"), _perm_id("guardias:registrar"),
        # PROFESOR
        _rp_id("PROFESOR", "avisos:confirmar"), _role_id("PROFESOR"), _perm_id("avisos:confirmar"),
        _rp_id("PROFESOR", "calificaciones:importar"), _role_id("PROFESOR"), _perm_id("calificaciones:importar"),
        _rp_id("PROFESOR", "atrasados:ver"), _role_id("PROFESOR"), _perm_id("atrasados:ver"),
        _rp_id("PROFESOR", "entregas:detectar"), _role_id("PROFESOR"), _perm_id("entregas:detectar"),
        _rp_id("PROFESOR", "comunicacion:enviar"), _role_id("PROFESOR"), _perm_id("comunicacion:enviar"),
        _rp_id("PROFESOR", "encuentros:gestionar"), _role_id("PROFESOR"), _perm_id("encuentros:gestionar"),
        _rp_id("PROFESOR", "guardias:registrar"), _role_id("PROFESOR"), _perm_id("guardias:registrar"),
        _rp_id("PROFESOR", "tareas:gestionar"), _role_id("PROFESOR"), _perm_id("tareas:gestionar"),
        # COORDINADOR
        _rp_id("COORDINADOR", "avisos:confirmar"), _role_id("COORDINADOR"), _perm_id("avisos:confirmar"),
        _rp_id("COORDINADOR", "calificaciones:importar"), _role_id("COORDINADOR"), _perm_id("calificaciones:importar"),
        _rp_id("COORDINADOR", "atrasados:ver"), _role_id("COORDINADOR"), _perm_id("atrasados:ver"),
        _rp_id("COORDINADOR", "entregas:detectar"), _role_id("COORDINADOR"), _perm_id("entregas:detectar"),
        _rp_id("COORDINADOR", "comunicacion:enviar"), _role_id("COORDINADOR"), _perm_id("comunicacion:enviar"),
        _rp_id("COORDINADOR", "comunicacion:aprobar"), _role_id("COORDINADOR"), _perm_id("comunicacion:aprobar"),
        _rp_id("COORDINADOR", "encuentros:gestionar"), _role_id("COORDINADOR"), _perm_id("encuentros:gestionar"),
        _rp_id("COORDINADOR", "guardias:registrar"), _role_id("COORDINADOR"), _perm_id("guardias:registrar"),
        _rp_id("COORDINADOR", "tareas:gestionar"), _role_id("COORDINADOR"), _perm_id("tareas:gestionar"),
        _rp_id("COORDINADOR", "avisos:publicar"), _role_id("COORDINADOR"), _perm_id("avisos:publicar"),
        _rp_id("COORDINADOR", "equipos:asignar"), _role_id("COORDINADOR"), _perm_id("equipos:asignar"),
        _rp_id("COORDINADOR", "auditoria:ver"), _role_id("COORDINADOR"), _perm_id("auditoria:ver"),
        # NEXO
        _rp_id("NEXO", "avisos:confirmar"), _role_id("NEXO"), _perm_id("avisos:confirmar"),
        _rp_id("NEXO", "atrasados:ver"), _role_id("NEXO"), _perm_id("atrasados:ver"),
        _rp_id("NEXO", "entregas:detectar"), _role_id("NEXO"), _perm_id("entregas:detectar"),
        _rp_id("NEXO", "encuentros:gestionar"), _role_id("NEXO"), _perm_id("encuentros:gestionar"),
        _rp_id("NEXO", "guardias:registrar"), _role_id("NEXO"), _perm_id("guardias:registrar"),
        _rp_id("NEXO", "comunicacion:enviar"), _role_id("NEXO"), _perm_id("comunicacion:enviar"),
        # ADMIN (ALL permissions)
        _rp_id("ADMIN", "estado:ver_propio"), _role_id("ADMIN"), _perm_id("estado:ver_propio"),
        _rp_id("ADMIN", "evaluacion:reservar"), _role_id("ADMIN"), _perm_id("evaluacion:reservar"),
        _rp_id("ADMIN", "avisos:confirmar"), _role_id("ADMIN"), _perm_id("avisos:confirmar"),
        _rp_id("ADMIN", "calificaciones:importar"), _role_id("ADMIN"), _perm_id("calificaciones:importar"),
        _rp_id("ADMIN", "atrasados:ver"), _role_id("ADMIN"), _perm_id("atrasados:ver"),
        _rp_id("ADMIN", "entregas:detectar"), _role_id("ADMIN"), _perm_id("entregas:detectar"),
        _rp_id("ADMIN", "comunicacion:enviar"), _role_id("ADMIN"), _perm_id("comunicacion:enviar"),
        _rp_id("ADMIN", "comunicacion:aprobar"), _role_id("ADMIN"), _perm_id("comunicacion:aprobar"),
        _rp_id("ADMIN", "encuentros:gestionar"), _role_id("ADMIN"), _perm_id("encuentros:gestionar"),
        _rp_id("ADMIN", "guardias:registrar"), _role_id("ADMIN"), _perm_id("guardias:registrar"),
        _rp_id("ADMIN", "tareas:gestionar"), _role_id("ADMIN"), _perm_id("tareas:gestionar"),
        _rp_id("ADMIN", "avisos:publicar"), _role_id("ADMIN"), _perm_id("avisos:publicar"),
        _rp_id("ADMIN", "equipos:asignar"), _role_id("ADMIN"), _perm_id("equipos:asignar"),
        _rp_id("ADMIN", "estructura:gestionar"), _role_id("ADMIN"), _perm_id("estructura:gestionar"),
        _rp_id("ADMIN", "usuarios:gestionar"), _role_id("ADMIN"), _perm_id("usuarios:gestionar"),
        _rp_id("ADMIN", "auditoria:ver"), _role_id("ADMIN"), _perm_id("auditoria:ver"),
        _rp_id("ADMIN", "salarios:operar"), _role_id("ADMIN"), _perm_id("salarios:operar"),
        _rp_id("ADMIN", "liquidaciones:cerrar"), _role_id("ADMIN"), _perm_id("liquidaciones:cerrar"),
        _rp_id("ADMIN", "facturas:gestionar"), _role_id("ADMIN"), _perm_id("facturas:gestionar"),
        _rp_id("ADMIN", "tenant:configurar"), _role_id("ADMIN"), _perm_id("tenant:configurar"),
        # FINANZAS
        _rp_id("FINANZAS", "avisos:confirmar"), _role_id("FINANZAS"), _perm_id("avisos:confirmar"),
        _rp_id("FINANZAS", "auditoria:ver"), _role_id("FINANZAS"), _perm_id("auditoria:ver"),
        _rp_id("FINANZAS", "salarios:operar"), _role_id("FINANZAS"), _perm_id("salarios:operar"),
        _rp_id("FINANZAS", "liquidaciones:cerrar"), _role_id("FINANZAS"), _perm_id("liquidaciones:cerrar"),
        _rp_id("FINANZAS", "facturas:gestionar"), _role_id("FINANZAS"), _perm_id("facturas:gestionar"),
    ]
    rp_list = [
        {"id": rp_data[i], "role_id": rp_data[i + 1], "permission_id": rp_data[i + 2]}
        for i in range(0, len(rp_data), 3)
    ]
    op.bulk_insert(rp_t, rp_list)


def upgrade() -> None:
    # ── role ────────────────────────────────────────────────────────────
    op.create_table(
        "role",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("codigo", sa.String(50), nullable=False),
        sa.Column("descripcion", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_role_tenant_codigo"),
    )
    op.create_index(op.f("ix_role_tenant_id"), "role", ["tenant_id"])

    # ── permission ──────────────────────────────────────────────────────
    op.create_table(
        "permission",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("codigo", sa.String(100), nullable=False),
        sa.Column("descripcion", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_permission_tenant_codigo"),
    )
    op.create_index(op.f("ix_permission_tenant_id"), "permission", ["tenant_id"])

    # ── role_permission ─────────────────────────────────────────────────
    op.create_table(
        "role_permission",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index(op.f("ix_role_permission_role_id"), "role_permission", ["role_id"])
    op.create_index(op.f("ix_role_permission_permission_id"), "role_permission", ["permission_id"])

    # ── user_role ───────────────────────────────────────────────────────
    op.create_table(
        "user_role",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role_id", "desde", name="uq_user_role_desde"),
    )
    op.create_index(op.f("ix_user_role_tenant_id"), "user_role", ["tenant_id"])
    op.create_index(op.f("ix_user_role_user_id"), "user_role", ["user_id"])

    # ── Seed data ───────────────────────────────────────────────────────
    _seed(op.get_bind())


def downgrade() -> None:
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
