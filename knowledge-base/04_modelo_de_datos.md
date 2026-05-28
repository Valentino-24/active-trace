# 04 — Modelo de Datos

> Todo este modelo está **inferido a partir de UI**. Los nombres reales de tablas/columnas pueden diferir.

> ⚠️ **Corrección estructural para activia-trace** — este modelo refleja PulseUPs/olsoft (sistema viejo). El modelo destino corrige tres cosas de raíz (ver [`ARQUITECTURA.md` §6 y §8](../docs/ARQUITECTURA.md)):
> 1. **`Tenant` es la raíz de todo el modelo**: cada entidad lleva `tenant_id` y los repositories filtran por tenant por defecto. Los datos jamás cruzan instituciones ([RNF-22](../docs/PRD.md#multi-tenancy)).
> 2. **Identidad de auth = UUID interno**, no el `legajo`. El `legajo` queda como atributo de negocio (corrige [P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver) / [RN-25](05_reglas_de_negocio.md#rn-25--legajo-es-la-natural-key-del-docente)).
> 3. **Padrón versionado** (no upsert destructivo) y **catálogo único de materias** por tenant (corrige [P2](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver) y [P1](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).

## Entidades principales detectadas

### E1 — Carrera
**Fuente**: `admin_carreras.php`
```
Carrera {
  id          : int       (PK)         # ej: 1
  codigo      : varchar   (UNIQUE)     # ej: "TUPAD"
  nombre      : text                   # ej: "Tecnicatura Universitaria en Programación a Distancia"
  estado      : enum                   # "Activa" / "Inactiva"
}
```

### E2 — Cohorte
**Fuente**: `admin_cohortes.php`
```
Cohorte {
  id          : int       (PK)         # ej: 2
  nombre      : varchar                # ej: "AGO-2025", "MAR-2026"
  anio        : int                    # ej: 2025
  vig_desde   : date                   # ej: 2025-08-04
  vig_hasta   : date       (NULL ok)
  estado      : enum                   # "Activa" / "Inactiva"
}
```
**Suposición:** Cohorte pertenece a una Carrera (FK no observada directamente, pero el contexto es solo TUPAD).

### E3 — Materia
**Fuente**: `index.php` (catálogo A) y `monitor_evalia.php` (catálogo B)
```
Materia {
  id          : int       (PK)
  codigo      : varchar               # ej: "PROG_I", "DB_II"
  nombre      : varchar               # ej: "Programación I"
  catalogo    : enum                  # "MOOD" o "EVALIA" — INFERIDO
}
```
**Discrepancia conocida**: existen dos catálogos paralelos sin relación visible (ver [02](02_descripcion_general.md#universos-de-materias-paralelos)).

### E4 — Profesor
**Fuente**: `admin_profesores.php`, `perfil.php`
```
Profesor {
  legajo              : int    (PK)    # ej: 1683, 5178, 59149
  nombre              : varchar         # ej: "Londero Oscar Alberto"
  dni                 : varchar         # ej: "18221615"
  sexo                : enum
  cuil_view           : varchar         # calculado a partir de DNI + sexo? — suposición
  banco               : varchar
  cbu                 : varchar
  alias_cbu           : varchar
  regional            : varchar         # ej: "Gral.Pacheco"
  email               : varchar
  factura             : bool            # facturador o no
  legajo_profesional  : varchar         # separado del legajo del sistema
  estado              : bool            # Activo/Inactivo
  is_admin            : bool
}
```

> ⚠️ **Corrección para activia-trace**: en el modelo destino, `legajo` deja de ser PK (la PK es un **UUID** de identidad); `is_admin` se reemplaza por **roles + permisos finos (RBAC)**; y la entidad lleva `tenant_id`. Datos sensibles (`cbu`, `dni`) van **cifrados en reposo (AES-256)** ([RNF-08](../docs/PRD.md#seguridad)). Ver [`ARQUITECTURA.md` §5](../docs/ARQUITECTURA.md).

### E5 — Asignación (Profesor ↔ Materia × Carrera × Cohorte × Comisión)
**Fuente**: `admin_asignaciones.php`, `mis_equipos.php`
```
Asignacion {
  id              : int       (PK)
  profesor_legajo : int       (FK → Profesor)
  materia_id      : int       (FK → Materia)
  carrera_id      : int       (FK → Carrera)
  cohorte_id      : int       (FK → Cohorte)
  rol             : enum                  # "PROFESOR", "COORDINADOR", ...
  comisiones      : array<string>          # multi-select
  responde_legs   : array<int>             # FK → Profesor (jerarquía: quién es el coordinador responsable)
  desde           : date
  hasta           : date
  estado          : enum                   # "Vigente", "Vencida" — derivado por fechas
}
```

### E6 — Padrón / Alumno
**Fuente**: `monitor_evalia.php`, `admin_monitor.php`
```
Alumno {
  id          : int       (PK)              # No visible, inferido
  nombre      : varchar
  apellidos   : varchar
  email       : varchar
  grupos      : varchar                     # tomado del Excel de Moodle (campo "Grupos")
  materia_id  : int       (FK → Materia)    # el padrón se carga POR materia
  comision    : varchar                     # inferido del campo "Grupos" o columna específica
  regional    : varchar                     # ej: filtrable en monitor general
}
```
**Comportamiento conocido**: "La nueva carga reemplaza el padrón anterior de esa materia" → **NO HAY HISTORIAL DEL PADRÓN**, es upsert destructivo.

### E7 — Actividad / Calificación
**Fuente**: `index.php` (1.a), `admin_monitor.php` (sección 2)
```
Calificacion {
  id              : int       (PK)
  alumno_id       : int       (FK → Alumno)
  materia_id      : int       (FK → Materia)
  actividad       : varchar                  # nombre de la columna en el Excel
  nota_real       : decimal                  # si columna termina en "(Real)"
  nota_texto      : varchar                  # ej: "Satisfactorio", "Supera lo esperado"
  aprobado        : bool                     # derivado: nota_real >= umbral OR nota_texto ∈ aprobados
  origen          : enum                     # "Moodle", "Manual" — suposición
}
```
**Reglas de derivación observadas** (literal en `index.php`):
- Columnas que terminan en `(Real)` → `nota_real`.
- `nota_texto` ∈ {"Satisfactorio", "Supera lo esperado"} → cuenta como aprobado.

### E8 — Umbral por materia (configuración)
**Fuente**: `index.php` (sección 1.a, "Umbral global")
```
Umbral {
  profesor_legajo : int    (FK)            # por docente
  materia_id      : int    (FK)
  umbral_pct      : int                    # default 60
}
```
**Suposición:** un umbral por par (profesor, materia) — la pantalla dice "Borra sólo tus datos en esta materia. No afecta a otros profesores."

### E9 — Slot de Encuentro
**Fuente**: `encuentros.php`
```
SlotEncuentro {
  id                : int       (PK)
  profesor_legajo   : int       (FK)
  materia_id        : int       (FK)
  hora              : time
  dow               : enum                  # día de la semana
  fecha_desde       : date
  cant_semanas      : int                   # genera N instancias
  fecha_single      : date       (NULL ok)  # alternativa: slot único
  titulo            : varchar
  meet_url          : varchar
  vigencia_desde    : date
  vigencia_hasta    : date
}
```

### E10 — Instancia de Encuentro
**Fuente**: `encuentros.php` (tabla detalle)
```
InstanciaEncuentro {
  id              : int       (PK)
  slot_id         : int       (FK → SlotEncuentro, NULL ok si fue creado standalone)
  fecha           : date
  hora            : time
  materia_id      : int       (FK)
  titulo          : varchar
  estado          : enum                    # "programado", "realizado", "cancelado" — inferido
  meet_url        : varchar
  video_url       : varchar
  comentario      : text
}
```

### E11 — Guardia
**Fuente**: `mis_guardias.php`
```
Guardia {
  id                : int       (PK)        # ej: 288
  tutor_legajo      : int       (FK → Profesor)
  materia_id        : int       (FK → Materia)
  carrera_id        : int       (FK → Carrera)
  cohorte_id        : int       (FK → Cohorte)
  dia               : enum                   # "Miercoles", ...
  horario           : varchar                # ej: "14:00–14:45"
  estado            : enum                   # "finalizado", (otros)
  comentarios       : text
  creada_at         : datetime
}
```

### E12 — Tarea (asignada profesor ↔ coordinación)
**Fuente**: `mis_tareas.php`, `admin_tareas.php`
```
Tarea {
  id                : int       (PK)
  materia_id        : int       (FK)
  profesor_legajo   : int       (FK)         # asignado a
  asignado_por      : int       (FK)         # quien asigna
  estado            : enum                   # múltiples valores, no enumerados
  descripcion       : text
  ultimo_comentario : text                   # último de la conversación
  ctx_id            : int                    # contexto — significado no claro
}
TareaComentario {
  id        : int   (PK)
  tarea_id  : int   (FK)
  texto     : text
  autor     : int
  fecha     : datetime
}
```

### E13 — Aviso
**Fuente**: `admin_avisos.php`
```
Aviso {
  id              : int       (PK)
  scope           : enum                     # ej: global, por materia, por cohorte
  materia_slug    : varchar    (NULL ok)
  cohorte_id      : int        (NULL ok)
  role_target     : enum                     # rol al que va dirigido
  severity        : enum                     # info, warn, error — suposición
  titulo          : varchar
  cuerpo          : text                     # rich text
  start_at        : datetime
  end_at          : datetime
  sort            : int                      # orden de prioridad
  active          : bool
  require_ack     : bool                     # exige acknowledgment del usuario
  vistos          : int                      # contador (denormalizado)
  ack_count       : int                      # contador (denormalizado)
}
```

### E14 — Evaluación / Coloquio
**Fuente**: `coloquios/index.php`, `admin_coloquios.php`
```
Evaluacion {
  id              : int       (PK)
  materia_id      : int       (FK)
  instancia       : varchar                  # ej: "Coloquio Final"
  dias_disponibles: int
  convocados      : int
  reservas        : int
  cupos_libres    : int                      # derivado
}
ReservaColoquio {
  id              : int       (PK)
  evaluacion_id   : int       (FK)
  alumno_id       : int       (FK)
  estado          : enum                     # activa, cancelada
  fecha_hora      : datetime
}
RegistroAcademicoColoquio {
  evaluacion_id   : int
  alumno_id       : int
  nota_final      : varchar / decimal
}
```

### E15 — Fecha Parcial / TP / Coloquio
**Fuente**: `fechas_parciales.php`
```
FechaParcial {
  id          : int       (PK)
  materia_id  : int       (FK)
  cohorte_id  : int       (FK)
  tipo        : enum                         # Parcial, TP, Coloquio
  numero      : int                          # 1er parcial, 2do parcial, etc.
  periodo     : varchar                      # cuatrimestre/año
  fecha       : date
  titulo      : varchar
}
```

### E16 — Programa (PDF)
**Fuente**: `programas_materias.php`
```
Programa {
  id          : int       (PK)
  materia_id  : int       (FK)
  carrera_id  : int       (FK)
  cohorte_id  : int       (FK)
  titulo      : varchar
  archivo_pdf : path                         # path a PDF en disco
  fecha       : datetime
}
```

### E17 — Liquidación / Salario
**Fuente**: `liquidaciones.php`, `salarios.php`
```
Liquidacion {
  id              : int       (PK)
  profesor_legajo : int       (FK)
  periodo         : varchar
  rol             : enum
  comisiones      : varchar
  base            : decimal
  plus            : decimal
  total           : decimal                  # base + plus
  estado          : enum                     # abierta, cerrada
}
SalarioGrilla {
  rol             : enum
  base            : decimal
  # ... estructura no observada en detalle
}
```

### E18 — Email (cola/historial de envío)
**Fuente**: `admin.php` (Estado de comunicaciones)
```
Email {
  id              : int       (PK)
  profesor_legajo : int       (FK → quien envía)
  materia_id      : int       (FK)
  destinatario    : varchar (email del alumno)
  asunto          : varchar
  cuerpo_html     : text
  estado          : enum                     # "Pend", "Send", "OK", "Fail", "Canc"
  batch_id        : int                      # agrupa envíos masivos
  enviado_at      : datetime
}
```

### E20 — SalarioBase (descubierto en segunda pasada)
**Fuente**: `salarios.php`
```
SalarioBase {
  id           : int       (PK)
  rol          : enum                # ALL | PROFESOR | TUTOR | NEXO | COORDINADOR
  monto        : decimal
  desde        : date
  hasta        : date       (NULL = vigente sin fin = ∞)
}
```
Datos observados al 2026-05:
- COORDINADOR: $800.000 (vigente desde 2026-02-01)
- NEXO: $660.000
- PROFESOR: $560.000
- TUTOR: $420.000

### E21 — SalarioPlus (descubierto en segunda pasada)
**Fuente**: `salarios.php`
```
SalarioPlus {
  id           : int       (PK)
  clave        : varchar             # ej: "PROG" — agrupador
  rol          : enum                # PROFESOR | TUTOR | NEXO | COORDINADOR
  descripcion  : varchar             # ej: "Plus Programación"
  monto        : decimal
  desde        : date
  hasta        : date       (NULL ok)
}
```
Datos observados:
- PROG/COORDINADOR: $180.000 ("Plus Programación")
- PROG/TUTOR: $140.000
- PROG/PROFESOR: $120.000

**Suposición:** la `clave` mapea a un grupo de materias (PROG = todas las de Programación). Puede haber otras claves (BD, ING, MAT, etc.) según el portfolio.

### E22 — Factura (descubierto en segunda pasada)
**Fuente**: `admin_facturas.php`
```
Factura {
  id              : int       (PK)
  profesor_legajo : int       (FK → Profesor)        # con factura=true
  mes             : varchar                          # formato "YYYY-MM"
  detalle         : varchar                          # texto libre del docente
  archivo_pdf     : path                             # PDF subido por el docente
  tamano_kb       : decimal                          # tamaño del archivo
  estado          : enum                             # "pendiente" | "abonada"
  fecha_carga     : datetime
  fecha_pago      : datetime    (NULL hasta abonar)
}
```
Datos observados: Pellegrino Florencia (legajo 2878, 2026-05 "Factura Mayo", 29.6 KB, pendiente), Landra Manuel (legajo 5082, 2026-05 "Armado de aula legislación", 84.1 KB, pendiente).

### E23 — Liquidación (refinada con datos reales)
> Reemplaza la definición previa de E17.
```
Liquidacion {
  id              : int       (PK)
  cohorte_id      : int       (FK → Cohorte)
  mes             : varchar                          # YYYY-MM
  profesor_legajo : int       (FK → Profesor)
  rol             : enum                             # PROFESOR | TUTOR | NEXO | COORDINADOR
  comisiones      : varchar / array                  # comisiones a las que aplica
  base            : decimal                          # de SalarioBase vigente
  plus            : decimal                          # suma de SalarioPlus aplicables
  total           : decimal                          # Base + Plus
  es_nexo         : bool                             # tabla separada en UI ([RN-36])
  es_factura      : bool                             # docente monotributista — NO se paga acá ([RN-35])
  estado          : enum                             # abierta | cerrada
}
```

### E19 — Log de auditoría
**Fuente**: `admin.php` (Últimas acciones)
```
AuditLog {
  id              : int       (PK)
  fecha           : datetime
  legajo          : int       (FK → Profesor)
  materia_id      : int       (FK, NULL ok)
  accion          : varchar                  # ej: "MOD_MIS_EQUIPOS"
  rows            : int                      # filas afectadas / cantidad
  ip              : varchar
  user_agent      : text
}
```

## Relaciones (ERD simplificado)

```
Carrera (1) ─── (N) Cohorte
Carrera (1) ─── (N) Asignacion
Cohorte (1) ─── (N) Asignacion
Materia (1) ─── (N) Asignacion
Profesor (1) ─── (N) Asignacion
Profesor (1) ─── (N) Asignacion (responde) ── (N) Profesor   # jerarquía

Materia (1) ─── (N) Alumno (vía padrón)
Alumno  (1) ─── (N) Calificacion
Materia (1) ─── (N) Calificacion

Profesor (1) ─── (N) Umbral por Materia
Profesor (1) ─── (N) SlotEncuentro
SlotEncuentro (1) ─── (N) InstanciaEncuentro
Profesor (1) ─── (N) Guardia
Profesor (1) ─── (N) Tarea (asignado a)
Profesor (1) ─── (N) Tarea (asignado por)
Tarea (1) ─── (N) TareaComentario

Materia (1) ─── (N) Aviso
Cohorte (1) ─── (N) Aviso

Materia (1) ─── (N) Evaluacion
Evaluacion (1) ─── (N) ReservaColoquio
Alumno (1) ─── (N) ReservaColoquio

Materia (1) ─── (N) FechaParcial
Materia (1) ─── (N) Programa

Profesor (1) ─── (N) Liquidacion
Profesor (1) ─── (N) Email
Profesor (1) ─── (N) AuditLog
```

## Datos seed observados

- **Carreras**: TUPAD (única activa).
- **Cohortes**: MAR-2025, AGO-2025, MAR-2026 (al menos).
- **Materias catálogo A**: 19 confirmadas (ver [02](02_descripcion_general.md#catálogo-a)).
- **Materias catálogo B (EVALIA)**: 12 confirmadas.
- **Programas cargados**: 14 (visible "Listado 14" en `programas_materias.php`).
- **Guardias activas**: 250 registros.
- **Tareas admin**: 443 registros.
- **Acciones log**: capadas a 200 más recientes.

## Códigos de acción observados (audit log)

- `MOD_MIS_EQUIPOS` (visible en log de admin.php)
- (otros no observados — el log tiene patrones similares para cada acción)

## Convenciones de nombres detectadas

| Patrón | Significado |
|--------|-------------|
| `_id` | FK numérica |
| `_legajo` / `legajo_*` | FK a Profesor (es el natural key del docente) |
| `legs[]`, `responde_legs[]` | Arrays de legajos para selects múltiples |
| `vig_desde` / `vig_hasta` | Vigencia temporal |
| `start_at` / `end_at` | Período de validez (avisos) |
| `csrf` | Token CSRF |
| `accion` / `action` | Discriminador de operación en POST self |
