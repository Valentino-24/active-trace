# Equipos Docentes

> Gestión de equipos docentes: asignación masiva, clonación, modificación de vigencia en bloque y exportación.

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `equipos:gestionar` | Operaciones masivas sobre equipos | COORDINADOR, ADMIN |

Los permisos individuales `equipos:asignar` y `equipos:revocar` pertenecen a la especificación de `asignaciones` (C-07).

## Escenarios

### E1: Docente ve su equipo

```
GET /api/equipos/mi-equipo
Authorization: Bearer <token>
```

**Contexto:** El usuario autenticado tiene rol DOCENTE (TUTOR, PROFESOR) con asignaciones vigentes.

**Respuesta exitosa (200):**
```json
{
    "items": [
        {
            "id": "uuid",
            "materia": {"id": "uuid", "nombre": "Álgebra"},
            "carrera": {"id": "uuid", "nombre": "Ing. Sistemas"},
            "cohorte": {"id": "uuid", "nombre": "2026"},
            "comisiones": ["A", "B"],
            "rol": "PROFESOR",
            "desde": "2026-03-01",
            "hasta": null,
            "responsable": {"id": "uuid", "nombre": "Juan Pérez"},
            "estado_vigencia": "vigente"
        }
    ],
    "total": 1
}
```

**Reglas:**
- Filtra por `usuario_id = current_user.id`
- Solo devuelve asignaciones vigentes (no vencidas ni pendientes)
- Accesible sin permiso especial (cualquier usuario autenticado puede ver su equipo)

---

### E2: COORDINADOR gestiona equipos del tenant

```
GET /api/equipos
Authorization: Bearer <token>
```

**Permiso requerido:** `equipos:gestionar`

**Parámetros de filtro (query):**
- `skip`, `limit` — paginación (default 0/100, max 500)
- `materia_id` — filtrar por materia
- `carrera_id` — filtrar por carrera
- `cohorte_id` — filtrar por cohorte
- `rol` — filtrar por código de rol
- `docente_id` — filtrar por docente asignado
- `vigentes_only` — bool, default true (si true, excluye vencidas y pendientes)
- `q` — búsqueda textual sobre nombre de materia y nombre de docente

**Respuesta exitosa (200):**
```json
{
    "items": [
        {
            "id": "uuid",
            "usuario": {"id": "uuid", "nombre": "María López", "email": "mlopez@inst.com"},
            "materia": {"id": "uuid", "nombre": "Álgebra"},
            "carrera": {"id": "uuid", "nombre": "Ing. Sistemas"},
            "cohorte": {"id": "uuid", "nombre": "2026"},
            "comisiones": ["A", "B"],
            "rol": "PROFESOR",
            "desde": "2026-03-01",
            "hasta": null,
            "responsable": {"id": "uuid", "nombre": "Juan Pérez"},
            "estado_vigencia": "vigente"
        }
    ],
    "total": 42
}
```

**Reglas:**
- Siempre scoped al tenant del usuario autenticado
- Incluye relaciones `usuario`, `materia`, `carrera`, `cohorte`, `responsable`
- La búsqueda `q` hace ILIKE sobre `usuario.nombre` y `materia.nombre`

---

### E3: Asignación masiva

```
POST /api/equipos/asignacion-masiva
Authorization: Bearer <token>
Content-Type: application/json

{
    "materia_id": "uuid",
    "carrera_id": "uuid",
    "cohorte_id": "uuid",
    "comisiones": ["A", "B"],
    "desde": "2026-03-01",
    "hasta": "2026-12-31",
    "asignaciones": [
        {"usuario_id": "uuid", "rol": "PROFESOR", "responsable_id": null},
        {"usuario_id": "uuid", "rol": "TUTOR", "responsable_id": "uuid"},
        {"usuario_id": "uuid", "rol": "TUTOR", "responsable_id": "uuid"}
    ]
}
```

**Permiso requerido:** `equipos:gestionar`

