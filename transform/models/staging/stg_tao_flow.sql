-- Net TAO flow per subnet — the cleanest demand signal.
-- Field names guarded with coalesce across plausible variants; check one
-- bronze file after your first run and trim to the real names.

with files as (

    select
        try_cast(fetched_at as timestamp) as fetched_at,
        unnest(from_json(data, '["json"]')) as rec
    from read_json_auto(
        '{{ env_var("BRONZE_ROOT", "s3://" ~ env_var("R2_BUCKET", "bittensor-lake") ~ "/bronze") }}/tao_flow/*/*.json',
        columns = {fetched_at: 'VARCHAR', endpoint: 'VARCHAR', run_id: 'VARCHAR',
                   row_count: 'BIGINT', data: 'JSON'}
    )

)

select
    try_cast(rec ->> 'netuid' as integer)                        as netuid,
    coalesce(
        try_cast(rec ->> 'timestamp' as timestamp),
        try_cast(rec ->> 'date' as timestamp),
        fetched_at
    )                                                            as flow_at,
    coalesce(
        try_cast(rec ->> 'net_tao_flow' as double),
        try_cast(rec ->> 'tao_flow' as double),
        try_cast(rec ->> 'net_flow' as double)
    ) / 1e9                                                      as net_flow_tao,
    coalesce(
        try_cast(rec ->> 'tao_in_flow' as double),
        try_cast(rec ->> 'buy_volume' as double)
    ) / 1e9                                                      as inflow_tao,
    coalesce(
        try_cast(rec ->> 'tao_out_flow' as double),
        try_cast(rec ->> 'sell_volume' as double)
    ) / 1e9                                                      as outflow_tao,
    fetched_at
from files
where try_cast(rec ->> 'netuid' as integer) is not null
