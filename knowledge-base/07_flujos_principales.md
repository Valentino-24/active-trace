# 07 — Flujos Principales

Flujos extremo a extremo observados o inferidos de la herramienta.

---

## FL-01 — Autenticación

```
[Usuario] → login.php (no observada)
         → credenciales (legajo + password — supuesto)
         → sesión PHP en cookie
         → redirect a index.php
         → menú renderizado según rol
         ...
         → logout.php → destruye sesión → redirect a login
```

**Suposición:** el campo de autenticación es `legajo` (es la natural key del docente).

> ⚠️ **Corrección para activia-trace** — este flujo es el del sistema VIEJO. NO replicar:
> - Login por **email + password (hash Argon2id) + 2FA opcional (TOTP)**, NUNCA por legajo. El legajo es atributo de negocio, no credencial. ([RF-01](../docs/PRD.md#auth-roles-y-tenants))
> - Sesión = **JWT firmado** (access 15 min + refresh con rotación), no cookie de sesión PHP. ([RNF-09](../docs/PRD.md#seguridad))
> - La identidad y el tenant salen **exclusivamente del JWT verificado**. Ningún `?leg=X`, id en query/body/header puede cambiar quién sos → así se mata [P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).
> - Recuperación de contraseña por email con token de un solo uso. ([RF-02](../docs/PRD.md#auth-roles-y-tenants))
>
> Detalle en [`docs/ARQUITECTURA.md` §5](../docs/ARQUITECTURA.md).

---

## FL-02 — Importar calificaciones y detectar atrasados (flujo central del PROFESOR)

```
[Profesor: Cortez Alberto]
  1. Login → index.php
  2. Selecciona materia (ej: Programación I — PROG_I, id=3)
       → URL: index.php?materia_id=3
       → se despliegan secciones 1.a, 1.b, 2.a, 2.b, 3, 4

  3. Sección 1.a — Sube .xlsx exportado de Moodle
       → click "Generar preview"
       → sistema parsea con PHPExcel
       → detecta columnas (Real) [RN-01]
       → detecta valores textuales [RN-02]
       → muestra lista de actividades para seleccionar

  4. Profesor selecciona actividades a analizar
       → confirma

  5. Profesor configura umbral (Sección 1.a "Umbral global")
       → default 60% [RN-03]
       → "Guardar umbral (%)"

  6. Sistema computa:
       - Sección 3: Estudiantes atrasados (faltantes o < umbral) [RN-06]
       - Sección 4: Ranking de aprobadas [RN-09]
       - Sección 2.a: Reportes rápidos
       - Sección 2.b: Notas finales agrupadas

  7. Sección 1.b — Sube reporte de finalización Moodle
       → click "Analizar correcciones"
       → sistema cruza con calificaciones
       → genera tabla "Posibles TPs sin corregir" [RN-07, RN-08]

  8. Exportar Excel de TPs sin corregir (acción opcional)

  9. Click sobre un alumno atrasado
       → modal "Alumnos"
       → modal "Previsualización del email" con Asunto + Cuerpo HTML
       → confirma envío
       → email pasa a estado "Pend" en cola

  10. (Worker en background)
        Pend → Send → OK / Fail / Canc [RN-15]
```

**Loggeable**: cada uno de los pasos 3, 5, 7, 9 genera un registro en AuditLog ([RN-23](05_reglas_de_negocio.md#rn-23)).

---

## FL-03 — Setup de inicio de cuatrimestre (COORDINADOR)

```
1. Coordinador → admin_cohortes.php
     → crea nueva cohorte (ej: AGO-2026, 2026, vig_desde, vig_hasta)

2. → admin_reportes.php (Equipos)
     → opción "Clonar equipo docente"
     → selecciona equipo origen (materia X / carrera TUPAD / cohorte MAR-2026)
     → selecciona destino (misma materia X / TUPAD / nueva cohorte AGO-2026)
     → confirma
     → todas las asignaciones se duplican con las fechas del nuevo período [RN-12]

3. → admin_asignaciones.php
     → ajusta asignaciones faltantes (profes nuevos, materias huérfanas)
     → puede usar "Asignación masiva" para alta bulk [F4.4]

4. → admin_reportes.php
     → "Modificar vigencia general del equipo" si las fechas necesitan ajuste

5. → programas_materias.php
     → sube los PDF actualizados para cada materia × cohorte

6. → fechas_parciales.php
     → carga las fechas de parciales/TP/coloquios del nuevo cuatrimestre

7. → admin_avisos.php
     → publica aviso de bienvenida con scope=cohorte AGO-2026, role_target=ALL

8. → admin_monitor.php
     → importa el padrón inicial (Listado + Actividades) cuando empieza el cursado
```

---

## FL-04 — Envío masivo de recordatorios con aprobación

```
[Profesor] → index.php?materia_id=X
  1. Importa calificaciones [FL-02 pasos 3-6]
  2. Identifica N alumnos atrasados
  3. Genera mails masivos (acción no observada en detalle — botón implícito)
  4. Cada mail va a estado "Pend"

[Admin de mails] → admin_mail_approval.php
  5. Ve cola pendiente
  6. Aprueba lote o cancela
  7. Aprobados pasan a "Send" → worker despacha → "OK" o "Fail"
  8. Cancelados quedan en "Canc"

[Profesor] → admin.php
  9. Tabla "Estado de comunicaciones" muestra OK/Fail por materia
```

**Suposición:** la aprobación es por **lote** o **por destinatario** — no observado en detalle.

---

## FL-05 — Workflow de Tareas (coordinación ↔ profesor)

```
[Coordinador] → admin_tareas.php
  1. Crea tarea: define materia, profesor asignado, descripción
  2. Tarea aparece en estado "abierta" (inferido)

[Profesor] → mis_tareas.php
  3. Ve tarea asignada
  4. Cambia estado (en progreso, completada, etc.)
  5. Agrega comentario

[Coordinador] → admin_tareas.php
  6. Filtra por estado, lee último comentario
  7. Aprueba cierre o devuelve para ajustes
```

**Volumen actual**: 443 tareas en admin → herramienta de alto uso.

---

## FL-06 — Encuentros recurrentes con grabaciones

```
[Profesor] → encuentros.php
  1. "Crear encuentro" → modo recurrente
  2. Define: materia, día semana = Miércoles, hora = 14:00, desde = 2026-03-04, 16 semanas
  3. Sistema genera 16 instancias automáticamente [RN-13]

(día del encuentro)
  4. Profesor accede a la instancia
  5. Edita: cambia estado a "realizado", pega URL del video grabado

[Coordinador] → encuentros.php → "Vista admin"
  6. Auditoría: ve qué encuentros se realizaron, cuáles no

[Profesor] → "HTML para Moodle"
  7. Copia snippet HTML con los slots
  8. Pega en aula virtual de Moodle (acción manual fuera del sistema)
```

---

## FL-07 — Coloquio: convocatoria a evaluación

```
[Profesor] → coloquios/index.php
  1. "Importar alumnos" → importar.php
  2. Carga padrón de candidatos a coloquio

  3. "Nueva evaluación" → convocatoria_form.php
  4. Define: materia, instancia (ej: "Coloquio Final"), días disponibles, cupos por día
  5. Sistema crea la evaluación con slots de reserva

(luego: alumnos reservan — flujo no observado, presumiblemente externo)

  6. Tabla muestra: convocados, reservas, cupos libres

[Coordinador] → admin_coloquios.php
  7. Ve agenda consolidada de reservas activas
  8. Ve registro académico consolidado (notas finales)
```

---

## FL-08 — Liquidación de honorarios

```
[Admin financiero] → liquidaciones.php
  1. Selecciona período
  2. Sistema calcula por docente:
     - Base (según rol/grilla salarios)
     - Plus (por comisiones extra)
     - Total = Base + Plus [RN-21]
  3. "Vista previa" → verifica tabla
  4. "Exportar Excel" → genera planilla para presentar/pagar
  5. "Cerrar liquidación" → inmutabiliza el período [RN-22]
  6. "Historial" → audita liquidaciones anteriores
```

---

## FL-09 — Publicación de aviso del sistema

```
[Coordinador] → admin_avisos.php
  1. Click en formulario "Nuevo aviso"
  2. Define:
     - scope (global/materia/cohorte)
     - materia_slug, cohorte_id (si aplica)
     - role_target
     - severity
     - título + cuerpo (HTML)
     - start_at, end_at (ventana)
     - sort (prioridad)
     - active (toggle)
     - require_ack (si exige confirmación)
  3. Publica

[Usuarios target] (al loguearse o navegar)
  4. Ven aviso según matching de rol/scope/cohorte [RN-20]
  5. Si require_ack=true → deben confirmar (contador ACK aumenta)
  6. Si vencen → fuera de ventana start_at..end_at → no se muestran [RN-18]
```

---

## FL-10 — Mensajería interna del docente

```
[Sistema] → genera mensaje (avisos personalizados, respuesta de alumno, notificación de coordinación)
  → inbox del docente

[Docente] → perfil.php
  1. Ve threads en su inbox
  2. Abre un mensaje
  3. Responde con reply_subject + reply_body
  4. "Enviar respuesta"
```

**Suposición:** este inbox es paralelo al sistema de emails a alumnos — es para comunicación interna entre roles del sistema.

---

## FL-11 — Auditoría de actividad por docente (panel admin)

```
[Coordinador/Admin] → admin.php
  1. Filtra por rango from/to + materia + legajo + inactive
  2. Ve:
     - "Acciones por día" (gráfico/serie)
     - "Estado de comunicaciones" (Pend/Send/OK/Fail/Canc por docente × materia)
     - "Interacciones por docente & materia" (métricas detalladas)
     - "Últimas acciones" (log con IP/UA, máx. 200)
  3. Identifica docentes inactivos → toma acción (mensaje, reasignación, etc.)
```

---

## Flujos no observados pero probables

- **Login**: no recorrido (usuario ya estaba logueado).
- **Recuperar contraseña**: no observado — supuesto.
- **Alta de guardia**: solo se vio el listado, no el form de creación.
- **Cómo el alumno reserva un coloquio**: posiblemente desde Moodle o un módulo externo.
- **Aprobación de mail masivo en detalle**: `admin_mail_approval.php` no accesible con el rol observado.
- **Definición de la grilla de salarios**: `salarios.php` no accesible.
- **Configuración inicial del sistema** (creación del primer admin, seed inicial): no observado.
