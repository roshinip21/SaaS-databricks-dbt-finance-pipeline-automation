with source as (
    select * from {{ ref('subscriptions') }}
),

renamed as (
    select
        subscription_id,
        customer_id,
        plan_id,
        cast(start_date as date) as start_date,
        cast(end_date as date) as end_date,
        status,
        cast(mrr_usd as decimal(10, 2)) as mrr_usd,
        end_date is null as is_current
    from source
)

select * from renamed
