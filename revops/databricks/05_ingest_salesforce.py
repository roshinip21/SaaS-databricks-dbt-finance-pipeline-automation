# Databricks notebook source
# ===========================================================================
# 05_ingest_salesforce.py  --  Salesforce -> gtm.bronze (the REAL source path)
# ===========================================================================
# Run this as a Databricks notebook (Python). It pulls the Salesforce objects
# populated by salesforce/load_salesforce.py and writes them to gtm.bronze.*
# with the SAME column names the CSV loader produces -- so 20_silver.sql and all
# gold marts run downstream UNCHANGED, whichever source you used. That
# source-swappability is the whole point of the bronze boundary.
#
# This is the portable alternative to Lakeflow Connect's managed Salesforce
# connector (which may be gated on Free Edition).
#
# SETUP (once):
#   - Cluster library:  PyPI  simple-salesforce
#   - Store creds as Databricks secrets (never inline):
#       databricks secrets create-scope revops
#       databricks secrets put-secret revops sf_username
#       databricks secrets put-secret revops sf_password
#       databricks secrets put-secret revops sf_token
#
# NOTE on audit dates: Salesforce sets Case CreatedDate/ClosedDate at load time,
# so exact historical case timestamps live only in the CSV path. For a
# date-exact demo of the 90-day CSAT window, use 10_bronze_load_csv.sql; this
# path is for demonstrating the live ingestion architecture.
# ===========================================================================

# COMMAND ----------
from pyspark.sql import functions as F
from simple_salesforce import Salesforce

sf = Salesforce(
    username=dbutils.secrets.get("revops", "sf_username"),      # noqa: F821
    password=dbutils.secrets.get("revops", "sf_password"),      # noqa: F821
    security_token=dbutils.secrets.get("revops", "sf_token"),   # noqa: F821
    domain="login",
)

CATALOG = "gtm"  # change if you couldn't create the gtm catalog


def ingest(bronze_table, soql, rename):
    """Query Salesforce, drop SOQL 'attributes', rename to bronze schema, write."""
    records = sf.query_all(soql)["records"]
    for r in records:
        r.pop("attributes", None)
        # flatten relationship dot-fields (e.g. Partner_Account__r.External_Id__c)
        for k in list(r.keys()):
            if isinstance(r[k], dict):
                r[k].pop("attributes", None)
    if not records:
        print(f"{bronze_table}: 0 rows (nothing to ingest)")
        return
    sdf = spark.createDataFrame(records)                        # noqa: F821
    for src, dst in rename.items():
        sdf = sdf.withColumnRenamed(src, dst) if src in sdf.columns else sdf
    sdf = sdf.select(*rename.values())
    sdf.write.mode("overwrite").saveAsTable(f"{CATALOG}.bronze.{bronze_table}")
    print(f"{bronze_table}: wrote {sdf.count()} rows")


# COMMAND ----------
ingest("accounts",
    "SELECT External_Id__c, Name, Account_Category__c, Industry__c, Region__c, "
    "Segment__c, NumberOfEmployees, AnnualRevenue, CSM_Owner__c, CreatedDate "
    "FROM Account WHERE External_Id__c != null",
    {"External_Id__c": "account_id", "Name": "account_name",
     "Account_Category__c": "account_type", "Industry__c": "industry",
     "Region__c": "region", "Segment__c": "segment",
     "NumberOfEmployees": "employee_count", "AnnualRevenue": "annual_revenue",
     "CSM_Owner__c": "csm_owner", "CreatedDate": "created_date"})

# COMMAND ----------
ingest("opportunities",
    "SELECT External_Id__c, Account__r.External_Id__c, Name, Opportunity_Category__c, "
    "Renewal_Stage__c, StageName, Amount, ARR__c, CloseDate, IsWon, IsClosed, "
    "Partner_Sourced__c, Partner_Influenced__c, Partner_Account__r.External_Id__c, "
    "CreatedDate FROM Opportunity WHERE External_Id__c != null",
    {"External_Id__c": "opportunity_id", "Account__r.External_Id__c": "account_id",
     "Name": "opportunity_name", "Opportunity_Category__c": "opportunity_type",
     "Renewal_Stage__c": "stage_name", "Amount": "amount", "ARR__c": "arr",
     "CloseDate": "close_date", "IsWon": "is_won", "IsClosed": "is_closed",
     "Partner_Sourced__c": "partner_sourced",
     "Partner_Influenced__c": "partner_influenced",
     "Partner_Account__r.External_Id__c": "partner_account_id",
     "CreatedDate": "created_date"})

# COMMAND ----------
ingest("contracts",
    "SELECT External_Id__c, Account__r.External_Id__c, StartDate, EndDate, "
    "ContractTerm, Total_ARR__c, Lifecycle_Status__c, Renewal_Date__c, "
    "Movement_Type__c FROM Contract WHERE External_Id__c != null",
    {"External_Id__c": "contract_id", "Account__r.External_Id__c": "account_id",
     "StartDate": "start_date", "EndDate": "end_date", "ContractTerm": "term_months",
     "Total_ARR__c": "total_arr", "Lifecycle_Status__c": "status",
     "Renewal_Date__c": "renewal_date", "Movement_Type__c": "movement_type"})

# COMMAND ----------
ingest("cases",
    "SELECT External_Id__c, Account__r.External_Id__c, CreatedDate, ClosedDate, "
    "Priority, Status, Case_Category__c, CSAT__c FROM Case WHERE External_Id__c != null",
    {"External_Id__c": "case_id", "Account__r.External_Id__c": "account_id",
     "CreatedDate": "created_date", "ClosedDate": "closed_date", "Priority": "priority",
     "Status": "status", "Case_Category__c": "case_type", "CSAT__c": "csat"})

# COMMAND ----------
# billing_frequency isn't a Salesforce concept here; silver only reads it as a
# passthrough label, so default it if you ingested contracts from Salesforce.
spark.sql(f"""                                                   -- noqa: F821
  ALTER TABLE {CATALOG}.bronze.contracts ADD COLUMNS (billing_frequency string)
""")
spark.sql(f"UPDATE {CATALOG}.bronze.contracts SET billing_frequency = 'Annual' "
          f"WHERE billing_frequency IS NULL")                    # noqa: F821
print("Salesforce -> bronze complete. Continue with 20_silver.sql.")
