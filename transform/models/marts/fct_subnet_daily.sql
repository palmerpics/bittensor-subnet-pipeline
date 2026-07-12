-- Daily grain, one row per subnet per day. The metric layer:
--   price returns (7d/30d), flow z-score, absorption ratio, emission share,
--   liquidity depth, root_prop, sentiment.
-- Materialized as external Parquet on R2 (gold/fct_subnet_daily.parquet).

with pool_daily as (

    -- last snapshot of each day wins
    select *
    from (
        select
            *,
            cast(snapshot_at as date) as snapshot_date,
            row_number() over (
                partition by netuid, cast(snapshot_at as date)
                order by snapshot_at desc
            ) as rn
        from {{ ref('stg_pool_snapshots') }}
    )
    where rn = 1

),

flow_daily as (

    select
        netuid,
        cast(flow_at as date) as flow_date,
        sum(net_flow_tao)     as net_flow_tao,
        sum(inflow_tao)       as inflow_tao,
        sum(outflow_tao)      as outflow_tao
    from {{ ref('stg_tao_flow') }}
    group by 1, 2

),

subnet_latest as (

    select *
    from (
        select
            *,
            row_number() over (partition by netuid order by fetched_at desc) as rn
        from {{ ref('stg_subnets') }}
    )
    where rn = 1

),

joined as (

    select
        p.netuid,
        p.snapshot_date                     as as_of_date,
        s.subnet_name,
        s.owner_coldkey,
        s.emission_share,
        s.emission_enabled,
        p.alpha_price_tao,
        p.root_prop,
        p.fear_greed,
        p.tao_reserve,
        p.alpha_reserve,
        p.market_cap_tao,
        p.volume_tao,
        f.net_flow_tao,
        f.inflow_tao,
        f.outflow_tao
    from pool_daily p
    left join flow_daily f
        on f.netuid = p.netuid and f.flow_date = p.snapshot_date
    left join subnet_latest s
        on s.netuid = p.netuid

),

metrics as (

    select
        *,

        -- price returns vs TAO (the number that matters — not USD)
        alpha_price_tao / nullif(lag(alpha_price_tao, 7) over w, 0) - 1
            as price_7d_pct,
        alpha_price_tao / nullif(lag(alpha_price_tao, 30) over w, 0) - 1
            as price_30d_pct,

        -- demand anomaly: today's net flow vs trailing distribution
        (net_flow_tao - avg(net_flow_tao) over w_trailing)
            / nullif(stddev_samp(net_flow_tao) over w_trailing, 0)
            as flow_zscore,

        -- can inflows absorb daily emission sell pressure?
        -- >1 = inflows exceed the emission-value ceiling; <0 = net exit
        net_flow_tao
            / nullif({{ var('alpha_emission_per_day') }} * alpha_price_tao, 0)
            as absorption_ratio,

        -- emission share trend (percentage-point change over 7d)
        emission_share - lag(emission_share, 7) over w
            as emission_share_7d_delta

    from joined
    window
        w as (partition by netuid order by as_of_date),
        w_trailing as (
            partition by netuid order by as_of_date
            rows between {{ var('flow_zscore_window_days') }} preceding
                     and 1 preceding
        )

)

select * from metrics
order by as_of_date, netuid
