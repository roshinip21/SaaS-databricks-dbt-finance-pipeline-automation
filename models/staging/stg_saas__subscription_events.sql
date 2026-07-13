with source as (
    select * from {{ ref('subscription_events') }}
),

renamed as (
    select
        event_id,
        subscription_id,
        customer_id,
        event_type,
        event_date::date as event_date,
        previous_plan_id,
        new_plan_id,
        mrr_delta_usd::number(10, 2) as mrr_delta_usd
    from source
)

select * from renamed
