-- ===========================================================================
-- 32_gold_renewal_pipeline.sql  --  Forward renewal book (next 120 days)
-- ===========================================================================
-- One row per active contract whose renewal_date falls within the forward
-- window after AS_OF. Joined to health so the CSM view shows which dollars are
-- at risk. renewal_probability is health-driven; expose it as a Tableau
-- parameter for what-if forecasting.
--   renewal rate (historical) = renewed ARR / ARR that came up for renewal
--   -> computed in 34_gold_qbr_summary.sql from closed Renewal opps.
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.gold.gold_renewal_pipeline AS
WITH due AS (
    SELECT
        c.contract_id,
        c.account_id,
        c.total_arr                        AS arr_up_for_renewal,
        c.renewal_date,
        datediff(c.renewal_date, DATE'2026-08-01') AS days_to_renewal,
        c.term_months,
        c.billing_frequency
    FROM gtm.silver.contracts c
    WHERE c.status = 'Active'
      AND c.renewal_date >= DATE'2026-08-01'
      AND c.renewal_date <  DATE'2026-08-01' + INTERVAL 120 DAYS
),
open_renewal AS (   -- latest open Renewal opp per account, for stage context
    SELECT account_id, stage_name,
           row_number() OVER (PARTITION BY account_id ORDER BY close_date) AS rn
    FROM gtm.silver.opportunities
    WHERE opportunity_type = 'Renewal' AND is_closed = false
)
SELECT
    d.contract_id,
    d.account_id,
    h.account_name,
    h.segment,
    h.region,
    h.csm_owner,
    d.arr_up_for_renewal,
    d.renewal_date,
    d.days_to_renewal,
    d.term_months,
    d.billing_frequency,
    coalesce(orn.stage_name, 'Renewal - Not Started') AS renewal_stage,
    coalesce(h.health_score, 50)          AS health_score,
    coalesce(h.health_band, 'Amber')      AS health_band,
    -- health-driven probability; clamp to a sane band
    round(least(0.97, greatest(0.15,
        0.40 + (coalesce(h.health_score, 50) - 50) / 100.0)), 2) AS renewal_probability,
    round(d.arr_up_for_renewal *
        round(least(0.97, greatest(0.15,
        0.40 + (coalesce(h.health_score, 50) - 50) / 100.0)), 2), 0) AS forecast_renewed_arr,
    (coalesce(h.health_band, 'Amber') = 'Red'
        OR coalesce(h.health_score, 50) < 45)               AS at_risk
FROM due d
LEFT JOIN gtm.gold.gold_health_scores h ON h.account_id = d.account_id
LEFT JOIN open_renewal orn ON orn.account_id = d.account_id AND orn.rn = 1;
