# Proposal: Liquidaciones y Honorarios

## Intent

Calcular, visualizar y cerrar honorarios docentes por período. Administrar grilla salarial (base + plus) y gestionar facturas de docentes monotributistas. Hoy no existe — es plataforma manual con planillas Excel.

## Scope

### In Scope
- `SalarioBase` (monto por rol con vigencia) y `SalarioPlus` (plus por grupo × rol con vigencia)
- `Liquidacion`: cálculo por período = base vigente + plus por grupos únicos (no acumulativo)
- `Factura`: comprobantes de docentes que facturan, excluidos de liquidación general
- Cierre inmutable (RN-22), segmentación NEXO/factura (F10.6)
- `grupo_plus` opcional en Materia (migration en C-18)

### Out of Scope
- Pago efectivo / transferencia bancaria
- Integración con AFIP/factura electrónica
- Dashboard/KPIs visuales (frontend C-23)

## Capabilities

### New Capabilities
- `salarios`: CRUD de grilla salarial (base + plus) con vigencia
- `liquidaciones`: cálculo, vista, cierre e historial
- `facturas`: ABM de comprobantes de docentes facturadores

### Modified Capabilities
- `materias`: agregar campo `grupo_plus` (String, nullable)

## Approach

4 modelos con FK a User, Cohorte, Materia. Cálculo batch: `count_distinct(grupo_plus)` por docente → base + ∑plus. Permisos `liquidaciones:*` para FINANZAS/ADMIN. Cierre con `estado=Cerrada`, validación de inmutabilidad en service.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/models/salario_base.py` | New | SalarioBase |
| `app/models/salario_plus.py` | New | SalarioPlus |
| `app/models/liquidacion.py` | New | Liquidacion |
| `app/models/factura.py` | New | Factura |
| `app/models/materia.py` | Modified | +grupo_plus |
| `app/models/__init__.py` | Modified | Exports |
| `app/repositories/` | New | 4 repos |
| `app/schemas/liquidaciones.py` | New | DTOs |
| `app/services/liquidacion_service.py` | New | Cálculo + CRUD |
| `app/api/v1/routers/liquidaciones.py` | New | Endpoints |
| `app/main.py` | Modified | Register |
| `alembic/versions/016_liquidaciones.py` | New | 4 tables + alter materia + seed perms |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cálculo incorrecto de plus | Med | Tests exhaustivos: 0 grupos, 1 grupo, N grupos distintos |
| Cierre inmutable violado | Bajo | Validación en service, test dedicado |
| grupo_plus null rompe cálculo | Bajo | `COALESCE` o filtrar nulls en query |

## Rollback

`alembic downgrade 015`. Eliminar archivos. Revertir `__init__.py` y `main.py`. Quitar `grupo_plus` de Materia.

## Dependencies

- C-07 usuarios-y-asignaciones, C-06 estructura-academica, C-13 encuentros-y-guardias, C-14 evaluaciones-y-coloquios

## Success Criteria

- [ ] 4 modelos con soft delete
- [ ] Cálculo: base vigente + sum(plus por grupo_plus distinto)
- [ ] Cierre inmutable (409 si ya cerrada)
- [ ] Facturas excluidas del total de liquidación
- [ ] 3 permisos nuevos: `liquidaciones:ver`, `liquidaciones:gestionar`, `liquidaciones:configurar-salarios`
- [ ] ≥25 tests, LOC ≤500
