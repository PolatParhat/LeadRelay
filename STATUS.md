# Status: LeadRelay
Updated: 2026-11-14 by /handoff

## Where we are
Steps 0-5 done. The real Close webhook subscription is live and the deployed stack processes real leads:
signature check → S3 → 10-minute delay → owner found on try 1 → enriched record → Slack alert.
Next: Step 6 (hardening), no SME input needed.

## Done this session (2026-11-14, no code changes)
- Real Close signature_key stored in SSM `/leadrelay/close_signature_key` (version 3, 64 chars, 14:49:20 UTC).
- Close had been sending since at least 11:50 UTC; ~832 events got 401 "bad signature" (test key in place).
- Even after the SSM update, warm receiver Lambdas kept the cached OLD key (steady traffic = never idle).
  Fixed by forcing new environments: user added env var `KEY_REFRESH=2026-11-14` with
  `aws lambda update-function-configuration` (14:51:10 UTC). 0 rejections after that.
- Verified 15:05 UTC: 72 leads saved in ~14 min (no repeated lead_id), 24 processed so far: 24 owner lookups,
  24 enriched records, 24 Slack alerts, 0 retries/warnings; DLQ 0. Example: owner "Ninad Magdum",
  funnel "New Data Career Accelerator - v1 - Paid Traffic Only", owner_found true. User saw alerts in Slack.

## Next actions
1. Step 6 on a new branch: `git switch main && git pull && git switch -c step6-hardening`.
   (a) Signature key refresh: re-read the key from SSM when a signature check fails (or cache with a TTL),
       so key rotation never needs a manual Lambda refresh; add tests.
   (b) CloudWatch alarm on DLQ messages > 0 with email (SNS: Simple Notification Service) notification.
   (c) Parallel test: 20 leads at once → 20 source/target files and 20 alerts, no mix-ups.
   Then `terraform plan` (will also remove the `KEY_REFRESH` drift) and the user applies.
2. Step 7: README deploy section + architecture diagram, demo video, `terraform destroy` (user runs it).
3. Step 8 (after teardown): local-only tutorial book in `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`.

## Open items
- PR #5 (`handoff-2026-11-14`, handoff notes only) open; user merges.
- The ~832 rejected events (11:50-14:51 UTC): Close retries non-2xx for up to 72 h, so late leads/alerts may
  still arrive; idempotency marker prevents duplicates. Ask Azmat/Ninad to confirm the subscription is active.
- Still open with the SME: are rare duplicate alerts acceptable (architecture.md section 4).
- Optional, offered not requested: AWS Budget alert.
- README still says "Deployment instructions (Terraform) will be added in Step 3" (fix in Step 7).

## Environment gotchas
- Lambdas cache SSM secrets for the life of a warm environment. After changing a secret in SSM, force new
  environments (any config change, e.g. an env var) until Step 6 (a) is done.
- `terraform plan` shows `KEY_REFRESH` being removed from the receiver: expected drift, harmless to apply.
- `scripts/send_test_lead.py` signs with the TEST key in `.env` → now gets 401 (correct).
- `dea-lead-owner` returns 403 for missing files (no ListBucket permission), not 404; owner files live only one day.
- Stacked PRs: deleting a base branch on merge CLOSES the dependent PR (no auto-retarget). Retarget first:
  `gh pr edit <n> --base main`.
- Terraform state is local (`infra/terraform.tfstate`, git-ignored): don't delete it while the stack is deployed.
- Run commands from the project root with `.venv/bin/python`; tests: `.venv/bin/python -m pytest`.
- Secret entry: `read -rs` silently accepts an empty line; use the guarded form that prints the length first.

## Key facts to keep straight
- Webhook: `https://0coi22ofrh.execute-api.us-east-1.amazonaws.com/crm`; logs `/aws/lambda/leadrelay-receiver`, `/aws/lambda/leadrelay-processor`.
- Lookup: `https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json` → lead_email, lead_owner, funnel.
- Raw file `source/crm_event_{lead_id}.json` stores the parsed webhook body (`subscription_id` + `event`).
- Owner lookup only AFTER the 10-minute delay (SQS delay 600 s; retries every 300 s; 6 tries then UNASSIGNED; DLQ after 10).
- Alert fields: Name, Lead ID, Created Date, Label (CRM event); Email, Lead Owner, Funnel (lookup).
- Only `lead` + `action = "created"` events; idempotent via `alerts_sent/{lead_id}` conditional-write marker.
- Real Close traffic is steady (~5 leads/min): don't send test leads expecting a quiet log.
- Secrets only in SSM / `.env`, never in git, chat or logs. User runs all create/change/delete cloud commands.
- Branches in this folder (no worktree folders); spell out abbreviations.
