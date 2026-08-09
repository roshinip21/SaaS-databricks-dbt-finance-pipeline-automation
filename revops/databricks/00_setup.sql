-- ===========================================================================
-- 00_setup.sql  --  Unity Catalog scaffolding for the GTM RevOps demo
-- ===========================================================================
-- HOW TO RUN: open the Databricks SQL Editor in the "GTM" workspace, attach it
-- to a (2X-Small serverless) SQL warehouse, paste this in, and Run All.
--
-- Layout (medallion):
--   gtm.bronze  = raw Salesforce-shaped tables (loaded from CSV or ingested
--                 live from Salesforce)
--   gtm.silver  = cleaned / conformed + a month x account ARR spine
--   gtm.gold    = the 5 marts that feed the 4 Tableau dashboards
--
-- FREE EDITION NOTE: if your workspace can't CREATE CATALOG (metastore admin
-- restriction), skip the catalog line and instead use an existing catalog you
-- own -- e.g. `workspace` -- by replacing every `gtm.` below and in the other
-- scripts with `<your_catalog>.`. The schema + table structure is identical.
-- ===========================================================================

CREATE CATALOG IF NOT EXISTS gtm;

CREATE SCHEMA IF NOT EXISTS gtm.bronze;
CREATE SCHEMA IF NOT EXISTS gtm.silver;
CREATE SCHEMA IF NOT EXISTS gtm.gold;

-- A Unity Catalog Volume is the landing zone for the CSVs produced by
-- revops/generate_revops_data.py. Upload the 7 files from revops/data/ into
-- this volume before running 10_bronze_load_csv.sql (see that file's header).
CREATE VOLUME IF NOT EXISTS gtm.bronze.landing;

SHOW SCHEMAS IN gtm;
