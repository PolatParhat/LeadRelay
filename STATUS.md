# Status: LeadRelay
Updated: 2026-11-03 by /new-project

## Where we are
Step 0, project created. Requirements doc moved to `docs/00_requirements/`.
The project steps have not been agreed yet.

## Done this session
- Project scaffold: CLAUDE.md, STATUS.md, README.md, docs/decisions.md, .gitignore, git init.

## Next actions
1. Agree on the project steps from the requirements doc, then write them here and in the CLAUDE.md plan table.

## Open items
- Reuse another project's stack (for example the CDK `infra/` pattern from globalpartners)? Not decided.
- Slack or email for notifications? Not decided.
- Azmat or Ninad must create the Close webhook subscription once our endpoint URL exists.

## Environment gotchas
- (none yet)

## Key facts to keep straight
- Lookup bucket: `dea-lead-owner` (public, us-east-1), file `{lead_id}.json`.
- Raw file name: `crm_event_{lead_id}.json`. Delay: 10 minutes before the owner lookup.
