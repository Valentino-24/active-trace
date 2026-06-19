# Especificación: Coloquios

## Evaluacion (convocatoria)

### AT-01: Crear convocatoria de coloquio (F7.3)
- Dado un COORDINADOR autenticado con permiso `coloquios:gestionar`
- Cuando envía `POST /api/coloquios` con materia_id, cohorte_id, tipo="Coloquio", instancia="Coloquio Final 2026", dias_disponibles=30
- Entonces el sistema responde 201
- Y se crea un registro en `evaluacion` con activa=true

### AT-02: Rechazar creación sin campos requeridos
- Dado un COORDINADOR autenticado
- Cuando envía `POST /api/coloquios` sin materia_id
- Entonces el sistema responde 422

### AT-03: Importar alumnos a convocatoria (F7.2)
- Dado que existe una Evaluacion
- Cuando un COORDINADOR envía `POST /api/coloquios/{id}/alumnos` con una lista de alumno_ids
- Entonces el sistema responde 200 con `importados=N`
- Y se crean N registros en `resultado_evaluacion` con nota_final=NULL

### AT-04: Importar alumnos duplicados se saltan
- Dado que ya existen 2 resultados para una evaluación
- Cuando se importan los mismos 2 IDs + 1 nuevo
- Entonces responde `importados=1` y `ya_existentes=2`

### AT-05: Listar convocatorias con métricas (F7.4)
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/coloquios`
- Entonces recibe una lista con campos materia, instancia, convocados, reservas_activas, cupo_disponible, activa
- Y los totales reflejan los datos existentes

### AT-06: Cerrar convocatoria
- Dado un COORDINADOR autenticado con permiso `coloquios:gestionar`
- Cuando envía `PATCH /api/coloquios/{id}` con `{"activa": false}`
- Entonces el sistema responde 200
- Y la evaluación queda con activa=false

## ReservaEvaluacion (turno ALUMNO)

### AT-07: ALUMNO reserva turno con cupo disponible
- Dado un ALUMNO autenticado que está habilitado para una convocatoria
- Cuando envía `POST /api/coloquios/{id}/reservar` con `fecha_hora` válida
- Entonces responde 201
- Y se crea `reserva_evaluacion` con estado="Activa"

### AT-08: Rechazar reserva sin cupo
- Dado que una convocatoria tiene dias_disponibles=1 y ya hay 1 reserva activa
- Cuando un ALUMNO intenta reservar
- Entonces responde 409 "No hay cupo disponible"

### AT-09: ALUMNO cancela su reserva
- Dado un ALUMNO con una reserva Activa
- Cuando envía `DELETE /api/coloquios/reservas/{id}`
- Entonces responde 200
- Y la reserva queda con estado="Cancelada"

### AT-10: Alumno ve solo convocatorias donde está habilitado
- Dado un ALUMNO que está en resultado_evaluacion de convocatoria A pero no de B
- Cuando consulta `GET /api/coloquios/disponibles`
- Entonces solo recibe la convocatoria A

### AT-11: Alumno ve sus reservas
- Dado un ALUMNO con 2 reservas activas
- Cuando consulta `GET /api/coloquios/mis-reservas`
- Entonces recibe 2 items con estado, fecha_hora, materia

## ResultadoEvaluacion (notas)

### AT-12: Registrar nota final
- Dado que existe un resultado con nota_final=NULL
- Cuando un COORDINADOR envía `PATCH /api/coloquios/resultados/{id}` con `{"nota_final": "8"}`
- Entonces responde 200
- Y el resultado se actualiza con nota_final="8"

## Métricas y consultas (F7.1, F7.5)

### AT-13: Panel de métricas
- Dado que existen evaluaciones, reservas y resultados
- Cuando un COORDINADOR consulta `GET /api/coloquios/metricas`
- Entonces recibe total_alumnos_cargados, instancias_activas, reservas_activas, notas_registradas
- Y los valores son correctos según los datos

### AT-14: Agenda consolidada
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/coloquios/agenda`
- Entonces recibe todas las reservas activas del tenant
- Con datos de alumno, materia, fecha_hora, evaluación

### AT-15: Registro académico consolidado
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/coloquios/registro`
- Entonces recibe todos los resultados con nota_final NOT NULL
- Con datos de alumno, materia, instancia, nota

## Permisos

### AT-16: 403 sin permiso coloquios:gestionar
- Dado un usuario SIN permiso `coloquios:gestionar`
- Cuando intenta POST/PATCH a /api/coloquios/*
- Entonces recibe 403

### AT-17: 403 sin permiso coloquios:ver
- Dado un usuario SIN permiso `coloquios:ver`
- Cuando intenta GET a /api/coloquios (listado, métricas, agenda, registro)
- Entonces recibe 403

### AT-18: ALUMNO no puede gestionar coloquios
- Dado un ALUMNO autenticado
- Cuando intenta POST /api/coloquios
- Entonces recibe 403

### AT-19: 401 sin token
- Dado un request SIN token JWT
- Cuando intenta cualquier endpoint de /api/coloquios/*
- Entonces recibe 401
