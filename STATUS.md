# Status: LeadRelay
Updated: 2026-11-10

## Where we are
Step 0 done. The 7-step plan is AGREED and recorded in the CLAUDE.md plan table.
Step 1 (architecture + decisions) is next. The requirements were walked through in detail in
6 parts (webhook, raw S3, delay queue, lookup, enrichment, alert).

## Done this session
- 6-part requirements walkthrough with local scratch demos (not in the repo).
- Re-checked `dea-lead-owner`: sample lead still returns HTTP 403.
- User agreed the 7 steps; written into CLAUDE.md and docs/decisions.md.

## Next actions
1. Step 1 (Slack, Terraform, names, missing-owner = retry-then-alert, public GitHub repo chosen 2026-11-11): all decisions made; write the architecture doc.
2. Send Azmat/Ninad the open questions below.
3. Write the architecture (diagram + components) into docs once decisions are made.

## Open items
- Branch `handoff-2026-11-04` (this handoff) not merged into main; remote is github.com/PolatParhat/LeadRelay (public), `main` not pushed yet.
- Questions for Azmat/Ninad: does `dea-lead-owner` still hold files, and how soon after lead creation;
  behaviour when the owner file is missing after 10 min; Close signing key for `Close-Sig-Hash`
  verification; are duplicate alerts acceptable.

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
