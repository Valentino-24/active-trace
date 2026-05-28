# 09 — Decisiones y Supuestos

Decisiones de diseño visibles en la herramienta + supuestos inferidos durante el análisis.

## Decisiones visibles (con evidencia)

### D1 — Moodle es upstream, no integración bidireccional
**Decisión**: el sistema **lee de Moodle vía exportación manual de Excel/CSV**, no escribe a Moodle ni consume API.

**Evidencia**: todas las importaciones son por subida de archivo. Las "salidas hacia Moodle" son snippets HTML que el docente pega manualmente.

**Por qué importa**: implica que el sistema vive desincronizado con Moodle entre cada import. Hay riesgo de datos viejos.

---

### D2 — Legajo como natural key del docente
**Decisión**: el docente se identifica universalmente por su `legajo` (entero), no por un UUID o email.

**Evidencia**: visible en URLs, en filtros, en campos `prof_leg`, `asig_leg`, `legs[]`, `responde_legs[]`.

**Por qué importa**: el sistema asume que el legajo es único, estable y disponible al alta. Si una institución no usa legajos, esto es bloqueante.

> ⚠️ **Decisión REVERTIDA en activia-trace**: la identidad de auth es un **UUID interno**, no el legajo. El legajo es atributo de negocio. Exponerlo como identidad en URLs habilitó [RN-41 / P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).

---

### D3 — Scope por (profesor, materia) en datos operativos
**Decisión**: los datos importados (calificaciones, umbrales, configuraciones) son **propios del par (docente, materia)**, no compartidos entre docentes.

**Evidencia**: leyenda explícita en `index.php`: *"Borra sólo tus datos en esta materia. No afecta a otros profesores."*

**Por qué importa**: dos profesores de la misma materia pueden tener importes y umbrales diferentes en paralelo. Cada uno ve sus métricas.

---

### D4 — Padrón EVALIA es upsert destructivo (sin historial)
**Decisión**: al importar un nuevo padrón de alumnos, el anterior se descarta.

**Evidencia**: *"La nueva carga reemplaza el padrón anterior de esa materia."*

**Por qué importa**: no hay historial de bajas/altas — solo el snapshot actual. Para análisis longitudinales, no es fiable.

---

### D5 — Aprobación humana para mails masivos
**Decisión**: existe un paso explícito de aprobación (`admin_mail_approval.php`) entre la generación y el despacho de mails.

**Evidencia**: ruta dedicada + estados Pend/Send/OK/Fail/Canc en `admin.php`.

**Por qué importa**: el sistema asume gobernanza institucional sobre comunicaciones — prioriza control sobre velocidad.

---

### D6 — Auditoría agresiva (IP + UA por acción)
**Decisión**: cada acción del usuario se loguea con IP y User-Agent.

**Evidencia**: tabla "Últimas acciones (máx. 200)" con columnas Fecha | Legajo | Materia | Acción | Rows | IP | User-Agent.

**Por qué importa**: comportamiento típico de sistemas en entornos regulados o con riesgo de disputa académica.

---

### D7 — Roles compuestos por flag `is_admin` + rol académico
**Decisión**: el modelo de permisos es ortogonal: el `rol` académico (PROFESOR, COORDINADOR) determina **qué se ve operativamente**, mientras que `is_admin` determina **qué se administra del sistema**.

**Evidencia**: checkbox `is_admin` separado del campo de rol en `admin_profesores.php`.

**Por qué importa**: un profesor regular puede ser admin (super-usuario funcional), y un coordinador puede no serlo (solo coordina sin manipular el sistema).

