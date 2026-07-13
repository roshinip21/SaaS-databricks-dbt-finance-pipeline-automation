with plans as (
    select * from {{ ref('stg_saas__plans') }}
),

active_subs as (
    select plan_id, count(*) as active_subscriber_count
    from {{ ref('stg_saas__subscriptions') }}
    where status = 'active'
    group by 1
)

select
    p.plan_id,
    p.plan_name,
    p.tier,
    p.billing_interval,
    p.price_usd,
    coalesce(a.active_subscriber_count, 0) as active_subscriber_count
from plans p
left join active_subs a on p.plan_id = a.plan_id
