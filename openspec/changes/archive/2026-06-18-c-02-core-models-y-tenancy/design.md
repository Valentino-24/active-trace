## Context

C-01 dejó el esqueleto del backend con `core/database.py` (engine async, Base declarativa, session factory), `core/config.py` (Settings), y placeholders en `core/security.py` y `core/tenancy.py`. El modelo de datos no existe: no hay `Tenant`, no hay mixin base, no hay repositorio con scope de tenant. C-02 construye ese piso.

El contrato de dominio (knowledge-base + docs) establece:
- ADR-002 cerrada: multi-tenancy row-level, columna `tenant_id` en toda tabla.
- Toda entidad tiene UUID como PK, timestamps de creación/actualización, y soft delete.
- Atributos PII (`[cifrado]`) deben almacenarse cifrados con AES-256.
- El repositorio filtra por tenant por defecto; un query sin scope es un bug.

Este change implementa esos contratos en código, reemplazando los placeholders de C-01.

## Goals / Non-Goals

**Goals:**
- Modelo `Tenant` como entidad raíz con atributos del dominio.
- Mixin base ORM que toda entidad hereda: `id` (UUID), `tenant_id`, `created_at`, `updated_at`, `deleted_at`.
- Repository genérico async con scope de tenant obligatorio y CRUD base (get, list, create, update, soft_delete).
- Utilidad AES-256 para cifrar/descifrar atributos PII en reposo.
- Alembic migration 001: crear tabla `tenant`.
- Tests de aislamiento multi-tenant, soft delete, cifrado round-trip.
- Reemplazar placeholder `core/security.py` con la implementación real de cifrado.

**Non-Goals:**
- Modelos de dominio específicos (Carrera, Cohorte, Materia → C-06; Usuario → C-07).
- Auth, JWT, Argon2id, 2FA, refresh rotation (→ C-03).
- RBAC, matriz de permisos, `require_permission` (→ C-04).
- Datos de seed (el tenant inicial se crea vía migración o setup script, no en C-02).

## Decisions

### D1 — Ubicación del mixin base y Tenant

```
app/
├── models/
│   ├── __init__.py          # re-exporta Tenant y mixins
│   ├── base.py              # TimeStampedMixin, SoftDeleteMixin
│   └── tenant.py            # Modelo Tenant
├── repositories/
│   ├── __init__.py
│   └── base.py              # BaseRepository genérico
├── core/
│   ├── security.py          # AES-256 encrypt/decrypt (reemplaza placeholder)
│   └── tenancy.py           # get_tenant_context() → dependency (reservado parcial)
```

Se separa `models/base.py` del `core/` para mantener la separación de capas: los mixins son del dominio (models), no de infraestructura (core).

**Alternativa descartada**: poner mixins en `core/database.py`. Se descarta porque mezcla responsabilidades — `database.py` es infraestructura (engine, session), no dominio.

### D2 — Estructura del mixin base

```python
class TimeStampedMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("tenant.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

El soft delete se separa como mixin aparte porque no todas las entidades necesariamente lo usan (ej: AuditLog es append-only sin delete). Sin embargo, por regla del proyecto (regla dura #13), **toda entidad de dominio usa soft delete**.

Se usa `server_default=func.now()` para timestamps manejados por la DB (consistente entre réplicas, evita desvíos de reloj de la app).

### D3 — Repository genérico con tenant scope

```python
class BaseRepository[T: TimeStampedMixin]:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self._session = session
        self._tenant_id = tenant_id  # Inyectado, nunca de un parámetro de request

    def _stmt(self) -> Select:
        """Base statement with tenant filter. Override in subclasses."""
        return select(self._model_cls).where(
            self._model_cls.tenant_id == self._tenant_id
        )

    async def get(self, id: uuid.UUID) -> T | None:
        stmt = self._stmt().where(self._model_cls.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, **filters) -> Sequence[T]:
        stmt = self._stmt()
        # ... apply filters
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, **data) -> T:
        instance = self._model_cls(**data, tenant_id=self._tenant_id)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def soft_delete(self, id: uuid.UUID) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(UTC)
        await self._session.flush()
        return True
