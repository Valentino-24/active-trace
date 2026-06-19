## Why

C-01 nos dio el esqueleto ejecutable (FastAPI, DB connection, config, contenedores). Pero no existe ni un solo modelo de datos — no hay `Tenant`, no hay mixin base, no hay repositorio que aisle queries por tenant, no hay soft delete, no hay cifrado. Sin esta base, ningún dominio (auth, RBAC, estructura académica) puede existir. Este change crea el piso de datos sobre el que se construye todo el sistema.

## What Changes

- Modelo **`Tenant`** con campos `id` (UUID), `nombre`, `codigo` único por sistema, `configuracion` (JSONB), `estado` (Activo/Inactivo) y timestamps.
- **Mixin base** `TimeStampedMixin` + `SoftDeleteMixin`: `id` UUID (PK), `tenant_id` (FK → Tenant), `created_at`, `updated_at`, `deleted_at`. Toda entidad del dominio lo hereda.
- **Repository genérico** con scope de tenant **obligatorio por defecto**: todo query filtra por `tenant_id`. Un query sin scope debe fallar en code review. Operaciones: `get`, `list`, `create`, `update`, `soft_delete` (setea `deleted_at`, no borra).
- **Utilidad de cifrado AES-256** (`core/security.py` — reemplaza el placeholder): `encrypt()` / `decrypt()` para atributos PII (CBU, DNI, email). Helper para cifrado/descifrado en reposo con clave desde `ENCRYPTION_KEY`.
- **Alembic Migration 001**: crea tabla `tenant` (primera migración de schema).
- **Reserva** de `models/__init__.py` para que C-03+ solo importen el mixin y creen sus modelos.
- **Tests**: aislamiento multi-tenant (un tenant no ve datos de otro), soft delete (registro existe post-delete), cifrado round-trip, mixin timestamps.

## Capabilities

### New Capabilities

- `tenant-model`: Entidad `Tenant` con atributos, unicidad por código y estado configurable.
- `base-mixin`: Mixin ORM que provee `id` (UUID), `tenant_id`, `created_at`, `updated_at`, `deleted_at` (soft delete) para toda entidad del dominio.
- `base-repository`: Repositorio genérico asíncrono con scope de tenant obligatorio, soft delete y métodos CRUD base.
- `encryption`: Utilidad AES-256 para cifrado de atributos PII en reposo con clave desde configuración.

### Modified Capabilities

<!-- Ninguna: es el primer change con datos del proyecto, no hay specs previos en openspec/specs/. -->

## Impact

- **Backend**: nuevos archivos en `app/models/`, `app/repositories/base.py`, `app/core/security.py` (reemplaza placeholder).
- **Migración**: `alembic/versions/001_crear_tenant.py`.
- **Dependencias**: usa `cryptography` (ya declarada en `pyproject.toml` desde C-01).
- **Tests**: nuevos archivos `tests/test_tenancy.py`, `tests/test_base_repository.py`, `tests/test_encryption.py`.
- **Contrato de extensión**: toda entidad futura debe heredar del mixin; todo repository debe heredar del genérico. Esto se hace explícito en el diseño.
- **Habilita** a C-03 (auth) que necesita `Tenant` y el mixin para su modelo `RefreshToken`.
- **Governance**: CRITICO — toca multi-tenancy, core-models y cifrado. Requiere aprobación humana explícita antes de implementar.
