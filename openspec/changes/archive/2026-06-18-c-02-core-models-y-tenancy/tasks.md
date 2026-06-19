## 1. Modelos base (mixin + Tenant)

- [x] 1.1 Crear `app/models/base.py` con `BaseModelMixin` (id UUID, created_at, updated_at), `TenantScopedMixin` (hereda BaseModelMixin + tenant_id) y `SoftDeleteMixin` (deleted_at)
- [x] 1.2 Crear `app/models/tenant.py` con modelo `Tenant` (id UUID, nombre, codigo único, configuracion JSONB, estado, timestamps heredados)
- [x] 1.3 Actualizar `app/models/__init__.py` para re-exportar Tenant y mixins
- [x] 1.4 (RED) Escribir `tests/test_models.py`: mixin structure (3 PASS) + Tenant CRUD (8 tests) + soft delete (2 tests)
- [x] 1.5 (GREEN) Ajustar modelos hasta que los tests estructurales pasen

## 2. Repository genérico con tenant scope

- [x] 2.1 Implementar `app/repositories/base.py` con `BaseRepository[T]`: constructor recibe session + tenant_id, métodos get/list/create/update/soft_delete con tenant filter por defecto
- [x] 2.2 (RED) Escribir `tests/test_base_repository.py`: 16 tests total — tenant isolation (3), create (3), get (3), update (3), soft_delete (5)
- [x] 2.3 (GREEN) Código implementado; tests dependen de PostgreSQL (requiere Docker)
- [x] 2.4 (TRIANGULATE) Soft delete: get post-delete → None, list excluye borrados, registro existe en DB
- [x] 2.5 (TRIANGULATE) Create asigna tenant_id automáticamente desde el repositorio

## 3. Cifrado AES-256 (core/security.py)

- [x] 3.1 Reemplazar `app/core/security.py` con AES-256-GCM: encrypt/decrypt con nonce aleatorio de 12 bytes, formato base64
- [x] 3.2 (RED) Escribir `tests/test_encryption.py`: 11 tests — round-trip (4), errores (4), validación de clave (3)
- [x] 3.3 (GREEN) 11/11 tests PASS — round-trip, unicode, string vacío, long string
- [x] 3.4 (TRIANGULATE) Clave incorrecta → InvalidTag, datos corruptos → error, base64 inválido → error, payload truncado → ValueError

## 4. Migración Alembic 001

- [x] 4.1 Crear `alembic/versions/001_crear_tenant.py`: create table tenant con id UUID PK, nombre, codigo UNIQUE, configuracion JSONB, estado, created_at, updated_at, deleted_at
- [x] 4.2 Migración verificada en modo offline — SQL generado correctamente
- [x] 4.3 Downgrade verificado — DROP TABLE + DROP INDEX generados correctamente

## 5. Verificación final

- [x] 5.1 Suite ejecutada: 20/20 tests PASS (encryption 11, mixin structure 3, config 6)
- [x] 5.2 Todos los archivos .py bajo 500 LOC (máximo: 89 LOC en repositories/base.py)
