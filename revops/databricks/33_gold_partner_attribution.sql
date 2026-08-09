-- ===========================================================================
-- 33_gold_partner_attribution.sql  --  Partner sourced vs influenced ARR
-- ===========================================================================
-- One row per partner. Attribution is measured on WON, NET-NEW opportunities
-- only (New Business / Expansion / Reactivation) -- renewals are never
-- partner-sourced here.
--
--   *** sourced_arr and influenced_arr MUST NOT BE SUMMED ***
-- Partner_Influenced is the SUPERSET (every sourced deal is also influenced),
-- so influenced_arr >= sourced_arr and adding them double-counts sourced ARR.
-- In Tableau show them as SIDE-BY-SIDE bars, never stacked. influenced_only_arr
-- (= influenced - sourced) is provided if you want a clean stack instead.
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.gold.gold_partner_attribution AS
WITH net_new_won AS (
    SELECT arr, partner_account_id, partner_sourced, partner_influenced
    FROM gtm.silver.opportunities
    WHERE is_won = true AND is_net_new = true
),
company_total AS (
    SELECT sum(arr) AS total_net_new_arr FROM net_new_won
),
by_partner AS (
    SELECT
        partner_account_id,
        sum(CASE WHEN partner_sourced    THEN arr ELSE 0 END)  AS sourced_arr,
        sum(CASE WHEN partner_influenced THEN arr ELSE 0 END)  AS influenced_arr,
        sum(CASE WHEN partner_sourced    THEN 1 ELSE 0 END)    AS sourced_deals,
        sum(CASE WHEN partner_influenced THEN 1 ELSE 0 END)    AS influenced_deals
    FROM net_new_won
    WHERE partner_influenced = true          -- only opps a partner touched
    GROUP BY partner_account_id
)
SELECT
    p.account_id                           AS partner_account_id,
    p.account_name                         AS partner_name,
    p.region                               AS partner_region,
    bp.sourced_arr,
    bp.influenced_arr,
    (bp.influenced_arr - bp.sourced_arr)   AS influenced_only_arr,   -- stack-safe
    bp.sourced_deals,
    bp.influenced_deals,
    round(bp.sourced_arr    / nullif(ct.total_net_new_arr, 0), 4) AS pct_of_net_new_sourced,
    round(bp.influenced_arr / nullif(ct.total_net_new_arr, 0), 4) AS pct_of_net_new_influenced,
    round(bp.sourced_arr    / nullif(bp.sourced_deals, 0), 0)     AS avg_sourced_deal_arr
FROM by_partner bp
JOIN gtm.silver.accounts p ON p.account_id = bp.partner_account_id
CROSS JOIN company_total ct
ORDER BY bp.influenced_arr DESC;