**Respuesta exitosa (201):**
```json
{
    "creadas": 3,
    "items": [
        {"id": "uuid", "usuario_id": "uuid", "rol": "PROFESOR", "desde": "2026-03-01", "hasta": "2026-12-31"},
        {"id": "uuid", "usuario_id": "uuid", "rol": "TUTOR", ...},
        {"id": "uuid", "usuario_id": "uuid", "rol": "TUTOR", ...}
    ]
}
```

**Reglas:**
- Los campos `materia_id`, `carrera_id`, `cohorte_id`, `comisiones`, `desde`, `hasta` se aplican a todas las asignaciones del lote
- Valida que todos los `usuario_id` existan en el tenant
- El `responsable_id` es opcional por cada asignación
- Máximo 200 asignaciones por lote (400 si se excede)
- Toda la operación es transaccional: si falla una, falla todo

---

### E4: Clonar equipo entre cohortes

```
POST /api/equipos/clonar
Authorization: Bearer <token>
Content-Type: application/json

{
    "origen": {
        "materia_id": "uuid",
        "carrera_id": "uuid",
        "cohorte_id": "uuid"
    },
    "destino": {
        "materia_id": "uuid",
        "carrera_id": "uuid",
        "cohorte_id": "uuid"
    },
    "incluir_roles": ["PROFESOR", "TUTOR"]
}
```

**Permiso requerido:** `equipos:gestionar`

**Respuesta exitosa (201):**
```json
{
    "clonadas": 5,
    "items": ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"]
}
```

**Reglas:**
- Solo clona asignaciones vigentes del origen (no vencidas, no eliminadas soft)
- El `desde` y `hasta` de cada asignación clonada se toman de la cohorte destino (`vig_desde`, `vig_hasta`)
- Si la cohorte destino no tiene `vig_hasta`, se copia como `hasta = None`
- `incluir_roles` filtra qué roles clonar (default: todos)
- RN-12: no se clonan asignaciones ya existentes en el destino con igual `usuario_id + materia_id + carrera_id + cohorte_id + rol`
- Toda la operación es transaccional
- Máximo 200 asignaciones clonadas por operación

---

### E5: Modificar vigencia en bloque

```
PATCH /api/equipos/vigencia
Authorization: Bearer <token>
Content-Type: application/json

{
    "materia_id": "uuid",
    "carrera_id": "uuid",
    "cohorte_id": "uuid",
    "rol": "PROFESOR",
    "nuevo_desde": "2026-04-01",
    "nuevo_hasta": "2026-12-31"
}
```

**Permiso requerido:** `equipos:gestionar`

**Respuesta exitosa (200):**
```json
{
    "actualizadas": 3,
    "items": ["uuid1", "uuid2", "uuid3"]
}
```

**Reglas:**
- Actualiza `desde` y/o `hasta` de todas las asignaciones que coincidan con los filtros
- Los filtros son OPCIONALES (si no se pasan, se actualiza TODO el tenant → requiere confirmación explícita con `confirmar=true`)
- `nuevo_desde` y `nuevo_hasta` son independientes (se puede cambiar solo uno)
- Se omite si `nuevo_desde` está en el pasado + no se pasa `confirmar=true` (protección contra dejar asignaciones "empezando ayer" sin intención)
- Toda la operación es transaccional

---

### E6: Exportar equipo a CSV

```
GET /api/equipos/exportar?materia_id=uuid&carrera_id=uuid&cohorte_id=uuid
Authorization: Bearer <token>
```

**Permiso requerido:** `equipos:gestionar`

**Respuesta exitosa (200):**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="equipo_2026-03-01.csv"

id,docente_nombre,docente_email,materia,carrera,cohorte,comisiones,rol,responsable,desde,hasta,estado
uuid,... (CSV rows)
```

**Reglas:**
- Usa `utf-8-sig` encoding (BOM para Excel)
- Columnas: id, docente, email, materia, carrera, cohorte, comisiones, rol, responsable, desde, hasta, estado_vigencia
- Filtros opcionales: materia_id, carrera_id, cohorte_id (si no se pasan, exporta todo el tenant)
- Límite: 10.000 filas
