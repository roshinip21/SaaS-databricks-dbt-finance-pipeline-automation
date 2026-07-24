with source as (
    select * from {{ ref('plans') }}
),

renamed as (
    select
        plan_id,
        plan_name,
        tier,
        billing_interval,
        cast(price_usd as decimal(10, 2)) as price_usd
    from source
)

select * from renamed
