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

Setup and run instructions will be added as the project is built.
