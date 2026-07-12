-- Subnet metadata + economics: identity, owner, registration, emission share.
-- Owner coldkey here is what you later join against transfers to build the
-- owner-selling flag.

with files as (

    select
        try_cast(fetched_at as timestamp) as fetched_at,
        unnest(from_json(data, '["json"]')) as rec
    from read_json_auto(
        '{{ env_var("BRONZE_ROOT", "s3://" ~ env_var("R2_BUCKET", "bittensor-lake") ~ "/bronze") }}/subnets/*/*.json',
        columns = {fetched_at: 'VARCHAR', endpoint: 'VARCHAR', run_id: 'VARCHAR',
                   row_count: 'BIGINT', data: 'JSON'}
    )

)

select
    try_cast(rec ->> 'netuid' as integer)                        as netuid,
    coalesce(
        rec ->> 'subnet_name',
        rec ->> 'name',
        rec -> 'identity' ->> 'subnet_name'
    )                                                            as subnet_name,
    coalesce(
        rec -> 'owner' ->> 'ss58',
        rec ->> 'owner_coldkey',
        rec ->> 'owner'
    )                                                            as owner_coldkey,
    try_cast(rec ->> 'registered_at' as timestamp)               as registered_at,
    try_cast(rec ->> 'registration_block' as bigint)             as registration_block,
    -- share of daily TAO emission (0..1); some payloads express as fraction
    coalesce(
        try_cast(rec ->> 'emission' as double),
        try_cast(rec ->> 'emission_percentage' as double) / 100.0
    )                                                            as emission_share,
    try_cast(rec ->> 'subnet_emission_enabled' as boolean)       as emission_enabled,
    fetched_at
from files
where try_cast(rec ->> 'netuid' as integer) is not null
