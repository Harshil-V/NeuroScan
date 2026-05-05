# AGENTS.md — NeuroScan Workstation

> Read this first if you are an AI agent (Cursor, Claude Code, Codex, etc.) starting work on this repo.

## What this project is

NeuroScan Workstation is a local-first medical imaging engineering platform that simulates an end-to-end MRI/DICOM workflow: Qt desktop viewer + React web viewer + FastAPI backend + Orthanc DICOM archive + MRI reconstruction service + simulated secure clinical data transfer (MinIO + signed URLs + audit + de-id checks). It is a **portfolio engineering project**, not a clinical product. It uses only synthetic or de-identified public imaging data.

## Where to start

Read these docs **in this order** before doing anything:

1. **[`docs/status.md`](docs/status.md)** — current state, active slice, immediate next action.
2. **[`docs/project-overview.md`](docs/project-overview.md)** — what & why, full-platform architecture vision.
3. **[`docs/roadmap.md`](docs/roadmap.md)** — phased slice plan, cross-slice locked decisions (AD-1 … AD-9).
4. The active slice spec under **[`docs/superpowers/specs/`](docs/superpowers/specs/)** — detailed design for whichever slice is currently being worked on.
5. **[`docs/prd/2026-05-05-original-prd.md`](docs/prd/2026-05-05-original-prd.md)** — original brief, frozen historical record. Reference, don't edit.

## How work is organized

The project is built in **independently-shippable slices**. Each slice goes through:

```text
brainstorming  →  spec  →  implementation plan  →  implementation
```

before the next slice starts. Spec files live in `docs/superpowers/specs/`. No slice is committed until its predecessors' Definition of Done is met.

## Hard rules for agents

- **Do not skip ahead.** If you are asked to do work that belongs to a future slice (per `roadmap.md`), surface that conflict before writing code.
- **Honor the locked cross-slice decisions** (AD-1 … AD-9 in `roadmap.md`). If a request requires breaking one, raise it explicitly — do not silently override.
- **Sample data is synthetic + small TCIA only.** Never download or commit real patient data, even if asked. Public de-identified data only.
- **Update `docs/status.md`** at the end of any meaningful work session.
- **Update `docs/roadmap.md`** when a slice's `status` changes.
- **Frozen docs stay frozen.** `docs/prd/2026-05-05-original-prd.md` is a historical anchor, not a working doc.
- **Slice specs are immutable once approved.** If the design needs to change, write a new spec that supersedes the old one; don't edit the old one in place.

## Key tooling decisions (locked)

- Python: `uv` + `pyproject.toml` (no pip, no poetry).
- JS: `npm` + Vite (no pnpm workspaces, no Turborepo).
- DB migrations: Alembic from day 1.
- Integration tests: `testcontainers`.
- E2E: Playwright.
- CI: GitHub Actions.

See `docs/roadmap.md` "Locked decisions" section for the full list.

## Commit conventions

- Conventional-style: `docs:`, `feat:`, `fix:`, `chore:`, `test:`, `refactor:`.
- One logical change per commit.
- Commit messages reference the slice when relevant (e.g., "feat(slice-1): add OrthancClient").

## What's specifically *not* in this project

- Real patient data, ever.
- HIPAA / FDA / clinical compliance claims.
- Real MRI hardware integration.
- Real cloud deployment in early slices (simulated locally with MinIO until a late slice).
- Multi-tenant enterprise auth.

If a request asks for any of the above, push back before implementing.
