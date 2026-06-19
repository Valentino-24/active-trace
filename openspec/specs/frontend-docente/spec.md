# Especificacion: Frontend Academico Docente

### AT-01: Pagina de calificaciones con importacion
- PROFESOR ve tabla de notas por materia
- Puede importar archivo CSV/Excel con preview
- Usa TanStack Query para fetching y mutaciones

### AT-02: Pagina de atrasados
- Tabla con alumnos atrasados, pendientes, dias de atraso
- Ranking con promedios

### AT-03: Pagina de comunicaciones
- Redactar mensaje para alumnos atrasados
- Enviar con tracking de estado en tiempo real

### AT-04: Rutas protegidas por permiso
- calificaciones → `calificaciones:importar`
- atrasados → `calificaciones:importar`
- comunicaciones → `comunicacion:enviar`

### AT-05: Tests
- Hooks de TanStack Query mockeados correctamente
- Al menos 2 tests de hook
