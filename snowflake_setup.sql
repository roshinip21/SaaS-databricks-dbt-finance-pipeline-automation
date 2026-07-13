-- One-time Snowflake setup for the saas_analytics dbt project.
-- Run as a role with SECURITYADMIN + SYSADMIN privileges (e.g. ACCOUNTADMIN).
-- Adjust names/sizes as needed, then set the matching env vars from
-- profiles.yml.example before running dbt.

use role securityadmin;

create role if not exists saas_analytics_role;
create user if not exists saas_analytics_svc
    password = 'CHANGE_ME_STRONG_PASSWORD'
    default_role = saas_analytics_role
    default_warehouse = 'saas_analytics_wh'
    must_change_password = true;

grant role saas_analytics_role to user saas_analytics_svc;
grant role saas_analytics_role to role sysadmin;

use role sysadmin;

create warehouse if not exists saas_analytics_wh
    warehouse_size = 'xsmall'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true;

create database if not exists saas_analytics;

create schema if not exists saas_analytics.seed;
create schema if not exists saas_analytics.dbt_dev;
create schema if not exists saas_analytics.dbt_prod;

grant usage on warehouse saas_analytics_wh to role saas_analytics_role;
grant operate on warehouse saas_analytics_wh to role saas_analytics_role;

grant usage on database saas_analytics to role saas_analytics_role;
grant all on schema saas_analytics.seed to role saas_analytics_role;
grant all on schema saas_analytics.dbt_dev to role saas_analytics_role;
grant all on schema saas_analytics.dbt_prod to role saas_analytics_role;

-- future objects created by dbt runs
grant all on future tables in database saas_analytics to role saas_analytics_role;
grant all on future views in database saas_analytics to role saas_analytics_role;

-- sanity check
use role saas_analytics_role;
use warehouse saas_analytics_wh;
use database saas_analytics;
select current_role(), current_warehouse(), current_database();
