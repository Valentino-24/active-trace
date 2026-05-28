# 05 — Reglas de Negocio

Reglas codificadas detectadas en la herramienta. Cada una con código `RN-XX` para referenciarla.

## Dominio: Importación de Calificaciones

### RN-01 — Detección de notas numéricas
Las columnas del Excel exportado de Moodle que **terminan en `(Real)`** son las que se toman como **nota numérica redondeada**.

**Evidencia**: nota literal en `index.php`: *"Se detectan columnas que terminan en (Real) para tomar notas numéricas redondeadas (Moodle)."*

### RN-02 — Mapeo de escala textual a aprobado
Los valores textuales **"Satisfactorio"** y **"Supera lo esperado"** se guardan en el campo `nota_texto` y **cuentan como aprobado**.

**Evidencia**: nota literal en `index.php`: *"Satisfactorio y Supera lo esperado se guarda en nota_texto y se considera aprobado."*

**Suposición:** existen otros valores en la escala ("No satisfactorio", "No alcanzado", etc.) que NO cuentan como aprobado — no observados directamente.

### RN-03 — Umbral por defecto
El umbral para considerar a un alumno "atrasado" por nota baja es **60% por defecto**, configurable por docente × materia.

**Evidencia**: input `type="number"` con valor `"60"` en sección "Umbral global" de `index.php`.

### RN-04 — Borrado de datos es scope-isolated
La operación "Vaciar datos de esta materia" elimina **solo los datos del docente logueado en esa materia**. No afecta a otros profesores.

**Evidencia**: leyenda literal en `index.php`: *"Borra sólo tus datos en esta materia. No afecta a otros profesores."*

**Implicación**: confirma que el modelo de datos tiene una clave `(profesor_legajo, materia_id)` para varios datasets, no son globales por materia.

### RN-05 — Padrón EVALIA es upsert destructivo
Al importar padrón de participantes en `monitor_evalia.php`, **la nueva carga reemplaza el padrón anterior de esa materia**.

**Evidencia**: leyenda literal: *"La nueva carga reemplaza el padrón anterior de esa materia."*

**Implicación**: no hay historial — si un alumno se da de baja antes del nuevo import, se pierde sin trazabilidad.

## Dominio: Detección de Atrasados y Pendientes

### RN-06 — Definición de "atrasado"
Un alumno está atrasado si tiene:
- **Actividades faltantes** (sin entrega), O
- **Nota < umbral configurado** (default 60).

**Evidencia**: título literal en `index.php` sección 3: *"Estudiantes atrasados (faltantes o < 60)"*.

### RN-07 — Detección de TPs sin corregir
La sección 1.b detecta entregas **finalizadas pero sin calificar** cruzando el reporte de finalización de Moodle con las calificaciones importadas.

**Evidencia**: leyenda en `index.php` 1.b: *"Acepta Excel o CSV/TSV directo de Moodle. Detecta entregas finalizadas sin calificar."*

### RN-08 — TPs sin corregir filtran solo escala textual
La tabla "Posibles TPs sin corregir (por actividad)" muestra **solo actividades de escala textual** (no las numéricas).

**Evidencia**: subtítulo literal: *"Sólo actividades de escala textual"*.

**Suposición:** el sistema asume que las actividades numéricas no quedan "sin corregir" porque o tienen nota o no se entregaron — la ambigüedad solo aplica a escala cualitativa.

## Dominio: Ranking y Reportes

### RN-09 — Ranking de aprobadas excluye sin actividades
El ranking "Realización de actividades (aprobadas)" lista **solo alumnos con al menos 1 actividad aprobada**.

**Evidencia**: leyenda literal: *"Ranking por cantidad de actividades aprobadas (sólo se listan quienes tienen al menos 1 aprobada)."*

## Dominio: Equipos Docentes

### RN-10 — Vigencia determina el estado de la asignación
Una asignación profesor↔materia se considera **Vigente** si la fecha actual cae entre `desde` y `hasta`.

