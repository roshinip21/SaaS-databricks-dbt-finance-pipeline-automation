-- ===========================================================================
-- 30_gold_arr_movement.sql  --  ARR waterfall per account per month
-- ===========================================================================
-- One row per customer per month with the classic movement decomposition:
--   new / expansion / contraction / churned / reactivation  -> ending ARR.
-- Sum by month for a company ARR waterfall; the trailing-12m rollup of these
-- columns is what yields NRR and GRR (see 34_gold_qbr_summary.sql).
--
-- Mirrors the repo's fct_mrr_monthly: a lag() over the ARR month spine.
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.gold.gold_arr_movement AS
WITH base AS (
    SELECT
        account_id,
        month,
        arr,
        lag(arr) OVER (PARTITION BY account_id ORDER BY month) AS prior_arr,
        min(CASE WHEN arr > 0 THEN month END)
            OVER (PARTITION BY account_id) AS first_active_month
    FROM gtm.silver.account_month_arr
)
SELECT
    account_id,
    month,
    arr                                    AS ending_arr,
    coalesce(prior_arr, 0)                 AS beginning_arr,
    -- first month a customer has ARR
    CASE WHEN arr > 0 AND month = first_active_month
         THEN arr ELSE 0 END               AS new_arr,
    -- came back from 0 after their first-ever active month
    CASE WHEN coalesce(prior_arr, 0) = 0 AND arr > 0 AND month <> first_active_month
         THEN arr ELSE 0 END               AS reactivation_arr,
    -- grew vs prior month
    CASE WHEN prior_arr > 0 AND arr > prior_arr
         THEN arr - prior_arr ELSE 0 END   AS expansion_arr,
    -- shrank but still active (negative)
    CASE WHEN prior_arr > 0 AND arr > 0 AND arr < prior_arr
         THEN arr - prior_arr ELSE 0 END   AS contraction_arr,
    -- dropped to 0 (negative)
    CASE WHEN prior_arr > 0 AND arr = 0
         THEN -prior_arr ELSE 0 END        AS churned_arr
FROM base;
