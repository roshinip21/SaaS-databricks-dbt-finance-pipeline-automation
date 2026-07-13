with customers as (
    select * from {{ ref('stg_saas__customers') }}
),

current_subscription as (
    select *
    from {{ ref('fct_subscriptions') }}
    where is_current
),

invoice_totals as (
    select
        customer_id,
        count(*) as invoice_count,
        sum(amount_usd) as lifetime_invoiced_usd,
        sum(case when invoice_status = 'paid' then amount_usd else 0 end) as lifetime_paid_usd
    from {{ ref('stg_saas__invoices') }}
    group by 1
),

usage_totals as (
    select
        customer_id,
        count(*) as lifetime_usage_events,
        min(event_date) as first_usage_date,
        max(event_date) as last_usage_date
    from {{ ref('stg_saas__usage_events') }}
    group by 1
),

ticket_totals as (
    select
        customer_id,
        count(*) as lifetime_ticket_count,
        avg(satisfaction_score) as avg_satisfaction_score
    from {{ ref('stg_saas__support_tickets') }}
    group by 1
)

select
    c.customer_id,
    c.company_name,
    c.industry,
    c.country,
    c.employee_count,
    c.acquisition_channel,
    c.signup_date,
    cs.subscription_id as current_subscription_id,
    cs.plan_id as current_plan_id,
    cs.plan_name as current_plan_name,
    cs.tier as current_tier,
    cs.mrr_usd as current_mrr_usd,
    case when cs.subscription_id is not null then 'active' else 'churned' end as customer_status,
    coalesce(it.invoice_count, 0) as invoice_count,
    coalesce(it.lifetime_invoiced_usd, 0) as lifetime_invoiced_usd,
    coalesce(it.lifetime_paid_usd, 0) as lifetime_paid_usd,
    coalesce(ut.lifetime_usage_events, 0) as lifetime_usage_events,
    ut.first_usage_date,
    ut.last_usage_date,
    coalesce(tt.lifetime_ticket_count, 0) as lifetime_ticket_count,
    tt.avg_satisfaction_score
from customers c
left join current_subscription cs on c.customer_id = cs.customer_id
left join invoice_totals it on c.customer_id = it.customer_id
left join usage_totals ut on c.customer_id = ut.customer_id
left join ticket_totals tt on c.customer_id = tt.customer_id
