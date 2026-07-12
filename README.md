# Bittensor Subnet Pipeline

Taostats API → Cloudflare R2 (bronze JSON → gold Parquet) → Evidence.dev dashboard on GitHub Pages, with Discord alerts. Orchestrated entirely by GitHub Actions. Runs at ~$0/month.

```
GitHub Actions (cron, daily 05:23 UTC)
│
├─ ingest/           Taostats API ──▶ R2  bronze/<endpoint>/dt=YYYY-MM-DD/*.json
├─ transform/        dbt-duckdb: bronze glob ──▶ gold/*.parquet on R2
├─ alerts/           DuckDB over gold ──▶ Discord webhook
└─ dashboard/        sync gold ──▶ Evidence build ──▶ GitHub Pages
```

**Metric layer** (in `fct_subnet_daily` / `dim_subnet_latest`): alpha price vs TAO with 7d/30d returns, net TAO flow + 30d z-score, absorption ratio (net inflow ÷ daily alpha-emission value), emission share + 7d delta, root_prop, TAO reserve depth, fear/greed, dereg risk rank.

---

## Setup (≈15 minutes)

### 1. Taostats API key
Sign up at `taostats.io/pro` → create an API key. Free tier (5 calls/min, 10k/month) covers the daily sweep with room to spare.

### 2. Cloudflare R2
1. Create a bucket (default name `bittensor-lake`, or set the `R2_BUCKET` repo variable).
2. R2 → *Manage API Tokens* → create a token with **Object Read & Write** scoped to the bucket. Note the Access Key ID / Secret and your **Account ID** (R2 overview page).
3. Do **not** enable R2 Data Catalog on this bucket — bronze stays as plain objects by design (see Roadmap).

### 3. GitHub repo
1. Push this folder to a new repo.
2. **Settings → Secrets and variables → Actions → Secrets**:
   - `TAOSTATS_API_KEY`
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   - `DISCORD_WEBHOOK_URL` *(optional — alerts print to the log without it)*
3. **Variables** (optional): `R2_BUCKET` if not `bittensor-lake`.
4. **Settings → Pages → Source: GitHub Actions.**
5. Actions tab → run **pipeline** manually once (`workflow_dispatch`) and watch it go green.

---

## First-run checklist (important)

Two endpoint paths in `ingest/config.py` are marked **VERIFY** (`subnets`, `dereg_ranking`) — confirm them against [docs.taostats.io/reference](https://docs.taostats.io/reference) before trusting those tables. Taostats reshapes payloads as chain mechanics evolve, so after the first run:

1. Pull one bronze file and eyeball the field names:
   ```sql
   -- duckdb (with your R2 secret configured)
   SELECT data->0 FROM read_json_auto('s3://bittensor-lake/bronze/pools/*/*.json') LIMIT 1;
   ```
2. Adjust the `rec ->> '...'` extractions in `transform/models/staging/*.sql`. They're written defensively (`try_cast` + `coalesce` across plausible names) so mismatches degrade to NULL columns, never failed builds — but NULL metrics help nobody.
3. Check rao-vs-unit scaling: reserve/flow fields assume raw values are rao (÷1e9). If a field arrives pre-scaled, drop the division.

## Local development

```bash
pip install -r requirements.txt
make transform-dev    # dbt against fixtures/ — no credentials needed
make alerts-dev       # alert rules against the local gold output
cp .env.example .env  # fill in, then `set -a; source .env` for real runs
make ingest && make transform && make alerts
```

Fixtures in `fixtures/bronze/` mirror real payload shapes (including string-typed numerics) — extend them as you discover real field names.

Dashboard locally:
```bash
aws s3 cp s3://$R2_BUCKET/gold/ dashboard/sources/subnets/data/ --recursive \
  --endpoint-url https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com
make dash
```

## Operating notes

- **Hourly snapshots**: uncomment the cron in `.github/workflows/hourly-ingest.yml` for intraday pool data. Public repos get unlimited Actions minutes; private repos burn the 2k/month free allowance (~10 min/day daily + ~2 min/hr hourly still fits).
- **Evidence versions**: deps are pinned to `latest`. If a major release breaks the build, scaffold fresh with `npx degit evidence-dev/template dashboard-new` and copy `sources/` + `pages/` over.
- **Evidence parquet paths**: source SQL reads `sources/subnets/data/*.parquet` relative to the project root. If a version resolves paths differently, switch to absolute paths in `dashboard/sources/subnets/*.sql`.
- **dbt tests**: a uniqueness test on `(netuid, as_of_date)` ships disabled; add `dbt_utils` to a `packages.yml`, run `dbt deps`, and flip `enabled: true` in `transform/models/schema.yml`.

## Roadmap hooks

- **Bronze compaction**: the staging glob rescans all bronze JSON each run. Fine for a year+ of daily files; once hourly history piles up, add a monthly job that rewrites old bronze into Parquet and narrow the glob.
- **R2 Data Catalog**: when you want Iceberg semantics (time travel, compaction, multi-engine access), point dbt-duckdb's external materializations at a catalog-enabled bucket — bronze stays plain-object either way.
- **Owner-sell detection**: join `stg_subnets.owner_coldkey` against the Taostats transfers endpoint; alert when an owner coldkey moves >X TAO to an exchange.
- **Validator yield / dereg endpoints**: flip `enabled: True` in `ingest/config.py`, add matching staging models, wire the yield-trap alert (high APY + negative 7d alpha/TAO).
- **ML features**: `fct_subnet_daily` is already a feature table — LightGBM on flow/price/absorption lags slots in as another Actions step.
