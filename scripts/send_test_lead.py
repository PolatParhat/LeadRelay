"""Send a fake "lead created" webhook to the deployed LeadRelay URL, signed the way Close signs.

    .venv/bin/python scripts/send_test_lead.py                  # a new lead, valid signature
    .venv/bin/python scripts/send_test_lead.py --bad-signature  # should get 401
    .venv/bin/python scripts/send_test_lead.py --action updated # should get 200 "ignored"
    .venv/bin/python scripts/send_test_lead.py --lead-id lead_abc --name "Jane Doe"

Reads TEST_SIGNATURE_KEY from .env and the URL from `terraform output` (or --url).
Uses only the standard library plus our own signature module.
"""

import argparse
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from leadrelay.signature import compute_signature  # noqa: E402


def read_env_value(name: str) -> str:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip()
    sys.exit(f"{name} not found in {env_file}")


def webhook_url_from_terraform() -> str:
    result = subprocess.run(["terraform", "output", "-raw", "webhook_url"],
                            cwd=ROOT / "infra", capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("could not read webhook_url from terraform output; pass --url")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lead-id", default=f"lead_test{secrets.token_hex(6)}")
    parser.add_argument("--name", default="Test Lead")
    parser.add_argument("--action", default="created")
    parser.add_argument("--bad-signature", action="store_true")
    parser.add_argument("--url")
    args = parser.parse_args()

    url = args.url or webhook_url_from_terraform()
    key = read_env_value("TEST_SIGNATURE_KEY")

    body = json.dumps({
        "subscription_id": "whsub_test",
        "event": {
            "id": f"ev_test{secrets.token_hex(6)}",
            "object_type": "lead",
            "action": args.action,
            "lead_id": args.lead_id,
            "data": {
                "id": args.lead_id,
                "display_name": args.name,
                "status_label": "Potential",
                "date_created": datetime.now(timezone.utc).isoformat(),
            },
        },
    })
    timestamp = str(int(time.time()))
    signature = "0" * 64 if args.bad_signature else compute_signature(key, timestamp, body)

    request = urllib.request.Request(url, data=body.encode(), method="POST", headers={
        "Content-Type": "application/json",
        "Close-Sig-Timestamp": timestamp,
        "Close-Sig-Hash": signature,
        "User-Agent": "LeadRelay test script",
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status, reply = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, reply = error.code, error.read().decode()

    print(f"lead_id : {args.lead_id}")
    print(f"sent to : {url}")
    print(f"reply   : {status} {reply}")


if __name__ == "__main__":
    main()
