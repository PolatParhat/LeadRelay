# Decisions and change log

## Decisions

| Date | Decision | Reason |
|---|---|---|

## Change log

- 2026-11-03: Project scaffold created; requirements doc moved to `docs/00_requirements/`.
- 2026-11-04:
  - Added `docs/00_requirements/requirements.txt` (plain-text copy of the .docx) for fast reading.
  - Requirements explained to the user; project steps proposed (not yet agreed).
  - Lookup bucket `dea-lead-owner` tested with curl: sample lead_ids return HTTP 403.
  - Workflow: `/new-project` skill now always explains the requirements doc (with an abbreviation
    glossary) before proposing steps; global CLAUDE.md now requires spelling out abbreviations.
