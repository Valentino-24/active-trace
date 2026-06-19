## Context

C-07 construyó el modelo `Asignacion` (usuario↔rol↔contexto académico con vigencia) y endpoints CRUD individuales (`/api/asignaciones`). C-08 agrega operaciones de alto nivel sobre ese mismo modelo: las que un COORDINADOR necesita para gestionar equipos docentes completos al inicio de cada cuatrimestre y durante el período lectivo.

No hay cambios de modelo de datos — todo se apoya en `Asignacion` tal como está. El cambio es puramente de lógica de negocio y nuevos endpoints agrupados bajo `/api/equipos`.

## Goals / Non-Goals

**Goals:**
- Vista "mi equipo" para el docente autenticado (filtrada a sus asignaciones)
- Vista de gestión de equipo para COORDINADOR/ADMIN (todas las asignaciones del tenant con filtros avanzados: materia, carrera, cohorte, rol, docente, vigencia)
- Asignación masiva: crear N asignaciones en una transacción
- Clonar equipo entre cohortes: duplicar asignaciones vigentes de un origen a un destino, ajustando fechas
- Modificar vigencia en bloque: actualizar `desde`/`hasta` de todas las asignaciones de un equipo
- Exportar equipo a CSV
- Auditoría: cada operación masiva registra evento `ASIGNACION_MODIFICAR`

**Non-Goals:**
- No se modifican los endpoints CRUD individuales de `/api/asignaciones` (C-07)
- No se agregan nuevos modelos ni migraciones
- No se implementa UI frontend (solo API)

## Decisions

### 1. Router separado `/api/equipos` en vez de extender `/api/asignaciones`
- **Decisión**: Los nuevos endpoints viven en su propio router `equipos.py` con prefijo `/api/equipos`.
- **Por qué**: Los endpoints de C-07 son CRUD de una entidad individual. Los de C-08 son operaciones de gestión de equipos (bulk, clonado, exportación). Son conceptualmente distintos y merecen su propio espacio de nombres y permisos.
- **Alternativa considerada**: Extender `/api/asignaciones` con endpoints bulk. Se descartó porque mezcla responsabilidades (CRUD de una entidad vs gestión de equipos).

### 2. Nuevo permiso `equipos:gestionar` para operaciones masivas
- **Decisión**: Se crea un permiso separado `equipos:gestionar` para las operaciones de asignación masiva, clonado, modificación de vigencia y exportación.
- **Por qué**: `equipos:asignar` y `equipos:revocar` (C-07) protegen operaciones individuales. Las operaciones masivas tienen mayor impacto y merecen un permiso distinto que puede asignarse selectivamente.
- **Asignación**: COORDINADOR y ADMIN obtienen `equipos:gestionar` en el seed.

### 3. Operaciones masivas con una sola transacción
- **Decisión**: `bulk_create()`, `clone_equipo()`, y `update_vigencia_masiva()` ejecutan todo en una sola transacción SQL. Si falla una operación individual, todo el batch se revierte.
- **Por qué**: Consistencia de datos. Una asignación masiva parcialmente exitosa dejaría el sistema en estado inconsistente.
- **Riesgo**: Operaciones muy grandes (>500 asignaciones) podrían tener lock contention. → Mitigación: se define un límite razonable (200 por lote) y se documenta como constraint.

### 4. Clonación usa el mismo `desde` del destino
- **Decisión**: Al clonar, todas las asignaciones duplicadas usan `desde = cohorte_destino.vig_desde` y `hasta = cohorte_destino.vig_hasta` (o None si el destino no tiene fecha fin).
- **Por qué**: El caso de uso (FL-03) es clonar el equipo de un cuatrimestre anterior al nuevo. Las fechas deben ser las del nuevo período, no las del origen.
- **Alternativa considerada**: Copiar las fechas原文 del origen. Se descartó porque no tiene sentido clonar con fechas vencidas.

### 5. Exportación como generación de CSV en servidor
- **Decisión**: `GET /api/equipos/exportar` devuelve un archivo CSV con `Content-Type: text/csv` y `Content-Disposition: attachment`.
- **Por qué**: Es el formato más universal y no requiere dependencias adicionales. El frontend puede disparar la descarga con un link directo.
- **Alternativa considerada**: XLSX con openpyxl. Se descartó por la sobrecarga de dependencia para un caso de uso que no requiere formato complejo.

### 6. Auditoría con evento único
- **Decisión**: Cada operación masiva genera UN solo registro de auditoría con metadatos del batch (cantidad de asignaciones afectadas, filtros usados).
- **Por qué**: Generar un registro por asignación individual en una operación de 200 sería ruido de auditoría inmanejable.
- **Formato**: `tipo_accion = "ASIGNACION_MODIFICAR"`, `detalle = {"operacion": "bulk_create|clone|vigencia_update|export", "cantidad": N, ...}`

## Risks / Trade-offs

- [Consistencia transaccional] → Las operaciones bulk son atómicas; si el batch es muy grande, aumenta la probabilidad de deadlocks → límite de 200 registros por operación.
- [Permisos duplicados] → `equipos:asignar` (individual, C-07) y `equipos:gestionar` (masivo, C-08) coexisten. Un usuario con solo `equipos:asignar` no podrá hacer operaciones masivas → documentar en la matriz de permisos.
- [Clonación con datos huérfanos] → Si una asignación origen referencia un `responsable_id` que ya no está activo, la clonación lo copia igual (es un FK, la consistencia referencial la mantiene la DB) → se documenta como comportamiento esperado.
