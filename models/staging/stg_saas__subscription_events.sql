with source as (
    select * from {{ ref('subscription_events') }}
),

renamed as (
    select
        event_id,
        subscription_id,
        customer_id,
        event_type,
        cast(event_date as date) as event_date,
        previous_plan_id,
        new_plan_id,
        cast(mrr_delta_usd as decimal(10, 2)) as mrr_delta_usd
    from source
)

select * from renamed
