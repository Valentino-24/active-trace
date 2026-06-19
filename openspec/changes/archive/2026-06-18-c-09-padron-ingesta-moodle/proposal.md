## Why

El PROFESOR y el COORDINADOR necesitan importar el padrón de alumnos de cada materia desde el LMS (Moodle) para que el sistema tenga una base contra la cual evaluar calificaciones, detectar atrasados y generar comunicaciones. Sin padrón, el sistema no sabe qué alumnos pertenecen a cada materia×comisión. Moodle expone estos datos vía Web Services, pero también debe soportarse la carga manual de archivos `.xlsx`/`.csv` como fallback para tenants sin acceso a la API.

## What Changes

- Nuevos modelos `VersionPadron` y `EntradaPadron` con versionado (cada import genera una nueva versión; la anterior se desactiva, no se borra)
- Cliente `integrations/moodle_ws.py` para sync desde Moodle Web Services (usuarios, actividades, calificaciones)
- Import manual de padrón: endpoints para subir archivo `.xlsx`/`.csv` con vista previa antes de confirmar
- Endpoint para vaciar datos de una materia (scope `usuario_id × materia_id`, RN-04)
- Todo protegido con permiso `padron:importar` (PROFESOR para sus materias; COORDINADOR global)
- Auditoría: evento `PADRON_CARGAR` en cada import
- Nueva capability `padron` con spec completo

## Capabilities

### New Capabilities
- `padron`: importación de padrón de alumnos (Moodle WS + archivo manual), versionado de padrones, vista previa, vaciado de materia

### Modified Capabilities
- *(ninguna — primera capability de importación)*

## Impact

- **New models**: `VersionPadron`, `EntradaPadron` con tenant scoping + soft delete
- **Migration**: `008_version_padron_entrada_padron.py`
- **New integration**: `backend/app/integrations/moodle_ws.py` — cliente Moodle Web Services (sync de usuarios/actividades/calificaciones, errores → 502, reintento configurable)
- **New router**: `backend/app/api/v1/routers/padron.py` — `/api/padron/*` con guard `padron:importar`
- **New schemas**: DTOs para import, preview, response
- **New permission**: `padron:importar` (seed: PROFESOR, COORDINADOR, ADMIN)
- **Dependencies**: C-07 (usuarios + asignaciones), C-06 (materias + cohortes)
- **Governance**: MEDIO
