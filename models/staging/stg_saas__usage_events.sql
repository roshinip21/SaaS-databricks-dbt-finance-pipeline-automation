with source as (
    select * from {{ ref('usage_events') }}
),

renamed as (
    select
        event_id,
        customer_id,
        user_id,
        event_name,
        feature_area,
        event_timestamp::timestamp_ntz as event_timestamp,
        date(event_timestamp::timestamp_ntz) as event_date
    from source
)

select * from renamed
