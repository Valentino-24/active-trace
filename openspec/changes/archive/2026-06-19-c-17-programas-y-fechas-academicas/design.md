# Design: C-17 Programas y Fechas Academicas

## Context

C-06 ya proveyo Materia, Carrera y Cohorte con sus endpoints admin. C-17 agrega dos entidades delgadas que referencian esas tres: ProgramaMateria (documento) y FechaAcademica (calendario evaluativo). Ambas son CRUD simple, catalogos sin logica de negocio compleja. Governance BAJO.

## Decisions

### 1. Modelos con triple FK: materia + carrera + cohorte

ProgramaMateria referencia materia_id + carrera_id + cohorte_id (un programa es para UNA materia en UNA carrera en UNA cohorte). FechaAcademica referencia materia_id + cohorte_id (una fecha de parcial es para UNA materia en UNA cohorte — la carrera se infiere de la cohorte).

### 2. TipoFecha enum: Parcial | TP | Coloquio | Recuperatorio

El diseno KB ya define estos 4 valores. Se usa `String(20)` con enum Python.

### 3. Referencia de archivo opaca

`referencia_archivo` es un `String(500)` que guarda la ruta o URL al documento. MVP: sin upload real, sin validacion de formato.

### 4. Permiso `estructura:gestionar` (reutilizado)

No se crea nuevo permiso. C-06 ya sembro `estructura:gestionar` para COORDINADOR y ADMIN. Ambos modulos lo usan.

### 5. Filtros en fechas-academicas

`GET /api/fechas-academicas` soporta query params: `materia_id`, `cohorte_id`, `tipo`, `periodo`. Combinables con AND.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/programa_materia.py` | Create | ProgramaMateria |
| `backend/app/models/fecha_academica.py` | Create | FechaAcademica + TipoFecha enum |
| `backend/app/models/__init__.py` | Modify | Export |
| `backend/app/repositories/programa_repository.py` | Create | CRUD Programa |
| `backend/app/repositories/fecha_repository.py` | Create | CRUD + filtros Fecha |
| `backend/app/repositories/__init__.py` | Modify | Export |
| `backend/app/schemas/programas_fechas.py` | Create | DTOs |
| `backend/app/services/programa_fecha_service.py` | Create | Service |
| `backend/app/api/v1/routers/programas_fechas.py` | Create | Router |
| `backend/app/main.py` | Modify | Register |
| `backend/alembic/versions/015_programas_fechas.py` | Create | Migration |

## Interfaces

### `POST /api/programas`
```json
// Request
{"materia_id": "uuid", "carrera_id": "uuid", "cohorte_id": "uuid", "titulo": "Programa 2025", "referencia_archivo": "/docs/prog1-2025.pdf"}
// Response 201
{"id": "uuid", "materia_id": "uuid", "titulo": "...", "cargado_at": "..."}
```

### `GET /api/programas?materia_id=X&cohorte_id=Y`
```json
{"items": [{"id": "uuid", "titulo": "...", "referencia_archivo": "...", "cargado_at": "..."}], "total": 3}
```

### `POST /api/fechas-academicas`
```json
// Request
{"materia_id": "uuid", "cohorte_id": "uuid", "tipo": "Parcial", "numero": 1, "periodo": "2025-1", "fecha": "2025-05-15", "titulo": "1er Parcial"}
```

### `GET /api/fechas-academicas?materia_id=X&tipo=Parcial&periodo=2025-1`
```json
{"items": [...], "total": 2}
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Enums, schema validation | Pure functions |
| Integration | Repo CRUD, filtros | seed_data fixture |
| E2E | HTTP endpoints, permisos, validacion | httpx AsyncClient |

## Migration 015

- `down_revision = "014"`
- `create_table("programa_materia")`: id, tenant_id, materia_id, carrera_id, cohorte_id, titulo, referencia_archivo, timestamps, deleted_at
- `create_table("fecha_academica")`: id, tenant_id, materia_id, cohorte_id, tipo, numero, periodo, fecha, titulo, timestamps, deleted_at
- FKs: materia, carrera, cohorte
- Indices: materia+cohorte, periodo
- Sin seed de permiso nuevo (reusa `estructura:gestionar`)
