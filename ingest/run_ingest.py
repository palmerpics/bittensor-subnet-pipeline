"""Pull every enabled endpoint and land the raw response in R2 (bronze).

Design notes:
- One JSON file per endpoint per run (all subnets together) so the bronze
  layer stays a small number of objects — the dbt glob scan reads whole-run
  files, not per-subnet fragments.
- Bronze is deliberately raw-and-boring: the untransformed API response plus
  a fetched_at envelope. All parsing lives in dbt, so schema drift on the
  Taostats side never loses data.

Usage:
    python -m ingest.run_ingest              # daily sweep (all enabled)
    python -m ingest.run_ingest --cadence hourly   # hourly endpoints only
"""

import argparse
import datetime as dt
import json
import logging
import sys
import uuid

import boto3

from ingest import config
from ingest.taostats_client import TaostatsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT_URL,
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def bronze_key(name: str, now: dt.datetime, run_id: str) -> str:
    return (
        f"{config.BRONZE_PREFIX}/{name}/"
        f"dt={now:%Y-%m-%d}/{name}_{now:%Y%m%dT%H%M%S}_{run_id}.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cadence", choices=["daily", "hourly"], default="daily")
    parser.add_argument("--only", help="comma-separated endpoint names", default=None)
    args = parser.parse_args()

    only = set(args.only.split(",")) if args.only else None
    now = dt.datetime.now(dt.timezone.utc)
    run_id = uuid.uuid4().hex[:8]

    client = TaostatsClient()
    s3 = r2_client()

    targets = [
        e for e in config.ENDPOINTS
        if e["enabled"]
        and (only is None or e["name"] in only)
        # daily sweep includes hourly endpoints too; hourly runs stay lean
        and (args.cadence == "daily" or e["cadence"] == "hourly")
    ]
    if not targets:
        log.warning("No endpoints matched — nothing to do.")
        return 0

    failures = 0
    for ep in targets:
        try:
            rows = client.fetch(ep)
            envelope = {
                "fetched_at": now.isoformat(),
                "endpoint": ep["path"],
                "run_id": run_id,
                "row_count": len(rows),
                "data": rows,
            }
            key = bronze_key(ep["name"], now, run_id)
            s3.put_object(
                Bucket=config.R2_BUCKET,
                Key=key,
                Body=json.dumps(envelope).encode("utf-8"),
                ContentType="application/json",
            )
            log.info("landed %s rows -> s3://%s/%s", len(rows), config.R2_BUCKET, key)
        except Exception:
            failures += 1
            log.exception("endpoint %s failed", ep["name"])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
