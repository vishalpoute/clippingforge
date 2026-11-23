# AGENTS.md

## Engineering Team Roles

| Agent | Role | Primary Ownership | Key Responsibilities |
|-------|------|-------------------|----------------------|
| **Agent 1** | Project Lead / Software Architect | Overall architecture, milestone planning, coordination | Define system components, set API contracts, review PRs, approve releases |
| **Agent 2** | Frontend Engineer | `apps/web/` | Build Next.js UI, integrate backend APIs, implement responsive dashboard |
| **Agent 3** | Backend Engineer | `services/api/` | Implement FastAPI services, database models, authentication, background jobs |
| **Agent 4** | AI/ML Engineer | `services/api/app/services/ai/` | OmniRouter integration, transcription, viral moment detection, caption generation |
| **Agent 5** | Video Processing Engineer | `services/api/app/services/video/` | FFmpeg pipelines, clipping, auto‑cropping, subtitle rendering |
| **Agent 6** | Social Platform Integration Engineer | `services/api/app/services/publishing/` | OAuth flows, YouTube/Instagram/Facebook APIs, publishing queue |
| **Agent 7** | DevOps Engineer | Docker & deployment scripts | Docker Compose, PostgreSQL/Redis setup, Windows startup scripts |
| **Agent 8** | QA & Security Engineer | Test suites, security review | Write automated tests, perform integration testing, audit security |

## Collaboration Rules

1. **Read‑before‑write** – every agent must consult the relevant markdown docs before editing code.
2. **Task ownership** – each file/folder is owned by the agent listed above; others must request a handoff.
3. **Branching** – agents work on isolated branches (or worktrees) when editing the same module.
4. **Review** – changes are reviewed by a different agent before merging to `main`.
5. **Handoff protocol** – after finishing a task, update `TASKS.md`, `PROGRESS.md`, and `HANDOFF.md` before passing work to the next agent.

## Coding Conventions

- **Type safety** – strict TypeScript (`tsconfig.json`) and Python typing (`mypy`).
- **Linting** – ESLint + Prettier for frontend; Ruff + mypy for backend.
- **Commit messages** – `<type>(<scope>): <short summary>`.
- **Documentation** – every public module must have a docstring and be referenced in the appropriate markdown file.

## Review Process

1. Agent finishes a feature → creates a PR.
2. A different agent runs `git review` (local script) which:
   - Runs lint / type checks.
   - Executes relevant unit / integration tests.
   - Checks that API contracts match `API_CONTRACTS.md`.
3. Reviewer approves or requests changes.
4. After approval, the PR is merged and the author updates `HANDOFF.md`.

## Handoff Protocol (summary)

- List changed files.
- Summarize tests executed and results.
- Note any blockers or open questions.
- Assign next owner or mark task as DONE.
