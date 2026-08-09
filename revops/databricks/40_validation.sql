-- ===========================================================================
-- 40_validation.sql  --  QA checks + headline KPI readout
-- ===========================================================================
-- Run after 00->34. Each check should return the expected result; the final
-- SELECT prints the numbers you'll quote in the interview. These mirror the
-- self-check the Python generator prints, so bronze/silver/gold should agree.
-- ===========================================================================

-- 1) Referential integrity: every child FK resolves to an account ---------
SELECT 'orphan_opportunities' AS check, count(*) AS bad_rows
FROM gtm.silver.opportunities o
LEFT JOIN gtm.silver.accounts a ON a.account_id = o.account_id
WHERE a.account_id IS NULL
UNION ALL
SELECT 'orphan_contracts', count(*)
FROM gtm.silver.contracts c
LEFT JOIN gtm.silver.accounts a ON a.account_id = c.account_id
WHERE a.account_id IS NULL
UNION ALL
SELECT 'orphan_cases', count(*)
FROM gtm.silver.cases c
LEFT JOIN gtm.silver.accounts a ON a.account_id = c.account_id
WHERE a.account_id IS NULL
UNION ALL
SELECT 'bad_partner_refs', count(*)
FROM gtm.silver.opportunities o
WHERE o.partner_account_id IS NOT NULL
  AND o.partner_account_id NOT IN (SELECT account_id FROM gtm.silver.accounts);

-- 2) Attribution invariant: sourced ARR must be <= influenced ARR ----------
SELECT 'sourced_le_influenced' AS check,
       count_if(sourced_arr > influenced_arr) AS violations
FROM gtm.gold.gold_partner_attribution;

-- 3) Waterfall ties to ending ARR: net movement should rebuild ending ARR --
--    (sum of all movement components across all months = current total ARR)
SELECT 'waterfall_reconciles' AS check,
       round(sum(new_arr + expansion_arr + contraction_arr
                 + churned_arr + reactivation_arr), 0) AS rebuilt_arr,
       (SELECT round(sum(ending_arr), 0) FROM gtm.gold.gold_arr_movement
        WHERE month = DATE'2026-08-01')                AS current_arr
FROM gtm.gold.gold_arr_movement;

-- 4) Renewal pipeline is populated ----------------------------------------
SELECT 'renewals_next_120d' AS check, count(*) AS contracts,
       round(sum(arr_up_for_renewal), 0) AS arr_up_for_renewal,
       count_if(at_risk) AS at_risk
FROM gtm.gold.gold_renewal_pipeline;

-- 5) HEADLINE KPIs (quote these) ------------------------------------------
SELECT
    format_number(total_arr, 0)              AS total_arr,
    format_number(net_new_arr_12m, 0)        AS net_new_arr_ttm,
    concat(cast(round(nrr * 100, 1) AS string), '%')            AS nrr,
    concat(cast(round(grr * 100, 1) AS string), '%')            AS grr,
    concat(cast(round(renewal_rate_12m * 100, 1) AS string), '%') AS renewal_rate,
    at_risk_accounts,
    format_number(at_risk_arr, 0)            AS at_risk_arr,
    format_number(partner_sourced_arr, 0)    AS partner_sourced_arr,
    format_number(partner_influenced_arr, 0) AS partner_influenced_arr,
    avg_health_score,
    red_accounts
FROM gtm.gold.gold_exec_kpis;
