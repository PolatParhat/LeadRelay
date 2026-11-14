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
| 2026-11-11 | Add Step 8 (final): tutorial book like WistiaVideoAnalytics, at `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`, kept local only (never in Git); hand-typed rebuild in `~/Documents/DataEngineerBootcamp/Practice/LeadRelay-rebuild/` | User decision: finish the project first, then learn every tool from the book and rebuild by hand |
| 2026-11-12 | Terraform: local state (git-ignored); AWS provider ~> 6.0; Lambdas python3.13 arm64, one shared zip of src/, JSON log format; secrets created as write-only `value_wo` placeholders (`CHANGE_ME`), real values set by the user with the AWS CLI; processor role has `s3:ListBucket` so missing markers return 404 not 403; API stage throttled 20 rps / burst 50 with access logs | Single user and environment; secrets never in state or git; ListBucket needed for `read_marker()` to work on real S3 |
| 2026-11-12 | Deploy (terraform apply) before SME approval | User's call: idle cost about zero, `terraform destroy` removes everything, SME changes can be applied in place |
| 2026-11-12 | **SME approved the architecture.** Owner files live one day in `dea-lead-owner` (old samples 403); signature_key to be shared by the SME; Slack alerts go to our own test channel | SME review of the deck, video and docs |
| 2026-11-14 | Step 4 marked done after the real-AWS missing-owner test; the owner-found path is tested in Step 5 | It needs a real Close lead whose owner file exists (files live one day) |
| 2026-11-14 | Step 5 done with the real Close subscription; Step 6 adds a signature-key refresh (re-read from SSM on a failed check, or a cache TTL) | Warm Lambdas kept the old cached key after the SSM update and rejected real events until a config change forced new environments |
| 2026-11-14 | Step 6 hardening: (a) re-read the Close key from SSM on a failed signature check, rate-limited to once per 60 s per Lambda (chosen over a cache TTL); (b) CloudWatch DLQ alarm → SNS email, address in git-ignored `infra/terraform.tfvars`; (c) parallel tests in moto with threads, not a live 20-lead burst | (a) fixes rotation with no extra SSM calls on the happy path and caps cost of fake requests; (b) nobody noticed DLQ messages before; (c) a live burst would post 20 fake Slack alerts into real traffic |
| 2026-11-14 | Final demo deck (13 slides, speaker notes = video script) published as an artifact like the design deck | User asked for speaker notes to wrap up |

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
  - Step 8 (tutorial book) added as the final step.
- 2026-11-12:
  - Step 2 done (8 modules, 104 tests, local demo); PR #3.
  - Step 3 Terraform written (27 resources; validate and plan clean; not applied); PR #4.
  - Deployed (27 resources). Real AWS check: the S3 test event went through notification → 10 min delay → processor, ignored as designed.
  - SME approved the architecture; open questions 1, 2, 4 answered (architecture.md section 7).
  - PR #2 and PR #4 merged (PR #3 closed when its base branch was deleted; retargeted #4 to main).
- 2026-11-13:
  - Real AWS end-to-end test passed: receiver 200/401/ignored; test lead retried 5 times every 5 min after the 10-min delay, then UNASSIGNED alert sent to Slack; enriched record and sent marker in S3; DLQ empty. Step 4 done.
- 2026-11-14:
  - Real Close signature_key stored in SSM (version 3). ~832 events rejected (11:50-14:51 UTC) because the old test key was cached in warm receiver Lambdas; fixed by adding env var `KEY_REFRESH` (forces new environments). 0 rejections after.
  - Real leads verified: 72 saved in ~14 min, first 24 processed with owner found on try 1, enriched, alerted on Slack; DLQ 0. Step 5 done.
- 2026-11-14 (later):
  - PR #5 merged. Step 6 (a/b/c) and Step 7 README on branch `step6-hardening`, PR #6 (not applied).
  - pytest 111 passed; `terraform plan` 3 add / 2 change / 0 destroy.
  - Real traffic 15:17 UTC: 92 received, 76 enriched + alerted (75 owner found, 1 UNASSIGNED), DLQ 0.
  - Final demo deck published: https://claude.ai/artifact/VzswHsZxHVniRdcXToSxzy
- 2026-11-14 (final):
  - Step 6 applied (alarm live, receiver key refresh deployed). PR #7: `scripts/trace_lead.py` (follow one lead,
    read-only) after the first demo draft tailed whole logs and was hard to follow.
  - Final demo video recorded; message to the SMEs drafted (asks them to delete the Close subscription).
  - Teardown: `terraform destroy` (30 resources); verified state empty, no leadrelay bucket or Lambdas.
  - Step 8: tutorial book at ~/Documents/DataEngineerBootcamp/Books/LeadRelay (17 chapters, 16 labs all
    passing, HTML build, both speaker-note scripts); local only, never in Git.

