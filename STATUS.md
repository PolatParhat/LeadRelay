# Status: LeadRelay
Updated: 2026-11-11

## Where we are
Step 2 (local code + pytest, no AWS) IN PROGRESS on branch `step2-local-code` (in this folder),
started before SME approval at the user's request. Video + deck sent to the SMEs; approval pending.
- `docs/architecture.md` on PR #2 (branch `step1-architecture`): do NOT merge until the SMEs approve.
- Design deck: https://claude.ai/artifact/JTCcBTgzPNRngHbBw2rUH1 (18 slides).
- Done in Step 2: dev setup + all 8 modules (signature, storage, lookup, enrich, alert, config, receiver,
  processor) with tests: 104 passed. Receiver verified on the requirements' sample webhook.
  `scripts/demo_local.py` runs leads end to end locally (found owner, duplicate, UNASSIGNED, forged).

## Next actions
1. User reviews the Step 2 PR (based on PR #2's branch; merge after PR #2).
2. Then Step 3: Terraform (infra/).
3. When SME feedback arrives: apply changes, record approval in docs/decisions.md, user merges PR #2.
4. Send Azmat/Ninad the open questions (deck slide 18 / architecture.md section 7).
5. FINAL (Step 8, after teardown): local-only tutorial book in `~/Documents/DataEngineerBootcamp/Books/LeadRelay/`,
   modelled on `Books/WistiaVideoAnalytics/` (chapters per tool, labs, walkthrough, rebuild guide).

## Open items
- Repo: github.com/PolatParhat/LeadRelay (public, default branch `main`).
- Questions for Azmat/Ninad: does `dea-lead-owner` still hold files, and how soon after lead creation;
  behaviour when the owner file is missing after 10 min; Close signing key for `Close-Sig-Hash`
  verification; are duplicate alerts acceptable; which Slack channel.

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
