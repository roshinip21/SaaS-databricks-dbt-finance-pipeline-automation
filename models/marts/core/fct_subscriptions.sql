with subscriptions as (
    select * from {{ ref('stg_saas__subscriptions') }}
),

plans as (
    select * from {{ ref('stg_saas__plans') }}
)

select
    s.subscription_id,
    s.customer_id,
    s.plan_id,
    p.plan_name,
    p.tier,
    p.billing_interval,
    s.start_date,
    s.end_date,
    s.status,
    s.is_current,
    s.mrr_usd,
    datediff('day', s.start_date, coalesce(s.end_date, current_date())) as duration_days
from subscriptions s
left join plans p on s.plan_id = p.plan_id
