-- ===========================================================================
-- 20_silver.sql  --  Clean / conform bronze + build the ARR month spine
-- ===========================================================================
-- AS_OF anchor for the whole model. It matches AS_OF in
-- revops/generate_revops_data.py. If you regenerate the data with a different
-- anchor, change every DATE'2026-08-01' below to match.
-- ===========================================================================

-- --- accounts: split customers vs partners, type the numerics --------------
CREATE OR REPLACE TABLE gtm.silver.accounts AS
SELECT
    account_id,
    account_name,
    account_type,                                   -- 'Customer' | 'Partner'
    industry,
    region,
    segment,                                        -- SMB | Mid-Market | Enterprise
    try_cast(employee_count AS int)        AS employee_count,
    try_cast(annual_revenue AS bigint)     AS annual_revenue,
    csm_owner,
    to_date(created_date)                  AS created_date
FROM gtm.bronze.accounts;

-- --- opportunities: type amounts/flags; mark net-new vs renewal ------------
-- Partner credit lives ONLY on net-new opps (New Business / Expansion /
-- Reactivation). Renewals are never partner-sourced in this model.
CREATE OR REPLACE TABLE gtm.silver.opportunities AS
SELECT
    opportunity_id,
    account_id,
    opportunity_name,
    opportunity_type,                               -- New Business | Renewal | Expansion
    stage_name,
    try_cast(amount AS double)             AS amount,
    try_cast(arr AS double)                AS arr,
    to_date(close_date)                    AS close_date,
    try_cast(is_won AS boolean)            AS is_won,
    try_cast(is_closed AS boolean)         AS is_closed,
    try_cast(partner_sourced AS boolean)   AS partner_sourced,
    try_cast(partner_influenced AS boolean) AS partner_influenced,
    nullif(partner_account_id, '')         AS partner_account_id,
    to_date(created_date)                  AS created_date,
    (opportunity_type IN ('New Business', 'Expansion')) AS is_net_new
FROM gtm.bronze.opportunities;

-- --- contracts: one contiguous ARR segment per row ------------------------
CREATE OR REPLACE TABLE gtm.silver.contracts AS
SELECT
    contract_id,
    account_id,
    to_date(start_date)                    AS start_date,
    to_date(end_date)                      AS end_date,
    try_cast(term_months AS int)           AS term_months,
    billing_frequency,
    try_cast(total_arr AS double)          AS total_arr,
    status,                                         -- Active | Renewed | Churned
    to_date(renewal_date)                  AS renewal_date,
    movement_type
FROM gtm.bronze.contracts;

-- --- cases: type timestamps + derived support flags -----------------------
CREATE OR REPLACE TABLE gtm.silver.cases AS
SELECT
    case_id,
    account_id,
    to_timestamp(created_date)             AS created_at,
    to_timestamp(closed_date)              AS closed_at,
    priority,
    status,                                         -- Open | Closed
    case_type,
    try_cast(csat AS int)                  AS csat,
    (status = 'Open')                              AS is_open,
    (priority IN ('High', 'Critical'))             AS is_high_priority
FROM gtm.bronze.cases;

-- --- usage: type the monthly adoption signal ------------------------------
CREATE OR REPLACE TABLE gtm.silver.usage_monthly AS
SELECT
    account_id,
    to_date(usage_month)                   AS usage_month,
    try_cast(active_users AS int)          AS active_users,
    try_cast(feature_adoption_pct AS double) AS feature_adoption_pct,
    try_cast(logins AS bigint)             AS logins,
    try_cast(events AS bigint)             AS events
FROM gtm.bronze.usage_monthly;

-- --- account_month_arr: THE SPINE -----------------------------------------
-- One row per customer per calendar month from their first contract month
-- through AS_OF, carrying the ARR of the contract ACTIVE on the first of that
-- month (0 in post-churn gaps). Contracts are contiguous half-open periods
-- [start, end): B.start = A.end, so exactly one contract is active on any given
-- date -- no gaps, no overlaps, and a contract that renews later in the current
-- month is still counted this month (which a month-truncated join would drop).
-- Gold's ARR waterfall is a lag() over this table -- the same pattern as the
-- repo's int_month_spine -> fct_mrr_monthly.
CREATE OR REPLACE TABLE gtm.silver.account_month_arr AS
WITH months AS (
    SELECT explode(sequence(
        (SELECT date_trunc('month', min(start_date)) FROM gtm.silver.contracts),
        DATE'2026-08-01',
        INTERVAL 1 MONTH)) AS month
),
cust AS (
    SELECT account_id, date_trunc('month', min(start_date)) AS first_month
    FROM gtm.silver.contracts
    GROUP BY account_id
),
account_months AS (
    SELECT cust.account_id, m.month
    FROM cust
    JOIN months m ON m.month >= cust.first_month
)
SELECT
    am.account_id,
    am.month,
    coalesce(max(ct.total_arr), 0) AS arr
FROM account_months am
LEFT JOIN gtm.silver.contracts ct
    ON ct.account_id = am.account_id
   AND ct.start_date <= am.month      -- active on the first of the month...
   AND ct.end_date   >  am.month      -- ...using actual dates, not truncated
GROUP BY am.account_id, am.month;

-- --- account_current: current ARR + active flag as of AS_OF ---------------
CREATE OR REPLACE TABLE gtm.silver.account_current AS
SELECT
    a.account_id,
    a.account_name,
    a.segment,
    a.industry,
    a.region,
    a.csm_owner,
    coalesce(amc.arr, 0)        AS current_arr,
    (coalesce(amc.arr, 0) > 0)  AS is_active
FROM gtm.silver.accounts a
LEFT JOIN gtm.silver.account_month_arr amc
    ON amc.account_id = a.account_id AND amc.month = DATE'2026-08-01'
WHERE a.account_type = 'Customer';

-- --- verification: confirms every table above was actually created --------
-- IMPORTANT: this script has 7 CREATE TABLE statements. In the Databricks SQL
-- Editor, "Run" alone only executes the statement under your cursor -- use
-- "Run All" (select all text first) so every statement runs, including these
-- last two tables that the gold marts depend on directly. If any row below
-- shows anything other than 'OK', re-run this whole script with Run All
-- before moving on to the gold scripts.
SELECT 'accounts' AS expected_table,
       CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END AS status
FROM gtm.silver.accounts
UNION ALL
SELECT 'opportunities', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.opportunities
UNION ALL
SELECT 'contracts', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.contracts
UNION ALL
SELECT 'cases', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.cases
UNION ALL
SELECT 'usage_monthly', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.usage_monthly
UNION ALL
SELECT 'account_month_arr', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.account_month_arr
UNION ALL
SELECT 'account_current', CASE WHEN count(*) > 0 THEN 'OK' ELSE 'MISSING' END FROM gtm.silver.account_current;
