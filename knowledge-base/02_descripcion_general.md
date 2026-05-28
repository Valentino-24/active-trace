# 02 — Descripción General

## Stack tecnológico (inferido)

| Capa | Tecnología detectada | Evidencia |
|------|---------------------|-----------|
| **Backend** | PHP | Todas las rutas terminan en `.php`; título del repo "Importar calificaciones (PHPExcel) + Reportes" |
| **Librería Excel** | PHPExcel (o derivado PhpSpreadsheet) | Mencionada explícitamente en el title HTML |
| **DB** | MySQL/MariaDB (suposición) | Stack típico de aplicaciones PHP en producción de este perfil |
| **Frontend** | HTML server-rendered + Bootstrap-like | Clases `card-header`, `btn`, `nav-link`, modales tipo BS |
| **JS** | Vanilla / jQuery (suposición) | Modales, AJAX para autocompletes, no se ven indicios de framework SPA |
| **Servidor web** | Apache o Nginx (suposición) | Producción típica para PHP |
| **Hosting** | olsoft.online | Dominio propio |
| **Auth** | Sesión PHP server-side | El logout es `logout.php` (sin JWT visible) |
| **CSRF** | Token CSRF por formulario | Campos `csrf:hidden` en cada POST detectado |

## Arquitectura general

El sistema sigue un patrón **MPA (Multi-Page Application) clásico de PHP**:
- 1 archivo `.php` = 1 endpoint = 1 vista renderizada server-side.
- No hay router central; cada `.php` maneja su propio GET (render) y POST (acción).
- Formularios siempre apuntan a `(self)` (mismo `.php`) y diferencian acción por un campo `action`/`accion` hidden.
- Cada POST lleva su `csrf` token.

### Convención de nombres de URLs observada

| Patrón | Significado |
|--------|-------------|
| `index.php` | Home + Procesos Moodle (POR USUARIO) |
| `mis_*.php` | Vista del usuario logueado (mis_equipos, mis_guardias, mis_tareas) |
| `admin_*.php` | Vista de coordinación/administración (global, multi-docente) |
| `admin_monitor_*.php` | Sub-vistas específicas de monitor |
| Sin prefijo (`encuentros.php`, `perfil.php`, etc.) | Funcionalidades transversales |
| Subdirectorios (`coloquios/index.php`) | Módulos funcionales aislados |

### Sub-módulos detectados

```
/evalia/
├── mood/          ← módulo principal documentado (Moodle integration)
│   ├── coloquios/ ← sub-módulo de coloquios
│   └── ...
└── corrector/     ← módulo externo "Correct-IA" (fuera de alcance)
```

## Integraciones externas

### 1. Moodle (entrada de datos)
- **Bidireccional? No**: el flujo es solo **Moodle → PulseUPs** (vía exportación manual de Excel).
- **Archivos importados**:
  - Excel de calificaciones (`.xlsx`) — vía `index.php` sección 1.a.
  - Reporte de finalización (`.xlsx` o `.csv` tabulado) — `index.php` sección 1.b.
  - Padrón de participantes — `monitor_evalia.php`.
  - Padrón de actividades — `admin_monitor.php`.
- **Detección automática de columnas**:
  - Columnas que terminan en `(Real)` → toman notas numéricas redondeadas.
  - Valores "Satisfactorio" / "Supera lo esperado" → se guardan en `nota_texto` y cuentan como aprobado.
- **Salida hacia Moodle**: hay secciones "HTML para Moodle" en `encuentros.php` y `fechas_parciales.php` — generan snippets HTML para que el profe pegue manualmente en el aula virtual.

### 2. Google Meet (encuentros)
- Cada slot/instancia tiene un campo `meet` (URL) y `video` (URL del video grabado).
- El sistema no crea reuniones — solo guarda el link manual.

### 3. Email (saliente)
- Hay un worker/queue de envío con estados: **Pend, Send, OK, Fail, Canc**.
- Modal "Previsualización del email" con Asunto + Cuerpo HTML antes de envío.
- Existe un proceso de **aprobación** (`admin_mail_approval.php`) antes del envío masivo.
- Métricas por docente: Emails OK / Emails FAIL / Batches.

### 4. Sistema bancario (liquidaciones)
- Se guarda banco, CBU, alias CBU por docente.
- Liquidación calcula Base + Plus por comisión.
- No se observa integración directa con bancos — exporta a Excel.

## Universos de materias paralelos (DISCREPANCIA DETECTADA)

El sistema maneja **dos catálogos de materias distintos** que no se cruzan visualmente:

### Catálogo A — Procesos Moodle (`index.php`)
19 materias con código tipo `(AYSO)`, `(PROG_I)`:
- IAD, AYSO, DB_I, DB_II, GDP, ING_I, ING_II, LEGIS, MATH, MET_I, MET_II, OE, PYE, PROG_I, PROG_II, PROG_III, PROG_IV, PF, SYS

### Catálogo B — Monitor EVALIA (`monitor_evalia.php`)
12 materias con IDs distintos, nombres descriptivos:
- Análisis de Datos [ID 1], Bases de Datos Relacionales [ID 15], Estadisticas [ID 13], Gestión desarrollo de software [ID 18], Metodologia de sistemas I [ID 14], Metodología de Sistemas II [ID 19], Pre Nivelatorio [ID 17], Programación - C Sharp [ID 6], Programación - Java [ID 5], Programación - JavaScript [ID 8], Programación - Python [ID 4], Sistemas Operativos [ID 10]

**Suposición:** son dos cohortes/programas diferentes (TUPAD malla vieja vs nueva, o cursos abiertos vs carrera), pero el sistema NO los une — son tablas o instancias separadas. Esto se confirma con que los IDs son completamente diferentes (PROG_I es id=3 en catálogo A, pero Programación - Python es id=4 en catálogo B).

→ Ver pregunta abierta en [10_preguntas_abiertas.md](10_preguntas_abiertas.md#PA-01).

## Seguridad observable

- **CSRF tokens** en todos los POST.
- **Control de roles a nivel ruta**: `admin_mail_approval.php` → silently redirect, `salarios.php` → "No autorizado" explícito.
- **Auditoría completa** en `admin.php`: cada acción con timestamp, legajo, materia, código de acción, rows, IP, User-Agent.
- **Sesión por servidor**: `logout.php` y cookies de sesión PHP.
- **Datos sensibles redactados en accessibility tree**: los hidden inputs muestran `[value redacted]`.

> 🔴 **Falla crítica observada (NO replicar)**: existe **impersonation por URL `?leg=X`** que permite cambiar de identidad (incluido super-admin) — Broken Access Control, OWASP A01. activia-trace lo elimina de raíz: identidad **solo desde JWT firmado**, RBAC fino, multi-tenant, impersonation auditada. Ver [P11](../docs/PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver) y [`ARQUITECTURA.md` §5](../docs/ARQUITECTURA.md).

## Branding

- Marca: **PulseUPs®** (con registro ®)
- Sub-marca: **Gestión académica**
- Autor: **OscarLondero®** ("by OscarLondero®" en el footer)
- Footer literal: "Gestor de Rendimiento Académico & Recordatorios — by OscarLondero®"
