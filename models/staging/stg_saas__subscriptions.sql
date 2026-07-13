with source as (
    select * from {{ ref('subscriptions') }}
),

renamed as (
    select
        subscription_id,
        customer_id,
        plan_id,
        start_date::date as start_date,
        end_date::date as end_date,
        status,
        mrr_usd::number(10, 2) as mrr_usd,
        end_date is null as is_current
    from source
)

select * from renamed
