# Status: LeadRelay
Updated: 2026-11-12

## Where we are
**SME approved the architecture (2026-11-12).** Steps 0-3 done; Step 4 (deploy + test) in progress.
- Deployed with `terraform apply` from branch `step3-terraform`: 27 resources, webhook URL
  `https://0coi22ofrh.execute-api.us-east-1.amazonaws.com/crm`. Secrets set: test signature key
  (also in `.env` as TEST_SIGNATURE_KEY) and Slack webhook (own test channel).
- Verified in AWS: S3 test event → 10 min delay → processor → "S3 test event ignored".
- PRs: #2 (Step 1 docs), #3 (Step 2 code), #4 (Step 3 Terraform + Step 4 script). Merge in that order.

## Next actions
1. User merges PR #2, then #3, then #4 (each retargets to main after the previous merge).
2. Send a signed test lead: `.venv/bin/python scripts/send_test_lead.py` (+ `--bad-signature`, `--action updated`);
   expect UNASSIGNED alert at ~35 min unless the lead_id has a fresh owner file.
3. Send the webhook URL to the SME for the Close subscription; when the real signature_key arrives, store it
   with the `set_secrets` command from `terraform output` (Step 5).
4. FINAL (Step 8, after teardown): local-only tutorial book in `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`,
   modelled on `Books/WistiaVideoAnalytics/` (chapters per tool, labs, walkthrough, rebuild guide).

## Open items
- Repo: github.com/PolatParhat/LeadRelay (public, default branch `main`).
- Still open with the SME: are rare duplicate alerts acceptable (architecture.md section 4).

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
