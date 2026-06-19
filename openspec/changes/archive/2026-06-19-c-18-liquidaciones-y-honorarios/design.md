# Design: C-18 Liquidaciones y Honorarios

## Context

Épica 10 (F10.1–F10.6) — módulo financiero. CRITICO: maneja importes reales. Cálculo batch por período, cierre inmutable.

## Decisions

### 1. PA-22: grupo_plus en Materia

Se agrega `grupo_plus: String(50) | None` a Materia. El ADMIN asigna cada materia a un grupo (ej: "PROG", "BD"). Null = sin plus. Migration de C-18 incluye `ALTER TABLE materia ADD COLUMN grupo_plus`.

### 2. PA-23: Plus no acumulativo

Un docente recibe **un** plus por `(grupo_plus, rol)` distinto, sin importar cuántas comisiones tenga. El cálculo: `COUNT(DISTINCT grupo_plus)` por asignación activa del docente → sum de SalarioPlus vigentes para esos grupos y su rol.

### 3. Permisos nuevos

| Permiso | Quién | Acceso |
|---------|-------|--------|
| `liquidaciones:ver` | FINANZAS, ADMIN | Vista, historial |
| `liquidaciones:gestionar` | FINANZAS | Cerrar, crear/calcular |
| `liquidaciones:configurar-salarios` | FINANZAS | ABM grilla salarial |

### 4. Cálculo de liquidación

```python
async def calcular_liquidacion(periodo, cohorte_id):
    for docente in docentes_activos(cohorte_id):
        base = salario_base_vigente(docente.rol, periodo)
        grupos = distinct_grupos_plus(docente.asignaciones)
        pluses = sum(salario_plus_vigente(g, docente.rol, periodo) for g in grupos)
        liquidacion = Liquidacion(
            monto_base=base, monto_plus=pluses, total=base + pluses,
            es_nexo=(docente.rol == "NEXO"),
            excluido_por_factura=docente.facturador,
        )
```

### 5. Factura

Modelo separado, soft delete. Estados: Pendiente → Abonada. Docentes con `facturador=True` se excluyen del total de liquidación.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/models/salario_base.py` | Create | SalarioBase (rol, monto, vigencia) |
| `app/models/salario_plus.py` | Create | SalarioPlus (grupo, rol, monto, vigencia) |
| `app/models/liquidacion.py` | Create | Liquidacion (cálculo, estado, segmentación) |
| `app/models/factura.py` | Create | Factura (Pendiente/Abonada) |
| `app/models/materia.py` | Modify | +grupo_plus |
| `app/models/__init__.py` | Modify | Exports |
| `app/repositories/salario_repository.py` | Create | CRUD + vigencia |
| `app/repositories/liquidacion_repository.py` | Create | CRUD + batch |
| `app/repositories/factura_repository.py` | Create | CRUD |
| `app/repositories/__init__.py` | Modify | Exports |
| `app/schemas/liquidaciones.py` | Create | DTOs |
| `app/services/liquidacion_service.py` | Create | Cálculo, cierre, grilla |
| `app/api/v1/routers/liquidaciones.py` | Create | Endpoints |
| `app/main.py` | Modify | Register |
| `alembic/versions/016_liquidaciones.py` | Create | 4 tables + alter materia + seed 3 perms |

## Interfaces

### `POST /api/liquidaciones/calcular`
```json
// Request: {"cohorte_id": "uuid", "periodo": "2025-06"}
// Response 201
{"items": [{"usuario_id": "uuid", "rol": "PROFESOR", "monto_base": 50000, "monto_plus": 15000, "total": 65000, ...}], "total": 10}
```

### `PATCH /api/liquidaciones/{id}/cerrar`
```json
// Response 200 — estado → Cerrada
// Response 409 — ya cerrada
```

### `GET /api/salarios/base`
```json
{"items": [{"rol": "PROFESOR", "monto": 50000, "desde": "2025-01-01", "hasta": null}], "total": 4}
```

### `POST /api/facturas`
```json
// Request: {"usuario_id": "uuid", "periodo": "2025-06", "detalle": "...", "referencia_archivo": "/docs/factura.pdf"}
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Cálculo: base + plus no acumulativo | Pure function |
| Integration | SalarioBase vigente por fecha, SalarioPlus por grupo | seed_data |
| Integration | Liquidación: calcular, cerrar inmutable, excluir facturadores | seed_data |
| E2E | HTTP endpoints, permisos, validación | httpx |

## Migration 016

- 4 tablas: salario_base, salario_plus, liquidacion, factura
- `ALTER TABLE materia ADD COLUMN grupo_plus VARCHAR(50)`
- Seed: 3 permisos `liquidaciones:ver`, `liquidaciones:gestionar`, `liquidaciones:configurar-salarios` para FINANZAS + ADMIN
