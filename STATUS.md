# Status: LeadRelay
Updated: 2026-11-04 by /handoff

## Where we are
Step 0 done: project scaffold committed (b029f7c). The requirements doc has been explained to the user
(beginner walkthrough + abbreviation glossary). Project steps are proposed but NOT yet agreed;
the CLAUDE.md plan table still has only Step 0.

## Done this session
- Scaffold: CLAUDE.md, STATUS.md, README.md, docs/decisions.md, .gitignore, git init (b029f7c).
- Requirements .docx moved to `docs/00_requirements/`; plain-text copy `requirements.txt` added.
- Explained the requirements doc in chat (not saved to a file).
- Tested the lookup bucket with curl: both sample lead_ids from the doc, a fake id, and a bucket
  listing all return HTTP 403 Access Denied (missing file and no permission look the same).

## Next actions
1. User answers the 3 check questions from the explanation (why the delay / SQS delay queue;
   which alert fields come from the lookup; why parallel leads don't collide).
2. User agrees on the proposed steps, then write them into the CLAUDE.md plan table and here:
   1 architecture + decisions · 2 local code + pytest (no AWS) · 3 infrastructure as code ·
   4 user deploys + curl end-to-end test · 5 real Close webhook via Azmat/Ninad ·
   6 hardening (retries, DLQ, logging, parallel test) · 7 README + diagram, demo video, teardown.
3. User decides: Slack or email; infrastructure tool (reuse globalpartners CDK `infra/` pattern?);
   create a GitHub repo (`gh repo create`)?

## Open items
- Branch `handoff-2026-11-04` (this handoff) not merged into main; no GitHub remote yet.
- Questions for Azmat/Ninad: does `dea-lead-owner` still hold files, and how soon after lead creation;
  behaviour when the owner file is missing after 10 min; Close signing key for `Close-Sig-Hash`
  verification; are duplicate alerts acceptable.
- User decisions pending: Slack vs email, IaC tool, bucket/folder names, enriched file name.

## Environment gotchas
- `dea-lead-owner` returns 403 for missing files (no ListBucket permission), not 404.

## Key facts to keep straight
- Lookup: `https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json` → lead_email, lead_owner, funnel.
- Raw file: `crm_event_{lead_id}.json` in the source folder; store the parsed webhook body
  (`subscription_id` + `event`), not the API Gateway wrapper. Webhook `body` arrives as a JSON string.
- Owner lookup only AFTER the 10-minute delay (SQS delay queue fed by S3 event notification).
- Alert fields: Name, Lead ID, Created Date, Label from the CRM event; Email, Lead Owner, Funnel from the lookup.
- Only handle `action = "created"` lead events; code must be idempotent (Close/SQS may deliver twice).
- User preference: spell out every abbreviation (now in ~/.claude/CLAUDE.md).