**Evidencia**: tabla en `mis_equipos.php` columna "Estado" con valor "Vigente" derivado del rango (ej: 2026-03-01 a 2026-07-31).

### RN-11 — Jerarquía de "responde"
Una asignación puede tener uno o más **legajos que "responden"** por ese profesor (`responde_legs[]`). Esto modela la cadena coordinador → profesor.

**Evidencia**: campo `responde_legs[]:select-multiple` en `admin_asignaciones.php` y filtro `f_responde` en filtros.

### RN-12 — Clonación de equipo entre cohortes
Existe la operación "Clonar equipo docente" que **duplica las asignaciones de un equipo origen (materia × carrera × cohorte) a un destino**.

**Evidencia**: heading "Clonar equipo docente — Duplicar asignaciones de un equipo a otro (origen → destino)" en `admin_reportes.php`.

**Caso de uso inferido**: cuando arranca un nuevo cuatrimestre, en lugar de re-asignar manualmente a todos los docentes, se clona el equipo de la cohorte anterior.

## Dominio: Encuentros

### RN-13 — Dos modos de creación de slot
Al crear un encuentro hay un radio button con dos modos:
1. **Recurrente**: día de semana + hora + fecha desde + N semanas → genera N instancias.
2. **Único**: fecha individual + hora → 1 instancia.

**Evidencia**: campos `mode:radio, mode:radio` + `slot_dow, slot_from, slot_weeks` vs `slot_single_date` en `encuentros.php`.

### RN-14 — Instancia tiene estado modificable
Cada instancia de encuentro tiene un campo `inst_estado` editable separado del slot.

**Suposición:** estados típicos: programado, realizado, cancelado, reprogramado.

## Dominio: Mensajería / Emails

### RN-15 — Estados de email del worker
Los emails pasan por el ciclo: **Pend → Send → OK** (éxito) o **Pend → Send → Fail** (error) o **Pend → Canc** (cancelado).

**Evidencia**: columnas `Pend | Send | OK | Fail | Canc` en tabla "Estado de comunicaciones" de `admin.php`.

### RN-16 — Preview obligatorio antes de envío
Todo email pasa por un modal "Previsualización del email" con Asunto + Cuerpo HTML renderizado antes del envío real.

**Evidencia**: modal con headings "Previsualización del email" + "Asunto" + "Cuerpo (render HTML)" en `index.php`.

### RN-17 — Existe aprobación administrativa
Hay un endpoint `admin_mail_approval.php` (no accesible con rol PROFESOR) → existe un workflow donde **alguien aprueba** envíos antes del despacho.

**Suposición:** los envíos masivos requieren aprobación por un admin antes de pasar de "Pend" a "Send".

## Dominio: Avisos

### RN-18 — Avisos tienen ventana de vigencia
Cada aviso tiene `start_at` y `end_at` (datetime-local) → solo se muestran al usuario dentro de ese rango.

### RN-19 — Avisos pueden requerir acknowledgment
Si `require_ack=true`, el usuario debe confirmar haber leído el aviso. El sistema cuenta cuántos lo vieron (`vistos`) y cuántos lo confirmaron (`ACK`).

**Evidencia**: columnas "Vistos | ACK" en la tabla + checkbox `require_ack` en el formulario.

### RN-20 — Avisos segmentables por rol y scope
Cada aviso tiene `scope` (global, materia, cohorte), `materia_slug`, `cohorte_id`, `role_target` y `severity`.

**Implicación**: el sistema renderiza solo avisos cuyo rol/cohorte/materia coincide con el usuario.

## Dominio: Liquidaciones

### RN-21 — Cálculo de liquidación = Base + Plus por comisión
Liquidación se compone de: **Base** (fijo por rol/cargo) + **Plus** (variable por comisión).

**Evidencia**: columnas `Base | Plus | Total` en tabla de liquidaciones.

**Suposición:** Total = Base + Plus.

