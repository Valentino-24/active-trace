## Why

C-07 ya modeló el equipo docente (asignaciones, roles). C-10 y C-11 completaron calificaciones y análisis. C-12 cerró comunicaciones. El próximo paso natural es habilitar la gestión de encuentros sincrónicos (clases virtuales) y el registro de guardias.

Sin este change, el sistema llega hasta "detectar atrasados y comunicar" pero no cubre la operación diaria del docente: planificar sus clases, registrar qué se dio y cuándo, publicar grabaciones, y llevar registro de las guardias de atención.

Cubre Épica 6 completa (F6.1–F6.6) del PRD. Es dependencia de C-14 (coloquios) y C-22 (frontend docente).

## What Changes

Nuevo módulo `encuentros` y `guardias` — dos dominios relacionados pero separados.

### Encuentros

- **Modelo `SlotEncuentro`**: plantilla de recurrencia semanal (materia, día, horario, fecha_inicio, cant_semanas). Soporta dos modos excluyentes (RN-13): recurrente (genera N instancias) o fecha única (fecha_unica no nullable, cant_semanas=0).
- **Modelo `InstanciaEncuentro`**: encuentro concreto derivado de un slot o independiente. Estado propio (Programado|Realizado|Cancelado) que puede modificarse sin afectar al slot ni a otras instancias (RN-14).
- **`POST /api/encuentros/slots`** (F6.1, F6.2): crea slot + genera instancias. Si `cant_semanas > 0` → recurrente. Si `fecha_unica` set → único. Guard: `encuentros:gestionar`.
- **`PATCH /api/encuentros/instancias/{id}`** (F6.3): modifica estado, meet_url, video_url, comentario de una instancia individual. Guard: `encuentros:gestionar`.
- **`GET /api/encuentros/instancias?materia_id=&desde=&hasta=`**: listado filtrado de instancias. Con scope por asignación del usuario.
- **`GET /api/encuentros/slots?materia_id=`**: listado de slots. Ídem scope.
- **`GET /api/encuentros/instancias/{id}/html`** (F6.4): genera bloque HTML formateado con los encuentros de una materia, listo para copiar al aula virtual.
- **`GET /api/encuentros/admin`** (F6.5): vista transversal para COORDINADOR/ADMIN de todos los encuentros del tenant.

### Guardias

- **Modelo `Guardia`**: registro de guardia cubierta (asignacion_id, materia_id, carrera_id, cohorte_id, dia, horario, estado, comentarios).
- **`POST /api/guardias`** (F6.6): TUTOR o PROFESOR registra su propia guardia. Guard: `guardias:gestionar`.
- **`GET /api/guardias?materia_id=&desde=&hasta=&estado=`**: listado filtrado. Scope por asignación. COORDINADOR/ADMIN ve todas.
- **`GET /api/guardias/export`**: exportación CSV/JSON del registro de guardias.
- **`PATCH /api/guardias/{id}`**: actualizar estado/comentarios de una guardia.

### Transversal

- **Permisos**: `encuentros:gestionar` (nuevo), `guardias:gestionar` (nuevo). Se seedean en migration.
- **Scope por rol**: PROFESOR/TUTOR ve solo sus materias (filtro por asignacion_ids). COORDINADOR/ADMIN ve todo.
- **Migración 0NN**: tablas `slot_encuentro`, `instancia_encuentro`, `guardia`.
- **Audit**: acciones `ENCUENTRO_CREAR`, `INSTANCIA_EDITAR`, `GUARDIA_REGISTRAR`, `GUARDIA_EDITAR`.

## Capabilities

### New Capabilities
- `encuentros`: Gestión de encuentros sincrónicos — slots recurrentes (RN-13), instancias con estado propio (RN-14), generación de bloque HTML para LMS, vista admin transversal.
- `guardias`: Registro de guardias de atención — alta por TUTOR/PROFESOR, consulta filtrada, exportación, vista admin global.

### Modified Capabilities
None — módulo completamente nuevo.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/slot_encuentro.py` | New | Modelo `SlotEncuentro` con recurrencia/fecha única, FKs a Asignacion/Materia |
| `backend/app/models/instancia_encuentro.py` | New | Modelo `InstanciaEncuentro` con estado propio, slot_id nullable, video_url |
| `backend/app/models/guardia.py` | New | Modelo `Guardia` con FK a Asignacion/Materia/Carrera/Cohorte |
| `backend/app/repositories/encuentro_repository.py` | New | SlotEncuentroRepository + InstanciaEncuentroRepository |
| `backend/app/repositories/guardia_repository.py` | New | GuardiaRepository |
| `backend/app/schemas/encuentros.py` | New | Pydantic DTOs: slot create, instancia update, list, HTML response |
| `backend/app/schemas/guardias.py` | New | Pydantic DTOs: create, list, export, update |
| `backend/app/services/encuentro_service.py` | New | Slot creation + instance generation, instance editing, HTML block gen |
| `backend/app/services/guardia_service.py` | New | CRUD guardias, export |
| `backend/app/api/v1/routers/encuentros.py` | New | Endpoints /api/encuentros/* con guards encuentros:gestionar |
| `backend/app/api/v1/routers/guardias.py` | New | Endpoints /api/guardias/* con guards guardias:gestionar |
| `backend/app/main.py` | Modified | Register both routers |
| `alembic/versions/XXX_encuentros_guardias.py` | New | Migración 0NN: slot_encuentro, instancia_encuentro, guardia + seed permisos |
