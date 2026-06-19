# Proposal: Panel de Auditoria y Metricas

## Intent

Exponer el `AuditLog` como panel de analytics: volumen diario, metricas por docente, ultimas acciones y log completo con filtros. Hoy los datos se escriben pero no se consultan.

## Scope

### In Scope
- 4 endpoints read-only sobre AuditLog existente
- Agregaciones: GROUP BY fecha/dia, GROUP BY actor_id, GROUP BY accion
- Scope COORDINADOR: ve solo sus propias acciones
- Permiso `auditoria:ver` (ADMIN, COORDINADOR)

### Out of Scope
- Graficos/visualizaciones (frontend C-23)
- Alertas/notificaciones basadas en auditoria
- Export CSV (futuro)

## Capabilities

### New Capabilities
- `auditoria`: Panel de metricas y log completo de auditoria (read-only)

### Modified Capabilities
None — no se modifican modelos ni specs existentes.

## Approach

Queries de agregacion directa sobre AuditLog (mismo patron C-11 analisis). Sin modelos nuevos. Migracion solo seedea permiso.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/repositories/audit_log_repository.py` | Modified | +metodos de agregacion |
| `app/services/auditoria_service.py` | New | Logica de scope + queries |
| `app/schemas/auditoria.py` | New | DTOs |
| `app/api/v1/routers/auditoria.py` | New | 4 endpoints |
| `app/main.py` | Modified | Register |
| `alembic/versions/017_auditoria.py` | New | Seed permiso + indice |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| GROUP BY lento en tabla grande | Med | Indice compuesto en migracion |
| Scope COORDINADOR mal aplicado | Bajo | Test dedicado |

## Rollback

Eliminar archivos nuevos, revertir main.py, `alembic downgrade 016`.

## Dependencies

C-05 audit-log, C-07 usuarios-y-asignaciones

## Success Criteria

- [ ] 4 endpoints con agregaciones y filtros
- [ ] Scope COORDINADOR (solo propias acciones)
- [ ] Permiso `auditoria:ver` seedeado
- [ ] ≥15 tests
