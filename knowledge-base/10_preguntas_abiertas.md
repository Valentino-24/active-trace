# 10 — Preguntas Abiertas

Inconsistencias detectadas y preguntas que requieren validación con el responsable del producto o acceso a más información.

## ✅ Preguntas CERRADAS en la segunda pasada (con `?leg=1`)

### ~~PA-02~~ — RESUELTA: el rol TUTOR existe formalmente
**Resolución**: el catálogo cerrado de roles en `salarios.php` es `ALL, PROFESOR, TUTOR, NEXO, COORDINADOR`. Se confirmó además un rol nuevo (**NEXO**) que no era visible en la primera pasada.

### ~~PA-06~~ — RESUELTA: cálculo de liquidación
**Resolución**: la fórmula se compone de **Base por rol** (catálogo grilla en `salarios.php`) + **Plus por (clave, rol)** donde la clave agrupa familias de materias (ej: `PROG` = Programación). Ver [RN-31](05_reglas_de_negocio.md#rn-31) a [RN-38](05_reglas_de_negocio.md#rn-38).

### ~~PA-03~~ — REFINADA: `admin_mail_approval.php` redirige cuando no hay items pendientes
**Resolución parcial**: aún con super-admin (`?leg=1`) la página redirige a `index.php` cuando se entra sin contexto. **Hipótesis**: redirige cuando la cola de mails pendientes está vacía. Sigue pendiente verificar con tráfico real.

## Nuevas preguntas detectadas en la segunda pasada

### PA-21 — ¿Cómo está auditado el uso de `?leg=X` (impersonation)?
**Observación**: navegar a `https://olsoft.online/evalia/mood/?leg=1` cambia el contexto del usuario logueado al legajo indicado (probado: cambió de Cortez Alberto a Rodriguez Georgina, legajo 1).

**Pregunta**: ¿Queda registrado en audit log quién hizo la impersonation y cuándo? ¿Quiénes tienen permiso de impersonar? ¿Hay forma de "salir" del contexto impersonado o se mantiene hasta cierre de sesión?

**Implicación de seguridad**: si no está logueado quién dispara `?leg=X`, cualquier acción del impersonator queda atribuida al impersonated, lo cual rompe la trazabilidad.

> 🔴 **Esta es una pregunta sobre olsoft, pero la dirección de diseño en activia-trace ya está cerrada**: clasificada como [P11 CRÍTICO (OWASP A01)](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver). Se elimina de raíz (identidad solo desde JWT; impersonation legítima permisada y auditada). **Lo único pendiente de verificar** es si en olsoft el `?leg=X` funciona también **sin sesión previa** (full pre-auth bypass) — eso es [ADR-004](../docs/ARQUITECTURA.md) y no cambia el diseño destino, solo la severidad documentada del sistema viejo.

### PA-22 — ¿Cuántas "claves de Plus" existen y cómo se mapean a materias?
**Observación**: en `salarios.php` se vio solo la clave `PROG` (Plus Programación) con valores para PROFESOR/TUTOR/COORDINADOR.

**Pregunta**: ¿Existen otras claves (BD, ING, MAT, etc.)? ¿Cómo se decide qué materias caen en cada clave? ¿Está hardcodeado o configurable?

### PA-23 — ¿Cómo se calcula el Plus si un docente tiene N comisiones de la misma clave?
**Pregunta**: si un PROFESOR tiene 3 comisiones de PROG, ¿se le suma 3 × Plus PROG o solo 1 × Plus PROG?

### PA-24 — ¿Las facturas se asocian a comisiones específicas o son globales por docente?
**Observación**: `admin_facturas.php` tiene columna "Detalle" con texto libre ("Factura Mayo", "Armado de aula legislación") pero no se ve asociación formal a una materia/comisión.

**Pregunta**: ¿Cómo se concilia la factura con el trabajo real prestado?

### PA-25 — ¿NEXO está asociado a un eje concreto (regional, programa, etc.)?
**Observación**: el rol existe y tiene tratamiento contable separado, pero su semántica no es explícita.

**Pregunta**: ¿Un NEXO cubre una regional? ¿Una cohorte? ¿Un grupo de docentes? ¿Es enlace con el alumno?

---

## Prioridad ALTA — bloqueantes para entender el modelo

### PA-01 — ¿Por qué hay dos catálogos de materias separados?
**Inconsistencia**: `index.php` muestra 19 materias con códigos `(AYSO)`, `(PROG_I)`, etc. con IDs 1-22. `monitor_evalia.php` muestra 12 materias con nombres descriptivos ("Programación - Python", "Programación - Java", etc.) con IDs 1-19 distintos.

Los IDs colisionan pero los nombres no coinciden:
- `id=3` en catálogo A = "Programacion I (PROG_I)"
- `id=4` en catálogo B = "Programación - Python"

**Hipótesis**:
- (a) Son DOS plataformas distintas (Procesos Moodle vs EVALIA) con tablas independientes.
- (b) Son DOS cohortes diferentes (plan viejo vs nuevo).
- (c) Son DOS programas distintos (carrera oficial vs cursos abiertos).

**Pregunta**: ¿Cuál es la fuente de verdad? ¿Hay relación entre ambos catálogos? ¿Las calificaciones se migran entre ellos?

---

### PA-02 — ¿Cuál es el rol "Tutor"?
**Evidencia**: link "Vista tutor" en `admin_monitor_evalia.php` y link "Vista admin" en `monitor_evalia.php` sugieren que existe un rol TUTOR distinto de PROFESOR y COORDINADOR.

**Pregunta**: ¿Es un rol formal en `admin_asignaciones.php`? ¿Qué pantallas ve un tutor que un profesor no?

---

### PA-03 — ¿Qué pasa en `admin_mail_approval.php`?
**Observación**: la ruta redirige silentemente al `index.php` para el usuario con rol PROFESOR+COORDINADOR observado.

**Pregunta**: ¿quién (qué rol) tiene acceso? ¿Es un superadmin? ¿Cuál es el flujo de aprobación: por lote, por destinatario, por contenido?

---

### PA-04 — ¿Cuál es la pantalla de login?
**Observación**: no se observó el flujo de auth porque el usuario estaba logueado al inicio.

**Pregunta**:
- ¿Login es por legajo o por email?
- ¿Hay 2FA?
- ¿Hay "Recordarme"?
- ¿Hay flujo de recuperación de contraseña?
- ¿Hay self-service signup o solo alta administrativa?

> ✅ **Dirección de diseño cerrada para activia-trace** (independiente de lo que haga olsoft): login por **email + password (Argon2id) + 2FA opcional (TOTP)**; recuperación por email con token de un solo uso; alta administrativa (signup self-service NO en MVP). Ver [RF-01/RF-02](../docs/PRD.md#auth-roles-y-tenants) y [`ARQUITECTURA.md` §5.1](../docs/ARQUITECTURA.md). Decisión auth propio vs Moodle SSO → [ADR-001 / OQ-04](../docs/PRD.md#12-open-questions-a-resolver-antes-de-cerrar-el-prd).

---

### PA-05 — ¿Cómo se da de alta una guardia?
**Observación**: `mis_guardias.php` solo muestra el listado de 250 guardias, no se vio formulario de creación.

**Pregunta**: ¿Las guardias se crean desde otro flujo (encuentros? tareas?) o hay una pantalla dedicada que requiere un permiso/contexto distinto?

---

### PA-06 — ¿Cómo se calcula la base y plus de liquidación?
**Observación**: tabla `Leg | Docente | Rol | Comisiones | Base | Plus | Total` en `liquidaciones.php`, pero la fórmula no es explícita.

**Hipótesis**:
- Base = valor de la grilla (`salarios.php`) según rol.
- Plus = bonificaciones por comisiones extra o por desempeño.
- Total = Base + Plus.

**Pregunta**: ¿el plus se calcula por reglas duras o se ingresa manualmente? ¿Hay otros conceptos (descuentos, retenciones)?

---

## Prioridad MEDIA — refinamiento del modelo

### PA-07 — ¿Las cohortes pertenecen a una carrera?
**Observación**: `admin_cohortes.php` no muestra columna "Carrera". Las cohortes parecen globales.

**Pregunta**: ¿Una cohorte como "MAR-2026" es exclusiva de TUPAD o pueden compartirse entre carreras?

---

### PA-08 — ¿Qué significan los estados de Tarea?
**Observación**: `admin_tareas.php` tiene filtro de estado pero no se observaron los valores del enum.

**Pregunta**: ¿Cuál es el ciclo de vida de una tarea? (ej: abierta → en progreso → completada → archivada)

---

### PA-09 — ¿Qué hay en la sub-tab "Mail" de Mis equipos?
**Observación**: tabs detectados: "Mi equipo / Monitoreo / Mail" en `mis_equipos.php`. La tab "Mail" no se exploró en profundidad.

**Pregunta**: ¿Es para mandar mails masivos al equipo? ¿O es comunicación grupal entre docentes?

---

### PA-10 — ¿`materia_slug` es el código o el ID?
**Observación**: en `admin_avisos.php` el campo se llama `materia_slug:select-one`.

**Pregunta**: ¿Es el código (PROG_I) o un ID alfanumérico distinto?

---

### PA-11 — ¿Qué hay detrás de "Criterio de clasificación" en monitor general?
**Observación**: botón con ese texto en `admin_monitor_general.php`, abre un modal.

**Pregunta**: ¿Qué criterios se pueden configurar? ¿Se guardan por usuario o son globales?

---

### PA-12 — ¿Qué incluye la "vista admin" de encuentros?
**Observación**: tab "Vista admin" detectada en `encuentros.php` pero no se exploró.

**Pregunta**: ¿Permite ver encuentros de TODOS los profesores y editarlos? ¿O solo agregar?

---

### PA-13 — ¿Qué es `ctx_id` en `mis_tareas.php`?
**Observación**: filtro `ctx_id:select-one` sin claridad de qué contiene.

**Pregunta**: ¿Es un agrupador por cohorte, materia, o algún contexto distinto?

---

### PA-14 — ¿Cómo funcionan las reservas de coloquios para el alumno?
**Observación**: el sistema muestra "Reservas activas" y "Cupos libres" pero no se vio cómo el alumno reserva.

**Pregunta**: ¿La reserva se hace desde Moodle? ¿Desde un link público? ¿Desde el inbox del docente?

---

### PA-15 — ¿`Correct-IA` está integrado con calificaciones?
**Observación**: link a `https://olsoft.online/evalia/corrector/index.php` desde el menú Procesos, pero es un módulo externo.

**Pregunta**: ¿Las correcciones automáticas vuelven a este sistema o son independientes? ¿Hay alguna sincronización?

---

## Prioridad BAJA — pulido y documentación

### PA-16 — ¿Hay convención de severities en avisos?
**Pregunta**: ¿Los `severity` son enums fijos (info/warn/error)? ¿Se renderizan con colores? ¿Cómo afectan al usuario?

---

### PA-17 — ¿`factura` cambia el cálculo de liquidación?
**Suposición:** el checkbox `factura` distingue monotributistas. ¿Modifica cálculos o solo es informativo?

---

### PA-18 — ¿`cuil_view` se calcula o se guarda?
**Pregunta**: ¿se genera con la regla CUIL = `prefijo-DNI-verificador` o se carga manualmente?

---

### PA-19 — ¿Hay flujo de baja de docente?
**Observación**: hay botón "Desactivar" pero no se observó qué pasa con sus asignaciones vigentes.

**Pregunta**: ¿Las asignaciones se cierran automáticamente al desactivar el docente? ¿Quedan huérfanas?

---

### PA-20 — ¿Cómo se documenta el sistema actualmente?
**Pregunta meta**: ¿Existe documentación interna ya escrita? ¿Manuales? ¿Wiki? ¿Casos de uso documentados?

---

## Inconsistencias menores detectadas

### IM-01 — Mezcla de "accion" y "action" como nombre de campo hidden
- `admin_profesores.php`: usa `action:hidden`
- `admin_carreras.php`: usa `accion:hidden`

→ Inconsistencia menor de nomenclatura.

### IM-02 — Codificación textual con typo: "redoneadas"
En la leyenda de `index.php`: *"para tomar notas numéricas **redoneadas** (Moodle)"* → typo de "redondeadas".

### IM-03 — Mezcla de "Programacion" sin acento y "Programación" con acento
- `Programacion I (PROG_I)` (sin acento)
- `Programación II (PROG_II)`, `Programación III (PROG_III)` (con acento)

→ Inconsistencia ortográfica en datos seed.

### IM-04 — Materia "SYS (SYS)" — redundante
Una de las opciones del select es literalmente `SYS (SYS)` — código y nombre iguales sugiere que falta el nombre largo.

### IM-05 — Mezcla "Miercoles" sin acento
En `mis_guardias.php`: día `Miercoles` (sin acento) en datos reales — debería ser "Miércoles".

---

## Validación recomendada

Para cerrar estas preguntas se recomienda:

1. **Una sesión de 60 minutos con el dueño del producto** (presumiblemente Oscar Londero según el footer).
2. **Acceso de lectura al esquema de DB** para confirmar el modelo de [04_modelo_de_datos.md](04_modelo_de_datos.md).
3. **Acceso con rol "ADMIN total"** para documentar `salarios.php` y `admin_mail_approval.php`.
4. **Documentar Correct-IA en un archivo separado** (`11_correct_ia.md`) como módulo extra de la KB.
