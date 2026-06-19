"""Seed script: creates default tenant + admin user + roles/permissions + demo data.

Run ONCE after first docker compose up:
    docker compose exec api python -c "import app.seed; import asyncio; asyncio.run(app.seed.seed())"
"""

import asyncio
import uuid
from datetime import date, datetime, UTC

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.asignacion import Asignacion
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.aviso import Aviso
from app.models.audit_log import AuditLog


ROLES = [
    ("ALUMNO", "Alumno"),
    ("TUTOR", "Tutor"),
    ("PROFESOR", "Profesor"),
    ("COORDINADOR", "Coordinador"),
    ("NEXO", "Nexo"),
    ("ADMIN", "Administrador"),
    ("FINANZAS", "Finanzas"),
]

PERMISSIONS = [
    ("calificaciones:importar", "Importar calificaciones"),
    ("calificaciones:ver", "Ver calificaciones"),
    ("calificaciones:gestionar", "Gestionar calificaciones"),
    ("atrasados:ver", "Ver atrasados"),
    ("comunicacion:enviar", "Enviar comunicaciones"),
    ("comunicacion:aprobar", "Aprobar comunicaciones"),
    ("comunicacion:ver", "Ver comunicaciones"),
    ("equipos:gestionar", "Gestionar equipos docentes"),
    ("encuentros:gestionar", "Gestionar encuentros"),
    ("guardias:gestionar", "Gestionar guardias"),
    ("coloquios:gestionar", "Gestionar coloquios"),
    ("coloquios:ver", "Ver coloquios"),
    ("avisos:publicar", "Publicar avisos"),
    ("tareas:gestionar", "Gestionar tareas"),
    ("estructura:gestionar", "Gestionar estructura academica"),
    ("liquidaciones:ver", "Ver liquidaciones"),
    ("liquidaciones:gestionar", "Gestionar liquidaciones"),
    ("liquidaciones:configurar-salarios", "Configurar grilla salarial"),
    ("auditoria:ver", "Ver panel de auditoria"),
]

# Which roles get which permissions
ROLE_PERM_MATRIX = {
    "ADMIN": [p[0] for p in PERMISSIONS],
    "COORDINADOR": [
        "calificaciones:ver", "comunicacion:enviar", "comunicacion:aprobar",
        "comunicacion:ver", "equipos:gestionar", "encuentros:gestionar",
        "guardias:gestionar", "coloquios:gestionar", "coloquios:ver",
        "avisos:publicar", "tareas:gestionar", "estructura:gestionar",
        "auditoria:ver", "atrasados:ver",
    ],
    "PROFESOR": [
        "calificaciones:importar", "calificaciones:ver",
        "comunicacion:enviar", "comunicacion:ver",
        "encuentros:gestionar", "guardias:gestionar",
        "coloquios:ver", "tareas:gestionar", "atrasados:ver",
    ],
    "TUTOR": [
        "calificaciones:ver", "comunicacion:ver",
        "coloquios:ver", "tareas:gestionar",
    ],
    "FINANZAS": [
        "liquidaciones:ver", "liquidaciones:gestionar",
        "liquidaciones:configurar-salarios", "auditoria:ver",
    ],
    "NEXO": [],
    "ALUMNO": [],
}


