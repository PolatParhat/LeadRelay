# Decisions and change log

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-11-10 | Build in 7 steps (architecture → local code+tests → IaC → deploy+curl test → real Close webhook → hardening → README/demo/teardown) | Local tests first so most work needs no AWS; real webhook only once the system works |

## Change log

- 2026-11-03: Project scaffold created; requirements doc moved to `docs/00_requirements/`.
- 2026-11-04:
  - Added `docs/00_requirements/requirements.txt` (plain-text copy of the .docx) for fast reading.
  - Requirements explained to the user; project steps proposed (not yet agreed).
  - Lookup bucket `dea-lead-owner` tested with curl: sample lead_ids return HTTP 403.
  - Workflow: `/new-project` skill now always explains the requirements doc (with an abbreviation
    glossary) before proposing steps; global CLAUDE.md now requires spelling out abbreviations.
- 2026-11-10:
  - Full requirements walkthrough in 6 parts (webhook, raw S3, delay queue, lookup, enrichment,
    alert) with local scratch demos; not saved to the repo.
  - `dea-lead-owner` re-checked: sample lead still HTTP 403.
  - User agreed the 7-step plan; added to the CLAUDE.md plan table.