> ⚠️ **Decisión REVERTIDA en activia-trace**: el flag binario `is_admin` se reemplaza por **RBAC con permisos finos por feature** y roles ricos (`ALUMNO, TUTOR, PROFESOR, COORDINADOR, ADMIN, FINANZAS`). El flag binario producía permisos opacos ([P10](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)). Ver [RF-04](../docs/PRD.md#auth-roles-y-tenants) y [`ARQUITECTURA.md` §5.2](../docs/ARQUITECTURA.md).

---

### D8 — Vigencia temporal por asignación
**Decisión**: cada asignación tiene `desde` y `hasta`. La validez se deriva del rango.

**Evidencia**: campos `desde:date, hasta:date` en `admin_asignaciones.php` + columna "Vigencia" en `mis_equipos.php`.

**Por qué importa**: facilita rotación entre cuatrimestres sin borrar histórico.

---

### D9 — Clonado de equipos entre cohortes como primitivo
**Decisión**: hay una operación de primera clase "Clonar equipo docente" en lugar de pedir re-asignar manualmente.

**Evidencia**: form dedicado en `admin_reportes.php` con `ori_*` y `dest_*`.

**Por qué importa**: optimiza el caso común de fin de cuatrimestre. Indica que el sistema fue construido con el ciclo académico en mente.

---

### D10 — Aviso con `require_ack` para comunicaciones críticas
**Decisión**: los avisos pueden requerir confirmación explícita del lector.

**Evidencia**: checkbox `require_ack` + columnas "Vistos | ACK" en `admin_avisos.php`.

**Por qué importa**: permite trazabilidad de comunicaciones obligatorias (políticas, cambios de fechas, etc.).

---

### D11 — Modal de preview obligatorio antes de envío
**Decisión**: ningún mail se envía sin que el docente vea primero el Asunto + el Cuerpo HTML renderizado.

**Evidencia**: modal "Previsualización del email" en `index.php`.

**Por qué importa**: previene errores embarazosos (variables sin reemplazar, formato roto).

---

### D12 — Reportes y operaciones siempre exportan a Excel
**Decisión**: casi toda vista tabular tiene "Exportar Excel".

**Evidencia**: botones en guardias, monitor general, equipos, TPs sin corregir, liquidaciones.

**Por qué importa**: el sistema asume que la institución sigue trabajando con Excel para operativa offline.

---

## Supuestos (inferencias razonables sin evidencia directa)

### S1 — Autenticación por legajo + password
**Suposición:** el login pide legajo (o email) + password. No se observó la pantalla.

**Cómo validar**: cerrar sesión y revisar `login.php` o equivalente.

> ⚠️ **Definido para activia-trace** (no suposición): login por **email + password (Argon2id) + 2FA opcional (TOTP)**, sesión por **JWT** (access 15 min + refresh rotation). Ver [RF-01](../docs/PRD.md#auth-roles-y-tenants), [RNF-09](../docs/PRD.md#seguridad), [`ARQUITECTURA.md` §5.1](../docs/ARQUITECTURA.md).

---

### S2 — La columna "Estado" de asignaciones se computa server-side
**Suposición:** los valores "Vigente" / "Vencida" se calculan al render comparando fechas con NOW(), no se guardan en DB.

**Cómo validar**: revisar si hay un evento que actualice estado de asignaciones expiradas.

---

### S3 — Catálogos duplicados de materias = dos cohortes/sistemas distintos
**Suposición:** los 19 materias de `index.php` y los 12 de `monitor_evalia.php` son catálogos paralelos, posiblemente:
- (a) Plan de estudios viejo vs nuevo de TUPAD, o
- (b) TUPAD vs otra carrera/programa no detectada, o
- (c) Cursos abiertos vs carrera oficial.

**Cómo validar**: ver [10_preguntas_abiertas.md PA-01](10_preguntas_abiertas.md#pa-01).

---

### S4 — El worker de mails es un cron/queue server-side
**Suposición:** los estados Pend/Send/OK/Fail/Canc implican una cola persistente procesada por un worker fuera del request HTTP.

**Cómo validar**: revisar `crontab -l` en el server, buscar processes de queue.

---

### S5 — La grilla de salarios es por (rol, regional, ...)
**Suposición:** `salarios.php` permite definir una grilla cruzando rol × regional × algún otro criterio (antigüedad? cohorte?) para alimentar el cálculo de liquidaciones.

**Cómo validar**: pedir acceso con rol admin financiero.

---

### S6 — `cuil_view` es un campo derivado
**Suposición:** el campo `cuil_view` (solo lectura en `perfil.php`) se calcula a partir del DNI y sexo del docente, sin almacenarse explícitamente.

**Cómo validar**: revisar código de render del perfil.

---

### S7 — `ctx_id` en `mis_tareas.php` es un contexto multi-tenant o multi-cohorte
**Suposición:** el filtro `ctx_id` agrupa tareas por algún contexto superior (cohorte? carrera? cuatrimestre?).

**Cómo validar**: inspeccionar las opciones del select cuando hay tareas asignadas.

---

### S8 — Los mails personalizados usan plantillas server-side
**Suposición:** existe un template engine (Twig? Blade? string interpolation manual?) que genera el body HTML para cada alumno.

**Cómo validar**: pedir un ejemplo del template o revisar el código.

---

### S9 — `materia_slug` en avisos es el codigo (ej: "PROG_I")
**Suposición:** el `materia_slug` en avisos es el código de materia (PROG_I, DB_II, ...), no el ID numérico ni el nombre.

**Cómo validar**: ver un aviso real con scope=materia.

---

### S10 — El rol "TUTOR" existe pero el usuario actual no lo tiene como primario
**Suposición:** el link "Vista admin" / "Vista tutor" en `monitor_evalia.php` sugiere un rol TUTOR diferenciado de PROFESOR y COORDINADOR.

**Cómo validar**: ver el catálogo de roles en `admin_asignaciones.php` (opción `f_rol`).

---

### S11 — Datos bancarios sensibles están cifrados en reposo
**Suposición:** CBU, alias y banco se almacenan cifrados.

**Cómo validar**: pedir acceso a DB o documentación interna.

---

### S12 — El sistema tiene CDN o caché de assets
**Suposición:** los modales y forms cargan rápido — probablemente hay caché de templates o de assets estáticos.

**Cómo validar**: revisar headers HTTP.

---

## No-decisiones (cosas que el sistema decididamente NO hace)

### ND1 — No tiene UI para alumno
El alumno es objeto, no usuario.

### ND2 — No genera reuniones de Meet automáticamente
Solo guarda URLs.

### ND3 — No envía mails sin aprobación
Existe el paso de aprobación intencional.

### ND4 — No mantiene historial de padrón
Cada import sobrescribe.

### ND5 — No tiene API pública documentada
Todas las operaciones son vía UI form-post.

### ND6 — No tiene reportes BI / dashboards analíticos
El panel es operativo (qué pasó), no analítico (tendencias, predicciones).
