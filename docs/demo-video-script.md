# LeadRelay final demo: video script (speaker notes)

Slides: https://claude.ai/artifact/VzswHsZxHVniRdcXToSxzy (same notes are attached to each slide).
Lines starting with [ON SCREEN] are cues, not words to say. Commands run from the project root.

## Slide 1: LeadRelay

Hi, I'm Polat. A few days ago I showed you the architecture design for LeadRelay and you approved it. Today is the final demo: the system is built, deployed on AWS, and connected to the real Close CRM webhook, so everything you'll see runs on real leads.

Here's the plan for the next ten minutes or so. First a quick reminder of what LeadRelay does and how it's built. Then a live demo: a real lead arriving from Close, the files it creates in S3, and the Slack alert the sales team gets. After that, the numbers from real traffic, one incident we hit on go-live and how I fixed it so it can't happen again, and the tests that prove the system handles many leads in parallel. I'll finish with how to run and tear down the system, and what I learned.

## Slide 2: A new lead reaches the right salesperson, automatically

Quick reminder of the job. The sales team uses Close as their CRM, which stands for customer relationship management. When a new lead is created, they want to know right away who it is and which salesperson owns it.

The catch is that Close assigns the owner a few minutes after the lead is created, and the owner lives in a separate lookup bucket, dea-lead-owner. So the system does three things. One: capture every new lead from Close's webhook and store the raw event in S3. Two: wait 10 minutes, and only then look up the owner. Looking it up earlier would just find nothing. Three: send one Slack alert with the seven fields the requirements ask for: name, lead ID, created date and label from the CRM event; email, lead owner and funnel from the lookup.

And it has to work when many leads arrive at the same time, without mixing them up and without sending the same alert twice.

## Slide 3: Six AWS pieces, one file set per lead

Here's the architecture you approved, now running. I'll follow one lead from left to right.

Close sends a signed webhook to an API Gateway URL. The receiver Lambda checks the signature, so only Close can send us leads. It ignores anything that isn't a new lead, saves the raw event to S3 under source/, and answers within Close's 15-second limit.

Saving that file triggers an S3 event notification into an SQS queue, SQS being Simple Queue Service. The queue has a 600-second delay, so the message is invisible for 10 minutes. That delay is the one thing that guarantees the owner lookup never happens early.

After 10 minutes the processor Lambda gets the message. It looks up the owner in dea-lead-owner. If the owner file isn't there yet, the message comes back every 5 minutes, and on the sixth try we alert anyway, marked UNASSIGNED, so no lead is silently dropped. Then the processor writes the enriched record to target/, and sends the Slack alert exactly once, guarded by a marker file written with an S3 conditional write.

If something keeps failing, after 10 tries the message moves to a dead-letter queue, and a CloudWatch alarm, new since the design, emails me.

The key idea for parallelism: every lead has its own files, named by its lead ID, so two leads never write the same object. All of it is built with Terraform, and the secrets live in SSM Parameter Store, never in git.

## Slide 4: A real lead, from Close to Slack

Now the live part. Everything I'm about to show is real Close traffic, not test data. Close is sending us roughly five new leads a minute right now.

[ON SCREEN: terminal in the LeadRelay folder.]

First I'll tail the receiver Lambda's log for the last few minutes:

```bash
aws logs tail /aws/lambda/leadrelay-receiver --since 5m --region us-east-1
```

Every line is JSON. You can see "lead saved" lines, each with a lead ID and the step name "receive". You'll also see some "event ignored" lines: those are other Close events, such as lead updates, which we answer with 200 so Close doesn't retry, but don't store. What you should not see is any "bad signature" warning, because the real signing key is in place.

Then the processor log, which shows the other end of the 10-minute wait:

```bash
aws logs tail /aws/lambda/leadrelay-processor --since 15m --region us-east-1
```

Pick one lead ID and follow it: "owner lookup done" with owner_found true, then "enriched record saved", then "alert sent". Notice the timestamps: the processor line is about 10 minutes after the receiver saved that lead. That's the SQS delay doing its job.

## Slide 5: Three files per lead, all named by lead_id

Next, the files in S3.

[ON SCREEN: terminal.]

First I'll save the bucket name in a variable, then list the three folders:

