# LeadRelay: Real-Time CRM Lead Processing and Notification System

Captures new leads from Close CRM webhooks, waits 10 minutes for the CRM to assign a lead owner,
enriches each lead with its owner and stores it in Amazon S3, and alerts the sales team on Slack.

**Why "LeadRelay"?** In a relay race each runner hands the baton to the next and nobody drops it.
LeadRelay does the same with every new lead: Close creates it, we capture it, hold it 10 minutes,
add its owner, and hand it to the sales team on Slack, without dropping any lead along the way.

## Documents

| Step | Document |
|---|---|
| 0 | [Requirements](docs/00_requirements/) |
| 1 | [Architecture](docs/architecture.md) |
| – | [Decisions and change log](docs/decisions.md) |

## Run it locally (no AWS needed)

Requires Python 3.13.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest              # all unit tests (S3/SSM faked with moto, HTTP faked locally)
.venv/bin/python scripts/demo_local.py  # one lead end to end: receiver -> processor -> Slack message
```

## Code

| Module (`src/leadrelay/`) | Job |
|---|---|
| `receiver.py` | Lambda: Close webhook in, verify, filter, save to `source/` |
| `processor.py` | Lambda: delayed SQS message in, lookup, `target/`, alert once |
| `signature.py` | Close HMAC-SHA256 signature check |
| `storage.py` | S3 key names, JSON read/write, alert marker (conditional writes) |
| `lookup.py` | Owner lookup over HTTPS with timeout and backoff |
| `enrich.py` | Merge CRM event + owner into the enriched record |
| `alert.py` | Slack message format and send with retries |
| `config.py` | Settings from environment variables, secrets from SSM Parameter Store |

Deployment instructions (Terraform) will be added in Step 3.
