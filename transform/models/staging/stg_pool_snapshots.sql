-- Pool snapshots: price, root_prop, reserves, sentiment.
-- Bronze files are {fetched_at, endpoint, data:[...]}; we keep `data` as raw
-- JSON and extract fields with ->> + try_cast so Taostats schema drift
-- degrades to NULLs instead of breaking the build.

with files as (

    select
        try_cast(fetched_at as timestamp) as fetched_at,
        unnest(from_json(data, '["json"]')) as rec
    from read_json_auto(
        '{{ env_var("BRONZE_ROOT", "s3://" ~ env_var("R2_BUCKET", "bittensor-lake") ~ "/bronze") }}/pools/*/*.json',
        columns = {fetched_at: 'VARCHAR', endpoint: 'VARCHAR', run_id: 'VARCHAR',
                   row_count: 'BIGINT', data: 'JSON'}
    )

),

parsed as (

    select
        try_cast(rec ->> 'netuid' as integer)                    as netuid,
        coalesce(
            try_cast(rec ->> 'timestamp' as timestamp),
            fetched_at
        )                                                        as snapshot_at,
        try_cast(rec ->> 'block_number' as bigint)               as block_number,

        -- alpha price denominated in TAO
        try_cast(rec ->> 'price' as double)                      as alpha_price_tao,
        try_cast(rec ->> 'root_prop' as double)                  as root_prop,
        coalesce(
            try_cast(rec ->> 'fear_and_greed_index' as double),
            try_cast(rec ->> 'fear_and_greed' as double)
        )                                                        as fear_greed,

        -- pool reserves (rao-denominated on the wire; normalize to units)
        try_cast(rec ->> 'tao_in' as double)  / 1e9              as tao_reserve,
        try_cast(rec ->> 'alpha_in' as double) / 1e9             as alpha_reserve,
        try_cast(rec ->> 'alpha_out' as double) / 1e9            as alpha_outstanding,

        try_cast(rec ->> 'market_cap' as double) / 1e9           as market_cap_tao,
        try_cast(rec ->> 'total_volume' as double) / 1e9         as volume_tao,
        fetched_at
    from files

)

select *
from parsed
where netuid is not null
