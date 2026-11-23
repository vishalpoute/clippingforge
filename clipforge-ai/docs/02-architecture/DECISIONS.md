# DECISIONS.md

## 2024-11-21 – Repository Structure Decision
- **Context**: Need a clear monorepo layout for frontend, backend, shared packages, and storage.
- **Options**: Single repo with nested `apps/` and `services/` vs multiple repositories.
- **Selected**: Single monorepo (chosen for simplicity, easier CI, and unified Docker Compose).
- **Rationale**: Cohesive development, shared TypeScript & Python utilities, straightforward deployment.
- **Consequences**: All agents work in same workspace; requires disciplined branch management.

## 2024-11-21 – Technology Stack Decision
- **Context**: Choose between Node.js vs Deno for frontend, and Flask vs FastAPI for backend.
- **Options**: React with Vite, Next.js, or Remix; Python Flask or FastAPI.
- **Selected**: Next.js (App Router) for SPA; FastAPI for backend due to async support and Pydantic v2.
- **Rationale**: Strong TypeScript integration, server-side rendering optional, FastAPI aligns with background tasks and OpenAPI generation.
- **Consequences**: Need to manage async concurrency; later may add GraphQL if required.

## 2025-11-21 – Native Windows Development Migration
- **Context**: Docker Desktop has permission issues with `.docker/config.json` on the development machine. PostgreSQL and Redis require Docker containers. Network/DNS issues blocked pip and npm installs during previous sessions. These blockers prevented completing Milestone 1.
- **Options**:
  1. Fix Docker permissions and continue with Docker-based development.
  2. Switch to native Windows development with lightweight alternatives.
  3. Use WSL2 for a Linux-like development environment.
- **Selected**: Option 2 — Native Windows development with SQLite and APScheduler.
- **Rationale**:
  - Removes all Docker dependencies for development.
  - SQLite requires zero configuration and is built into Python.
  - APScheduler with SQLite job store provides persistent background jobs without Redis.
  - All interfaces remain compatible with PostgreSQL and Celery for production.
  - Faster iteration cycle (no container build/startup overhead).
- **Consequences**:
  - Single-writer constraint with SQLite (acceptable for single-user MVP).
  - Must maintain dual-database compatibility in SQLAlchemy models.
  - Docker Compose retained as optional production deployment infrastructure.
  - PowerShell scripts replace `docker compose` commands for development.
  - `.env.example` updated with SQLite defaults and native paths.
