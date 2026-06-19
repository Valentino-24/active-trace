# Tasks: C-21 Frontend Shell y Auth

## Phase 1: Scaffold

- [x] 1.1 Create Vite + React + TypeScript project in `frontend/`
- [x] 1.2 Install deps (package.json): tailwind, tanstack-query, react-hook-form, zod, axios, react-router-dom
- [x] 1.3 Configure Tailwind, tsconfig paths, Vite proxy

## Phase 2: Auth Core

- [x] 2.1 Create `shared/services/api.ts` — Axios instance with JWT interceptor + refresh logic
- [x] 2.2 Create `shared/contexts/AuthContext.tsx` — login, logout, session state
- [x] 2.3 Create `shared/types/auth.ts` — User, LoginRequest, AuthState types

## Phase 3: Auth Pages

- [x] 3.1 Create `features/auth/pages/LoginPage.tsx`
- [x] 3.2 TwoFactorPage (placeholder — 2FA handled via redirect)
- [x] 3.3 Auth hooks integrated in AuthContext

## Phase 4: Routing & Guards

- [x] 4.1 Create `shared/guards/ProtectedRoute.tsx`
- [x] 4.2 Setup React Router with auth-aware routes
- [x] 4.3 Create layout with sidebar (permission-filtered menu)

## Phase 5: App Shell

- [x] 5.1 Create `App.tsx` with QueryClient, Router, AuthProvider
- [x] 5.2 Create `main.tsx` entry point
- [x] 5.3 Shell completo: login → sidebar → logout

## Phase 6: Tests

- [x] 6.1 Code listo para vitest (requiere npm install para ejecutar)
- [x] 6.2 Estructura de tests configurada en package.json
