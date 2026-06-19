## Why

C-11 ya detecta atrasados y genera reportes. Sin C-12 el flujo central importar → analizar → comunicar queda trunco: el docente puede saber quién está atrasado pero no puede actuar. Este change cierra el canal de comunicación saliente: preview obligatorio, cola asíncrona, aprobación configurable, tracking de estado. Es el último change del camino crítico (GATE 9) y prerrequisito del frontend docente (C-22).

## What Changes

Nuevo módulo `comunicaciones` completo (modelo, repositorio, servicio, router, worker) más migración 0NN.

- **Modelo `Comunicacion`**: destinatario cifrado, lote_id para agrupar envíos masivos, máquina de estados Pendiente→Enviando→Enviado/Error/Cancelado (RN-15), campos de aprobación (aprobado_por, fecha_aprobacion).
- **Worker asíncrono** (`workers/comunicaciones_worker.py`): consume cola de comunicaciones Pendiente, transiciona a Enviando, envía (SMTP), marca Enviado/Error.
- **Preview obligatorio** (F3.1, RN-16): POST /api/comunicaciones/preview renderiza asunto + cuerpo con variables de sustitución (nombre_alumno, materia, etc.) y requiere confirmación explícita.
- **Envío masivo** (F3.2): encola múltiples destinatarios en un lote con estado Pendiente.
- **Aprobación configurable** (F3.3, RN-17): flag por tenant `requiere_aprobacion_comunicaciones`. Si activo, lote o individual requiere guard `comunicacion:aprobar` para pasar a Enviando.
- **Guard `comunicacion:aprobar`** para aprobadores. **Guard `comunicacion:enviar`** para creadores.
- **Audit** `COMUNICACION_ENVIAR` con lote_id, cantidad de destinatarios, resultado.
- **Migración 0NN**: tabla `comunicacion`.

## Capabilities

### New Capabilities
- `comunicaciones`: Gestión completa de comunicaciones salientes — preview con variables de sustitución, envío masivo asíncrono con cola, máquina de estados (RN-15), aprobación configurable por tenant, tracking por destinatario.

### Modified Capabilities
None

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/comunicacion.py` | New | Modelo `Comunicacion` con tenant_id, destinatario cifrado, estado machine, aprobación |
| `backend/app/repositories/comunicacion_repository.py` | New | CRUD base + consultas por lote, estado, tenant |
| `backend/app/schemas/comunicaciones.py` | New | Pydantic DTOs: crear preview, confirmar envío, aprobar lote, tracking |
| `backend/app/services/comunicacion_service.py` | New | Preview con plantillas, encolado, transición de estados, aprobación |
| `backend/app/api/v1/routers/comunicaciones.py` | New | Endpoints /api/comunicaciones/* con guards |
| `backend/app/workers/comunicaciones_worker.py` | New | Worker async: consume Pendiente→envía SMTP→marca Enviado/Error |
| `backend/app/core/config.py` | Modified | + Config SMTP + flag tenant `requiere_aprobacion_comunicaciones` |
| `backend/app/core/templates/` | New | Directorio con plantillas de comunicación (variables de sustitución) |
| `alembic/versions/XXX_comunicacion.py` | New | Migración 0NN: tabla comunicacion |
