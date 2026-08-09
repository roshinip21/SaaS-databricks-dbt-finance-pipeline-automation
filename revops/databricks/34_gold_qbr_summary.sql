-- ===========================================================================
-- 34_gold_qbr_summary.sql  --  Executive rollup: monthly trend + KPI snapshot
-- ===========================================================================
-- Produces TWO gold tables that feed the Executive QBR Summary tab:
--   gold_qbr_summary  -- one row per month: ARR waterfall components + counts
--   gold_exec_kpis    -- single-row headline snapshot (NRR, GRR, renewal rate,
--                        at-risk, partner sourced/influenced) as of AS_OF
-- Definitions (trailing 12 months, start = ending ARR 12 months before AS_OF):
--   NRR = (start + expansion + contraction + churn) / start
--   GRR = (start + contraction + churn) / start      (contraction, churn < 0)
--   Renewal rate = renewed ARR / ARR that came up for renewal
-- Reactivation is excluded from NRR/GRR (standard, conservative).
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.gold.gold_qbr_summary AS
SELECT
    month,
    round(sum(ending_arr), 0)          AS ending_arr,
    round(sum(new_arr), 0)             AS new_arr,
    round(sum(expansion_arr), 0)       AS expansion_arr,
    round(sum(contraction_arr), 0)     AS contraction_arr,
    round(sum(churned_arr), 0)         AS churned_arr,
    round(sum(reactivation_arr), 0)    AS reactivation_arr,
    round(sum(new_arr + expansion_arr + contraction_arr
              + churned_arr + reactivation_arr), 0) AS net_new_arr,
    count_if(ending_arr > 0)           AS active_customers
FROM gtm.gold.gold_arr_movement
GROUP BY month;

-- --------------------------------------------------------------------------
CREATE OR REPLACE TABLE gtm.gold.gold_exec_kpis AS
WITH mv AS (
    SELECT * FROM gtm.gold.gold_arr_movement
),
-- NRR/GRR are COHORT-based: measured only on customers that had ARR 12 months
-- before AS_OF. New-logo movement inside the window is (correctly) excluded.
cohort AS (
    SELECT account_id FROM mv WHERE month = DATE'2025-08-01' AND ending_arr > 0
),
cohort_agg AS (
    SELECT
        sum(CASE WHEN mv.month = DATE'2025-08-01' THEN ending_arr ELSE 0 END) AS start_arr,
        sum(CASE WHEN mv.month > DATE'2025-08-01' THEN expansion_arr ELSE 0 END)   AS expansion,
        sum(CASE WHEN mv.month > DATE'2025-08-01' THEN contraction_arr ELSE 0 END) AS contraction,
        sum(CASE WHEN mv.month > DATE'2025-08-01' THEN churned_arr ELSE 0 END)     AS churn
    FROM mv JOIN cohort USING (account_id)
),
company AS (   -- company-wide totals (all accounts)
    SELECT
        sum(CASE WHEN month = DATE'2026-08-01' THEN ending_arr ELSE 0 END) AS total_arr,
        sum(CASE WHEN month > DATE'2025-08-01' THEN new_arr ELSE 0 END)    AS new_12m,
        sum(CASE WHEN month > DATE'2025-08-01' THEN
            new_arr + expansion_arr + contraction_arr
            + churned_arr + reactivation_arr ELSE 0 END)                   AS net_new_12m
    FROM mv
),
renewals AS (   -- trailing-12m renewal rate from closed Renewal opps
    SELECT
        sum(CASE WHEN is_won THEN arr ELSE 0 END) AS renewed_arr,
        sum(arr)                                  AS due_arr
    FROM gtm.silver.opportunities
    WHERE opportunity_type = 'Renewal' AND is_closed = true
      AND close_date > DATE'2025-08-01' AND close_date <= DATE'2026-08-01'
),
risk AS (
    SELECT count(*) AS at_risk_accounts, coalesce(sum(arr_up_for_renewal), 0) AS at_risk_arr
    FROM gtm.gold.gold_renewal_pipeline WHERE at_risk
),
partner AS (
    SELECT coalesce(sum(sourced_arr), 0)    AS partner_sourced_arr,
           coalesce(sum(influenced_arr), 0) AS partner_influenced_arr
    FROM gtm.gold.gold_partner_attribution
),
health AS (
    SELECT round(avg(health_score), 1) AS avg_health_score,
           count_if(health_band = 'Red') AS red_accounts
    FROM gtm.gold.gold_health_scores
)
SELECT
    DATE'2026-08-01'                       AS as_of_date,
    c.total_arr,
    c.new_12m                              AS new_arr_12m,
    c.net_new_12m                          AS net_new_arr_12m,
    round((ca.start_arr + ca.expansion + ca.contraction + ca.churn)
          / nullif(ca.start_arr, 0), 4)    AS nrr,
    round((ca.start_arr + ca.contraction + ca.churn)
          / nullif(ca.start_arr, 0), 4)    AS grr,
    round(-ca.churn / nullif(ca.start_arr, 0), 4) AS gross_churn_rate,
    round(r.renewed_arr / nullif(r.due_arr, 0), 4) AS renewal_rate_12m,
    rk.at_risk_accounts,
    rk.at_risk_arr,
    pt.partner_sourced_arr,
    pt.partner_influenced_arr,             -- NOTE: superset of sourced; do not sum
    h.avg_health_score,
    h.red_accounts
FROM cohort_agg ca
CROSS JOIN company c
CROSS JOIN renewals r
CROSS JOIN risk rk
CROSS JOIN partner pt
CROSS JOIN health h;
