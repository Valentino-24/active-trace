# Padrón de Alumnos

> Importación de padrones de alumnos desde Moodle Web Services o archivos `.xlsx`/`.csv`. Cada import genera una nueva versión; la anterior se desactiva.

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `padron:importar` | Importar padrón y vaciar materia | PROFESOR (scope propia materia), COORDINADOR, ADMIN |

## Escenarios

### E1: Importar padrón desde Moodle Web Services

```
POST /api/padron/moodle-sync
Authorization: Bearer <token>
Content-Type: application/json

{
    "materia_id": "uuid",
    "cohorte_id": "uuid"
}
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (201):**
```json
{
    "version_id": "uuid",
    "materia_id": "uuid",
    "cohorte_id": "uuid",
    "total_entradas": 35,
    "fecha": "2026-06-18T12:00:00Z",
    "modo": "moodle_ws"
}
```

**Reglas:**
- El cliente Moodle WS se configura por tenant (URL base + token en tabla de configuraciones)
- Si Moodle WS no está configurado para el tenant, devuelve 400 con mensaje explicativo
- Errores de conexión a Moodle: 502 con mensaje de error + sugerencia de reintento
- Máximo 3 reintentos con backoff exponencial
- Si ya existe una versión activa para `(materia_id, cohorte_id)`, la nueva versión se crea como activa y la anterior se desactiva
- Audit: evento `PADRON_CARGAR` con `{version_id, materia_id, cohorte_id, modo: "moodle_ws"}`

### E2: Vista previa de import desde archivo

```
POST /api/padron/preview
Authorization: Bearer <token>
Content-Type: multipart/form-data

archivo: <file.xlsx>
materia_id: "uuid"
cohorte_id: "uuid"
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (200):**
```json
{
    "total_filas": 35,
    "columnas_detectadas": ["nombre", "apellidos", "email", "comision", "regional"],
    "filas": [
        {"fila": 1, "nombre": "Juan", "apellidos": "Pérez", "email": "jperez@test.com", "comision": "A", "regional": "CABA"},
        {"fila": 2, "nombre": "María", "apellidos": "López", "email": "mlopez@test.com", "comision": "A", "regional": "CABA"}
    ],
    "errores": [
        {"fila": 3, "campo": "email", "mensaje": "Email inválido"}
    ]
}
```

**Reglas:**
- Archivos soportados: `.xlsx`, `.csv`
- Columnas esperadas (por nombre de encabezado): `nombre`, `apellidos` (o `apellido`), `email`, `comision` (opcional), `regional` (opcional)
- CSV: detecta encoding (utf-8-sig, latin-1), separador `;` o `,`
- Máximo 10.000 filas por preview
- Los errores de parseo se devuelven por fila, no detienen el preview completo
- No se persiste nada en este endpoint — es solo vista previa

### E3: Confirmar import desde archivo

```
POST /api/padron/import
Authorization: Bearer <token>
Content-Type: application/json

{
    "materia_id": "uuid",
    "cohorte_id": "uuid",
    "filas": [
        {"nombre": "Juan", "apellidos": "Pérez", "email": "jperez@test.com", "comision": "A", "regional": "CABA"},
        {"nombre": "María", "apellidos": "López", "email": "mlopez@test.com", "comision": "A", "regional": "CABA"}
    ]
}
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (201):**
```json
{
    "version_id": "uuid",
    "materia_id": "uuid",
    "cohorte_id": "uuid",
    "total_entradas": 35,
    "total_sin_usuario": 2,
    "fecha": "2026-06-18T12:00:00Z",
    "modo": "archivo"
}
```

**Reglas:**
- Crea una nueva `VersionPadron` con `activa=true`
- Desactiva la versión anterior de `(materia_id, cohorte_id)` si existe
- Crea `EntradaPadron` para cada fila:
  - Intenta matchear `email` contra `users.email_hash` (C-07); si matchea, asigna `usuario_id`
  - Si no matchea, `usuario_id` queda NULL
  - El email se almacena cifrado (AES-256) y con hash (SHA-256)
- Validaciones: materia_id y cohorte_id deben existir en el tenant
- Máximo 10.000 filas por import
- Toda la operación es transaccional
- Audit: evento `PADRON_CARGAR` con `{version_id, materia_id, cohorte_id, modo: "archivo", total_entradas, total_sin_usuario}`

### E4: Vaciar datos de una materia

```
DELETE /api/padron/materia/{materia_id}
Authorization: Bearer <token>
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (200):**
```json
{
    "mensaje": "Datos de la materia eliminados",
    "materia_id": "uuid",
    "versiones_desactivadas": 1,
    "entradas_eliminadas": 35
}
```

**Reglas:**
- Aplica soft delete a todas las `VersionPadron` y `EntradaPadron` de la materia
- Scope: si el usuario es PROFESOR, solo sus propias versiones (`cargado_por = current_user.id`)
- Scope: si el usuario es COORDINADOR o ADMIN, elimina todas las versiones de la materia en el tenant
- Las versiones desactivadas se marcan con `deleted_at` (soft delete)
- Las entradas de padrón se marcan con `deleted_at` (soft delete)
- No afecta datos de otras materias (RN-04)
- Audit: evento `PADRON_VACIAR` con `{materia_id, versiones_afectadas, entradas_afectadas}`

### E5: Listar versiones de padrón de una materia

```
GET /api/padron/versiones?materia_id=uuid&cohorte_id=uuid
Authorization: Bearer <token>
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (200):**
```json
{
    "items": [
        {
            "version_id": "uuid",
            "materia_id": "uuid",
            "cohorte_id": "uuid",
            "activa": true,
            "total_entradas": 35,
            "total_sin_usuario": 2,
            "cargado_por": {"id": "uuid", "nombre": "Admin"},
            "cargado_at": "2026-06-18T12:00:00Z",
            "modo": "archivo"
        }
    ],
    "total": 1
}
```

**Reglas:**
- Lista todas las versiones (activas e inactivas) de una materia×cohorte
- No incluye versiones soft-deleted
- Paginación: skip/limit (default 100)

### E6: Obtener detalle de una versión de padrón

```
GET /api/padron/versiones/{version_id}
Authorization: Bearer <token>
```

**Permiso requerido:** `padron:importar`

**Respuesta exitosa (200):**
```json
{
    "version_id": "uuid",
    "materia_id": "uuid",
    "cohorte_id": "uuid",
    "activa": true,
    "cargado_por": {"id": "uuid", "nombre": "Admin"},
    "cargado_at": "2026-06-18T12:00:00Z",
    "modo": "archivo",
    "entradas": [
        {"id": "uuid", "nombre": "Juan", "apellidos": "Pérez", "email_hash": "...", "comision": "A", "regional": "CABA", "tiene_usuario": true},
        {"id": "uuid", "nombre": "María", "apellidos": "López", "email_hash": "...", "comision": "A", "regional": "CABA", "tiene_usuario": false}
    ],
    "total_entradas": 35
}
```

**Reglas:**
- El email NO se devuelve (solo hash) — PII protegida
- Paginación de entradas: skip/limit (default 100)
