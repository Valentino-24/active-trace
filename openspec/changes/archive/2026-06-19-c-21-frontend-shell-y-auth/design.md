# Design: C-21 Frontend Shell y Auth

## Context

Primer change de frontend. BAJO governance. Establece la base sobre la que se construyen C-22 a C-24.

## Decisions

### 1. Estructura feature-based

```
frontend/src/
├── features/
│   └── auth/
│       ├── pages/        LoginPage, TwoFactorPage, RecoveryPage
│       ├── components/   LoginForm, TwoFactorForm
│       └── hooks/        useAuth, useLogin
├── shared/
│   ├── services/
│   │   └── api.ts        Axios client + interceptors
│   ├── guards/
│   │   └── ProtectedRoute.tsx
│   ├── contexts/
│   │   └── AuthContext.tsx
│   └── types/
│       └── auth.ts
├── App.tsx
└── main.tsx
```

### 2. Auth flow

1. Login → POST /api/auth/login → access_token + refresh_token
2. Access token en header `Authorization: Bearer <token>`
3. Interceptor: 401 → intenta refresh con /api/auth/refresh
4. Si refresh falla → redirect a /login
5. AuthContext expone: user, roles, permissions, isAuthenticated

### 3. ProtectedRoute

```tsx
<ProtectedRoute permission="calificaciones:importar">
  <CalificacionesPage />
</ProtectedRoute>
```

Verifica: sesion activa → permisos del usuario → 403 si no tiene.

### 4. Sidebar/Layout

Menu items visibles segun `user.permissions`. Roles admin ven todo, coordinador ve modulos de gestion, profesor ve herramientas academicas.

## Dependencies

Backend C-03 (login, refresh, 2FA) y C-04 (RBAC, permisos).

## Testing

Tests unitarios con vitest + @testing-library/react. Mock de axios. Login flow, guard, refresh interceptor.
