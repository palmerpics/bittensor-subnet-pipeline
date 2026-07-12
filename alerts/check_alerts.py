"""Read gold Parquet straight off R2, evaluate alert rules, post to Discord.

Rules (thresholds via env):
  FLOW_Z        net-flow z-score breach (default |z| >= 2.5)
  PRICE_DROP    alpha/TAO 7d return below threshold (default -15%)
  DEREG_RISK    subnet within N of the bottom of the dereg rank (default 5)
  YIELD_TRAP    high APY + falling alpha/TAO — enable once validator_yield lands

No webhook configured -> prints findings and exits 0 (safe default).
"""

import os
import sys

import duckdb
import requests

R2_BUCKET = os.environ.get("R2_BUCKET", "bittensor-lake")
GOLD_ROOT = os.environ.get("GOLD_ROOT", f"s3://{R2_BUCKET}/gold")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

Z_THRESHOLD = float(os.environ.get("ALERT_FLOW_Z", "2.5"))
PRICE_DROP_7D = float(os.environ.get("ALERT_PRICE_DROP_7D", "-0.15"))
DEREG_WITHIN = int(os.environ.get("ALERT_DEREG_WITHIN", "5"))


def connect():
    con = duckdb.connect()
    if GOLD_ROOT.startswith("s3://"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"""
            CREATE SECRET r2 (
                TYPE S3,
                KEY_ID '{os.environ["R2_ACCESS_KEY_ID"]}',
                SECRET '{os.environ["R2_SECRET_ACCESS_KEY"]}',
                ENDPOINT '{os.environ["R2_ACCOUNT_ID"]}.r2.cloudflarestorage.com',
                URL_STYLE 'path'
            );
        """)
    return con


def gather(con) -> list[str]:
    latest = f"{GOLD_ROOT}/dim_subnet_latest.parquet"
    daily = f"{GOLD_ROOT}/fct_subnet_daily.parquet"
    alerts: list[str] = []

    rows = con.execute(f"""
        SELECT netuid, subnet_name, flow_zscore, net_flow_tao
        FROM read_parquet('{latest}')
        WHERE abs(flow_zscore) >= {Z_THRESHOLD}
        ORDER BY abs(flow_zscore) DESC
    """).fetchall()
    for netuid, name, z, flow in rows:
        direction = "inflow" if (flow or 0) >= 0 else "OUTFLOW"
        alerts.append(
            f"**SN{netuid}** ({name or 'unnamed'}): flow z-score {z:+.1f} "
            f"({direction} {flow:,.0f} TAO)"
        )

    rows = con.execute(f"""
        SELECT netuid, subnet_name, price_7d_pct
        FROM read_parquet('{latest}')
        WHERE price_7d_pct <= {PRICE_DROP_7D}
        ORDER BY price_7d_pct ASC
    """).fetchall()
    for netuid, name, pct in rows:
        alerts.append(
            f"**SN{netuid}** ({name or 'unnamed'}): alpha/TAO {pct:+.1%} over 7d"
        )

    rows = con.execute(f"""
        SELECT netuid, subnet_name, dereg_risk_rank
        FROM read_parquet('{latest}')
        WHERE dereg_risk_rank <= {DEREG_WITHIN}
        ORDER BY dereg_risk_rank
    """).fetchall()
    for netuid, name, rk in rows:
        alerts.append(
            f"**SN{netuid}** ({name or 'unnamed'}): dereg risk rank #{int(rk)} "
            f"(proxy — lowest alpha price)"
        )

    # keep the daily table referenced so a broken export fails loudly here
    con.execute(f"SELECT count(*) FROM read_parquet('{daily}')").fetchone()
    return alerts


def notify(alerts: list[str]) -> None:
    if not alerts:
        print("No alerts today.")
        return
    body = "\n".join(f"- {a}" for a in alerts)
    print(body)
    if not WEBHOOK:
        print("(DISCORD_WEBHOOK_URL not set — printed only)")
        return
    # Discord caps content at 2000 chars; chunk to be safe
    chunk, chunks = "", []
    for line in body.splitlines():
        if len(chunk) + len(line) + 1 > 1900:
            chunks.append(chunk)
            chunk = ""
        chunk += line + "\n"
    chunks.append(chunk)
    for i, c in enumerate(chunks):
        header = "🚨 **Subnet alerts**\n" if i == 0 else ""
        requests.post(WEBHOOK, json={"content": header + c}, timeout=30).raise_for_status()


if __name__ == "__main__":
    try:
        con = connect()
        notify(gather(con))
    except Exception as exc:  # alert job should never mask pipeline success
        print(f"alerts failed: {exc}", file=sys.stderr)
        sys.exit(0)
