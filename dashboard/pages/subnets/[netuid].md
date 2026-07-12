# Subnet {params.netuid}

```sql latest
select *
from subnets.subnet_latest
where netuid = ${params.netuid}
```

<BigValue data={latest} value=alpha_price_tao title="α price (τ)" fmt="0.00000" />
<BigValue data={latest} value=price_7d_pct title="7d vs τ" fmt="+0.0%;-0.0%" />
<BigValue data={latest} value=emission_share title="Emission share" fmt="0.00%" />
<BigValue data={latest} value=absorption_ratio title="Absorption" fmt="0.00" />
<BigValue data={latest} value=dereg_risk_rank title="Dereg rank (proxy)" />

```sql history
select
  as_of_date,
  alpha_price_tao,
  net_flow_tao,
  flow_zscore,
  absorption_ratio,
  emission_share,
  root_prop,
  tao_reserve,
  fear_greed
from subnets.subnet_daily
where netuid = ${params.netuid}
order by as_of_date
```

<LineChart data={history} x=as_of_date y=alpha_price_tao
  title="Alpha price (TAO)" yFmt="0.00000" />

<BarChart data={history} x=as_of_date y=net_flow_tao
  title="Net TAO flow / day" yFmt="+#,##0;-#,##0" />

<LineChart data={history} x=as_of_date y=absorption_ratio
  title="Absorption ratio (net inflow ÷ daily emission value)" />

<LineChart data={history} x=as_of_date y={["emission_share","root_prop"]}
  title="Emission share & root proportion" />

<LineChart data={history} x=as_of_date y=tao_reserve
  title="TAO reserve (pool depth)" yFmt="#,##0" />
