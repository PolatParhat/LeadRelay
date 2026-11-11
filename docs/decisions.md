# Decisions and change log

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-11-10 | Build in 7 steps (architecture → local code+tests → IaC → deploy+curl test → real Close webhook → hardening → README/demo/teardown) | Local tests first so most work needs no AWS; real webhook only once the system works |
| 2026-11-11 | Alerts go to Slack via an incoming webhook (not email) | Simplest setup, the option the requirements link to, best for the demo; webhook URL kept in AWS Secrets Manager / `.env`, never in git |
| 2026-11-11 | Infrastructure as code with Terraform (not CDK) | User's choice: learn Terraform on this project; Terraform v1.15.8 already installed |
| 2026-11-11 | Names: bucket `leadrelay-{account_id}`; raw `source/crm_event_{lead_id}.json`; enriched `target/enriched_{lead_id}.json`; alert markers `alerts_sent/{lead_id}` | Account ID makes the bucket name globally unique; enriched name mirrors the raw one |
| 2026-11-11 | Missing owner after the delay: retry, then alert as UNASSIGNED (option C). Retry by letting the SQS message return (visibility timeout ~5 min, read `ApproximateReceiveCount`); after ~6 tries alert with `Lead Owner: UNASSIGNED` and log a WARNING. Real errors (Slack down, bad data) still go to the DLQ. Gap and try count are settings | Usually gets the owner, never drops a lead; tune numbers once Azmat/Ninad say how fast owners appear |
| 2026-11-11 | GitHub repo `PolatParhat/LeadRelay` is public | User's choice (portfolio); requirements doc with sample names/emails is visible, accepted by user |
| 2026-11-11 | Architecture (docs/architecture.md): API Gateway HTTP API (payload 1.0); secrets in SSM Parameter Store SecureString; SQS delay 600 s, visibility 300 s, DLQ after 10 tries; processor batch size 1, timeout 30 s; `OWNER_MAX_TRIES = 6`; alert marker claimed with S3 conditional write (`IfNoneMatch="*"`); runtime code uses standard library + boto3 only | HTTP API cheaper/simpler; Parameter Store free; batch size 1 keeps one lead's failure from retrying others; maxReceiveCount > 6 keeps "owner missing" out of the DLQ; conditional write makes the alert claim atomic; no dependencies means a plain zip |
| 2026-11-11 | Start Step 2 (local code + tests, no AWS) before SME approval arrives; PR #2 stays unmerged until approval | User expects approval; local code is cheap to change if the SMEs ask for changes. Nothing is deployed before approval |

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
- 2026-11-11:
  - Step 1 decisions made (Slack, Terraform, names, missing-owner policy, public repo); PR #1 merged.
  - `docs/architecture.md` written. Verified: Close signature scheme against Close docs (HMAC-SHA256 of
    timestamp + body, hex key; 2xx within 15 s; retries up to 72 h) and S3 conditional write with moto
    (second `IfNoneMatch="*"` put fails with PreconditionFailed).
  - Gate added: Step 2 starts only after the user's SMEs approve the architecture and implementation plan.
    Design deck (17 slides with speaker notes as the video script) published for the review.
  - Design deck now 18 slides (added "Why we named it LeadRelay"); video recorded and sent to the SMEs.
  - Step 2 started at user's request before approval (branch `step2-local-code`).