### RN-22 — Liquidación tiene ciclo cerrado
Existe un botón "Cerrar liquidación" → las liquidaciones tienen estados (abierta / cerrada) y al cerrarse se inmutabilizan.

## Dominio: Auditoría

### RN-23 — Toda acción se loguea con IP + UA
Cada acción significativa del usuario queda registrada con timestamp, legajo, materia, código de acción, cantidad de filas, IP y User-Agent.

**Evidencia**: tabla "Últimas acciones (máx. 200)" en `admin.php`.

### RN-24 — Códigos de acción son enums
Las acciones se codifican con strings tipo `MOD_MIS_EQUIPOS`. **Suposición:** existe un catálogo cerrado de códigos de acción.

## Dominio: Datos del Docente

### RN-25 — Legajo es la natural key del docente
El docente se identifica por `legajo` (no por id autonumérico). Visible en URLs, formularios y tablas.

> ⚠️ **Corrección para activia-trace**: exponer el `legajo` como identidad en URLs fue parte de la causa de [RN-41](#rn-41--impersonation-vía-legx) / [P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver). En activia-trace la **identidad de auth es un UUID interno**; el `legajo` se conserva solo como **atributo de negocio** (no es credencial ni selector de identidad).

### RN-26 — Datos bancarios obligatorios para liquidar
El profesor tiene banco, CBU, alias CBU obligatorios para que pueda recibir liquidaciones.

**Suposición:** no se valida en la UI pero es requisito de negocio.

### RN-27 — Estado "factura" diferencia tipo de docente
Hay un checkbox `factura` en `perfil.php` → distingue docentes monotributistas (que facturan) de relación de dependencia.

**Suposición:** el cálculo de liquidación puede variar según este flag.

## Reglas de Validación / UI

### RN-28 — CSRF token por POST
Todo formulario POST lleva un campo `csrf:hidden`. Sin el token el POST debería rechazarse.

### RN-29 — `materia_id=0` significa "Todas"
En filtros donde hay un selector de materia, el value `0` significa "Todas las materias".

**Evidencia**: `option "Todas" (selected) value="0"` en `coloquios/index.php`.

### RN-30 — Búsqueda bulk con autocomplete
En "Asignación masiva" hay un input `bulkSearch:text` que sugiere autocomplete server-side para encontrar docentes a asignar.

---

## Dominio: Salarios y Liquidaciones (descubierto en segunda pasada)

### RN-31 — Grilla salarial con vigencia abierta
Las grillas de Base y Plus tienen `desde` (fecha) y `hasta` que puede ser `∞` (sin fecha de fin).

**Evidencia**: visible en `salarios.php` — "NEXO — $660000.00 — 2026-02-01 → ∞".

**Implicación**: las reglas salariales se versionan en el tiempo; al cerrar un mes la liquidación toma la vigente para ese mes.

### RN-32 — Base por rol
Existe una **Base salarial fija por rol** independiente de la materia.

**Evidencia**: tabla "Base" en `salarios.php`. Valores reales observados (al 2026-05):
- COORDINADOR: $800.000
- NEXO: $660.000
- PROFESOR: $560.000
- TUTOR: $420.000

### RN-33 — Plus por (categoría, rol)
Los plus son **adicionales identificados por una clave** (ej: `PROG`) que se cruzan con un rol.

**Evidencia**: tabla "Plus" en `salarios.php`. Valores reales observados:
- PROG/PROFESOR: $120.000 (Plus Programación)
- PROG/TUTOR: $140.000 (Plus Programación)
- PROG/COORDINADOR: $180.000 (Plus Programación)

**Suposición:** la clave del plus identifica un agrupamiento de materias (PROG = todas las materias de Programación). Otras claves posibles: BD, ING, MAT, etc.

### RN-34 — Cálculo de liquidación
Liquidación mensual = (Base del rol vigente al mes) + (suma de Plus aplicables por (clave_materia, rol) para cada comisión asignada).

**Evidencia**: las columnas `Base | Plus | Total` en `liquidaciones.php` + leyenda *"Liquidación mensual por materia y rol - Revisar conformación de equipos"*.

**Suposición:** Total = Base + Σ(Plus). Si un docente tiene N comisiones de programación, suma N veces el Plus PROG según su rol — pendiente de confirmar.

### RN-35 — Monotributistas se liquidan por separado (vía Facturas)
Los docentes con flag `factura=true` (monotributistas) **NO se incluyen en la liquidación general** — se les paga contra factura presentada.

**Evidencia**: en `liquidaciones.php` hay una tabla aparte titulada *"Docentes que facturan — No se incluyen en la liquidación general; se pagan por otro medio."*. El admin gestiona sus pagos en `admin_facturas.php`.

**Implicación**: hay **dos flujos contables paralelos**: liquidación tradicional (Base+Plus calculados) vs pago contra factura (monto definido en el PDF).

### RN-36 — NEXO se muestra aparte pero suma al total
El rol NEXO aparece en una tabla separada en la liquidación pero su importe se incluye en el total general y en el resumen por docente.

**Evidencia**: leyenda literal en `liquidaciones.php`: *"Roles NEXO (se muestran aparte, pero suman al total y al resumen por docente)."*

**Suposición:** el NEXO probablemente cumple funciones transversales (no atadas a una materia específica) que merecen visibilidad contable separada.

### RN-37 — Liquidación se cierra por (cohorte × mes)
La liquidación se opera por la dupla (cohorte, mes) — al "Cerrar liquidación" se inmutabiliza ese período específico.

**Evidencia**: filtros en `liquidaciones.php` son Cohorte (MAR-2026/AGO-2025/MAR-2025) + Mes + Legajo opcional.

### RN-38 — KPIs contables visibles en cabecera
La cabecera de Liquidaciones muestra: *"Total sin Factura"* y *"Total con factura"* — el sistema separa esos universos en la UI.

### RN-39 — Factura: estados pendiente / abonada
Las facturas presentadas por monotributistas tienen 2 estados: `pendiente` (cargada, sin pagar) y `abonada` (pagada).

**Evidencia**: filtro estado en `admin_facturas.php` con valores `pendiente:Pendiente, abonada:Abonada`.

### RN-40 — Factura = (Docente, Mes, PDF, Detalle, Estado)
Cada factura subida por un docente tiene: docente (legajo), mes (YYYY-MM), detalle (texto libre, ej "Factura Mayo", "Armado de aula Legislación"), archivo PDF, tamaño, fecha de carga, estado.

**Evidencia**: columnas reales en `admin_facturas.php`: Fecha carga | Docente | Mes | Detalle | Archivo | Tamaño | Estado | Pago | Acción.

### RN-41 — Impersonation vía `?leg=X`
El sistema permite a un super-admin **operar como otro docente** pasando `?leg=<legajo>` en cualquier URL.

**Evidencia**: navegación a `/?leg=1` cambia el contexto del usuario logueado (de Cortez Alberto a Rodriguez Georgina, legajo 1) y muestra el menú/datos de ese legajo.

**Implicación de seguridad**: este mecanismo debería estar restringido a usuarios con permiso de impersonation. Cada impersonation idealmente debería loguearse en el audit log con quién la inició.

→ Ver pregunta abierta [PA-21](10_preguntas_abiertas.md#pa-21).

> 🔴 **Corrección para activia-trace — RN-41 es el pecado original (Broken Access Control, OWASP A01).** NO replicar bajo ninguna circunstancia. La identidad se deriva **exclusivamente del JWT firmado**; ningún parámetro de URL/body/header puede cambiar de usuario. La impersonation legítima (soporte) será una feature **explícita, permisada (`impersonation:use`) y 100% auditada** — quién, a quién, desde y hasta cuándo. Ver [P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver) y [`ARQUITECTURA.md` §5.3](../docs/ARQUITECTURA.md).
