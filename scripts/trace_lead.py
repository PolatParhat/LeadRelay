"""Follow ONE lead through the deployed system, step by step (read-only).

    .venv/bin/python scripts/trace_lead.py                       # the most recently alerted lead
    .venv/bin/python scripts/trace_lead.py --lead-id lead_abc    # a lead you choose
    .venv/bin/python scripts/trace_lead.py --pause               # wait for Enter between steps (for the video)

It reads only this lead's files in S3 and only this lead's lines in the two Lambda logs
(CloudWatch filter on the JSON field lead_id), so the output tells one story:
received -> saved -> waited 10 minutes -> owner lookup -> enriched record -> alert sent once.
Nothing is created, changed or deleted.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
REGION = "us-east-1"
RECEIVER_LOG = "/aws/lambda/leadrelay-receiver"
PROCESSOR_LOG = "/aws/lambda/leadrelay-processor"


def bucket_from_terraform() -> str:
    result = subprocess.run(["terraform", "output", "-raw", "bucket_name"],
                            cwd=ROOT / "infra", capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("could not read bucket_name from terraform output; pass --bucket")
    return result.stdout.strip()


def latest_alerted_lead(s3, bucket: str) -> str:
    """The lead whose alerts_sent/ marker was written last."""
    newest = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="alerts_sent/"):
        for obj in page.get("Contents", []):
            if newest is None or obj["LastModified"] > newest["LastModified"]:
                newest = obj
    if newest is None:
        sys.exit("no alerts sent yet")
    return newest["Key"].removeprefix("alerts_sent/")


def read_json(s3, bucket: str, key: str):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except s3.exceptions.NoSuchKey:
        return None, None
    return json.loads(obj["Body"].read()), obj["LastModified"]


def log_lines(logs, group: str, lead_id: str, start: datetime) -> list[dict]:
    """This lead's log lines only, oldest first."""
    lines = []
    paginator = logs.get_paginator("filter_log_events")
    for page in paginator.paginate(logGroupName=group,
                                   filterPattern=f'{{ $.lead_id = "{lead_id}" }}',
                                   startTime=int(start.timestamp() * 1000)):
        for event in page["events"]:
            try:
                lines.append(json.loads(event["message"]))
            except ValueError:
                pass
    return sorted(lines, key=lambda line: line.get("timestamp", ""))


def hhmmss(value) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime("%H:%M:%S UTC")


def step(number: int, title: str, pause: bool) -> None:
    if pause and number > 1:
        input("\n   [Enter] next step ")
    print(f"\n{number}. {title}")
    print("   " + "-" * (len(title) + 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lead-id")
    parser.add_argument("--bucket")
    parser.add_argument("--pause", action="store_true", help="wait for Enter between steps")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    logs = boto3.client("logs", region_name=REGION)
    bucket = args.bucket or bucket_from_terraform()
    lead_id = args.lead_id or latest_alerted_lead(s3, bucket)

    print(f"Following ONE lead: {lead_id}")

    # 1-2. The receiver saved the raw Close event.
    source, saved_at = read_json(s3, bucket, f"source/crm_event_{lead_id}.json")
    if source is None:
        sys.exit(f"no source file for {lead_id}: not received (or a typo in the lead_id)")
    start = saved_at - timedelta(minutes=5)

    step(1, "Close sent the webhook; the receiver checked the signature and saved it", args.pause)
    for line in log_lines(logs, RECEIVER_LOG, lead_id, start):
        print(f"   {hhmmss(line['timestamp'])}  receiver: {line['message']}")

    step(2, f"Raw event in S3: source/crm_event_{lead_id}.json", args.pause)
    data = source["event"]["data"]
    print(f"   saved at      {hhmmss(saved_at)}")
    print(f"   Name          {data.get('display_name')}")
    print(f"   Created Date  {data.get('date_created')}")
    print(f"   Label         {data.get('status_label')}")

    # 3-4. Ten minutes in the SQS delay queue, then the processor.
    processor_lines = log_lines(logs, PROCESSOR_LOG, lead_id, start)
    lookups = [line for line in processor_lines if line["message"] == "owner lookup done"]

    step(3, "Waited in the SQS delay queue (owner lookup is never early)", args.pause)
    if lookups:
        first = datetime.fromisoformat(lookups[0]["timestamp"].replace("Z", "+00:00"))
        minutes = (first - saved_at).total_seconds() / 60
        print(f"   saved {hhmmss(saved_at)}  ->  first lookup {hhmmss(first)}  =  {minutes:.1f} minutes later")
    else:
        print("   no lookup yet: the lead is still inside its 10-minute wait")

    step(4, "Processor: owner lookup in dea-lead-owner, enrich, alert", args.pause)
    for line in processor_lines:
        extra = ""
        if "try" in line:
            extra += f"  (try {line['try']})"
        if "owner_found" in line:
            extra += f"  owner_found={line['owner_found']}"
        print(f"   {hhmmss(line['timestamp'])}  processor: {line['message']}{extra}")

    # 5. The enriched record.
    step(5, f"Enriched record in S3: target/enriched_{lead_id}.json", args.pause)
    record, _ = read_json(s3, bucket, f"target/enriched_{lead_id}.json")
    if record is None:
        print("   not written yet")
    else:
        for label, field in [("Name", "display_name"), ("Lead ID", "lead_id"), ("Created Date", "date_created"),
                             ("Label", "status_label"), ("Email", "lead_email"), ("Lead Owner", "lead_owner"),
                             ("Funnel", "funnel")]:
            print(f"   {label:<13} {record.get(field)}")
        print(f"   {'owner_found':<13} {record.get('owner_found')}")

    # 6. The alert marker.
    step(6, f"Alert sent exactly once: alerts_sent/{lead_id}", args.pause)
    marker, _ = read_json(s3, bucket, f"alerts_sent/{lead_id}")
    if marker is None:
        print("   no alert yet")
    else:
        print(f"   status {marker['status']} at {hhmmss(marker['at'])}")
        print(f"   In Slack, search for: {lead_id}")


if __name__ == "__main__":
    main()
