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
        cast(event_timestamp as timestamp) as event_timestamp,
        cast(event_timestamp as date) as event_date
    from source
)

select * from renamed
