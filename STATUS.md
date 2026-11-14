# Status: LeadRelay
Updated: 2026-11-14 by /handoff

## Where we are
Steps 0-4 done. Everything is merged to `main` (PR #2 and PR #4; PR #3 closed, its commits went in via #4).
The deployed stack passed an end-to-end test on real AWS (missing-owner path → UNASSIGNED alert).
Next: Step 5 (real Close webhook, waits on the SME); Step 6 (hardening) needs no SME input.

## Done this session
- Step 2 code (8 modules, 104 tests pass), Step 3 Terraform (27 resources), `scripts/send_test_lead.py`; merged (e748f67).
- Deployed: webhook `https://0coi22ofrh.execute-api.us-east-1.amazonaws.com/crm`; `terraform plan` shows no changes.
- Secrets set in SSM: signature key = test key (version 2, also `.env` TEST_SIGNATURE_KEY), Slack URL (version 3, own channel).
- Real AWS test (2026-11-13): receiver 200 saved / 401 forged / 200 ignored (action updated).
  Lead `lead_testa1f6237465a4` saved 00:48:44 UTC; tries at 00:58:47, 01:03:46, 01:08:46, 01:13:46, 01:18:46
  ("owner not there yet, retry later"); try 6 at 01:23:46 → WARNING UNASSIGNED → enriched record → Slack alert sent.
  S3 holds source/, target/ (owner fields null, owner_found false) and alerts_sent/ marker {"status": "sent"}; DLQ = 0.

## Next actions
1. Step 5: user sends the webhook URL to the SME; SME creates the Close subscription and shares signature_key.
   Store it with the `set_secrets` command: `cd infra && terraform output -raw set_secrets`. Then test with
   recent real leads (owner-found path, alert at the 10-minute mark).
2. Step 6 hardening on a new branch: `git switch main && git pull && git switch -c step6-hardening`.
   (a) CloudWatch alarm on DLQ messages > 0 with email (SNS) notification; (b) parallel test: 20 leads at once
   → 20 source/target files and 20 alerts, no mix-ups.
3. Step 7: README deploy section + architecture diagram, demo video, `terraform destroy` (user runs it).
4. Step 8 (after teardown): local-only tutorial book in `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`.

## Open items
- Still open with the SME: are rare duplicate alerts acceptable (architecture.md section 4).
- Optional, offered not requested: AWS Budget alert.
- README still says "Deployment instructions (Terraform) will be added in Step 3" (fix in Step 7).

## Environment gotchas
- `dea-lead-owner` returns 403 for missing files (no ListBucket permission), not 404; owner files live only one day.
- Stacked PRs: deleting a base branch on merge CLOSES the dependent PR (no auto-retarget). Retarget first:
  `gh pr edit <n> --base main`.
- Terraform state is local (`infra/terraform.tfstate`, git-ignored): don't delete it while the stack is deployed.
- Run commands from the project root with `.venv/bin/python`; tests: `.venv/bin/python -m pytest`.

## Key facts to keep straight
- Lookup: `https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json` → lead_email, lead_owner, funnel.
- Raw file `source/crm_event_{lead_id}.json` stores the parsed webhook body (`subscription_id` + `event`).
- Owner lookup only AFTER the 10-minute delay (SQS delay 600 s; retries every 300 s; 6 tries then UNASSIGNED; DLQ after 10).
- Alert fields: Name, Lead ID, Created Date, Label (CRM event); Email, Lead Owner, Funnel (lookup).
- Only `lead` + `action = "created"` events; idempotent via `alerts_sent/{lead_id}` conditional-write marker.
- Secrets only in SSM / `.env`, never in git or logs. User runs all create/change/delete cloud commands.
- Branches in this folder (no worktree folders); spell out abbreviations.