```bash
B=$(terraform -chdir=infra output -raw bucket_name)
aws s3 ls s3://$B/source/ --region us-east-1 | tail -3
aws s3 ls s3://$B/target/ --region us-east-1 | tail -3
aws s3 ls s3://$B/alerts_sent/ --region us-east-1 | tail -3
```

source/ has the raw Close event for every lead we received, stored exactly as it arrived, so we can always replay it. target/ has the enriched record. alerts_sent/ has the marker that says this lead's alert already went out.

Now let's open one enriched record. I'll copy a lead ID from the target listing:

```bash
aws s3 cp s3://$B/target/enriched_PASTE_LEAD_ID.json - --region us-east-1 | python3 -m json.tool
```

Here are the seven alert fields in one flat record, plus owner_found, which tells us whether the owner came from the lookup or the lead was alerted as unassigned, and a pointer back to the source file.

Why one file per lead ID? Because then fifty leads in the same second are fifty different files. No two Lambdas ever write the same object, so there's nothing to race on. And if the same lead is processed twice, it just overwrites its own file with the same content.

## Slide 6: The alert the sales team sees

And here's what the sales team actually gets.

[ON SCREEN: switch to the Slack channel and scroll through the recent alerts.]

Each alert has the seven fields from the requirements, in that order. Name, lead ID, created date and label come from the Close event. Email, lead owner and funnel come from the owner lookup, done 10 minutes after the lead was created.

[ON SCREEN: point at one alert, then find the same lead ID in the enriched record from the previous step.]

This alert matches the enriched record I just opened in S3: same lead ID, same owner.

If the owner still isn't in the lookup bucket after the sixth try, about 35 minutes after the lead arrived, we don't drop the lead. The alert goes out with Lead Owner set to UNASSIGNED, so someone can pick it up by hand. You'll see one of those in the numbers on the next slide.

Every lead gets one alert, never two. Even if SQS delivers the same message twice, the alerts_sent marker stops the second copy.

## Slide 7: Every lead accounted for, nothing in the DLQ

Here are the numbers from real Close traffic. This snapshot is from November 14th at 15:17 UTC. [UPDATE these four numbers just before you record, with the commands below.]

92 leads received and saved to S3. 76 of them already enriched and alerted on Slack, each exactly once: there are 76 enriched records and 76 sent markers, the same count. 75 of those had their owner found by the lookup. One lead still had no owner after six tries, so it went out as UNASSIGNED, which is the policy you approved. And zero messages in the dead-letter queue: nothing failed.

The 16-lead gap between received and alerted isn't a backlog. Those leads are either still inside their 10-minute delay, or their owner file isn't in the lookup bucket yet, so they come back every 5 minutes, exactly as designed.

Commands to refresh the numbers:

```bash
B=$(terraform -chdir=infra output -raw bucket_name)
for p in source/ target/ alerts_sent/; do echo "$p $(aws s3 ls s3://$B/$p --region us-east-1 | wc -l)"; done
aws sqs get-queue-attributes --queue-url "$(terraform -chdir=infra output -raw dlq_url)" --attribute-names ApproximateNumberOfMessages --region us-east-1 --output text
```

The owner-found count comes from reading owner_found in the target records.

## Slide 8: A new key in SSM, an old key in memory

I want to be open about the one incident we had on go-live, because it led to the most useful hardening change.

Close started sending real leads at about 11:50 UTC. At that point our SSM parameter still held the test signing key I'd used for my own tests. So every real webhook failed the signature check and got a 401. That's the system doing its security job correctly, but it meant about 832 webhooks were rejected over three hours. Nothing bad was saved, and nothing was lost, because Close retries any failed delivery for up to 72 hours.

At 14:49 I stored the real key in SSM. And the rejections didn't stop. Here's why: to stay fast, each Lambda reads its secrets once when it starts and keeps them in memory. With five leads a minute, the Lambdas never went idle, so they never restarted, and kept using the old key.

The quick fix was to change a setting on the Lambda, which forces AWS to start fresh copies that read the new key. From 14:51, zero rejections.

But a manual restart every time a key changes isn't production quality. So that became the first hardening item, on the next slide.

## Slide 9: Three changes so it runs without me watching

Step 6 was hardening: three changes so the system runs without me watching it.

