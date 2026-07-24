-- One-time Databricks (Unity Catalog) setup for the saas_analytics dbt project.
--
-- HOW TO RUN: open the Databricks SQL Editor, attach it to your SQL warehouse
-- (top-right selector), paste this in, and Run All. You need permission to
-- create catalogs -- on a trial workspace your default admin user has it.
--
-- dbt will also create these schemas on its own if they are missing, but
-- creating them up front lets you see the layout in the Catalog Explorer and
-- avoids any first-run permission surprises.

-- Catalog = top level of the 3-level namespace (catalog.schema.table).
-- Think of it as the Snowflake "database" equivalent.
CREATE CATALOG IF NOT EXISTS saas_analytics;

-- One schema per dbt layer. These match the +schema configs in dbt_project.yml
-- and the generate_schema_name macro, so models land in clean names like
-- saas_analytics.marts.fct_invoices.
CREATE SCHEMA IF NOT EXISTS saas_analytics.seed;          -- raw seed CSVs (dbt seed)
CREATE SCHEMA IF NOT EXISTS saas_analytics.staging;       -- staging views
CREATE SCHEMA IF NOT EXISTS saas_analytics.intermediate;  -- intermediate views
CREATE SCHEMA IF NOT EXISTS saas_analytics.marts;         -- final mart tables
CREATE SCHEMA IF NOT EXISTS saas_analytics.dbt_dev;       -- fallback default schema (dev target)
CREATE SCHEMA IF NOT EXISTS saas_analytics.dbt_prod;      -- fallback default schema (prod target)

-- Quick check
SHOW SCHEMAS IN saas_analytics;
