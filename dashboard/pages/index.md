# Bittensor Subnet Screener

```sql kpis
select
  count(*)                                       as subnets,
  sum(market_cap_tao)                            as total_mcap_tao,
  sum(net_flow_tao)                              as net_flow_today,
  count(*) filter (where absorption_ratio > 1)   as absorbing
from subnets.subnet_latest
```

<BigValue data={kpis} value=subnets title="Active subnets" />
<BigValue data={kpis} value=total_mcap_tao title="Combined mcap (TAO)" fmt="#,##0" />
<BigValue data={kpis} value=net_flow_today title="Net flow today (TAO)" fmt="+#,##0;-#,##0" />
<BigValue data={kpis} value=absorbing title="Absorbing emissions" />

## Screener

Flow z-score = today's net TAO flow vs its own trailing 30d. Absorption > 1 means
staking inflows exceed the value of daily alpha emissions.

```sql screener
select
  netuid,
  coalesce(subnet_name, 'SN' || netuid)  as subnet,
  alpha_price_tao,
  price_7d_pct,
  price_30d_pct,
  emission_share,
  net_flow_tao,
  flow_zscore,
  absorption_ratio,
  root_prop,
  tao_reserve,
  dereg_risk_rank
from subnets.subnet_latest
order by emission_share desc nulls last
```

<DataTable data={screener} rows=25 search=true link=false>
  <Column id=netuid title="SN" />
  <Column id=subnet />
  <Column id=alpha_price_tao title="α price (τ)" fmt="0.00000" />
  <Column id=price_7d_pct title="7d" fmt="+0.0%;-0.0%" contentType=delta />
  <Column id=price_30d_pct title="30d" fmt="+0.0%;-0.0%" contentType=delta />
  <Column id=emission_share title="Emission" fmt="0.00%" contentType=colorscale />
  <Column id=net_flow_tao title="Net flow (τ)" fmt="+#,##0;-#,##0" />
  <Column id=flow_zscore title="Flow z" fmt="+0.0;-0.0" contentType=colorscale scaleColor=red />
  <Column id=absorption_ratio title="Absorb" fmt="0.00" />
  <Column id=root_prop title="Root prop" fmt="0.00" />
  <Column id=dereg_risk_rank title="Dereg #" />
</DataTable>

Drill into any subnet at `/subnets/<netuid>` — e.g. [/subnets/64](/subnets/64).

## Flow anomalies (|z| ≥ 2)

```sql movers
select
  netuid,
  coalesce(subnet_name, 'SN' || netuid) as subnet,
  flow_zscore,
  net_flow_tao
from subnets.subnet_latest
where abs(flow_zscore) >= 2
order by abs(flow_zscore) desc
limit 15
```

<BarChart
  data={movers}
  x=subnet
  y=net_flow_tao
  swapXY=true
  title="Largest flow anomalies (net TAO, today)"
/>

## Emission share — top subnets, trailing 90d

```sql emission_trend
with top as (
  select netuid from subnets.subnet_latest
  order by emission_share desc nulls last
  limit 8
)
select
  d.as_of_date,
  'SN' || d.netuid || ' ' || coalesce(d.subnet_name, '') as subnet,
  d.emission_share
from subnets.subnet_daily d
join top using (netuid)
where d.as_of_date >= current_date - interval 90 day
order by d.as_of_date
```

<LineChart
  data={emission_trend}
  x=as_of_date
  y=emission_share
  series=subnet
  yFmt="0.0%"
  title="Share of daily TAO emission"
/>
