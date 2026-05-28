# 11 — Historias de Usuario

Historias de usuario derivadas del análisis funcional. Formato **Connextra** (Como / Quiero / Para) con criterios de aceptación (CA) y referencias a [Features (06)](06_funcionalidades.md) y [Reglas de Negocio (05)](05_reglas_de_negocio.md).

**Convenciones**:
- ID `HU-XX` para cada historia.
- Prioridad: 🔴 Alta · 🟡 Media · 🟢 Baja (derivada del impacto observado en producción).
- Estado: ✅ Implementada (visible en producción) · 🔧 Parcial · ❓ Inferida.

---

## Épica 1 — Ingesta de Datos desde Moodle

### HU-01 🔴 ✅ — Importar calificaciones por materia
**Como** PROFESOR
**Quiero** subir el Excel de calificaciones exportado de Moodle de mi materia
**Para** consolidar todas las notas de las actividades en un solo lugar y poder analizarlas.

**CA**:
- Debo poder seleccionar la materia desde un dropdown antes de subir.
- El sistema acepta solo archivos `.xlsx`.
- Al darle "Generar preview" veo la lista de actividades detectadas y elijo cuáles analizar.
- Las columnas terminadas en `(Real)` se interpretan como nota numérica redondeada ([RN-01](05_reglas_de_negocio.md#rn-01)).
- Los valores "Satisfactorio" y "Supera lo esperado" se guardan como `nota_texto` y cuentan como aprobado ([RN-02](05_reglas_de_negocio.md#rn-02)).
- La acción queda registrada en el audit log ([RN-23](05_reglas_de_negocio.md#rn-23)).

→ Ref: [F1.1](06_funcionalidades.md#f11--importar-excel-de-calificaciones-por-materia)

---

### HU-02 🔴 ✅ — Detectar entregas finalizadas sin corregir
**Como** PROFESOR
**Quiero** subir el reporte de finalización de Moodle
**Para** que el sistema me marque qué trabajos están entregados pero todavía no califiqué.

**CA**:
- Acepta archivos `.xlsx` o `.csv/.tsv` directamente de Moodle.
- Se obtiene una tabla "Posibles TPs sin corregir" agrupada por actividad.
- Solo se listan actividades de **escala textual** ([RN-08](05_reglas_de_negocio.md#rn-08)).
- Puedo exportar la tabla a Excel.
- Si no hay pendientes, se muestra "No se detectaron pendientes para corregir 🎉".

→ Ref: [F1.2](06_funcionalidades.md#f12--importar-reporte-de-finalización-para-detectar-tp-sin-corregir), [RN-07](05_reglas_de_negocio.md#rn-07)

---

### HU-03 🟡 ✅ — Importar padrón de alumnos EVALIA
**Como** PROFESOR
**Quiero** cargar el padrón de participantes desde Moodle para una materia EVALIA
**Para** tener la lista actualizada de alumnos contra la cual cruzar las actividades.

**CA**:
- Subo el archivo y selecciono la materia.
- El sistema toma Nombre, Apellido(s), Email y Grupos.
- La nueva carga **reemplaza** el padrón anterior — no hay merge ([RN-05](05_reglas_de_negocio.md#rn-05)).
- Recibo confirmación visible del resultado.

→ Ref: [F1.3](06_funcionalidades.md#f13--importar-padrón-evalia)

---

### HU-04 🟡 ✅ — Vaciar mis datos de una materia
**Como** PROFESOR
**Quiero** un botón para borrar mis datos de una materia
**Para** poder empezar de cero sin afectar a los otros profesores de esa misma materia.

**CA**:
- El borrado afecta solo a mi `(profesor_legajo, materia_id)`, no a otros docentes ([RN-04](05_reglas_de_negocio.md#rn-04)).
- Se muestra leyenda explicativa antes del confirm.
- El POST lleva token CSRF.

→ Ref: [F1.5](06_funcionalidades.md#f15--vaciar-datos-por-materia)

---

## Épica 2 — Análisis y Reportes Académicos

### HU-05 🔴 ✅ — Configurar umbral de aprobación por materia
**Como** PROFESOR
**Quiero** definir el umbral porcentual para considerar a un alumno como atrasado
**Para** ajustar el criterio a las pautas pedagógicas de cada materia.

**CA**:
- El valor default es 60% ([RN-03](05_reglas_de_negocio.md#rn-03)).
- Se guarda por `(profesor_legajo, materia_id)`.
- El cambio impacta inmediatamente en la sección "Estudiantes atrasados" y rankings.

→ Ref: [F2.1](06_funcionalidades.md#f21--configurar-umbral-por-materia)

---

### HU-06 🔴 ✅ — Ver lista de alumnos atrasados
**Como** PROFESOR
**Quiero** ver qué alumnos están atrasados (sin entregas o con nota < umbral)
**Para** decidir a quiénes mandar recordatorios.

**CA**:
- La sección 3 muestra cantidad de alumnos y la tabla detallada.
- Definición: faltantes o `nota < umbral` ([RN-06](05_reglas_de_negocio.md#rn-06)).
- Si no hay atrasados se muestra "¡No hay atrasados! 🎉".

→ Ref: [F2.2](06_funcionalidades.md#f22--visualizar-estudiantes-atrasados)

---

### HU-07 🟡 ✅ — Ver ranking de alumnos por aprobadas
**Como** PROFESOR
**Quiero** un ranking de alumnos por cantidad de actividades aprobadas
**Para** identificar quiénes están más adelantados y quiénes necesitan apoyo.

**CA**:
- Solo se listan alumnos con al menos 1 actividad aprobada ([RN-09](05_reglas_de_negocio.md#rn-09)).
- Si no hay datos suficientes se muestra mensaje aclaratorio.

→ Ref: [F2.3](06_funcionalidades.md#f23--ranking-de-aprobadas)

---

### HU-08 🟡 ✅ — Generar notas finales agrupadas para Excel
**Como** PROFESOR
**Quiero** definir agrupaciones de actividades para producir la nota final del alumno
**Para** exportar el reporte oficial de la materia.

**CA**:
- Se puede configurar qué actividades entran en cada grupo.
- Output exportable a Excel.
- Si no hay actividades configuradas se muestra el placeholder explicativo.

→ Ref: [F2.5](06_funcionalidades.md#f25--notas-finales-agrupación-para-excel)

---

### HU-09 🟡 ✅ — Filtrar monitor general de alumnos
**Como** COORDINADOR
**Quiero** filtrar el monitor general por materia, regional, comisión, búsqueda libre y estado
**Para** ubicar rápidamente a alumnos en riesgo a nivel institucional.

**CA**:
- Los filtros se aplican vía GET (URL compartible).
- Acción "Exportar" descarga la vista filtrada.
- Existe modal "Criterio de clasificación" para ajustar reglas (→ [PA-11](10_preguntas_abiertas.md#pa-11)).

→ Ref: [F2.7](06_funcionalidades.md#f27--monitor-general-de-alumnos-vista-admin)

---

## Épica 3 — Comunicación con Alumnos

### HU-10 🔴 ✅ — Previsualizar mail antes de enviarlo
**Como** PROFESOR
**Quiero** ver el Asunto + Cuerpo HTML renderizado de cada mail antes del envío
**Para** evitar errores de formato o variables sin reemplazar.

**CA**:
- Se abre un modal "Previsualización del email" con render HTML real.
- El mail NO se envía hasta que confirmo desde el preview ([RN-16](05_reglas_de_negocio.md#rn-16)).

→ Ref: [F3.1](06_funcionalidades.md#f31--preview-del-email-antes-de-enviar)

---

### HU-11 🔴 ✅ — Enviar recordatorios masivos a alumnos atrasados
**Como** PROFESOR
**Quiero** disparar un envío masivo a todos los alumnos atrasados detectados
**Para** comunicar el estado y motivar la regularización sin escribir mails uno por uno.

**CA**:
- Los mails entran a la cola en estado `Pend` ([RN-15](05_reglas_de_negocio.md#rn-15)).
- Cada mail es personalizado por alumno (no copy-paste).
- Veo el conteo de OK/Fail/Canc en el panel de interacciones (`admin.php`).

→ Ref: [F3.2](06_funcionalidades.md#f32--envío-masivo-con-cola)

---

### HU-12 🔴 ❓ — Aprobar mails masivos antes de despacho
**Como** ADMIN (o rol con permiso de aprobación)
**Quiero** revisar y aprobar la cola de mails pendientes
**Para** evitar envíos accidentales o no autorizados desde la institución.

**CA**:
- Acceso restringido al endpoint `admin_mail_approval.php`.
- Roles sin permiso reciben silently-redirect al index.
- Al aprobar, el mail pasa de `Pend` → `Send` y el worker lo despacha.
- Al cancelar, queda en estado `Canc` ([RN-17](05_reglas_de_negocio.md#rn-17)).

→ Ref: [F3.3](06_funcionalidades.md#f33--aprobación-de-envíos-masivos), [PA-03](10_preguntas_abiertas.md#pa-03)

---

### HU-13 🟡 ✅ — Recibir y responder mensajes internos
**Como** DOCENTE (PROFESOR o COORDINADOR)
**Quiero** ver mi inbox y responder mensajes desde el perfil
**Para** mantener comunicación interna con coordinación y el sistema.

**CA**:
- En `perfil.php` veo los threads abiertos.
- Puedo responder con asunto + cuerpo.
- La respuesta queda asociada al thread original.

→ Ref: [F3.4](06_funcionalidades.md#f34--mensajería-interna-inbox-del-docente)

---

### HU-14 🟡 ✅ — Publicar aviso del sistema con scope y vigencia
**Como** COORDINADOR
**Quiero** publicar avisos segmentados por materia, cohorte y rol con ventana de vigencia
**Para** comunicar novedades a los docentes pertinentes sin spamear al resto.

**CA**:
- Defino scope (global / materia / cohorte), `materia_slug`, `cohorte_id`, `role_target`, severity.
- Defino `start_at` y `end_at` — solo se muestra dentro de la ventana ([RN-18](05_reglas_de_negocio.md#rn-18)).
- Puedo marcar `require_ack` si necesito confirmación obligatoria ([RN-19](05_reglas_de_negocio.md#rn-19)).
- El listado muestra contadores Vistos / ACK.

→ Ref: [F3.5](06_funcionalidades.md#f35--avisos-del-sistema-tablón)

---

### HU-15 🟢 ✅ — Acusar recibo de un aviso obligatorio
**Como** DOCENTE
**Quiero** confirmar que leí un aviso marcado `require_ack`
**Para** dejar registro de cumplimiento ante la institución.

**CA**:
- El sistema cuenta mi ACK en el contador agregado del aviso.
- Una vez ACK, el aviso queda marcado como leído por mí.

→ Ref: [RN-19](05_reglas_de_negocio.md#rn-19)

---

## Épica 4 — Gestión de Equipos Docentes

### HU-16 🔴 ✅ — Dar de alta un profesor
**Como** COORDINADOR
**Quiero** registrar un nuevo profesor con sus datos personales y bancarios
**Para** que pueda recibir asignaciones y liquidaciones.

**CA**:
- Campos requeridos: legajo, nombre, dni, banco, cbu, alias_cbu, regional, email.
- Campos opcionales: legajo_profesional.
- Flags: `estado` (activo/inactivo), `is_admin`.
- El legajo es la natural key — debe ser único ([D2](09_decisiones_y_supuestos.md#d2)).
- POST con CSRF.

→ Ref: [F4.1](06_funcionalidades.md#f41--abm-de-profesores)

---

### HU-17 🟡 ✅ — Ver mis equipos de trabajo
**Como** DOCENTE
**Quiero** ver en qué materias, carrera, cohorte y rol estoy asignado actualmente
**Para** tener una vista consolidada de mis responsabilidades.

**CA**:
- La tabla muestra Carrera | Cohorte | Rol | Comisiones | Vigencia | Estado.
- El Estado se deriva del rango de vigencia ([RN-10](05_reglas_de_negocio.md#rn-10)).
- Puedo filtrar por estado/materia/rol/carrera/cohorte.

→ Ref: [F4.2](06_funcionalidades.md#f42--mis-equipos-vista-propia)

---

### HU-18 🔴 ✅ — Asignar masivamente docentes a una materia
**Como** COORDINADOR
**Quiero** asignar múltiples docentes a una materia × carrera × cohorte × rol en una sola operación
**Para** acelerar el setup de inicio de cuatrimestre.

**CA**:
- Selecciono materia, carrera, cohorte, rol, fechas desde/hasta y comisiones.
- Puedo seleccionar múltiples legajos con checkboxes o con búsqueda bulk ([RN-30](05_reglas_de_negocio.md#rn-30)).
- Puedo indicar uno o varios "responde_legs" (jerarquía coordinador→profesor) ([RN-11](05_reglas_de_negocio.md#rn-11)).
- El POST lleva CSRF.

→ Ref: [F4.4](06_funcionalidades.md#f44--asignación-masiva)

---

### HU-19 🔴 ✅ — Clonar equipo docente entre cohortes
**Como** COORDINADOR
**Quiero** copiar todas las asignaciones de una materia/carrera/cohorte origen a otra cohorte destino
**Para** no recrear manualmente el equipo al cambiar cuatrimestre.

**CA**:
- Defino origen (materia × carrera × cohorte) y destino (idem).
- El sistema duplica las asignaciones con las fechas del destino ([RN-12](05_reglas_de_negocio.md#rn-12)).
- Se confirma con preview o mensaje de éxito.

→ Ref: [F4.5](06_funcionalidades.md#f45--clonar-equipo-docente)

---

### HU-20 🟡 ✅ — Modificar vigencia general de un equipo
**Como** COORDINADOR
**Quiero** cambiar las fechas `desde/hasta` de todas las asignaciones de un equipo en bloque
**Para** ajustar el período cuando cambia el calendario académico.

**CA**:
- Selecciono el equipo (materia × carrera × cohorte).
- Defino nueva `vigenciaDesdeEquipo` y `vigenciaHastaEquipo`.
- El cambio se aplica a TODAS las asignaciones vigentes del equipo.

→ Ref: [F4.6](06_funcionalidades.md#f46--modificar-vigencia-general-del-equipo)

---

## Épica 5 — Estructura Académica

### HU-21 🟡 ✅ — Administrar carreras
**Como** COORDINADOR
**Quiero** crear, editar y desactivar carreras (código + nombre)
**Para** mantener actualizado el catálogo institucional.

**CA**:
- Campos: código (único, ej "TUPAD") y nombre largo.
- Estados: Activa / Inactiva.
- POST con CSRF.

→ Ref: [F5.1](06_funcionalidades.md#f51--abm-de-carreras)

---

### HU-22 🔴 ✅ — Administrar cohortes
**Como** COORDINADOR
**Quiero** crear cohortes con nombre, año, vig_desde, vig_hasta
**Para** que las asignaciones y avisos puedan asociarse a periodos específicos.

**CA**:
- Campos: nombre (ej "MAR-2026"), año, fecha desde, fecha hasta (opcional), estado.
- Se puede desactivar sin borrar histórico.

→ Ref: [F5.2](06_funcionalidades.md#f52--abm-de-cohortes)

---

### HU-23 🟡 ✅ — Subir programa de materia (PDF)
**Como** COORDINADOR
**Quiero** subir el PDF del programa de cada materia por carrera + cohorte
**Para** que los docentes y la institución tengan la versión oficial centralizada.

**CA**:
- Selecciono materia + carrera + cohorte + título + archivo PDF.
- Puedo listar, descargar y reemplazar programas existentes.
- Filtrable por materia/carrera/cohorte.

→ Ref: [F5.3](06_funcionalidades.md#f53--programas-de-materias-pdf)

---

### HU-24 🟡 ✅ — Gestionar fechas de parciales/TP/coloquios
**Como** COORDINADOR
**Quiero** cargar las fechas clave de evaluación por materia + cohorte
**Para** que los docentes y alumnos sepan cuándo es cada instancia.

**CA**:
- Campos: materia, tipo (Parcial/TP/Coloquio), número, fecha, cohorte, título.
- Vistas: tabla lineal y Calendario de evaluaciones.
- Hay sección "HTML para Moodle" para pegar el cronograma en el aula virtual.

→ Ref: [F5.4](06_funcionalidades.md#f54--fechas-de-parciales--tp--coloquios)

---

## Épica 6 — Encuentros y Disponibilidad

### HU-25 🔴 ✅ — Crear slot de encuentro recurrente
**Como** PROFESOR
**Quiero** definir un encuentro recurrente (mismo día y hora durante N semanas)
**Para** que el sistema genere automáticamente todas las instancias del cuatrimestre.

**CA**:
- Modo recurrente: día semana + hora + fecha desde + cantidad de semanas ([RN-13](05_reglas_de_negocio.md#rn-13)).
- Se generan N instancias automáticamente.
- Cada instancia hereda materia, título y URL de Meet.

→ Ref: [F6.1](06_funcionalidades.md#f61--crear-slot-de-encuentro-recurrente)

---

### HU-26 🟡 ✅ — Crear encuentro único (no recurrente)
**Como** PROFESOR
**Quiero** crear un encuentro de una sola fecha
**Para** los casos especiales (recuperatorios, charlas, eventos puntuales).

**CA**:
- Modo único: una sola fecha + hora + título + meet.

→ Ref: [F6.2](06_funcionalidades.md#f62--crear-encuentro-único)

---

### HU-27 🟡 ✅ — Editar instancia individual de encuentro
**Como** PROFESOR
**Quiero** editar el estado, URL de Meet, URL del video grabado y comentarios de cada instancia
**Para** llevar registro de lo que efectivamente ocurrió ([RN-14](05_reglas_de_negocio.md#rn-14)).

**CA**:
- Edito instancia por ID, sin afectar el slot recurrente original.
- El campo `video_url` queda disponible post-encuentro.

→ Ref: [F6.3](06_funcionalidades.md#f63--editar-instancia-de-encuentro)

---

### HU-28 🟢 ✅ — Generar HTML de encuentros para Moodle
**Como** PROFESOR
**Quiero** obtener un snippet HTML con mis slots/instancias
**Para** pegarlo en el aula virtual sin formatearlo manualmente.

**CA**:
- Botón/sección "HTML para Moodle" devuelve el snippet listo para copiar.

→ Ref: [F6.4](06_funcionalidades.md#f64--generar-html-para-moodle)

---

### HU-29 🟡 ✅ — Ver mis guardias realizadas
**Como** TUTOR / PROFESOR
**Quiero** ver el historial de mis guardias con día, horario, estado y comentarios
**Para** llevar registro de mi disponibilidad efectiva.

**CA**:
- Tabla con # | Tutor | Materia | Carrera/Cohorte | Día | Horario | Estado | Comentarios | Creada.
- Estado mínimo confirmado: "finalizado".
- Puedo exportar a Excel.
- (→ [PA-05](10_preguntas_abiertas.md#pa-05): no se observó el flujo de alta de guardia).

→ Ref: [F6.6](06_funcionalidades.md#f66--registro-de-guardias)

---

## Épica 7 — Coloquios

### HU-30 🟡 ✅ — Importar alumnos para coloquio
**Como** PROFESOR
**Quiero** cargar el padrón de alumnos elegibles para una instancia de coloquio
**Para** convocar solo a los que corresponde.

**CA**:
- Endpoint dedicado `importar.php` dentro de `coloquios/`.

→ Ref: [F7.2](06_funcionalidades.md#f72--importar-alumnos-a-coloquios)

---

### HU-31 🔴 ✅ — Crear nueva convocatoria de coloquio
**Como** PROFESOR
**Quiero** definir una evaluación de coloquio con materia, instancia, días disponibles y cupos
**Para** que los alumnos puedan reservar lugar.

**CA**:
- Form en `convocatoria_form.php`.
- El listado posterior muestra Convocados, Reservas y Cupos libres.

→ Ref: [F7.3](06_funcionalidades.md#f73--nueva-evaluación-de-coloquio)

---

### HU-32 🟡 ✅ — Ver agenda consolidada de reservas
**Como** COORDINADOR
**Quiero** ver todas las reservas activas de coloquios en una agenda
**Para** anticipar carga operativa y solapamientos.

**CA**:
- Sección "Agenda de reservas activas" en `admin_coloquios.php`.
- Filtros: materia, tutor, desde, hasta, búsqueda libre.

→ Ref: [F7.5](06_funcionalidades.md#f75--admin-de-coloquios)

---

### HU-33 🟡 ✅ — Ver registro académico consolidado de coloquios
**Como** COORDINADOR
**Quiero** ver las notas finales consolidadas de los coloquios rendidos
**Para** auditar resultados y generar reportes oficiales.

**CA**:
- Sección "Registro académico consolidado" en `admin_coloquios.php`.

→ Ref: [F7.5](06_funcionalidades.md#f75--admin-de-coloquios)

---

## Épica 8 — Workflow de Tareas

### HU-34 🟡 ✅ — Ver mis tareas asignadas
**Como** PROFESOR
**Quiero** ver las tareas que la coordinación me asignó
**Para** organizar mi trabajo administrativo.

**CA**:
- Listado en `mis_tareas.php` filtrable por contexto.
- Veo descripción, último comentario y estado.

→ Ref: [F8.1](06_funcionalidades.md#f81--mis-tareas-vista-profesor)

---

### HU-35 🟡 ✅ — Delegar una tarea a otro profesor
**Como** PROFESOR
**Quiero** asignar una tarea a un colega
**Para** delegar trabajo de coordinación interna entre el equipo.

**CA**:
- Botón "Asignar (Profe)" disponible desde `mis_tareas.php`.

→ Ref: [F8.2](06_funcionalidades.md#f82--asignar-tarea-profe--otro-profe)

---

### HU-36 🔴 ✅ — Administrar todas las tareas (coordinación)
**Como** COORDINADOR
**Quiero** ver, filtrar y actualizar estado de todas las tareas del sistema
**Para** dar seguimiento al workflow del equipo docente.

**CA**:
- Listado en `admin_tareas.php` con filtros por profesor asignado, asignador, materia, estado y búsqueda libre.
- Puedo cambiar estado y agregar comentario en cada tarea.
- (→ [PA-08](10_preguntas_abiertas.md#pa-08): ciclo de vida del estado no documentado).

→ Ref: [F8.3](06_funcionalidades.md#f83--administrar-tareas-coordinación)

---

## Épica 9 — Auditoría y Métricas

### HU-37 🔴 ✅ — Ver panel de interacciones por docente
**Como** COORDINADOR
**Quiero** ver acciones por día, estado de comunicaciones y métricas por docente × materia
**Para** identificar docentes inactivos o con problemas operativos.

**CA**:
- Filtros: from/to, materia, legajo, "inactive".
- Tablas: Estado de comunicaciones (Pend/Send/OK/Fail/Canc) + Interacciones por docente & materia (Preview/Import/Env./Reset/Umbral/Emails OK/Emails FAIL/Batches).
- Última actividad por docente visible.

→ Ref: [F9.1](06_funcionalidades.md#f91--panel-de-interacciones)

---

### HU-38 🔴 ✅ — Auditar acciones individuales
**Como** COORDINADOR / ADMIN
**Quiero** ver el log de las últimas 200 acciones con timestamp, legajo, materia, código de acción, filas afectadas, IP y User-Agent
**Para** investigar incidentes y dejar trazabilidad regulatoria.

**CA**:
- Tabla "Últimas acciones (máx. 200)" en `admin.php` ([RN-23](05_reglas_de_negocio.md#rn-23)).
- Códigos de acción tipo `MOD_MIS_EQUIPOS`.

→ Ref: [F9.2](06_funcionalidades.md#f92--log-de-auditoría-completo)

---

## Épica 10 — Liquidaciones y Honorarios

### HU-39 🔴 ✅ — Ver vista previa de liquidación del período
**Como** ADMIN FINANCIERO
**Quiero** ver la liquidación calculada por docente con Base + Plus + Total
**Para** validar antes de cerrar el período ([RN-21](05_reglas_de_negocio.md#rn-21)).

**CA**:
- Tabla con columnas Leg | Docente | Rol | Comisiones | Base | Plus | Total.
- Botón "Vista previa" antes del cierre.
- Puedo exportar a Excel sin cerrar.

→ Ref: [F10.1](06_funcionalidades.md#f101--vista-de-liquidaciones)

---

### HU-40 🔴 ✅ — Cerrar liquidación de un período
**Como** ADMIN FINANCIERO
**Quiero** cerrar la liquidación calculada
**Para** inmutabilizar los montos del período y proceder al pago ([RN-22](05_reglas_de_negocio.md#rn-22)).

**CA**:
- Acción "Cerrar liquidación" con confirmación explícita.
- Una vez cerrada, no se puede modificar.
- Aparece en "Historial" para auditoría posterior.

→ Ref: [F10.2](06_funcionalidades.md#f102--cerrar-liquidación)

---

### HU-41 🟡 ✅ — Mantener la grilla de salarios
**Como** ADMIN FINANCIERO
**Quiero** mantener la grilla maestra de salarios (por rol y posibles dimensiones adicionales)
**Para** que el cálculo automático de Base sea consistente ([S5](09_decisiones_y_supuestos.md#s5)).

**CA**:
- Acceso restringido a `salarios.php` (devuelve "No autorizado" para roles no autorizados).
- (→ [PA-06](10_preguntas_abiertas.md#pa-06): fórmula exacta no documentada).

→ Ref: [F10.4](06_funcionalidades.md#f104--abm-de-salarios-grilla)

---

## Épica 11 — Perfil y Sesión

### HU-42 🟡 ✅ — Editar mis datos personales y bancarios
**Como** DOCENTE
**Quiero** actualizar mis datos personales y bancarios desde mi perfil
**Para** que las liquidaciones lleguen a la cuenta correcta y mis datos estén al día.

**CA**:
- Campos editables: nombre, dni, sexo, banco, cbu, alias_cbu, regional, email, factura (checkbox), legajo_profesional.
- `cuil_view` es solo lectura ([S6](09_decisiones_y_supuestos.md#s6)).
- POST con CSRF.

→ Ref: [F11.1](06_funcionalidades.md#f111--editar-perfil)

---

### HU-43 🟢 ✅ — Cerrar sesión
**Como** USUARIO
**Quiero** cerrar sesión desde el menú
**Para** proteger mi acceso cuando termino de trabajar.

**CA**:
- Link "Salir" en menú llama a `logout.php`.
- La sesión PHP se destruye server-side.
- Redirect a pantalla de login (→ [PA-04](10_preguntas_abiertas.md#pa-04)).

> ⚠️ **Corrección para activia-trace**: no hay "sesión PHP". Cerrar sesión **revoca el refresh token** (rotación) y descarta el access JWT en el cliente. Ver [RF-46](../docs/PRD.md#perfil) y [`ARQUITECTURA.md` §5.1](../docs/ARQUITECTURA.md).

→ Ref: [F11.3](06_funcionalidades.md#f113--logout)

---

## Épica 12 — Integraciones Externas

### HU-44 🟢 ✅ — Acceder a Correct-IA
**Como** PROFESOR
**Quiero** acceder al corrector automático Correct-IA desde el menú
**Para** apoyarme en correcciones automatizadas.

**CA**:
- Link en menú Procesos → `https://olsoft.online/evalia/corrector/index.php`.
- Es un módulo externo — su comportamiento no está documentado en esta KB.

→ Ref: [F12.1](06_funcionalidades.md#f121--acceso-a-correct-ia)

---

---

## Épica 13 — Facturación de monotributistas (descubierta en segunda pasada)

### HU-48 🔴 ✅ — Gestionar facturas de docentes monotributistas
**Como** ADMIN FINANCIERO / super-admin
**Quiero** ver, filtrar y marcar como abonadas las facturas que presentan los docentes monotributistas
**Para** llevar control del pago paralelo a la liquidación general.

**CA**:
- Listado con filtros: profesor, estado (pendiente/abonada), rango de fechas, búsqueda libre.
- Cada factura tiene: Fecha carga, Docente, Mes (YYYY-MM), Detalle (texto libre), Archivo PDF descargable, Tamaño, Estado, Pago, Acción.
- Estados: `pendiente` ([RN-39](05_reglas_de_negocio.md#rn-39)) → `abonada`.
- POST con CSRF para cambiar estado.

→ Ref: [F10.5](06_funcionalidades.md#f105--gestión-de-facturas-descubierto-en-segunda-pasada)

---

### HU-49 ❓ — Docente sube su factura mensual
**Como** PROFESOR monotributista
**Quiero** subir mi factura mensual en PDF
**Para** que la administración la procese.

**CA pendientes** (no observado el form de upload):
- ¿Desde qué pantalla sube?
- ¿Hay validación de monto vs. liquidación calculada equivalente?
- ¿Notificación al admin cuando hay una nueva factura cargada?

---

## Historias inferidas / pendientes de descubrimiento

### HU-45 ❓ — Login del usuario
**Como** USUARIO con credenciales válidas
**Quiero** loguearme en la plataforma
**Para** acceder a mis pantallas según mi rol.

**CA pendientes** (observado en olsoft → [PA-04](10_preguntas_abiertas.md#pa-04)):
- ¿Identificador es legajo o email?
- ¿Hay 2FA, "recordarme", recuperación de password?
- ¿Hay self-service signup o solo alta admin?

> ✅ **CA destino para activia-trace** (esto NO es pendiente — ya está decidido):
> - Login por **email + password (Argon2id)** — nunca por legajo.
> - **2FA opcional (TOTP)** + recuperación por email con token de un solo uso. Sin self-service signup en MVP (alta administrativa).
> - Sesión = **JWT** (access 15 min + refresh rotation), no cookie de sesión PHP.
> - Identidad/tenant **solo desde el JWT** — ningún `?leg=X` cambia de usuario ([P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
> - Ref: [RF-01](../docs/PRD.md#auth-roles-y-tenants), [RNF-09](../docs/PRD.md#seguridad), [`ARQUITECTURA.md` §5](../docs/ARQUITECTURA.md).

---

### HU-46 ❓ — Crear una guardia
**Como** TUTOR / PROFESOR
**Quiero** registrar una nueva guardia
**Para** que quede en mi historial.

**CA pendientes** (→ [PA-05](10_preguntas_abiertas.md#pa-05)):
- ¿Desde qué pantalla se crea?
- ¿Es un sub-flujo de encuentros o tareas?

---

### HU-47 ❓ — Alumno reserva un coloquio
**Como** ALUMNO
**Quiero** reservar un lugar en una instancia de coloquio
**Para** rendir según mi disponibilidad.

**CA pendientes** (→ [PA-14](10_preguntas_abiertas.md#pa-14)):
- ¿La reserva ocurre dentro de este sistema o en Moodle?
- ¿Hay UI dedicada para alumno?

---

## Resumen por épica

| Épica | HUs | ✅ Implementadas | 🔧 Parciales | ❓ Inferidas |
|-------|-----|------------------|--------------|--------------|
| 1 — Ingesta Moodle | HU-01..04 | 4 | 0 | 0 |
| 2 — Análisis | HU-05..09 | 5 | 0 | 0 |
| 3 — Comunicación | HU-10..15 | 5 | 0 | 1 |
| 4 — Equipos | HU-16..20 | 5 | 0 | 0 |
| 5 — Estructura | HU-21..24 | 4 | 0 | 0 |
| 6 — Encuentros | HU-25..29 | 5 | 0 | 0 |
| 7 — Coloquios | HU-30..33 | 4 | 0 | 0 |
| 8 — Tareas | HU-34..36 | 3 | 0 | 0 |
| 9 — Auditoría | HU-37..38 | 2 | 0 | 0 |
| 10 — Liquidaciones | HU-39..41 | 3 | 0 | 0 |
| 11 — Perfil | HU-42..43 | 2 | 0 | 0 |
| 12 — Externos | HU-44 | 1 | 0 | 0 |
| 13 — Facturación monotributistas | HU-48..49 | 1 | 0 | 1 |
| Pendientes descubrimiento | HU-45..47 | — | — | 3 |
| **TOTAL** | **49 HU** | **44** | **0** | **5** |

## Convenciones para futuro

Si surgen nuevas HUs:
- Continuar numeración `HU-48`, `HU-49`, …
- Vincular siempre a una épica de [06_funcionalidades.md](06_funcionalidades.md) y a las RN aplicables.
- Marcar estado: ✅ / 🔧 / ❓.
- Si una HU descubre una nueva regla de negocio, agregarla a [05_reglas_de_negocio.md](05_reglas_de_negocio.md) y referenciarla.
