# PRD — activia-trace

**Producto**: activia-trace
**Versión del documento**: 0.1 (draft inicial)
**Fecha**: 2026-05-28
**Estado**: Draft — requiere validación con stakeholders
**Referencia funcional**: [Base de conocimiento de PulseUPs](../knowledge-base/README.md)

---

## TL;DR

**activia-trace** es la **evolución/reemplazo de PulseUPs** — una plataforma de gestión académica y trazabilidad de actividades estudiantiles que orquesta encima de Moodle. Tomamos lo que demostrado funcionar en producción (importación de calificaciones, detección de atrasados, mails con preview y aprobación, audit log) y resolvemos las deudas técnicas y de UX detectadas en el análisis de PulseUPs.

**El nombre lo dice todo**: *activia-trace* = trazabilidad de actividades. La promesa central es que **toda actividad académica relevante quede registrada, atribuida y auditable**, sin fricción para el docente.

---

## 1. Contexto y problema

### 1.1 Contexto

La institución (TUPAD inicial, escalable a otras carreras) usa **Moodle** como LMS pero Moodle por sí solo no resuelve:

- Consolidar calificaciones de múltiples actividades por alumno en una vista accionable.
- Detectar y comunicar atrasos masivamente con personalización.
- Coordinar equipos docentes (asignaciones, jerarquías, vigencias) a través de comisiones.
- Operar liquidaciones de honorarios contra la actividad efectiva del docente.
- Mantener trazabilidad institucional de cada acción.

**Hoy** existe PulseUPs cubriendo estos huecos, pero acumuló deuda técnica y de producto que el análisis funcional dejó a la vista (ver [09_decisiones_y_supuestos.md](../knowledge-base/09_decisiones_y_supuestos.md) y [10_preguntas_abiertas.md](../knowledge-base/10_preguntas_abiertas.md)).

### 1.2 Problemas observados en PulseUPs que activia-trace debe resolver

