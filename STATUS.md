# Status: LeadRelay
Updated: 2026-11-14 (project complete)

## Where we are
All steps 0-8 done. The AWS stack is destroyed; the repo is the final record.
Tutorial book (local only): ~/Documents/DataEngineerBootcamp/Books/LeadRelay (open LeadRelay_book.html).

## Done
- Steps 0-5: design (SME approved), local code + tests, Terraform, deploy, real Close webhook.
- Step 6: Close key refresh on failed signature (60 s limit), DLQ alarm -> SNS email, parallel tests. 111 tests.
- Step 7: README (diagram, deploy, operate, teardown), final demo deck + video, `scripts/trace_lead.py`,
  `terraform destroy` (30 resources) verified: state empty, no leadrelay bucket or Lambdas.
- Step 8: book with 17 chapters, 16 labs (`bash run_all_labs.sh`: 16 passed), speaker notes for both videos.

## Next actions
1. Rebuild by hand from the book: Chapter 16 (local) then Chapter 17 (cloud), in
   ~/Documents/DataEngineerBootcamp/Practice/LeadRelay-rebuild.

## Open items
- SMEs: delete the Close webhook subscription (requested in the final message); answer on rare duplicate alerts.

## Key facts to keep straight
- Book and rebuild folders are local only; never push them to GitHub.
- Re-deploying needs: `infra/terraform.tfvars` (alarm_email), then apply, confirm SNS email, set both SSM secrets,
  and a new Close subscription (new URL, new signature_key).
