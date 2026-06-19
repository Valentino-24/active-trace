# Tasks: C-18 Liquidaciones y Honorarios

## Phase 1: Models & Migration

- [x] 1.1 Modify `backend/app/models/materia.py` — add `grupo_plus` (String(50), nullable)
- [x] 1.2 Create `backend/app/models/salario_base.py` — `SalarioBase` (rol, monto, desde, hasta, soft delete)
- [x] 1.3 Create `backend/app/models/salario_plus.py` — `SalarioPlus` (grupo, rol, monto, desde, hasta, soft delete)
- [x] 1.4 Create `backend/app/models/liquidacion.py` — `Liquidacion` (cohorte_id, periodo, usuario_id, rol, monto_base, monto_plus, total, es_nexo, excluido_por_factura, estado Abierta/Cerrada)
- [x] 1.5 Create `backend/app/models/factura.py` — `Factura` (usuario_id, periodo, detalle, referencia_archivo, estado Pendiente/Abonada, soft delete)
- [x] 1.6 Export new models in `backend/app/models/__init__.py`
- [x] 1.7 Create `backend/alembic/versions/016_liquidaciones.py` — 4 tables + alter materia grupo_plus + seed 3 perms

## Phase 2: Repositories

- [x] 2.1 Create salario repositories — `SalarioBaseRepository` (CRUD, get_vigente) + `SalarioPlusRepository` (CRUD, get_vigentes_por_grupo_rol)
- [x] 2.2 Create `liquidacion_repository.py` — `LiquidacionRepository` (CRUD, batch create, list_por_periodo)
- [x] 2.3 Create `factura_repository.py` — `FacturaRepository` (CRUD, list_con_filtros)
- [x] 2.4 Export in `__init__.py`

## Phase 3: Schemas

- [x] 3.1 Create `backend/app/schemas/liquidaciones.py` — DTOs, all `extra='forbid'`, responses `from_attributes=True`

## Phase 4: Services

- [x] 4.1 Create `backend/app/services/liquidacion_service.py` — calcular_liquidacion (batch), cerrar (inmutable), CRUD grilla salarial, CRUD facturas, audit

## Phase 5: API & Wiring

- [x] 5.1 Create `backend/app/api/v1/routers/liquidaciones.py` — endpoints:
  - Salarios: CRUD /api/salarios/base, /api/salarios/plus
  - Liquidaciones: POST /calcular, GET /, PATCH /{id}/cerrar
  - Facturas: CRUD /api/facturas
- [x] 5.2 Modify `backend/app/main.py` — register router

## Phase 6: Testing

- [x] 6.1 Unit tests: cálculo base + plus (no acumulativo, grupos distintos, sin grupo_plus)
- [x] 6.2 Integration: salario repos (vigencia), liquidacion repo
- [x] 6.3 Integration: service calcular, cerrar inmutable, exclusión facturadores
- [x] 6.4 E2E: HTTP endpoints, permisos, validación
- [x] 6.5 Run all tests, verify LOC ≤500, `extra='forbid'`, no business logic in routers
