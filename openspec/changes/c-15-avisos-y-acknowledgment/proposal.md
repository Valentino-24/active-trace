## Why

C-12 implementó comunicaciones salientes (emails a alumnos). Pero el sistema no tiene un mecanismo interno para que COORDINADOR/ADMIN comuniquen novedades a los docentes: cambios de calendario, recordatorios, circulares. Eso es el tablón de avisos (F3.5).

Sin este change, las comunicaciones internas quedan fuera del sistema (WhatsApp, mail informal). Los avisos con acuse obligatorio permiten trazabilidad institucional.

Depende de C-06 (estructura académica) porque los avisos pueden segmentarse por materia/cohorte.

## What Changes

Nuevo módulo `avisos` con ABM completo, visualización segmentada por audiencia, y acuse de recibo.

### Modelos
- **`Aviso`**: notificación institucional con alcance (Global|PorMateria|PorCohorte|PorRol), severidad (Info|Advertencia|Crítico), ventana de vigencia (inicio_en, fin_en), orden, requiere_ack, activo.
- **`AcknowledgmentAviso`**: registro de confirmación de lectura (aviso_id, usuario_id, confirmado_at).

### Funcionalidades

- **Gestión de avisos** (COORDINADOR/ADMIN, guard `avisos:publicar`):
  - `POST /api/avisos` — crear aviso con alcance, contexto, severidad, vigencia, orden, requiere_ack.
  - `PATCH /api/avisos/{id}` — modificar campos (incluyendo activo/inactivo para publicar/ocultar).
  - `DELETE /api/avisos/{id}` — eliminar aviso (soft delete).
  - `GET /api/avisos` — listado con contadores derivados (vistos, acuses).

- **Visualización por destinatario** (todos los roles autenticados):
  - `GET /api/avisos/mis-avisos` — avisos activos visibles para el usuario actual, filtrados por alcance/rol/cohorte/materia (RN-20), dentro de ventana de vigencia (RN-18), ordenados por `orden`.
  - Si `requiere_ack=true` y el usuario ya acusó, el aviso NO se muestra (o se muestra como leído).

- **Acuse de recibo** (todos los roles):
  - `POST /api/avisos/{id}/ack` — confirma lectura. Crea `AcknowledgmentAviso`. Si el aviso no requiere ack → 409.
  - `GET /api/avisos/{id}/acks` — listado de acuses (solo para COORDINADOR/ADMIN con `avisos:publicar`).

- **Contadores derivados**: `total_vistos` se calcula como count de `AcknowledgmentAviso`; no se denormaliza.

### Transversal
- **Permiso**: `avisos:publicar` (nuevo). Se seedea en migration.
- **Migración 013**: tablas `aviso`, `acknowledgment_aviso`.
- **Audit**: acciones `AVISO_CREAR`, `AVISO_MODIFICAR`, `AVISO_ELIMINAR`, `AVISO_ACK`.

## Capabilities

### New Capabilities
- `avisos`: Tablón de avisos institucionales — ABM con segmentación por audiencia (RN-20), ventana de vigencia (RN-18), acuse de recibo obligatorio (RN-19), contadores derivados.

### Modified Capabilities
None.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/aviso.py` | New | Modelo `Aviso` + enums AlcanceAviso, SeveridadAviso |
| `backend/app/models/acknowledgment_aviso.py` | New | Modelo `AcknowledgmentAviso` |
| `backend/app/repositories/aviso_repository.py` | New | AvisoRepository + AcknowledgmentRepository |
| `backend/app/schemas/avisos.py` | New | Pydantic DTOs: crear, modificar, listar, mis-avisos, ack |
| `backend/app/services/aviso_service.py` | New | Lógica de creación, filtrado por audiencia, ack, contadores |
| `backend/app/api/v1/routers/avisos.py` | New | Endpoints /api/avisos/* |
| `backend/app/main.py` | Modified | Registrar router |
| `backend/alembic/versions/013_avisos.py` | New | Migration: aviso + acknowledgment_aviso + seed permiso |
