"""Minimal Taostats API client: auth, pagination, rate limiting, retries."""

import logging
import os
import time

import requests

from ingest import config

log = logging.getLogger(__name__)


class TaostatsClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["TAOSTATS_API_KEY"]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": self.api_key,
                "accept": "application/json",
            }
        )
        self._last_call = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        wait = config.RATE_LIMIT_SLEEP_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict) -> dict | list:
        url = f"{config.TAOSTATS_BASE_URL}{path}"
        backoff = 15
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._throttle()
            resp = self.session.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning(
                    "GET %s -> %s (attempt %s/%s), backing off %ss",
                    path, resp.status_code, attempt, config.MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Exhausted retries for {path}")

    def fetch(self, endpoint: dict) -> list[dict]:
        """Fetch all records for a registry entry, walking pages if needed."""
        params = dict(endpoint.get("params") or {})
        if not endpoint.get("paginated"):
            payload = self._get(endpoint["path"], params)
            return self._extract_rows(payload)

        rows: list[dict] = []
        page = 1
        while True:
            payload = self._get(
                endpoint["path"], {**params, "page": page, "limit": config.PAGE_LIMIT}
            )
            batch = self._extract_rows(payload)
            rows.extend(batch)
            if not self._has_next_page(payload, len(batch)):
                break
            page += 1
        return rows

    @staticmethod
    def _extract_rows(payload) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data
            if data is not None:
                return [data]
            return [payload]
        return []

    @staticmethod
    def _has_next_page(payload, batch_len: int) -> bool:
        if isinstance(payload, dict):
            pg = payload.get("pagination") or {}
            if "next_page" in pg:
                return pg["next_page"] is not None
            cur, total = pg.get("current_page"), pg.get("total_pages")
            if cur is not None and total is not None:
                return cur < total
        # Fallback heuristic: a full page implies there may be more.
        return batch_len >= config.PAGE_LIMIT
