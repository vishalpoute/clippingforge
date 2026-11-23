# DATABASE_SCHEMA.md

## Database Engine
- **Development**: SQLite (`data/clipforge.db`) with WAL mode and foreign keys enabled
- **Production**: PostgreSQL 16

SQLAlchemy ORM provides database-agnostic model definitions.

## Tables (Milestone 1)

### users
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, autoincrement |
| `email` | String(320) | UNIQUE, NOT NULL, indexed |
| `password_hash` | String(256) | NOT NULL |
| `display_name` | String(128) | nullable |
| `created_at` | DateTime(tz) | default: now() |
| `updated_at` | DateTime(tz) | default: now(), onupdate: now() |

### projects
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, autoincrement |
| `user_id` | Integer | FK → users.id, NOT NULL, indexed |
| `name` | String(256) | NOT NULL |
| `description` | Text | nullable |
| `created_at` | DateTime(tz) | default: now() |

## Relationships
- `User` has many `Project` (one-to-many via `user_id` FK)

## Migrations
Alembic manages schema migrations:
- Config: `services/api/alembic.ini`
- Scripts: `services/api/migrations/`
- Current revision: `001_initial` (users + projects)

## Planned Tables (Future Milestones)
- `video_sources` — uploaded/imported video files
- `transcripts` — speech-to-text segments
- `clips` — generated short-form clips
- `publishing_jobs` — social media publishing queue
- `connected_accounts` — OAuth tokens for platforms
- `analytics` — platform performance metrics

---
*Schema will be expanded as milestones are implemented.*