First, key rotation. When a signature check fails, the receiver now asks: maybe my copy of the key is out of date? It re-reads the key from SSM, and if the key changed, checks the signature again. There's a rate limit: each Lambda re-reads at most once a minute. Anyone on the internet can send us fake requests, and without the limit each one would cost an SSM call. With this change, the incident you just saw would have fixed itself within a minute of storing the new key.

Second, alerting. Before, if a lead ended up in the dead-letter queue, nobody would know. Now a CloudWatch alarm watches the queue. If even one message lands there, SNS, Simple Notification Service, emails me. When the queue is empty again, I get an "OK" email.

Third, parallelism. The requirement says many leads in parallel without race conditions. The design handles that with one file per lead, but I wanted proof, so I wrote tests that push 20 leads through the receiver and processor at the same time, and a nastier one: 10 copies of the same lead racing to send its alert. More on that on the next slide.

## Slide 10: 111 tests, run on my Mac with no AWS

All of this is tested: 111 tests that run on my Mac in about four seconds, without touching AWS.

[ON SCREEN, optional: run the tests.]

```bash
.venv/bin/python -m pytest -q
```

The new parallel test sends 20 leads through the real receiver and processor code at the same time, in 20 threads. It checks we get 20 source files, 20 target files and 20 alerts, and that every record and every alert names only its own lead and its own owner. No mix-ups.

The race test is the interesting one. Ten processors grab the same lead at the same moment, which is what happens if SQS delivers a message more than once. Only one alert goes out. And I checked the test isn't just passing by luck: I temporarily switched off the marker's "only if it doesn't exist yet" check, and the test failed with 10 alerts instead of 1. So the conditional write in S3 is what makes it safe.

Same idea for the key rotation fix: I ran the new test against the old code and it failed, so it really catches the incident from earlier.

How it runs without AWS: a library called moto fakes S3 and SSM in memory, and small local web servers stand in for the owner bucket and Slack.

## Slide 11: Deploy, operate and tear down from the README

Everything you need to run LeadRelay is in the README, next to the architecture diagram.

[ON SCREEN, optional: scroll through the README on GitHub.]

Deploying is one terraform apply, which creates about 30 AWS resources. Then two manual steps that keep secrets out of git: store the Slack webhook URL and the Close signing key in SSM, using commands that Terraform prints for you, and click the confirmation link in the alarm email.

Operating it: if the DLQ alarm fires, find the lead ID in the processor log, fix the cause, and redrive the message from the SQS console. If Close rotates the signing key, put the new one in SSM, and the receiver picks it up within a minute, no restart. A code change is just another terraform apply.

And tearing down is terraform destroy. It removes everything, including the bucket and all lead data in it, so that's the last step of this project, after this recording. I'll also ask Azmat or Ninad to delete the Close webhook subscription, so Close doesn't keep retrying a URL that no longer exists.

## Slide 12: Four lessons from building it for real

Four things I'll take with me from this project.

One: let the queue do the waiting. The whole "wait 10 minutes before the lookup" requirement is a single SQS setting, a 600-second delay. No timers, no Lambda sitting idle and paying for it.

Two: name your files by the key you process on. Using the lead ID in every file name removed almost every possible race. The one left, two copies of the same lead both sending the alert, is closed by an S3 conditional write: only the first copy can create the marker.

Three: caches need a way to expire. Caching the secrets made the Lambdas fast, and it also made key rotation silently fail on go-live. Now a failed check triggers a refresh.

Four: test locally, prove the tests, then deploy. With fakes for S3, SSM and HTTP, almost all of the work happened on my laptop. And breaking the code on purpose to watch a test fail is the cheapest way to know the test is real.

## Slide 13: LeadRelay is live and complete

To wrap up: LeadRelay is live and complete. Real Close leads come in, wait 10 minutes for their owner, get enriched, and land in Slack as one alert each. Behind that there's a dead-letter queue with an email alarm, automatic key rotation, and 111 tests including the parallel ones.

The code, the architecture diagram and the full deploy, operate and teardown runbook are in the README on GitHub.

Next, I'll tear the stack down with terraform destroy, and ask Azmat or Ninad to remove the Close webhook subscription.

Thanks for the approval on the design, and for setting up the Close webhook. Happy to take any questions.
