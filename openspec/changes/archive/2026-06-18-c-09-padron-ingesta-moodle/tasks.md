## 1. Migración de base de datos (008)

- [x] 1.1 Crear `008_version_padron_entrada_padron.py`: tabla `version_padron` (id, tenant_id, materia_id, cohorte_id, cargado_por, cargado_at, activa, modo, created_at, updated_at, deleted_at)
- [x] 1.2 Crear tabla `entrada_padron` (id, version_id, tenant_id, usuario_id nullable, nombre, apellidos, email_cifrado, email_hash, comision, regional, created_at, updated_at, deleted_at)
- [x] 1.3 Agregar índices: ix_entrada_padron_version_id, ix_version_padron_materia_cohorte_activa

## 2. Modelos SQLAlchemy

- [x] 2.1 Crear `VersionPadron` model con TenantScopedMixin, SoftDeleteMixin, columnas: materia_id, cohorte_id, cargado_por, cargado_at, activa, modo
- [x] 2.2 Crear `EntradaPadron` model con TenantScopedMixin, SoftDeleteMixin, columnas: version_id, usuario_id (nullable), nombre, apellidos, email_cifrado, email_hash, comision, regional
- [x] 2.3 Agregar relationships: VersionPadron.entradas, VersionPadron.cargado_por (User), EntradaPadron.usuario (User, nullable)

## 3. Schemas Pydantic

- [x] 3.1 Crear `backend/app/schemas/padron.py`: VersionPadronResponse, VersionPadronListResponse, EntradaPadronResponse, PreviewRow, PreviewResponse, ImportRequest, ImportResponse, MoodleSyncRequest, VaciarResponse

## 4. Integración Moodle WS

- [x] 4.1 Crear `backend/app/integrations/__init__.py`
- [x] 4.2 Crear `backend/app/integrations/moodle_ws.py`: clase `MoodleClient` async con httpx, métodos `sync_alumnos(materia_id, cohorte_id)`, timeout configurable, 3 reintentos con backoff, errores mapean a HTTPException 502

## 5. Repositorio padron

- [x] 5.1 Crear `backend/app/repositories/padron_repository.py`: VersionPadronRepository con create_version, deactivate_previous, list_versiones, get_version_detail, soft_delete_by_materia
- [x] 5.2 Crear `EntradaPadronRepository` con bulk_create_from_import, list_entradas_by_version, match_by_email_hash, soft_delete_by_materia
- [x] 5.3 Implementar `match_by_email_hash()`: busca usuarios por email_hash, asigna usuario_id si matchea

## 6. Router padron

- [x] 6.1 Crear `backend/app/api/v1/routers/padron.py` con prefijo `/api/padron` y tag "padron"
- [x] 6.2 Implementar `POST /api/padron/moodle-sync` protegido con `padron:importar`
- [x] 6.3 Implementar `POST /api/padron/preview` protegido con `padron:importar` (parseo de archivo, devuelve preview sin persistir)
- [x] 6.4 Implementar `POST /api/padron/import` protegido con `padron:importar` (crea version + entradas, transaccional)
- [x] 6.5 Implementar `DELETE /api/padron/materia/{materia_id}` protegido con `padron:importar` (scope: PROFESOR=suyas, COORDINADOR/ADMIN=todas)
- [x] 6.6 Implementar `GET /api/padron/versiones` protegido con `padron:importar` (filtros materia_id, cohorte_id)
- [x] 6.7 Implementar `GET /api/padron/versiones/{version_id}` protegido con `padron:importar` (detalle con entradas paginadas)
- [x] 6.8 Registrar router en `main.py`

## 7. Permisos y seed

- [x] 7.1 Agregar permiso `padron:importar` al seed de permisos (módulo `padron`)
- [x] 7.2 Asignar `padron:importar` a los roles PROFESOR, COORDINADOR y ADMIN

## 8. Tests

- [x] 8.1 Test de `POST /api/padron/moodle-sync`: sync exitoso, error si Moodle no configurado, error 502 si Moodle falla
- [x] 8.2 Test de `POST /api/padron/preview`: preview de CSV/xlsx, errores de parseo por fila, archivo malformado
- [x] 8.3 Test de `POST /api/padron/import`: import exitoso con y sin match de usuario, versión anterior se desactiva
- [x] 8.4 Test de `DELETE /api/padron/materia/{materia_id}`: vaciado exitoso, scope PROFESOR (solo sus datos), scope COORDINADOR (todos los datos)
- [x] 8.5 Test de `GET /api/padron/versiones`: listado con filtros, paginación
- [x] 8.6 Test de `GET /api/padron/versiones/{version_id}`: detalle con entradas, email no expuesto
- [x] 8.7 Test de permisos: usuario sin `padron:importar` recibe 403
- [x] 8.8 Test de multi-tenancy: datos de tenant A no visibles en tenant B
