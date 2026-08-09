-- ===========================================================================
-- 10_bronze_load_csv.sql  --  Load bronze from the synthetic CSVs
-- ===========================================================================
-- This is the GUARANTEED-WORKING demo path: no Salesforce required. (For the
-- live Salesforce -> bronze path, run 05_ingest_salesforce.py instead; it
-- creates the same gtm.bronze.* tables, after which silver/gold are identical.)
--
-- PREREQUISITE -- upload the CSVs to the volume first. Either:
--   (a) Catalog Explorer > gtm > bronze > landing > Upload to this volume, and
--       drop in all 7 files from revops/data/, OR
--   (b) Databricks CLI:
--         databricks fs cp --overwrite --recursive \
--           revops/data/ dbfs:/Volumes/gtm/bronze/landing/
--
-- read_files() infers types from the CSV header/content; the silver layer does
-- the authoritative casting, so inference variance here is harmless.
-- CREATE OR REPLACE makes this script safely re-runnable.
-- ===========================================================================

CREATE OR REPLACE TABLE gtm.bronze.accounts AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/accounts.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.opportunities AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/opportunities.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.contracts AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/contracts.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.cases AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/cases.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.usage_monthly AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/usage_monthly.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.campaigns AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/campaigns.csv',
  format => 'csv', header => true, inferSchema => true);

CREATE OR REPLACE TABLE gtm.bronze.campaign_members AS
SELECT * FROM read_files('/Volumes/gtm/bronze/landing/campaign_members.csv',
  format => 'csv', header => true, inferSchema => true);

-- sanity: row counts
SELECT 'accounts' t, count(*) n FROM gtm.bronze.accounts
UNION ALL SELECT 'opportunities', count(*) FROM gtm.bronze.opportunities
UNION ALL SELECT 'contracts', count(*) FROM gtm.bronze.contracts
UNION ALL SELECT 'cases', count(*) FROM gtm.bronze.cases
UNION ALL SELECT 'usage_monthly', count(*) FROM gtm.bronze.usage_monthly
UNION ALL SELECT 'campaigns', count(*) FROM gtm.bronze.campaigns
UNION ALL SELECT 'campaign_members', count(*) FROM gtm.bronze.campaign_members;
