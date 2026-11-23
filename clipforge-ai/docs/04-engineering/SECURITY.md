# SECURITY.md

## Overview
Security is a core requirement for ClipForge AI. All sensitive data (password hashes, OAuth tokens, encryption keys) must be stored outside the codebase and never exposed to the client.

## Authentication & Authorization
- **JWT** is used for stateless authentication. The secret (`JWT_SECRET`) is defined in `.env.example` and must be provided at runtime.
- Passwords are hashed with **bcrypt** (via `passlib` or similar) – implementation will be added in later milestones.
- Role‑based access control (RBAC) will be introduced when user and admin endpoints are defined.

## Secret Management
- Environment variables (`*.env*`) are the single source of truth for secrets.
- In production, a secret manager (e.g., GCP Secret Manager, Azure Key Vault) should be used to inject these values into containers.
- The `ENCRYPTION_KEY` is used for encrypting OAuth refresh tokens at rest.

## Data Validation & Sanitization
- All incoming request bodies are validated with **Pydantic v2** models.
- File uploads are scanned for MIME type and size limits (`MAX_UPLOAD_SIZE_MB`).
- SQLAlchemy ORM prevents SQL injection; raw queries are avoided.

## Transport Security
- Services must be served behind TLS (HTTPS) in production. Development uses plain HTTP on `localhost`.
- CORS is configured to allow only the frontend origin (`NEXT_PUBLIC_API_URL`).

## Auditing & Logging
- Structured logs include request IDs, user IDs (when authenticated), and timestamps.
- Critical actions (login, token refresh, publishing) will generate audit entries in the `AuditLog` table (planned).

## Future Hardening
- Rate limiting via `slowapi` or similar middleware.
- HTTP security headers (Content‑Security‑Policy, X‑Frame‑Options, etc.).
- Regular dependency scanning (`safety`, `pip-audit`).

*Implementation of the above mechanisms will be added in later milestones; the current repository includes placeholders and the environment variable definitions.*