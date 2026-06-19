## 1. Modelos

- [x] 1.1 Crear `backend/app/models/carrera.py` con modelo `Carrera` (Base, TenantScopedMixin, SoftDeleteMixin): campos `codigo`, `nombre`, `estado`. Unicidad `(tenant_id, codigo)`.
- [x] 1.2 Crear `backend/app/models/cohorte.py` con modelo `Cohorte` (Base, TenantScopedMixin, SoftDeleteMixin): campos `carrera_id` (FK), `nombre`, `anio`, `vig_desde`, `vig_hasta`, `estado`. Unicidad `(tenant_id, carrera_id, nombre)`.
- [x] 1.3 Crear `backend/app/models/materia.py` con modelo `Materia` (Base, TenantScopedMixin, SoftDeleteMixin): campos `codigo`, `nombre`, `estado`. Unicidad `(tenant_id, codigo)`.
- [x] 1.4 Crear `backend/app/models/dictado.py` con modelo `Dictado` (Base, TenantScopedMixin, SoftDeleteMixin): campos `materia_id` (FK), `carrera_id` (FK), `cohorte_id` (FK), `estado`. Unicidad `(tenant_id, materia_id, carrera_id, cohorte_id)`.
- [x] 1.5 Agregar re-exports de todos los modelos en `backend/app/models/__init__.py`.

## 2. Repositorios

- [x] 2.1 Crear `backend/app/repositories/carrera_repository.py` con `CarreraRepository(BaseRepository[Carrera])`. Método adicional `get_by_codigo(codigo)`.
- [x] 2.2 Crear `backend/app/repositories/cohorte_repository.py` con `CohorteRepository(BaseRepository[Cohorte])`. Método adicional `list_by_carrera(carrera_id)`.
- [x] 2.3 Crear `backend/app/repositories/materia_repository.py` con `MateriaRepository(BaseRepository[Materia])`. Método adicional `get_by_codigo(codigo)`.
- [x] 2.4 Crear `backend/app/repositories/dictado_repository.py` con `DictadoRepository(BaseRepository[Dictado])`. Método adicional `list_by_materia(materia_id)` y `list_by_cohorte(cohorte_id)`.
- [x] 2.5 Agregar re-exports en `backend/app/repositories/__init__.py`.

## 3. Schemas Pydantic

- [x] 3.1 Crear schemas request/response para Carrera en un archivo compartido o inline en el router: `CarreraCreate`, `CarreraUpdate`, `CarreraResponse`, `CarreraListResponse`.
- [x] 3.2 Crear schemas para Cohorte: `CohorteCreate`, `CohorteUpdate`, `CohorteResponse`, `CohorteListResponse`.
- [x] 3.3 Crear schemas para Materia: `MateriaCreate`, `MateriaUpdate`, `MateriaResponse`, `MateriaListResponse`.
- [x] 3.4 Crear schemas para Dictado: `DictadoCreate`, `DictadoUpdate`, `DictadoResponse`, `DictadoListResponse`.

## 4. Endpoints

- [x] 4.1 Crear `backend/app/api/v1/routers/admin/__init__.py` con sub-routers para admin.
- [x] 4.2 Crear `backend/app/api/v1/routers/admin/carreras.py` con CRUD completo (`GET /, POST /, GET /{id}, PUT /{id}, DELETE /{id}`) y guard `estructura:gestionar`.
- [x] 4.3 Crear `backend/app/api/v1/routers/admin/cohortes.py` con CRUD completo + query param `carrera_id` para filtrado. Validar que carrera esté activa al crear.
- [x] 4.4 Crear `backend/app/api/v1/routers/admin/materias.py` con CRUD completo y guard `estructura:gestionar`.
- [x] 4.5 Crear `backend/app/api/v1/routers/admin/dictados.py` con CRUD completo + query params `materia_id`, `cohorte_id` para filtrado. Validar materia/carrera activas al crear.
- [x] 4.6 Registrar los routers en `backend/app/main.py` bajo prefijo `/api/admin`.

## 5. Migración Alembic 005

- [x] 5.1 Crear migración `005_crear_estructura_academica.py` con tablas `carrera`, `cohorte`, `materia`, `dictado`. FKs y unique constraints. `down_revision = "004"`.
- [x] 5.2 Verificar que la migración corre y revierte correctamente.

## 6. Tests

- [x] 6.1 Crear `tests/test_carreras_api.py` con tests CRUD: crear, listar, obtener por ID, actualizar, soft-delete, unicidad código por tenant, aislamiento multi-tenant.
- [x] 6.2 Crear `tests/test_cohortes_api.py` con tests CRUD: crear, listar (con y sin filtro carrera_id), crear en carrera inactiva (400), unicidad nombre por (tenant, carrera), aislamiento multi-tenant, cerrar cohorte.
- [x] 6.3 Crear `tests/test_materias_api.py` con tests CRUD: crear, listar, actualizar, desactivar, unicidad código por tenant.
- [x] 6.4 Crear `tests/test_dictados_api.py` con tests CRUD: crear, listar (con filtros), crear con materia/carrera inactiva (400), duplicado (409), cerrar dictado, aislamiento multi-tenant.
