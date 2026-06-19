# Tasks: C-20 Perfil y Mensajeria Interna

## Phase 1: Models & Migration

- [ ] 1.1 Create `backend/app/models/mensaje.py` — `Mensaje` (remitente_id, destinatario_id, asunto, texto, leido, leido_at, soft delete)
- [ ] 1.2 Export in `__init__.py`
- [ ] 1.3 Create `backend/alembic/versions/018_mensaje.py`

## Phase 2: Repos & Schemas

- [ ] 2.1 Create `mensaje_repository.py` — CRUD + list_recibidos, list_enviados
- [ ] 2.2 Create `schemas/perfil_inbox.py` — DTOs

## Phase 3: Service

- [ ] 3.1 Create `services/perfil_inbox_service.py` — perfil (PATCH con CUIL bloqueado), mensajes (enviar, bandeja, leido)

## Phase 4: Router

- [ ] 4.1 Create `routers/perfil_inbox.py` — PATCH/GET perfil, POST/GET inbox
- [ ] 4.2 Wire main.py

## Phase 5: Tests

- [ ] 5.1 Unit + Integration + E2E
- [ ] 5.2 Run all tests, LOC ≤500
