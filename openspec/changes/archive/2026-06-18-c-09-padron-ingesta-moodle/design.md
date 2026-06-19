## Context

C-09 es la primera capability de importación de datos del sistema. Hasta ahora activia-trace tiene: estructura académica (C-06), usuarios con PII cifrada + asignaciones (C-07) y equipos docentes (C-08). Para que el sistema pueda operar con datos reales de alumnos y calificaciones, necesita un padrón de estudiantes importado desde el LMS institucional (Moodle) o mediante carga manual de archivos.

El modelo `VersionPadron` + `EntradaPadron` está diseñado en la KB (E6). La integración con Moodle Web Services es unidireccional entrante: Moodle es fuente de verdad, activia-trace consume. El fallback manual con `.xlsx`/`.csv` asegura que tenants sin acceso a la API de Moodle puedan operar igual.

## Goals / Non-Goals

**Goals:**
- Modelo versionado de padrones (`VersionPadron` + `EntradaPadron`) con soft delete y tenant scoping
- Cliente Moodle Web Services (`integrations/moodle_ws.py`) para sync de usuarios (alumnos), actividades y calificaciones
- Import manual de padrón: subir archivo → vista previa → confirmar (o descartar)
- Vaciar datos de una materia (scope `usuario_id × materia_id`, RN-04)
- Auditoría: cada import registra `PADRON_CARGAR`
- Permiso `padron:importar` para PROFESOR (scope propia materia), COORDINADOR y ADMIN (global)

**Non-Goals:**
- No se implementa sync nocturna automática (se hará con cron/N8N externo — esta change expone el endpoint on-demand)
- No se implementa importación de calificaciones en este cambio (es C-10)
- No se implementa UI frontend (solo API REST)

## Decisions

### 1. Versionado con flag `activa` en vez de borrado físico
- **Decisión**: Al importar un nuevo padrón, se crea un nuevo `VersionPadron` con `activa=true` y la versión anterior pasa a `activa=false`. El borrado no existe: se desactiva.
- **Por qué**: Consistente con el principio de soft delete del sistema y con E6 de la KB. La versión anterior se conserva para trazabilidad.
- **Alternativa considerada**: Reemplazo físico (borrar versión anterior). Se descartó porque rompe el principio de auditoría del sistema.

### 2. Moodle WS como cliente async HTTP separado
- **Decisión**: El cliente Moodle WS vive en `integrations/moodle_ws.py` como clase async que usa httpx. Recibe configuración por tenant (URL base + token). Expone métodos `sync_alumnos()`, `sync_actividades()`, `sync_calificaciones()`.
- **Por qué**: Es un módulo aislado que puede testearse con mock de httpx. No depende del resto del sistema.
- **Detalle técnico**: Moodle Web Services usa token de servicio (no por usuario). Se configura por tenant como setting en la tabla `Tenant` o en una tabla de configuración específica.

### 3. Import de archivo con flujo de dos pasos (preview → confirm)
- **Decisión**: El import manual tiene dos endpoints: `POST /api/padron/preview` (sube archivo, parsea, devuelve preview con filas parseadas y errores de validación) y `POST /api/padron/import` (confirma el import, crea la versión y las entradas).
- **Por qué**: El usuario debe poder ver qué se va a importar antes de confirmar. Especialmente importante para detectar errores de parsing (columnas faltantes, formato incorrecto).
- **Alternativa considerada**: Import directo. Se descartó porque el feedback del usuario es necesario — el preview es un requisito explícito (F1.4).

### 4. Parsing de archivos con openpyxl + csv
- **Decisión**: `.xlsx` se parsea con openpyxl, `.csv` con el módulo estándar csv de Python (con detección de encoding utf-8-sig, latin-1).
- **Por qué**: openpyxl ya es una dependencia común y robusta. CSV no requiere dependencias externas.
- **Columnas esperadas**: nombre, apellido(s), email, comisión (opcional), regional (opcional). Se define una convención documentada en el spec.

### 5. `EntradaPadron.usuario_id` nullable
- **Decisión**: El alumno puede no tener aún cuenta en activia-trace al momento del import. `usuario_id` es nullable; el match se intenta por email contra la tabla `users`.
- **Por qué**: Es común que el padrón se importe antes de que los alumnos activen su cuenta. RN-05 no requiere que exista el usuario.
- **Match**: Se busca `users` por `email_hash` (el email del padrón se cifra y hashea igual que en C-07). Si no existe, `usuario_id` queda NULL.

### 6. `PADRON_CARGAR` como evento único por import
- **Decisión**: Cada import (versión de padrón) genera UN registro de auditoría con metadatos: `{version_id, materia_id, cohorte_id, total_entradas, modo: "moodle_ws"|"archivo"}`.
- **Por qué**: Generar un evento por cada una de las 200+ entradas sería ruido de auditoría.
- **Consistente con**: C-08 (misma decisión para operaciones bulk).

## Risks / Trade-offs

- [Dependencia externa Moodle] → Moodle WS puede cambiar su API o caerse → el cliente tiene timeout configurable y reintento (3 intentos con backoff). Si falla, se devuelve 502.
- [Archivo malformado] → El preview detecta filas inválidas y las reporta al usuario. El import se rechaza si hay errores de parsing (fail-fast).
- [Email no coincide] → Si el email del padrón no coincide con ningún usuario en el sistema, `usuario_id` queda NULL. El match se puede hacer después manualmente o con un re-match endpoint (post-MVP).
- [Volumen de datos] → Un padrón de 5000 alumnos es factible. Para >10K considerar paginación en la respuesta de preview. Límite inicial: 10K filas.
