-- Latest row per subnet + a deregistration-risk proxy.
-- Dereg is driven by the EMA of alpha price ranked across subnets; until the
-- dedicated dereg endpoint is enabled in config.py, rank by latest price as
-- a rough stand-in (lowest rank = most at risk). Swap in the real endpoint's
-- ranking when you wire it up.

with latest as (

    select *
    from (
        select
            *,
            row_number() over (partition by netuid order by as_of_date desc) as rn
        from {{ ref('fct_subnet_daily') }}
    )
    where rn = 1

)

select
    * exclude (rn),
    rank() over (order by alpha_price_tao asc)          as dereg_risk_rank,
    count(*) over ()                                    as active_subnets
from latest