```

El `tenant_id` se inyecta en el constructor del repository, NO se pasa por parámetro en cada método. Esto garantiza que ningún método "olvide" filtrar.

**Alternativa descartada**: pasar `tenant_id` como decorador de query. Se descarta porque la inyección en constructor es más explícita y el type safety del genérico evita errores.

### D4 — Cifrado AES-256 en core/security.py

Se usa `cryptography` (ya declarada en pyproject.toml desde C-01) con AES-256-GCM:
- **GCM** provee autenticación integrada (detección de manipulación).
- `ENCRYPTION_KEY` se deriva con PBKDF2 para obtener una clave de 256 bits.
- Cada cifrado genera un nonce aleatorio de 12 bytes, almacenado junto al ciphertext.
- Formato de salida: base64(nonce + ciphertext + tag).

```python
def encrypt(plaintext: str, key: bytes) -> str:
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ciphertext = cipher.update(plaintext.encode()) + cipher.finalize()
    return base64.b64encode(nonce + ciphertext + cipher.tag).decode()

def decrypt(ciphertext_b64: str, key: bytes) -> str:
    raw = base64.b64decode(ciphertext_b64)
    nonce, ciphertext, tag = raw[:12], raw[12:-16], raw[-16:]
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).decryptor()
    plaintext = cipher.update(ciphertext) + cipher.finalize_with_tag(tag)
    return plaintext.decode()
```

**Alternativa descartada**: Fernet (simétrico simple). Se descarta porque Fernet usa AES-128-CBC + HMAC, mientras que AES-256-GCM es requerimiento del stack.

### D5 — Estrategia de tests

- **Base real de PostgreSQL** (vía fixture `db_engine` + `db_session` de C-01), nunca mocks de DB (regla dura #4).
- Tests de aislamiento: crear dos tenants, insertar datos en cada uno, verificar que el repository de un tenant no ve datos del otro.
- Tests de soft delete: `get` post-delete devuelve `None`; `list` no incluye borrados; el registro existe en DB.
- Tests de cifrado: round-trip (encrypt → decrypt = original), con clave incorrecta falla, con datos corruptos falla.
- Tests de timestamps: `created_at` y `updated_at` se setean automáticamente.

### D6 — Migración 001

Única migración de C-02: crear tabla `tenant`. Se implementa como migración Alembic convencional (no autogenerate inicial) para que el schema refleje exactamente lo que define el modelo.

```python
# 001_crear_tenant.py
def upgrade():
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("codigo", sa.String(50), nullable=False),
        sa.Column("configuracion", sa.JSONB(), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False, server_default="activo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_index(op.f("ix_tenant_codigo"), "tenant", ["codigo"])
```

## Risks / Trade-offs

- **[Repository genérico con genéricos de Python (T)]** → Mitigación: se usa `TypeVar` con bound al mixin. El type checker (mypy/pyright) valida que los tipos sean correctos en cada repositorio concreto.
- **[AES-256-GCM nonce único por operación]** → Mitigación: `os.urandom(12)` garantiza nonce criptográficamente aleatorio. El riesgo de re-uso de nonce con la misma clave es despreciable.
- **[Timestamps con server_default pueden diferir del reloj de la app]** → Trade-off aceptado: la consistencia entre réplicas pesa más que la micro-diferencia. El timestamp de la app se usa para logs, no para lógica de negocio.
- **[Tenant creado en migración (seed) vs setup externo]** → Decisión: no se incluye seed en C-02. El primer tenant se crea mediante un script de setup o migración de datos en deploy. Esto mantiene C-02 puro (solo schema + modelo).

## Migration Plan

1. Ejecutar `alembic upgrade head` → crea tabla `tenant`.
2. Crear tenant inicial vía script de bootstrap (fuera de C-02).
3. Los changes siguientes (C-03+) ejecutan sus propias migraciones que agregan `tenant_id` FK.

Rollback: `alembic downgrade -1` elimina la tabla `tenant`. Sin datos en producción al ser el primer change de datos, el rollback es seguro.

## Open Questions

- **Seed del tenant inicial**: ¿migración de datos con Alembic, script Python separado, o endpoint `/setup`? Se decide en apply. Recomendación: script separado `scripts/bootstrap_tenant.py` para no mezclar schema con datos.
- **Cache de `ENCRYPTION_KEY`**: ¿cargar en el arranque y mantener en memoria, o leer en cada encrypt/decrypt? Recomendación: cargar al iniciar Settings y pasar la clave derivada como dependencia.
