# Proposal: Deploy y CI (C-24)

## Intent
Containerizar el frontend, unir backend+frontend en docker-compose, y configurar CI para tests + build.

## Scope
- Dockerfile multi-stage para frontend (Vite build → nginx)
- Agregar servicio `frontend` a docker-compose.yml
- GitHub Actions CI: pytest + vitest + build
- `.env.example` para producción

## Out of Scope
- Deploy a Easypanel/VPS (configuración manual)
- Kubernetes
- CD automático

## Capabilities
### New
- `deploy`: Configuración de contenedores y CI

## Dependencies
C-01 a C-23 completos

## Success Criteria
- [ ] `docker compose up` levanta API + frontend + DB
- [ ] CI pipeline ejecuta tests de backend y frontend
