# Status: LeadRelay
Updated: 2026-11-14 by /handoff

## Where we are
Step 6 (hardening) code done and Step 7 README done, on branch `step6-hardening` (PR #6, open, NOT applied yet).
Final demo deck with speaker notes published: https://claude.ai/artifact/VzswHsZxHVniRdcXToSxzy (13 slides).
Remaining: merge PR #6, `terraform apply`, record demo video, teardown, then Step 8 book.

## Done this session
- PR #5 (handoff notes) merged.
- 6a `30a5806`: receiver re-reads the Close key from SSM on a failed signature check (max once per 60 s per
  Lambda environment, `SecretStore.refresh`), then re-checks. Test fails on old code, passes on new.
- 6b `3231808`: `infra/alarms.tf`: CloudWatch alarm `leadrelay-dlq-not-empty` → SNS topic `leadrelay-alarms` → email.
  Variable `alarm_email` set in git-ignored `infra/terraform.tfvars` (user's account email; `*.tfvars` now ignored).
- 6c `03ceeb4`: `tests/test_parallel.py`: 20 leads at once → 20 correct files/alerts; 10 racing copies of one lead
  → 1 alert (with the marker guard disabled the test sees 10, so it is real). `FakeHttpServer.responder` added.
- 7 `7cb9e3d`: README: mermaid architecture diagram, deploy, test, operate, teardown; architecture.md notes for Step 6.
- pytest: 111 passed. `terraform plan`: 3 to add (alarm, SNS topic, subscription), 2 to change (both Lambdas;
  receiver drops `KEY_REFRESH`), 0 to destroy.
- Real traffic snapshot 15:17 UTC: source 92, target 76, alerts_sent 76, owner_found 75 + 1 UNASSIGNED, DLQ 0.
- Demo deck "LeadRelay Final Demo" (artifact slug ead4aaf6-a110-4a07-9bb6-b858580a83e6): notes are the video
  script with [ON SCREEN] cues and exact commands; results slide numbers = the 15:17 snapshot.

## Next actions
1. User reviews and merges PR #6, then: `git switch main && git pull`.
2. User applies: `cd infra && terraform apply` (expect 3 add, 2 change, 0 destroy), then clicks the
   "AWS Notification - Subscription Confirmation" email link.
3. Before recording: refresh results-slide numbers with the commands in that slide's notes; record the demo video.
4. Teardown (user runs): `cd infra && terraform destroy`; ask Azmat/Ninad to delete the Close webhook subscription.
   Then mark Steps 6-7 Done in CLAUDE.md.
5. Step 8: local-only tutorial book in `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`.

## Open items
- PR #6 (`step6-hardening`) open; not applied to AWS yet.
- ~832 events rejected 11:50-14:51 UTC (old key): Close retries up to 72 h; ask Azmat/Ninad to confirm subscription active.
- Still open with the SME: are rare duplicate alerts acceptable (architecture.md section 4).
- Optional, offered not requested: AWS Budget alert.

## Environment gotchas
- Until PR #6 is applied, the deployed receiver still caches the SSM key forever: after changing a secret, force
  new environments (any config change). Slack URL changes still need that even after apply (only the Close key auto-refreshes).
- `terraform plan` shows `KEY_REFRESH` being removed from the receiver: expected, harmless.
- `scripts/send_test_lead.py` signs with the TEST key in `.env` → now gets 401 (correct).
- `dea-lead-owner` returns 403 for missing files (no ListBucket permission), not 404; owner files live only one day.
- Stacked PRs: deleting a base branch on merge CLOSES the dependent PR. Retarget first: `gh pr edit <n> --base main`.
- Terraform state is local (`infra/terraform.tfstate`, git-ignored): don't delete it while the stack is deployed.
- Run commands from the project root with `.venv/bin/python`; tests: `.venv/bin/python -m pytest`.
  One-off Python importing the package needs `PYTHONPATH=src:tests`.
- Secret entry: `read -rs` silently accepts an empty line; use the guarded form that prints the length first.

## Key facts to keep straight
- Webhook: `https://0coi22ofrh.execute-api.us-east-1.amazonaws.com/crm`; logs `/aws/lambda/leadrelay-receiver`, `/aws/lambda/leadrelay-processor`.
- Lookup: `https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json` → lead_email, lead_owner, funnel.
- Raw file `source/crm_event_{lead_id}.json` stores the parsed webhook body (`subscription_id` + `event`).
- Owner lookup only AFTER the 10-minute delay (SQS delay 600 s; retries every 300 s; 6 tries then UNASSIGNED; DLQ after 10).
- Alert fields: Name, Lead ID, Created Date, Label (CRM event); Email, Lead Owner, Funnel (lookup).
- Only `lead` + `action = "created"` events; idempotent via `alerts_sent/{lead_id}` conditional-write marker.
- Real Close traffic is steady (~5 leads/min): don't send test leads expecting a quiet log.
- `terraform destroy` deletes the bucket WITH all lead data (`force_destroy = true`).
- Secrets only in SSM / `.env`, never in git, chat or logs. User runs all create/change/delete cloud commands.
- Branches in this folder (no worktree folders); spell out abbreviations.
