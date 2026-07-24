-- Monthly recurring revenue waterfall per customer: new / expansion /
-- contraction / churned / reactivated MRR, in the spirit of a standard
-- SaaS MRR movement report.
with months as (
    select * from {{ ref('int_month_spine') }}
),

customers as (
    select customer_id, signup_date from {{ ref('stg_saas__customers') }}
),

customer_months as (
    select
        c.customer_id,
        m.date_month as month
    from customers c
    inner join months m
        on m.date_month >= date_trunc('month', c.signup_date)
),

subscription_mrr as (
    select * from {{ ref('int_subscriptions_by_month') }}
),

joined as (
    select
        cm.customer_id,
        cm.month,
        coalesce(sm.mrr_usd, 0) as mrr_usd,
        sm.plan_id
    from customer_months cm
    left join subscription_mrr sm
        on cm.customer_id = sm.customer_id
        and cm.month = sm.month
),

with_history as (
    select
        j.*,
        lag(mrr_usd) over (partition by customer_id order by month) as prior_mrr_usd,
        min(case when mrr_usd > 0 then month end) over (partition by customer_id) as first_mrr_month
    from joined j
),

final as (
    select
        customer_id,
        month,
        plan_id,
        mrr_usd,
        coalesce(prior_mrr_usd, 0) as prior_mrr_usd,
        case when mrr_usd > 0 and month = first_mrr_month
            then mrr_usd else 0 end as new_mrr,
        case when coalesce(prior_mrr_usd, 0) = 0 and mrr_usd > 0 and month != first_mrr_month
            then mrr_usd else 0 end as reactivation_mrr,
        case when prior_mrr_usd > 0 and mrr_usd > prior_mrr_usd
            then mrr_usd - prior_mrr_usd else 0 end as expansion_mrr,
        case when prior_mrr_usd > 0 and mrr_usd > 0 and mrr_usd < prior_mrr_usd
            then mrr_usd - prior_mrr_usd else 0 end as contraction_mrr,
        case when prior_mrr_usd > 0 and mrr_usd = 0
            then -prior_mrr_usd else 0 end as churned_mrr
    from with_history
)

select * from final
