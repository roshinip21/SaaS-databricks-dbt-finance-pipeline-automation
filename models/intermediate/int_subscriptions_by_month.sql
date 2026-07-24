-- One row per customer per month, carrying whichever subscription stint
-- was active on that month's last calendar day (i.e. an end-of-month MRR
-- snapshot). Customers with no active subscription in a given month are
-- simply absent and get backfilled to 0 MRR downstream.
with months as (
    select * from {{ ref('int_month_spine') }}
),

subscriptions as (
    select * from {{ ref('stg_saas__subscriptions') }}
),

spined as (
    select
        s.subscription_id,
        s.customer_id,
        s.plan_id,
        s.mrr_usd,
        m.date_month as month
    from subscriptions s
    inner join months m
        on s.start_date <= last_day(m.date_month)
        and (s.end_date is null or s.end_date > last_day(m.date_month))
)

select
    customer_id,
    month,
    sum(mrr_usd) as mrr_usd,
    max(plan_id) as plan_id
from spined
group by 1, 2
