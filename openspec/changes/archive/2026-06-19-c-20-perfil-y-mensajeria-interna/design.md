# Design: C-20 Perfil y Mensajeria Interna

## Context

BAJO governance. Dos funcionalidades simples: edicion de perfil y mensajeria.

## Decisions

### 1. Perfil — PATCH sobre User existente

Campos editables: display_name, datos_fiscales (JSON), regional, modalidad_cobro. CUIL es read-only (se setea en creacion). Validacion: si body incluye CUIL → 422.

### 2. Mensaje — modelo simple

`Mensaje`: remitente_id, destinatario_id, asunto, texto, leido (bool), leido_at. Soft delete. Orden DESC por created_at.

### 3. Endpoints

| Endpoint | Desc |
|----------|------|
| `PATCH /api/perfil` | Editar perfil propio |
| `GET /api/perfil` | Ver perfil propio |
| `POST /api/inbox/enviar` | Enviar mensaje |
| `GET /api/inbox/recibidos` | Bandeja de entrada |
| `GET /api/inbox/enviados` | Mensajes enviados |
| `GET /api/inbox/{id}` | Ver hilo/mensaje |
| `PATCH /api/inbox/{id}/leido` | Marcar como leido |

### 4. Sin permisos especiales

Cualquier usuario autenticado puede usar inbox y editar su perfil. No requiere nuevo permiso.

## File Changes

| File | Action |
|------|--------|
| `app/models/mensaje.py` | Create |
| `app/repositories/mensaje_repository.py` | Create |
| `app/schemas/perfil_inbox.py` | Create |
| `app/services/perfil_inbox_service.py` | Create |
| `app/api/v1/routers/perfil_inbox.py` | Create |
| `app/main.py` | Modify |
| `alembic/versions/018_mensaje.py` | Create |

## Migration 018

Solo `create_table("mensaje")`. Sin seed de permiso.
