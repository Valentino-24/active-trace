## 1. Nuevos schemas Pydantic

- [x] 1.1 Crear `AsignacionDocenteInfo` en `asignacion.py`: response con relaciones expandidas (usuario: nombre/email, materia: nombre, carrera: nombre, cohorte: nombre, responsable: nombre)
- [x] 1.2 Crear `AsignacionMasivaRequest` en `equipo.py`: materia_id, carrera_id, cohorte_id, comisiones, desde, hasta, asignaciones[] (cada una: usuario_id, rol, responsable_id opcional)
- [x] 1.3 Crear `AsignacionMasivaResponse` en `equipo.py`: creadas (int), items (list[AsignacionDocenteInfo])
- [x] 1.4 Crear `CloneEquipoRequest` en `equipo.py`: origen (materia_id, carrera_id, cohorte_id), destino (materia_id, carrera_id, cohorte_id), incluir_roles (opcional, default todos)
- [x] 1.5 Crear `CloneEquipoResponse` en `equipo.py`: clonadas (int), items (list[uuid])
- [x] 1.6 Crear `VigenciaRequest` en `equipo.py`: materia_id (opcional), carrera_id (opcional), cohorte_id (opcional), rol (opcional), nuevo_desde (opcional), nuevo_hasta (opcional), confirmar (bool, default false)
- [x] 1.7 Crear `VigenciaResponse` en `equipo.py`: actualizadas (int), items (list[uuid])
- [x] 1.8 Crear `EquipoListResponse` en `equipo.py`: items (list[AsignacionDocenteInfo]), total (int)

## 2. Extender repositorio (asignacion_repository.py)

- [x] 2.1 Agregar `bulk_create()`: crea múltiples asignaciones en una transacción con validación previa de existencia de usuarios
- [x] 2.2 Agregar `clone_equipo()`: copia asignaciones vigentes de origen → destino, ajusta fechas desde cohorte destino, respeta RN-12 (evita duplicados)
- [x] 2.3 Agregar `update_vigencia_masiva()`: actualiza desde/hasta de asignaciones que coincidan con filtros, con protección de fechas pasadas
- [x] 2.4 Agregar `list_equipo_docente()`: lista asignaciones del usuario autenticado con joins a materia/carrera/cohorte/responsable
- [x] 2.5 Agregar `list_equipos_tenant()`: lista paginada con filtros múltiples + búsqueda textual (ILIKE sobre usuario.nombre y materia.nombre)

## 3. Nuevo router equipos

- [x] 3.1 Crear `backend/app/api/v1/routers/equipos.py` con prefijo `/api/equipos` y tag "equipos"
- [x] 3.2 Implementar `GET /api/equipos/mi-equipo` protegido solo por auth (sin permiso extra)
- [x] 3.3 Implementar `GET /api/equipos` protegido con `equipos:gestionar`, filtros query: skip, limit, materia_id, carrera_id, cohorte_id, rol, docente_id, vigentes_only, q
- [x] 3.4 Implementar `POST /api/equipos/asignacion-masiva` protegido con `equipos:gestionar` (transaccional, max 200)
- [x] 3.5 Implementar `POST /api/equipos/clonar` protegido con `equipos:gestionar` (transaccional, RN-12, max 200)
- [x] 3.6 Implementar `PATCH /api/equipos/vigencia` protegido con `equipos:gestionar` (transaccional, protección fechas pasadas)
- [x] 3.7 Implementar `GET /api/equipos/exportar` protegido con `equipos:gestionar` (CSV con BOM, max 10K filas)
- [x] 3.8 Registrar router en `main.py`

## 4. Permisos y seed

- [x] 4.1 Agregar permiso `equipos:gestionar` al seed de permisos (módulo `equipos`)
- [x] 4.2 Asignar `equipos:gestionar` a los roles COORDINADOR y ADMIN

## 5. Tests

- [x] 5.1 Test de `GET /api/equipos/mi-equipo`: docente ve sus asignaciones, no ve las de otros
- [x] 5.2 Test de `GET /api/equipos`: listado con filtros, paginación, búsqueda textual
- [x] 5.3 Test de `POST /api/equipos/asignacion-masiva`: creación exitosa, error si usuario no existe en tenant, error si excede límite
- [x] 5.4 Test de `POST /api/equipos/clonar`: clonación exitosa, respeta RN-12 (no duplica), error si origen/destino iguales
- [x] 5.5 Test de `PATCH /api/equipos/vigencia`: actualización exitosa, protección fecha pasada, confirmación explícita
- [x] 5.6 Test de `GET /api/equipos/exportar`: CSV generado con cabeceras correctas
- [x] 5.7 Test de permisos: usuario sin `equipos:gestionar` recibe 403 en endpoints masivos
- [x] 5.8 Test de multi-tenancy: datos de tenant A no visibles en tenant B