async def seed():
    settings = Settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # ── Check if already seeded ─────────────────────────────────
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Tenant).where(Tenant.codigo == "AT"))
        if result.scalar_one_or_none():
            print("⚠️  Tenant 'AT' ya existe. Seed ya ejecutado. Saliendo.")
            return

        # ── Tenant ───────────────────────────────────────────────────
        tenant = Tenant(nombre="activia-trace", codigo="AT")
        session.add(tenant)
        await session.flush()
        tid = tenant.id
        print(f"Tenant creado: {tid}")

        # ── Roles ────────────────────────────────────────────────────
        roles = {}
        for codigo, nombre in ROLES:
            r = Role(tenant_id=tid, codigo=codigo, nombre=nombre)
            session.add(r)
            await session.flush()
            roles[codigo] = r.id
        print(f"Roles creados: {len(roles)}")

        # ── Permissions ──────────────────────────────────────────────
        perms = {}
        for codigo, desc in PERMISSIONS:
            p = Permission(tenant_id=tid, codigo=codigo, descripcion=desc)
            session.add(p)
            await session.flush()
            perms[codigo] = p.id
        print(f"Permisos creados: {len(perms)}")

        # ── Role-Permission ──────────────────────────────────────────
        rp_count = 0
        for role_code, perm_codes in ROLE_PERM_MATRIX.items():
            for pc in perm_codes:
                if pc in perms and role_code in roles:
                    session.add(RolePermission(
                        role_id=roles[role_code],
                        permission_id=perms[pc],
                    ))
                    rp_count += 1
        await session.flush()
        print(f"Role-Permissions creados: {rp_count}")

        # ── Admin user ───────────────────────────────────────────────
        admin = User(
            tenant_id=tid,
            email="admin@activia-trace.com",
            password_hash=hash_password("Admin123!"),
            display_name="Administrador",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        session.add(UserRole(
            user_id=admin.id, role_id=roles["ADMIN"],
            tenant_id=tid, desde=date.today(),
        ))
        print(f"Admin creado: admin@activia-trace.com / Admin123!")

        # ── Demo users ───────────────────────────────────────────────
        prof = User(tenant_id=tid, email="profesor@test.com",
                     password_hash=hash_password("Test123!"), display_name="Juan Profesor",
                     is_active=True)
        tutor = User(tenant_id=tid, email="tutor@test.com",
                      password_hash=hash_password("Test123!"), display_name="Maria Tutora",
                      is_active=True)
        coord = User(tenant_id=tid, email="coordinador@test.com",
                      password_hash=hash_password("Test123!"), display_name="Carlos Coordinador",
                      is_active=True)
        session.add_all([prof, tutor, coord])
        await session.flush()

        session.add(UserRole(user_id=prof.id, role_id=roles["PROFESOR"], tenant_id=tid, desde=date.today()))
        session.add(UserRole(user_id=tutor.id, role_id=roles["TUTOR"], tenant_id=tid, desde=date.today()))
        session.add(UserRole(user_id=coord.id, role_id=roles["COORDINADOR"], tenant_id=tid, desde=date.today()))
        print(f"Demo users: profesor@test.com, tutor@test.com, coordinador@test.com (pass: Test123!)")

        # ── Academic structure ──────────────────────────────────────
        carrera = Carrera(tenant_id=tid, codigo="TUP", nombre="Tecnicatura Univ. en Programacion")
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(tenant_id=tid, carrera_id=carrera.id, nombre="2025-A",
                          anio=2025, vig_desde=date(2025, 1, 1))
        session.add(cohorte)
        await session.flush()

        materias = [
            Materia(tenant_id=tid, codigo="PROG1", nombre="Programacion I", grupo_plus="PROG"),
            Materia(tenant_id=tid, codigo="PROG2", nombre="Programacion II", grupo_plus="PROG"),
            Materia(tenant_id=tid, codigo="BD1", nombre="Base de Datos I", grupo_plus="BD"),
            Materia(tenant_id=tid, codigo="MAT1", nombre="Matematica I", grupo_plus=None),
        ]
        session.add_all(materias)
        await session.flush()
        print(f"Creadas: 1 carrera, 1 cohorte, {len(materias)} materias")

        # ── Asignaciones ────────────────────────────────────────────
        asignaciones = [
            Asignacion(tenant_id=tid, usuario_id=prof.id, rol="PROFESOR",
                       materia_id=materias[0].id, cohorte_id=cohorte.id,
                       comisiones=[], desde=date(2025, 1, 1)),
            Asignacion(tenant_id=tid, usuario_id=prof.id, rol="PROFESOR",
                       materia_id=materias[1].id, cohorte_id=cohorte.id,
                       comisiones=[], desde=date(2025, 1, 1)),
            Asignacion(tenant_id=tid, usuario_id=prof.id, rol="PROFESOR",
                       materia_id=materias[2].id, cohorte_id=cohorte.id,
                       comisiones=[], desde=date(2025, 1, 1)),
            Asignacion(tenant_id=tid, usuario_id=tutor.id, rol="TUTOR",
                       materia_id=materias[0].id, cohorte_id=cohorte.id,
                       comisiones=[], desde=date(2025, 1, 1)),
            Asignacion(tenant_id=tid, usuario_id=admin.id, rol="PROFESOR",
                       materia_id=materias[0].id, cohorte_id=cohorte.id,
                       comisiones=[], desde=date(2025, 1, 1)),
        ]
        session.add_all(asignaciones)
        await session.flush()

        # ── Avisos demo ─────────────────────────────────────────────
        ahora = datetime.now(UTC)
        avisos = [
            Aviso(tenant_id=tid, alcance="Global", severidad="Info",
                  titulo="Bienvenido a activia-trace",
                  cuerpo="Plataforma de gestion academica y trazabilidad.",
                  inicio_en=ahora, fin_en=datetime(2026, 12, 31, tzinfo=UTC),
                  orden=1, activo=True, requiere_ack=False),
            Aviso(tenant_id=tid, alcance="Global", severidad="Advertencia",
                  titulo="Cierre de cuatrimestre",
                  cuerpo="Recuerden cargar las notas finales antes del 30/06.",
                  inicio_en=ahora, fin_en=datetime(2026, 7, 15, tzinfo=UTC),
                  orden=2, activo=True, requiere_ack=True),
        ]
        session.add_all(avisos)
        await session.flush()

        # ── Audit entries demo ─────────────────────────────────────
        for i, accion in enumerate(["LOGIN", "TAREA_CREAR", "AVISO_PUBLICAR", "CALIFICACIONES_IMPORTAR", "LOGIN"]):
            session.add(AuditLog(tenant_id=tid, actor_id=admin.id, accion=accion,
                                 fecha_hora=datetime(2026, 6, 19, 10 + i, 0, 0, tzinfo=UTC),
                                 filas_afectadas=1))

        await session.commit()
        print(f"Asignaciones: {len(asignaciones)}, Avisos: {len(avisos)}, Audit entries: 5")
        print("\n✅ Seed completo!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