| # | Problema | Origen | Impacto |
|---|----------|--------|---------|
| P1 | **Dos catálogos de materias paralelos** sin relación (19 vs 12 con IDs distintos) | [PA-01](../knowledge-base/10_preguntas_abiertas.md#pa-01) | Datos divergentes, doble carga manual, confusión |
| P2 | **Padrón upsert destructivo** sin historial de bajas/altas | [RN-05](../knowledge-base/05_reglas_de_negocio.md#rn-05), [D4](../knowledge-base/09_decisiones_y_supuestos.md#d4) | Imposible auditar quién entró/salió de una cohorte |
| P3 | **Integración con Moodle solo por subida manual de Excel** | [D1](../knowledge-base/09_decisiones_y_supuestos.md#d1) | Datos siempre desactualizados, alto costo operativo |
| P4 | **No hay UI para alumno** | [ND1](../knowledge-base/09_decisiones_y_supuestos.md#nd1) | El alumno no puede ver su propio estado ni autogestionarse |
| P5 | **No hay API pública** | [ND5](../knowledge-base/09_decisiones_y_supuestos.md#nd5) | Imposible integrar con otras plataformas (RRHH, BI, etc.) |
| P6 | **Stack PHP MPA monolítico** | Observación de stack | Difícil escalar, testear, evolucionar; bajo bus factor |
| P7 | **No hay dashboards analíticos** (solo operativos) | [ND6](../knowledge-base/09_decisiones_y_supuestos.md#nd6) | No se pueden detectar tendencias ni hacer predicción |
| P8 | **Mezcla `action`/`accion` y typos en seed** | [IM-01](../knowledge-base/10_preguntas_abiertas.md#im-01), [IM-02](../knowledge-base/10_preguntas_abiertas.md#im-02) | Refleja falta de code review y QA de contenido |
| P9 | **Auditoría capada a 200 acciones recientes en UI** | [F9.2](../knowledge-base/06_funcionalidades.md#f92--log-de-auditoría-completo) | Investigación de incidentes lejana imposible |
| P10 | **Modelo de roles ambiguo** (no se sabe qué hace TUTOR) | [PA-02](../knowledge-base/10_preguntas_abiertas.md#pa-02) | Permisos opacos, decisiones de authz inconsistentes |
| **P11** | **🔴 CRÍTICO — Broken Access Control vía `?leg=X` (OWASP A01)** | [RN-41](../knowledge-base/05_reglas_de_negocio.md#rn-41), [PA-21](../knowledge-base/10_preguntas_abiertas.md#pa-21), [OQ-14](#12-open-questions-a-resolver-antes-de-cerrar-el-prd) | Cambiar un parámetro de URL escala privilegios a otra identidad (incl. super-admin) sin re-autenticación. Toda acción del impersonator queda atribuida al impersonated → trazabilidad rota. **El #1 del OWASP Top 10.** |

> ### 🔴 Nota de severidad — P11 es bloqueante de seguridad
>
> El mecanismo `?leg=X` permite **cambiar de identidad alterando un parámetro de URL** (evidencia: la navegación a `/?leg=1` cambió el contexto del usuario logueado de *Cortez Alberto* a *Rodriguez Georgina*, legajo 1 — super-admin). Esto es **Broken Access Control (OWASP A01:2021)** — la categoría #1 del Top 10.
>
> **Lo que está CONFIRMADO**: un usuario con sesión activa escala a otra identidad (incluida la de máximos privilegios) sin re-autenticación ni segunda verificación.
>
> **Lo que requiere VERIFICACIÓN (no afirmar sin probar)**: si el `?leg=X` funciona también **sin sesión previa** (totalmente pre-auth). De confirmarse, la severidad pasa de *privilege escalation* a *full authentication bypass*. Ligado a [PA-04](../knowledge-base/10_preguntas_abiertas.md#pa-04) (flujo de login) y [OQ-14](#12-open-questions-a-resolver-antes-de-cerrar-el-prd).
>
> **Cómo lo mata activia-trace**: la identidad **JAMÁS** se deriva de un parámetro de request ([RF-04](#auth-roles-y-tenants) RBAC real, no flag binario `is_admin`); la sesión sale exclusivamente de un JWT firmado y de corta vida ([RNF-09](#seguridad)); la impersonation legítima (soporte) es una feature **explícita, permisada y 100% auditada** ([RF-05](#auth-roles-y-tenants), [RNF-12](#seguridad)) — nunca un efecto colateral de editar la URL. Ver detalle en [`docs/ARQUITECTURA.md`](./ARQUITECTURA.md) §Seguridad.

### 1.3 Lo que PulseUPs SÍ hace bien — y queremos conservar

| # | Comportamiento | Por qué conservarlo |
|---|----------------|---------------------|
| K1 | **Preview obligatorio del mail antes de envío** ([RN-16](../knowledge-base/05_reglas_de_negocio.md#rn-16)) | Previene errores comunicacionales caros |
| K2 | **Aprobación humana de mails masivos** ([RN-17](../knowledge-base/05_reglas_de_negocio.md#rn-17)) | Gobernanza comunicacional, evita spam reputacional |
| K3 | **Audit log con IP + User-Agent** ([RN-23](../knowledge-base/05_reglas_de_negocio.md#rn-23)) | Trazabilidad regulatoria robusta |
| K4 | **Scope por (docente, materia) en datos importados** ([RN-04](../knowledge-base/05_reglas_de_negocio.md#rn-04)) | Cada docente trabaja sin pisarle datos a otro |
| K5 | **Clonado de equipos entre cohortes** ([RN-12](../knowledge-base/05_reglas_de_negocio.md#rn-12)) | Reduce setup de inicio de cuatrimestre de horas a minutos |
| K6 | **Avisos con scope, severity, vigencia y require_ack** ([RN-18..20](../knowledge-base/05_reglas_de_negocio.md#rn-18--avisos-tienen-ventana-de-vigencia)) | Comunicación institucional con trazabilidad |
| K7 | **Vigencia temporal por asignación** ([RN-10](../knowledge-base/05_reglas_de_negocio.md#rn-10)) | Permite rotación natural entre periodos |
| K8 | **Estados de email del worker** ([RN-15](../knowledge-base/05_reglas_de_negocio.md#rn-15)) | Visibilidad operativa de la cola |
| K9 | **Umbral configurable por docente × materia** ([RN-03](../knowledge-base/05_reglas_de_negocio.md#rn-03)) | Respeta criterio pedagógico individual |
| K10 | **Detección de TPs entregados sin corregir** ([RN-07](../knowledge-base/05_reglas_de_negocio.md#rn-07)) | Killer-feature según el contexto observado |

---

## 2. Visión y North Star

### 2.1 Visión

> **"Que ningún alumno se pierda y ningún docente se quede atrás por falta de información."**

activia-trace es la **capa de inteligencia operativa** entre Moodle y el día a día del equipo docente. Convierte la actividad cruda del LMS en **decisiones accionables** y deja **trazabilidad completa** de cada una.

### 2.2 North Star Metric

**% de alumnos atrasados que recibieron un recordatorio dentro de 48hs de detectado el atraso.**

Justificación: combina detección efectiva (que el sistema detecte rápido) + ejecución (que el docente reciba la alerta y actúe) + impacto (que el alumno reciba la comunicación). Mide el ciclo completo end-to-end del valor del producto.

### 2.3 Secondary metrics

- **MTTR** de detección de TP sin corregir (desde entrega del alumno hasta que el docente lo ve listado).
- **Email delivery rate** (% en estado OK del total enviado).
- **% de cohorte cubierta** por avisos `require_ack` confirmados.
- **Tiempo promedio de setup de cuatrimestre nuevo** (alta de cohorte + clonado de equipos + carga inicial).
- **% de docentes activos** en la última semana (login + ≥1 import o ≥1 acción registrada).

---

## 3. Audiencia / Personas

> Las personas se derivan directamente de los [actores del sistema](../knowledge-base/03_actores_y_roles.md). Ampliamos con JTBD (Jobs To Be Done).

### Persona 1 — Profesor de comisión

- **Rol**: PROFESOR
- **Contexto**: maneja entre 1 y 4 comisiones simultáneas en TUPAD. Dicta clase asincrónica + encuentros sincrónicos semanales. Cobra honorarios mensuales por la institución.
- **Jobs**:
  - "Cuando termino una semana de cursado, quiero saber **quién quedó descolgado** sin perder media hora cruzando Moodle a mano."
  - "Cuando subo notas, quiero **detectar lo que entregaron pero no califiqué** para no quedar mal."
  - "Cuando mando recordatorios, quiero **estar seguro de que el mail se ve bien** antes de apretar enviar."
- **Pains hoy en PulseUPs**:
  - Tener que exportar de Moodle, descargar, subir, parsear. Doble manipulación de archivos.
  - No tener visión consolidada al instante.
  - Que su trabajo "se pierda" si no carga el padrón al día.

### Persona 2 — Coordinador académico

- **Rol**: COORDINADOR
- **Contexto**: responsable de un conjunto de materias o de una cohorte completa. Asigna profesores, sigue rendimiento, decide medidas pedagógicas.
- **Jobs**:
  - "Cuando arranca un cuatrimestre, quiero **clonar el equipo del anterior** y solo ajustar deltas."
  - "Cuando hay un alumno en riesgo, quiero **ver el panorama completo** (todas las materias, todos los docentes que lo tocan)."
  - "Cuando un docente está inactivo, quiero **detectarlo antes de que sea problema**."
- **Pains hoy**:
  - El monitor general es plano (sin segmentación inteligente, sin alertas proactivas).
  - No tiene vista cruzada del alumno (debería ver al alumno X en todas sus materias).
  - El log de acciones está truncado a 200.

### Persona 3 — Administrador del sistema (super-admin)

- **Rol**: COORDINADOR + `is_admin=true`
- **Jobs**:
  - "Quiero **dar de alta una nueva cohorte** sin tener que repetir 100 asignaciones."
  - "Quiero **auditar quién hizo qué** ante cualquier reclamo académico."
  - "Quiero **aprobar/rechazar envíos masivos** antes de que salgan."
- **Pains hoy**:
  - ABM repetitivo de carreras/cohortes/programas.
  - Permisos finos confusos (`is_admin` vs roles específicos no claros).

### Persona 4 — Admin financiero / Liquidaciones

- **Rol**: rol específico de finanzas (acceso a `salarios.php` y `liquidaciones.php`)
- **Jobs**:
  - "A fin de mes, quiero **generar la liquidación de todo el equipo** y exportar el listado para el pago bancario."
  - "Quiero **inmutabilizar** la liquidación una vez aprobada para que nadie la modifique."
- **Pains hoy**:
  - La fórmula de cálculo no es transparente (ver [PA-06](../knowledge-base/10_preguntas_abiertas.md#pa-06)).
  - No hay flujo claro de revisión + cierre.

### Persona 5 — Alumno (NUEVO en activia-trace)

> **PulseUPs no tiene UI de alumno** ([ND1](../knowledge-base/09_decisiones_y_supuestos.md#nd1)). activia-trace **sí** la incorpora en Fase 2.

- **Rol**: ALUMNO
- **Contexto**: cursa entre 4 y 6 materias en paralelo en TUPAD, vive en distintas regionales del país.
- **Jobs**:
  - "Quiero **ver mi estado consolidado** en todas las materias sin entrar a Moodle materia por materia."
  - "Quiero **reservar lugar en un coloquio** sin esperar mail del docente."
  - "Quiero **recibir avisos importantes** en un solo lugar."
- **Pains hoy**: depende 100% del docente para enterarse de su propio estado.

### Persona 6 — Tutor / Ayudante

- **Rol**: TUTOR (rol inferido — a confirmar)
- **Jobs**:
  - "Quiero registrar las **guardias** que cubro."
  - "Quiero ver los **alumnos asignados a mí** en cada materia."
- **Pains hoy**: el rol existe pero está mal documentado, los permisos son opacos.

---

## 4. Goals & Non-Goals

### 4.1 Goals (lo que SÍ vamos a hacer)

#### G1 — Paridad funcional con PulseUPs en el MVP
Todo lo que un docente hace hoy en PulseUPs (importar, ver atrasados, enviar mails con preview, gestionar encuentros) **debe estar cubierto en el MVP**.

#### G2 — Integración bidireccional con Moodle (no upload manual)
Eliminar la fricción del "exportá Excel, subilo, parseá". Conectar vía **Moodle Web Services / OAuth2** para tomar calificaciones, padrones y reportes **en background**.

#### G3 — Modelo de datos único y consistente
**Un solo catálogo de materias** ([P1](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)), con historial de padrón ([P2](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)) y modelo de roles claro ([P10](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).

#### G4 — Multi-tenant desde el día 1
TUPAD es el primer cliente, pero el modelo debe permitir **N instituciones** sin re-arquitectura.

#### G5 — API REST pública con OpenAPI
Todo lo que se hace por UI se puede hacer por API. Habilita integraciones, automation, y prepara para apps móviles futuras.

#### G6 — Trazabilidad sin tope
Audit log **sin límite de 200** en UI, búsqueda full-text y rangos largos.

#### G7 — UI de alumno (Fase 2)
El alumno deja de ser solo "objeto" del sistema y pasa a tener acceso de lectura a su propio estado.

#### G8 — Observabilidad y métricas product-level
North Star + secondary metrics implementadas como dashboards internos desde el día 1.

### 4.2 Non-Goals (lo que NO vamos a hacer)

#### NG1 — Reemplazar a Moodle
Moodle sigue siendo el LMS oficial. activia-trace es la capa de inteligencia operativa. No alojamos contenidos pedagógicos ni recibimos entregas.

#### NG2 — Correctores automáticos con IA generativa
Correct-IA es un módulo externo que sigue siendo externo. No replicamos su funcionalidad en MVP ni Fase 2.

#### NG3 — App móvil nativa en MVP
Web responsive sí; app nativa queda para Fase 3+. Si surge la necesidad antes, evaluar PWA primero.

#### NG4 — Pagos / facturación electrónica
Las liquidaciones generan listados/exports para que finanzas opere — no integramos AFIP ni pasarelas de pago.

#### NG5 — Marketplace de cursos / catálogo público
activia-trace es B2B-institucional, no consumer.

---

## 5. Métricas de éxito

### 5.1 Métricas de producto (las que importan)

| Métrica | Tipo | Target (Año 1) |
|---------|------|----------------|
| **North Star**: % alumnos atrasados con recordatorio en ≤48h | Outcome | ≥ 85% |
| **% docentes activos / semana** | Adoption | ≥ 80% |
| **Tiempo promedio de setup cuatrimestre** | Efficiency | ≤ 30 min (vs estimado actual ≥ 4h) |
| **% emails OK / total enviados** | Quality | ≥ 95% |
| **Latencia detección TP sin corregir (alumno entrega → docente lo ve)** | Velocity | ≤ 4h |
| **% cohorte que ACK avisos `require_ack`** | Compliance | ≥ 90% en 7 días |
| **NPS docente** | Satisfaction | ≥ 40 |

### 5.2 Métricas técnicas (SLO)

| Métrica | Target |
|---------|--------|
| Uptime | 99.5% mensual |
| P95 de respuesta API | < 500 ms |
| Tiempo de import Moodle (materia 100 alumnos) | < 30 s |
| RPO (Recovery Point Objective) | ≤ 1 hora |
| RTO (Recovery Time Objective) | ≤ 4 horas |

---

## 6. Requirements

Requirements numerados como **RF-XX** (funcional) y **RNF-XX** (no funcional). Cada uno está vinculado a las [HUs de la KB](../knowledge-base/11_historias_de_usuario.md) cuando aplica.

### 6.1 Requirements funcionales — MVP (Fase 1)

#### Auth, Roles y Tenants

> 🔐 Este bloque (RF-01 a RF-05) + RNF-07..12 son la respuesta directa a [P11](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver) (Broken Access Control vía `?leg=X`). Diseño completo en [`ARQUITECTURA.md` §5 Seguridad](./ARQUITECTURA.md). **Regla de oro**: la identidad y el tenant se derivan EXCLUSIVAMENTE del JWT verificado — nunca de un parámetro de request.

- **RF-01** — Login con email + password + 2FA opcional (TOTP). Resuelve [PA-04](../knowledge-base/10_preguntas_abiertas.md#pa-04). [HU-45](../knowledge-base/11_historias_de_usuario.md#hu-45--ofcial---login-del-usuario)
- **RF-02** — Recuperación de contraseña por email.
- **RF-03** — Multi-tenancy: cada institución es un tenant aislado. Datos jamás cruzan.
- **RF-04** — Modelo de roles claro: ALUMNO, TUTOR, PROFESOR, COORDINADOR, ADMIN, FINANZAS. Permisos finos por feature (no flag binario `is_admin`).
- **RF-05** — Audit log de TODO login, logout, cambio de contraseña, cambio de rol.

#### Ingesta y Datos

- **RF-06** — Integración con Moodle vía **Web Services** (función `core_grades_get_grades`, `core_user_get_users_by_field`, etc.). Sync nocturna automática + sync on-demand.
- **RF-07** — Fallback: import manual de `.xlsx`/`.csv` para casos sin acceso WS. [HU-01](../knowledge-base/11_historias_de_usuario.md#hu-01---importar-calificaciones-por-materia)
- **RF-08** — Detección de columnas `(Real)` para notas numéricas ([RN-01](../knowledge-base/05_reglas_de_negocio.md#rn-01)).
- **RF-09** — Mapeo de escala textual ("Satisfactorio", "Supera lo esperado") con catálogo configurable por tenant ([RN-02](../knowledge-base/05_reglas_de_negocio.md#rn-02)).
- **RF-10** — **Padrón con historial**: ningún import borra el anterior — se versiona. Resuelve [P2](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver). [HU-03](../knowledge-base/11_historias_de_usuario.md#hu-03---importar-padrón-de-alumnos-evalia)
- **RF-11** — **Catálogo único de materias** por tenant — un solo dataset con scoping por carrera/cohorte. Resuelve [P1](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).

#### Análisis y Reportes

- **RF-12** — Umbral configurable por docente × materia (default 60%). [HU-05](../knowledge-base/11_historias_de_usuario.md#hu-05---configurar-umbral-de-aprobación-por-materia)
- **RF-13** — Lista de atrasados (faltantes O nota < umbral). [HU-06](../knowledge-base/11_historias_de_usuario.md#hu-06---ver-lista-de-alumnos-atrasados)
- **RF-14** — Ranking de aprobadas (excluyendo alumnos sin actividad). [HU-07](../knowledge-base/11_historias_de_usuario.md#hu-07---ver-ranking-de-alumnos-por-aprobadas)
- **RF-15** — Notas finales agrupadas exportables a Excel. [HU-08](../knowledge-base/11_historias_de_usuario.md#hu-08---generar-notas-finales-agrupadas-para-excel)
- **RF-16** — Detección de TP entregados sin corregir, filtrable y exportable. [HU-02](../knowledge-base/11_historias_de_usuario.md#hu-02---detectar-entregas-finalizadas-sin-corregir)

#### Comunicación

- **RF-17** — Preview obligatorio del mail antes del envío (Asunto + HTML render). [HU-10](../knowledge-base/11_historias_de_usuario.md#hu-10---previsualizar-mail-antes-de-enviarlo)
- **RF-18** — Cola de mails con estados Pend/Send/OK/Fail/Canc. [HU-11](../knowledge-base/11_historias_de_usuario.md#hu-11---enviar-recordatorios-masivos-a-alumnos-atrasados)
- **RF-19** — Aprobación humana opcional (configurable por tenant): si está activa, envíos masivos requieren aprobación. [HU-12](../knowledge-base/11_historias_de_usuario.md#hu-12---aprobar-mails-masivos-antes-de-despacho)
- **RF-20** — Plantillas de mail con variables tipo `{{alumno.nombre}}`, `{{materia.nombre}}`, etc., editables por COORDINADOR.
- **RF-21** — Avisos del sistema (tablón) con scope (global/materia/cohorte), severity, role_target, vigencia, sort, require_ack. [HU-14](../knowledge-base/11_historias_de_usuario.md#hu-14---publicar-aviso-del-sistema-con-scope-y-vigencia)
- **RF-22** — Mensajería interna docente ↔ coordinación (threads + responder). [HU-13](../knowledge-base/11_historias_de_usuario.md#hu-13---recibir-y-responder-mensajes-internos)

#### Equipos Docentes y Estructura Académica

- **RF-23** — ABM de carreras, cohortes, materias, profesores. [HU-16](../knowledge-base/11_historias_de_usuario.md#hu-16---dar-de-alta-un-profesor), [HU-21](../knowledge-base/11_historias_de_usuario.md#hu-21---administrar-carreras), [HU-22](../knowledge-base/11_historias_de_usuario.md#hu-22---administrar-cohortes)
- **RF-24** — Asignaciones individuales y masivas profesor↔materia con vigencia y jerarquía (`responde_a`). [HU-18](../knowledge-base/11_historias_de_usuario.md#hu-18---asignar-masivamente-docentes-a-una-materia)
- **RF-25** — Clonado de equipo entre cohortes. [HU-19](../knowledge-base/11_historias_de_usuario.md#hu-19---clonar-equipo-docente-entre-cohortes)
- **RF-26** — Modificar vigencia general de un equipo en bloque. [HU-20](../knowledge-base/11_historias_de_usuario.md#hu-20---modificar-vigencia-general-de-un-equipo)
- **RF-27** — Subida de programas (PDF) por materia × carrera × cohorte. [HU-23](../knowledge-base/11_historias_de_usuario.md#hu-23---subir-programa-de-materia-pdf)
- **RF-28** — Calendario académico con fechas de parciales, TP y coloquios. [HU-24](../knowledge-base/11_historias_de_usuario.md#hu-24---gestionar-fechas-de-parcialestpcoloquios)

#### Encuentros y Disponibilidad

- **RF-29** — Slots de encuentro recurrentes con generación automática de N instancias. [HU-25](../knowledge-base/11_historias_de_usuario.md#hu-25---crear-slot-de-encuentro-recurrente)
- **RF-30** — Encuentros únicos (no recurrentes). [HU-26](../knowledge-base/11_historias_de_usuario.md#hu-26---crear-encuentro-único-no-recurrente)
- **RF-31** — Edición de instancia individual (estado, meet, video, comentario). [HU-27](../knowledge-base/11_historias_de_usuario.md#hu-27---editar-instancia-individual-de-encuentro)
- **RF-32** — Snippet HTML exportable para pegar en Moodle. [HU-28](../knowledge-base/11_historias_de_usuario.md#hu-28---generar-html-de-encuentros-para-moodle)
- **RF-33** — Registro de guardias con form de alta. Resuelve [PA-05](../knowledge-base/10_preguntas_abiertas.md#pa-05). [HU-29](../knowledge-base/11_historias_de_usuario.md#hu-29---ver-mis-guardias-realizadas), [HU-46](../knowledge-base/11_historias_de_usuario.md#hu-46---ofcial---crear-una-guardia)

#### Coloquios

- **RF-34** — Convocatoria a coloquio (instancia + días + cupos). [HU-31](../knowledge-base/11_historias_de_usuario.md#hu-31---crear-nueva-convocatoria-de-coloquio)
- **RF-35** — Reservas de alumnos con cupos auto-decreciendo.
- **RF-36** — Agenda admin consolidada de reservas. [HU-32](../knowledge-base/11_historias_de_usuario.md#hu-32---ver-agenda-consolidada-de-reservas)

#### Tareas internas

- **RF-37** — Workflow profesor ↔ coordinación con estados + comentarios. [HU-34](../knowledge-base/11_historias_de_usuario.md#hu-34---ver-mis-tareas-asignadas), [HU-36](../knowledge-base/11_historias_de_usuario.md#hu-36---administrar-todas-las-tareas-coordinación)

#### Auditoría

- **RF-38** — Audit log persistente sin límite, con búsqueda full-text por código de acción, legajo, materia, rango de fechas, IP. Resuelve [P9](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver). [HU-38](../knowledge-base/11_historias_de_usuario.md#hu-38---auditar-acciones-individuales)
- **RF-39** — Panel de interacciones por docente con filtros y exportación. [HU-37](../knowledge-base/11_historias_de_usuario.md#hu-37---ver-panel-de-interacciones-por-docente)
- **RF-40** — Webhooks de eventos (acciones críticas) para integraciones externas.

#### Liquidaciones

- **RF-41** — Grilla de salarios editable por rol y otros ejes configurables. [HU-41](../knowledge-base/11_historias_de_usuario.md#hu-41---mantener-la-grilla-de-salarios)
- **RF-42** — Cálculo de liquidación = Base + Plus, con fórmula transparente y testeable. Resuelve [PA-06](../knowledge-base/10_preguntas_abiertas.md#pa-06). [HU-39](../knowledge-base/11_historias_de_usuario.md#hu-39---ver-vista-previa-de-liquidación-del-período)
- **RF-43** — Cerrar liquidación = inmutabilizar período. [HU-40](../knowledge-base/11_historias_de_usuario.md#hu-40---cerrar-liquidación-de-un-período)
- **RF-44** — Historial completo de liquidaciones por docente.

#### Perfil

- **RF-45** — Editar datos personales y bancarios. [HU-42](../knowledge-base/11_historias_de_usuario.md#hu-42---editar-mis-datos-personales-y-bancarios)
- **RF-46** — Logout. [HU-43](../knowledge-base/11_historias_de_usuario.md#hu-43---cerrar-sesión)

#### Facturación de monotributistas (descubierto en KB v0.2)

- **RF-61** — Docente monotributista (flag `factura=true`) puede subir factura mensual en PDF con detalle libre. [HU-49](../knowledge-base/11_historias_de_usuario.md#hu-49---docente-sube-su-factura-mensual)
- **RF-62** — Admin gestiona facturas con filtros (docente, estado pendiente/abonada, rango de fechas), marca como abonada y descarga PDFs. Las facturas NO se incluyen en la liquidación general — sustituyen al cálculo Base+Plus. [HU-48](../knowledge-base/11_historias_de_usuario.md#hu-48---gestionar-facturas-de-docentes-monotributistas)
- **RF-63** — Reglas de negocio confirmadas: NEXO suma al total pero se muestra aparte; monotributistas se segregan completamente; liquidación se opera por (cohorte × mes); ABM de grilla Base + grilla Plus con vigencia abierta. Ver [RN-31..40](../knowledge-base/05_reglas_de_negocio.md#dominio-salarios-y-liquidaciones-descubierto-en-segunda-pasada).

### 6.2 Requirements funcionales — Fase 2

#### Portal del Alumno

- **RF-47** — Login alumno con SSO institucional (Moodle SSO ideal).
- **RF-48** — Vista consolidada: estado del alumno en TODAS sus materias. Resuelve [P4](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).
- **RF-49** — Self-service: reserva de coloquios, ACK de avisos, descarga de programas. [HU-47](../knowledge-base/11_historias_de_usuario.md#hu-47---ofcial---alumno-reserva-un-coloquio)
- **RF-50** — Notificaciones push (web) al alumno.

#### Analytics y BI

- **RF-51** — Dashboard de tendencias (atrasados por cohorte vs tiempo, distribución de notas, etc.). Resuelve [P7](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).
- **RF-52** — Predicción de abandono ML-driven (riesgo alto/medio/bajo por alumno).
- **RF-53** — Reportes ejecutivos exportables PDF/Excel.

#### API y Ecosistema

- **RF-54** — API REST pública documentada con OpenAPI 3.1. Resuelve [P5](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver).
- **RF-55** — Webhooks suscribibles para eventos clave.
- **RF-56** — Integraciones nativas: Google Workspace (Calendar para encuentros), Slack (notificaciones).

### 6.3 Requirements funcionales — Fase 3+

- **RF-57** — App móvil (PWA primero, luego nativa según adopción).
- **RF-58** — Mensajería real-time (chat docente↔alumno).
- **RF-59** — Integración con AFIP (factura electrónica para monotributistas).
- **RF-60** — Multi-idioma (i18n).

### 6.4 Requirements no funcionales

#### Performance y Escalabilidad

- **RNF-01** — P95 de respuesta API < 500 ms para listados, < 2s para reportes.
- **RNF-02** — Soporte ≥ 10.000 usuarios concurrentes con elasticidad horizontal.
- **RNF-03** — Import Moodle de 100 alumnos × 30 actividades en < 30s.

#### Disponibilidad

- **RNF-04** — Uptime mensual ≥ 99.5%.
- **RNF-05** — RPO ≤ 1h, RTO ≤ 4h.
- **RNF-06** — Backups diarios + retención 30 días.

#### Seguridad

- **RNF-07** — Todo tráfico HTTPS con TLS 1.3.
- **RNF-08** — Datos sensibles (CBU, DNI) encriptados en reposo (AES-256).
- **RNF-09** — Auth con JWT corto (15min) + refresh token rotation.
- **RNF-10** — CSRF protection en endpoints state-changing.
- **RNF-11** — Rate limiting por IP y por usuario.
- **RNF-12** — Audit log inmutable (append-only, idealmente write-once storage).
- **RNF-13** — Cumplir Ley 25.326 Argentina (Datos Personales).
- **RNF-14** — Pentest anual + bug bounty.

#### Mantenibilidad

- **RNF-15** — Coverage de tests ≥ 80% líneas + 90% reglas de negocio.
- **RNF-16** — CI/CD pipeline (build + test + lint + deploy automatizado).
- **RNF-17** — Logs estructurados (JSON) + observability (OpenTelemetry).
- **RNF-18** — Feature flags para rollouts graduales.

#### UX

- **RNF-19** — Responsive desde 360px hasta 4K.
- **RNF-20** — WCAG 2.1 AA mínimo.
- **RNF-21** — Tiempo de aprendizaje del docente nuevo < 30 min para flujo principal.

#### Multi-tenancy

- **RNF-22** — Aislamiento total de datos por tenant (database-level si es factible, row-level mínimo).
- **RNF-23** — Configuración por tenant: idioma, branding, plantillas de mail, catálogo de escalas.

---

## 7. Scope: MVP vs Fases

### 7.1 MVP (Fase 1) — meta 3 a 4 meses

**Objetivo**: paridad funcional con PulseUPs + base limpia para escalar. Adoptable por docentes desde día 1.

Incluye RF-01 a RF-46 + RNF-01 a RNF-23.

**Excluye explícitamente**:
- Portal del alumno
- Dashboards analíticos avanzados
- API pública (solo interna)
- App móvil
- ML / predicción

### 7.2 Fase 2 — Portal del alumno + Analytics — meta +3 meses post-MVP

Incluye RF-47 a RF-56.

### 7.3 Fase 3+ — Móvil + Real-time + Ecosistema

Incluye RF-57 a RF-60.

---

## 8. User Journeys clave (MVP)

> Las journeys completos están en [07_flujos_principales.md](../knowledge-base/07_flujos_principales.md). Acá los resumimos como el flow esperado en activia-trace (con las mejoras vs PulseUPs).

### Journey 1 — Profesor detecta atrasados y manda recordatorios

```
1. Profesor → login con 2FA
2. Dashboard "Mi semana": ve KPIs de cada materia (atrasados, sin corregir, próximos parciales)
3. Click en materia X → vista detallada
4. (Background: el sistema ya sincronizó con Moodle automáticamente esa madrugada — RF-06)
5. Sección "Alumnos atrasados" muestra los N detectados
6. Click en "Recordar a todos"
7. Sistema arma N mails personalizados con plantilla
8. Modal de preview muestra los primeros 3 mails
9. Profesor aprueba → cola Pend
10. (Si tenant tiene aprobación activa) → admin aprueba → Send
11. (Worker) → OK/Fail → métricas visibles
```

**Mejora vs PulseUPs**: pasos 4 y 6-7 son automáticos. PulseUPs requería 5 pasos manuales (exportar Moodle, descargar, subir, parsear, mandar) — acá son cero clicks adicionales.

### Journey 2 — Coordinador arma nueva cohorte

```
1. Coordinador → "Cohortes" → "Nueva cohorte" → "AGO-2026"
2. Sistema sugiere clonar de la cohorte anterior (MAR-2026)
3. Coordinador acepta → todas las asignaciones se duplican
4. Coordinador ajusta deltas (profes nuevos, materias huérfanas)
5. Sistema confirma OK
6. Coordinador publica aviso de bienvenida con `require_ack`
```

**Mejora vs PulseUPs**: paso 2 con sugerencia proactiva (vs ir manualmente al menú "Clonar"). Tiempo total esperado: < 30 min.

### Journey 3 — Alumno consulta su estado (Fase 2)

```
1. Alumno → login con SSO Moodle
2. Dashboard: muestra sus 5 materias con barra de progreso
3. Click en materia → ve actividades, calificaciones, faltantes
4. Si hay coloquio con cupos abiertos → CTA "Reservar"
5. Reserva en 2 clicks
6. Recibe confirmación por email + sistema cuenta el cupo
```

**Mejora vs PulseUPs**: este journey **no existe** en PulseUPs (P4).

---

## 9. Modelo de datos (high-level)

> Modelo detallado en [04_modelo_de_datos.md](../knowledge-base/04_modelo_de_datos.md). Acá las diferencias vs PulseUPs.

### Cambios estructurales respecto a PulseUPs

| Cambio | Por qué |
|--------|---------|
| **Tenant** como primer nivel | Multi-tenancy real (G4) |
| **Catálogo único de Materia** con código global | Resolver P1 |
| **PadronVersion** (snapshot con timestamp) | Resolver P2 — historial completo |
| **Usuario** abstrae Profesor + Alumno + Tutor | Unifica el modelo para Fase 2 |
| **Rol** y **Permiso** como entidades | Modelo de permisos finos (no flag is_admin) |
| **AuditEvent** sin tope, particionado por mes | Resolver P9 |
| **ConfigTenant** | Permite escalas, plantillas y umbrales por tenant |

### ERD high-level

```
Tenant (1) ─── (N) Usuario ──┬─ rol → Rol
                              │
                              ├─ Profesor (especialización)
                              ├─ Alumno (especialización)
                              └─ Tutor (especialización)

Tenant (1) ─── (N) Carrera ── (N) Cohorte
Tenant (1) ─── (N) Materia
Carrera × Cohorte × Materia (N:N:N) ── Asignacion ── Profesor
Materia ─── (N) PadronVersion ─── (N) AlumnoEnPadron
Asignacion ─── (N) Calificacion
```

---

## 10. Stack tecnológico propuesto

> Este PRD no decide el stack — eso vive en la **ADR (Architecture Decision Records)** específica. Acá solo recomendaciones de principios.

### Principios

- **Backend**: framework moderno con tipado fuerte. Candidatos: NestJS (Node + TS), FastAPI (Python), Go con net/http.
- **Frontend**: SPA o SSR moderno. Candidatos: Next.js, Remix, SvelteKit.
- **DB principal**: PostgreSQL.
- **Cache + Queue**: Redis.
- **Almacenamiento PDF/objetos**: S3-compatible (MinIO en self-host o S3 en cloud).
- **Auth**: Keycloak / Auth0 / Cognito o implementación propia con JWT + refresh tokens rotativos.
- **Observability**: OpenTelemetry + Grafana stack.
- **CI/CD**: GitHub Actions / GitLab CI.

### Anti-principios

- ❌ No replicar PHP MPA monolítico ([P6](#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
- ❌ No mezclar lógica de negocio en templates de UI.
- ❌ No hidden inputs como mecanismo de carry-state (usar sesión o JWT claims).

---

## 11. Riesgos y mitigaciones

| ID | Riesgo | Probabilidad | Impacto | Mitigación |
|----|--------|--------------|---------|------------|
| R1 | Moodle WS deshabilitado o sin permisos en algún tenant | Media | Alto | Mantener fallback de import manual ([RF-07](#auth-roles-y-tenants)) |
| R2 | Migración de datos PulseUPs → activia-trace pierde información | Media | Alto | Doble corrida + reconciliación + período de coexistencia |
| R3 | Adopción baja del docente (resistencia al cambio) | Alta | Alto | Onboarding guiado, paridad funcional 100% en MVP, evangelización de un champion por carrera |
| R4 | Catálogos paralelos de PulseUPs (P1) son intencionales y unirlos rompe negocio | Media | Alto | Investigar con dueño (PA-01) **antes** de cerrar modelo de datos |
| R5 | Performance degrada con tenants grandes (10k+ alumnos) | Media | Medio | Tests de carga continuos, particionado por tenant_id |
| R6 | Lock-in con un proveedor (auth, cloud) | Baja | Medio | Preferir estándares abiertos (OAuth2, S3 API, OpenTelemetry) |
| R7 | Compliance / Ley 25.326 mal implementado | Baja | Alto | Asesoría legal antes de MVP go-live, cifrado de PII en reposo |
| R8 | Equipo subestima complejidad de liquidaciones | Alta | Medio | Definir fórmula con finanzas en sprint 1, no asumir |

---

## 12. Open questions (a resolver antes de cerrar el PRD)

> Algunas heredadas de la KB ([10_preguntas_abiertas.md](../knowledge-base/10_preguntas_abiertas.md)), otras del PRD.

### Heredadas de la KB

- **OQ-01** — Validar [PA-01](../knowledge-base/10_preguntas_abiertas.md#pa-01) (catálogos paralelos). **Bloquea G3 y RF-11.**
- ~~**OQ-02**~~ — ✅ **RESUELTA en KB v0.2**: la fórmula es Base por rol + Plus por (clave, rol). Ver [RN-31..38](../knowledge-base/05_reglas_de_negocio.md#rn-31--grilla-salarial-con-vigencia-abierta).
- ~~**OQ-03**~~ — ✅ **RESUELTA en KB v0.2**: catálogo cerrado de roles es `ALL, PROFESOR, TUTOR, NEXO, COORDINADOR`. Aparece rol NEXO no detectado en primera pasada.

### Nuevas open questions surgidas en v0.2

- **OQ-11** — ¿Cómo se mapean las claves de Plus a familias de materias? Solo se observó `PROG` — [PA-22](../knowledge-base/10_preguntas_abiertas.md#pa-22).
- **OQ-12** — ¿Cómo se calcula el Plus si un docente tiene N comisiones de la misma clave? — [PA-23](../knowledge-base/10_preguntas_abiertas.md#pa-23).
- **OQ-13** — ¿Cuál es la semántica de NEXO (regional? programa? enlace alumno?) — [PA-25](../knowledge-base/10_preguntas_abiertas.md#pa-25).
- **OQ-14** — ¿Se audita el uso de `?leg=X` (impersonation)? Crítico para seguridad/atribución — [PA-21](../knowledge-base/10_preguntas_abiertas.md#pa-21).

### Específicas del PRD

- **OQ-04** — ¿La institución TUPAD acepta auth federado con Moodle SSO o prefiere login propio? Impacta RF-01.
- **OQ-05** — ¿Quién es el "ADMIN financiero" hoy? ¿Existe el rol o es el coordinador con `is_admin`?
- **OQ-06** — ¿Hay otros tenants potenciales además de TUPAD? Si sí, ¿en qué horizonte? Impacta priorización de G4.
- **OQ-07** — ¿La institución tiene presupuesto para hosting cloud o requiere self-host?
- **OQ-08** — ¿Hay compromiso firme de migrar de PulseUPs o conviven? Impacta R2.
- **OQ-09** — ¿Quién aprueba el envío de mails masivos en MVP? Sin esa pregunta resuelta, RF-19 queda incompleto.
- **OQ-10** — ¿El feature de Correct-IA queda como módulo externo separado o lo incluimos en Fase 2?

---

## 13. Apéndices

### A — Trazabilidad PRD → KB

| Requirement | KB Reference |
|-------------|--------------|
| RF-01..05 | [03_actores_y_roles](../knowledge-base/03_actores_y_roles.md), [HU-45](../knowledge-base/11_historias_de_usuario.md#hu-45) |
| RF-06..11 | [Épica 1 — Ingesta Moodle](../knowledge-base/06_funcionalidades.md#épica-1--ingesta-de-datos-desde-moodle) |
| RF-12..16 | [Épica 2 — Análisis](../knowledge-base/06_funcionalidades.md#épica-2--análisis-y-reportes-académicos) |
| RF-17..22 | [Épica 3 — Comunicación](../knowledge-base/06_funcionalidades.md#épica-3--comunicación-con-alumnos) |
| RF-23..28 | [Épica 4 + 5 — Equipos y Estructura](../knowledge-base/06_funcionalidades.md#épica-4--gestión-de-equipos-docentes) |
| RF-29..33 | [Épica 6 — Encuentros](../knowledge-base/06_funcionalidades.md#épica-6--encuentros-y-disponibilidad) |
| RF-34..36 | [Épica 7 — Coloquios](../knowledge-base/06_funcionalidades.md#épica-7--coloquios) |
| RF-37 | [Épica 8 — Tareas](../knowledge-base/06_funcionalidades.md#épica-8--workflow-de-tareas) |
| RF-38..40 | [Épica 9 — Auditoría](../knowledge-base/06_funcionalidades.md#épica-9--auditoría-y-métricas) |
| RF-41..44 | [Épica 10 — Liquidaciones](../knowledge-base/06_funcionalidades.md#épica-10--liquidaciones-y-honorarios) |
| RF-45..46 | [Épica 11 — Perfil](../knowledge-base/06_funcionalidades.md#épica-11--perfil-y-sesión) |
| RF-61..62 (nuevos) | [Épica 13 — Facturación monotributistas](../knowledge-base/11_historias_de_usuario.md#épica-13--facturación-de-monotributistas-descubierta-en-segunda-pasada) |

### B — Glosario

| Término | Definición |
|---------|-----------|
| **PulseUPs** | Sistema actual del cual evoluciona activia-trace. Documentado en [knowledge-base/](../knowledge-base/) |
| **TUPAD** | Tecnicatura Universitaria en Programación a Distancia — primer tenant |
| **Moodle** | LMS open-source que la institución usa como sistema oficial |
| **MTTR** | Mean Time To Resolution |
| **NPS** | Net Promoter Score |
| **JTBD** | Jobs To Be Done — framework de definición de oportunidades |
| **ADR** | Architecture Decision Record — documento por decisión técnica |
| **PII** | Personally Identifiable Information |
| **PWA** | Progressive Web App |

### C — Historial de cambios

| Fecha | Versión | Cambio | Autor |
|-------|---------|--------|-------|
| 2026-05-28 | 0.1 | Draft inicial derivado de KB | Análisis automatizado |

---

## Siguiente paso recomendado

1. **Revisar este PRD con stakeholders** (dueño del producto, COORDINADOR académico, ADMIN financiero, IT).
2. **Cerrar las Open Questions** (OQ-01 a OQ-10) — especialmente OQ-01 que bloquea modelo de datos.
3. **Generar ADRs** para decisiones técnicas (stack, auth, hosting).
4. **Backlog inicial**: convertir RF-01..46 en épicas y user stories sprintables.
5. **Definir métricas baseline** en PulseUPs (cuántos atrasados se detectan hoy, cuánto tarda el setup, etc.) para medir el delta del MVP.
