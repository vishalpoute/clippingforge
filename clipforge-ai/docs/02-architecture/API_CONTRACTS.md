# API_CONTRACTS.md

## Health Endpoints
- `GET /api/v1/health`
  - Response: `{ "status": "ok" }`
  - Status codes: 200
- `GET /api/v1/health/dependencies`
  - Response: `{ "database": "<DATABASE_URL>", "redis": "<REDIS_URL>" }`
  - Status codes: 200

## Video Upload (stub)
- `POST /api/v1/videos/upload`
  - Request: `multipart/form-data` with `file` field.
  - Response: `{ "video_id": "<uuid>", "status": "queued" }`
  - Status codes: 201, 400, 401

*All other endpoints will be added as implementation progresses and reflected here.*