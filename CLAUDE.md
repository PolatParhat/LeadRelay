# LeadRelay: Real-Time CRM Lead Processing and Notification System

Learning project built to production standard, following
`docs/00_requirements/Real-Time CRM Lead Processing and Notification System.docx`
(plain-text copy: `docs/00_requirements/requirements.txt`). The requirements doc is the source of truth.

State: STATUS.md · History: docs/decisions.md (read it before re-deciding anything)

## Project context

- **Goal:** Capture new leads from Close CRM webhooks in real time, wait 10 minutes for the CRM to
  assign an owner, enrich each lead with its owner from a lookup bucket, store it in S3, and alert the
  sales team on Slack or email.
- **Constraints (from requirements):** AWS services (webhook receiver URL, S3, SQS delay for the
  10-minute wait, S3 event notifications); Close CRM webhook subscription (Azmat or Ninad create it once
  our URL exists); lookup from the public bucket `dea-lead-owner` (`{lead_id}.json`, us-east-1);
  notification via Slack incoming webhook or email.
- **Deliverables:** README with instructions and architecture diagram; modular code (ingestion,
  lookup, S3 writing); error handling, retries, logging.

## Plan status

| Step | Description | Status |
|---|---|---|
| 0 | Project scaffold | Done |
| 1 | Architecture + decisions (Slack/email, IaC tool, bucket/folder/file names, missing-owner policy) | Awaiting SME approval (docs/architecture.md + design deck + video) |
| 2 | Local code + pytest, no AWS (receiver, lookup, enrich, alert modules) | Done (PR #3) |
| 3 | Infrastructure as code (bucket, queues + DLQ, Lambdas, API Gateway, notification) | Done (PR #4, not applied) |
| 4 | User deploys; end-to-end test with curl | In progress |
| 5 | Real Close webhook subscription via Azmat/Ninad | To do |
| 6 | Hardening: retries, DLQ, logging, parallel-leads test | To do |
| 7 | README + architecture diagram, demo video, teardown | To do |
| 8 | FINAL: local-only tutorial book (every tool from a data-engineering view, examples + runnable labs, project walkthrough, rebuild guide), same format as WistiaVideoAnalytics | To do (after teardown) |

## Key facts (a fresh session must not get these wrong)

- Bucket `leadrelay-{account_id}`. Raw: `source/crm_event_{lead_id}.json`. Enriched: `target/enriched_{lead_id}.json`.
  Alert-sent markers: `alerts_sent/{lead_id}`. Alerts go to Slack (incoming webhook). Infrastructure: Terraform.
- Lookup URL: `https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json`.
- Owner lookup must happen only **after** the 10-minute delay, never before.
- The alert must include: Name (display_name), Lead ID, Created Date, Label (status_label) from the CRM
  event, and Email (lead_email), Lead Owner, Funnel from the lookup.
- Must handle many leads in parallel without race conditions (one file per lead_id).
- Region us-east-1. The user runs commands that create, change or delete AWS resources; Claude explains them.

## Repo layout

```
LeadRelay/
├── CLAUDE.md · STATUS.md · README.md    rules · current state · index
├── docs/00_requirements/                requirements doc (+ text copy)
├── docs/architecture.md                 flow diagram, components, settings, idempotency
└── docs/decisions.md                    decisions and change log
src/leadrelay/                           Python package (Lambda code)
tests/                                   pytest tests (no AWS)
pyproject.toml · requirements-dev.txt    pytest settings · dev dependencies
```

## Conventions

- Secrets (Slack webhook URL, Close signing key, AWS keys) live in `.env` or AWS, never in git.
- Code changes go on a branch in this same folder (no separate worktree folders) and reach `main` through a PR the user reviews.
- Gate: PR #2 is not merged until the user's SMEs approve the architecture. Steps 2-4 (code,
  Terraform, first deploy) went ahead before approval at the user's request; SME changes are applied
  in place afterwards.
