# Status: LeadRelay
Updated: 2026-11-11

## Where we are
Step 1 deliverables ready, AWAITING SME APPROVAL. Do not start Step 2 until the user says the SMEs approved.
- `docs/architecture.md` (PR #2, branch `step1-architecture`).
- Design deck for the video and SME review: https://claude.ai/artifact/JTCcBTgzPNRngHbBw2rUH1
  (17 slides, speaker notes = video script; private to the user until they share it).

## Done this session
- 6-part requirements walkthrough; 7-step plan agreed.
- Decisions: Slack, Terraform, names, missing-owner = retry then UNASSIGNED, public GitHub repo.
- GitHub repo created (public), PR #1 merged, default branch `main`.
- Architecture doc written; Close signature scheme and S3 conditional write verified.

## Next actions
1. User reviews the deck and PR #2, records the video walkthrough, sends both to the SMEs.
2. Apply any SME feedback to the deck and docs/architecture.md; record the approval in docs/decisions.md.
3. After approval: merge PR #2, then Step 2 (local code + pytest).
4. Send Azmat/Ninad the open questions (deck slide 17 / architecture.md section 7).

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
