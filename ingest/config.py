"""Central config for the ingestion layer.

Endpoint paths are config, not code: Taostats evolves quickly (tao_flow only
appeared in early 2026), so when they add/rename endpoints you should only
need to touch this file. Verify paths against https://docs.taostats.io/reference
before enabling anything marked VERIFY.
"""

import os

TAOSTATS_BASE_URL = os.environ.get("TAOSTATS_BASE_URL", "https://api.taostats.io")

# Free tier = 5 calls/min. 13s spacing keeps a comfortable margin.
RATE_LIMIT_SLEEP_SECONDS = float(os.environ.get("TAOSTATS_RATE_SLEEP", "13"))
MAX_RETRIES = 5
PAGE_LIMIT = 200  # rows per page where pagination is supported

# R2 (S3-compatible) settings — all via env / GitHub secrets
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ.get("R2_BUCKET", "bittensor-lake")
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

BRONZE_PREFIX = "bronze"

# ---------------------------------------------------------------------------
# Endpoint registry
#
# name          -> bronze folder name (bronze/<name>/dt=YYYY-MM-DD/...)
# path          -> API path
# paginated     -> walk ?page=N until exhausted
# params        -> static query params
# enabled       -> pulled on every run
# cadence       -> "daily" | "hourly" (hourly runs pull only hourly endpoints)
# ---------------------------------------------------------------------------
ENDPOINTS = [
    {
        "name": "pools",
        "path": "/api/dtao/pool/latest/v1",
        "paginated": True,
        "params": {},
        "enabled": True,
        "cadence": "hourly",  # price / root_prop / reserves — the workhorse
    },
    {
        "name": "tao_flow",
        "path": "/api/dtao/tao_flow/v1",
        "paginated": True,
        "params": {},
        "enabled": True,
        "cadence": "daily",
    },
    {
        "name": "subnets",
        # VERIFY: subnet metadata/economics (owner, registration, emission).
        # Check the exact path under "Subnets" in the API reference.
        "path": "/api/subnet/latest/v1",
        "paginated": True,
        "params": {},
        "enabled": True,
        "cadence": "daily",
    },
    {
        "name": "validator_yield",
        "path": "/api/dtao/validator/yield/latest/v1",
        "paginated": True,
        "params": {},
        "enabled": False,  # large payload; enable once you want APY red-flags
        "cadence": "daily",
    },
    {
        "name": "dereg_ranking",
        # VERIFY: newer endpoint — grab the exact path from
        # docs.taostats.io/reference/subnet-deregistration-ranking
        "path": "/api/subnet/deregistration/v1",
        "paginated": False,
        "params": {},
        "enabled": False,
        "cadence": "daily",
    },
]
