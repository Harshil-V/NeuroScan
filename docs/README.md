# NeuroScan Workstation — Docs Index

If you're new (or returning) to the project, read in this order:

1. **[`status.md`](./status.md)** — what's happening right now
2. **[`project-overview.md`](./project-overview.md)** — what this project is and why
3. **[`roadmap.md`](./roadmap.md)** — slice list and status
4. **[`superpowers/specs/`](./superpowers/specs/)** — detailed design spec for whichever slice is active
5. **[`prd/2026-05-05-original-prd.md`](./prd/2026-05-05-original-prd.md)** — frozen original brief, for historical context

## Doc roles at a glance

| Doc | Purpose | Update cadence |
|---|---|---|
| `status.md` | Current slice, what's next | Every working session |
| `project-overview.md` | What & why, full-platform vision | Rarely (only when scope shifts) |
| `roadmap.md` | Phased slice plan with status | When a slice opens or closes |
| `superpowers/specs/<date>-slice-N-*.md` | Detailed design for one slice | Frozen once approved; supersede by writing a new spec |
| `prd/2026-05-05-original-prd.md` | Original brief | Never — historical anchor |

## Naming conventions

- Slice specs live in `docs/superpowers/specs/` and follow `YYYY-MM-DD-slice-N-<short-topic>-design.md`.
- Implementation plans (later) live in `docs/superpowers/plans/` and follow the same date prefix.
- QA documents (when introduced) live in `docs/qa/`.
