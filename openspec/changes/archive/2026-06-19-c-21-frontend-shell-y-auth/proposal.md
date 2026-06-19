# Proposal: Frontend Shell y Auth (C-21)

## Intent

Crear la SPA React que consume el backend ya construido. Shell con login, 2FA, proteccion de rutas por permiso, refresh transparente de JWT, y layout adaptado al rol.

## Scope

### In Scope
- Vite + React 18 + TypeScript scaffold
- Cliente Axios con interceptor de auth + refresh transparente
- AuthContext: login, 2FA, logout, estado de sesion
- Login page, 2FA page, password recovery
- ProtectedRoute con guard por permiso `modulo:accion`
- Layout con sidebar adaptado a permisos del rol

### Out of Scope
- Features de dominio (C-22 a C-24)
- E2E tests (Playwright — no disponible en este entorno)
- Deploy (C-24)

## Capabilities

### New
- `frontend-shell`: SPA shell con auth, routing protegido, layout

### Modified
None

## Approach

Feature-based: `features/auth/{pages,components,hooks,services}`, `shared/services/api` (axios client), `shared/guards/ProtectedRoute`. Tailwind + TanStack Query + Zod.

## Dependencies
C-04 (RBAC), C-03 (auth JWT)

## Success Criteria
- [ ] Login funcional contra /api/auth/login
- [ ] Token se refresca automaticamente al expirar
- [ ] Rutas protegidas redirigen a login sin sesion
- [ ] Sidebar muestra solo modulos del rol
