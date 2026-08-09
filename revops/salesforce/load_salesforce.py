#!/usr/bin/env python3
"""Load the synthetic RevOps CSVs into a Salesforce Developer org.

Populates Accounts -> Opportunities / Contracts / Cases using the Bulk API via
simple-salesforce. Records are UPSERTED on External_Id__c, so the load is
idempotent and children resolve their parent Account by our synthetic id.

CREDENTIALS COME FROM THE ENVIRONMENT -- never hard-code or paste them:
    export SF_USERNAME='you@example.com'
    export SF_PASSWORD='yourPassword'
    export SF_SECURITY_TOKEN='yourSecurityToken'      # Setup > Reset My Security Token
    # optional: export SF_DOMAIN='login'              # 'login' (prod/dev) | 'test' (sandbox)

PREREQUISITES:
    pip install simple-salesforce
    Create the custom fields first -- see custom_fields.md.

USAGE:
    python3 load_salesforce.py            # load everything
    python3 load_salesforce.py --dry-run  # parse + map only, no API calls
"""
import argparse
import csv
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# our stage/priority/status vocab -> safe standard Salesforce picklist values
STAGE_MAP = {"Closed Won": "Closed Won", "Closed Lost": "Closed Lost"}
DEFAULT_OPEN_STAGE = "Negotiation/Review"
PRIORITY_MAP = {"Critical": "High", "High": "High", "Medium": "Medium", "Low": "Low"}
CASE_STATUS_MAP = {"Open": "New", "Closed": "Closed"}


def read_csv(name):
    with open(os.path.join(DATA_DIR, f"{name}.csv"), newline="") as f:
        return list(csv.DictReader(f))


def b(v):  # 'true'/'false' -> bool
    return str(v).strip().lower() == "true"


def num(v):
    return None if v in (None, "") else v


def build_payloads():
    accounts = read_csv("accounts")
    opps = read_csv("opportunities")
    contracts = read_csv("contracts")
    cases = read_csv("cases")

    acct_rows = [{
        "External_Id__c": a["account_id"],
        "Name": a["account_name"],
        "Account_Category__c": a["account_type"],           # Customer | Partner
        "Segment__c": num(a["segment"]) if a["segment"] != "Partner" else None,
        "Region__c": a["region"],
        "Industry__c": a["industry"],
        "CSM_Owner__c": num(a["csm_owner"]),
        "NumberOfEmployees": num(a["employee_count"]),
        "AnnualRevenue": num(a["annual_revenue"]),
    } for a in accounts]

    opp_rows = [{
        "External_Id__c": o["opportunity_id"],
        "Name": o["opportunity_name"],
        "Account__ExternalId": o["account_id"],             # resolved below
        "Partner__ExternalId": num(o["partner_account_id"]),  # resolved below
        "StageName": STAGE_MAP.get(o["stage_name"], DEFAULT_OPEN_STAGE),
        "Renewal_Stage__c": o["stage_name"] if o["opportunity_type"] == "Renewal" else None,
        "Opportunity_Category__c": o["opportunity_type"],
        "Amount": num(o["amount"]),
        "ARR__c": num(o["arr"]),
        "CloseDate": o["close_date"],
        "Partner_Sourced__c": b(o["partner_sourced"]),
        "Partner_Influenced__c": b(o["partner_influenced"]),
    } for o in opps]

    contract_rows = [{
        "External_Id__c": c["contract_id"],
        "Account__ExternalId": c["account_id"],
        "StartDate": c["start_date"],
        "ContractTerm": num(c["term_months"]),
        "Status": "Draft",
        "Total_ARR__c": num(c["total_arr"]),
        "Renewal_Date__c": c["renewal_date"],
        "Lifecycle_Status__c": c["status"],
        "Movement_Type__c": c["movement_type"],
    } for c in contracts]

    case_rows = [{
        "External_Id__c": c["case_id"],
        "Account__ExternalId": c["account_id"],
        "Priority": PRIORITY_MAP.get(c["priority"], "Medium"),
        "Status": CASE_STATUS_MAP.get(c["status"], "New"),
        "Case_Category__c": c["case_type"],
        "CSAT__c": num(c["csat"]),
    } for c in cases]

    return acct_rows, opp_rows, contract_rows, case_rows


def resolve_refs(rows, id_map, ref_field, target_field, required=True):
    """Replace a *__ExternalId placeholder with the real Salesforce Id."""
    out = []
    for r in rows:
        ext = r.pop(ref_field, None)
        if ext:
            sfid = id_map.get(ext)
            if sfid is None and required:
                raise KeyError(f"unresolved {ref_field}={ext}")
            if sfid:
                r[target_field] = sfid
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    acct_rows, opp_rows, contract_rows, case_rows = build_payloads()
    print(f"parsed: {len(acct_rows)} accounts, {len(opp_rows)} opps, "
          f"{len(contract_rows)} contracts, {len(case_rows)} cases")

    if args.dry_run:
        print("dry-run: no Salesforce calls made. Sample account:")
        print(acct_rows[0])
        return

    try:
        from simple_salesforce import Salesforce
    except ImportError:
        sys.exit("pip install simple-salesforce first")

    creds = {k: os.environ.get(v) for k, v in {
        "username": "SF_USERNAME", "password": "SF_PASSWORD",
        "security_token": "SF_SECURITY_TOKEN"}.items()}
    if not all(creds.values()):
        sys.exit("set SF_USERNAME, SF_PASSWORD, SF_SECURITY_TOKEN in the env")
    sf = Salesforce(domain=os.environ.get("SF_DOMAIN", "login"), **creds)

    # 1) upsert accounts on External_Id__c
    print("upserting accounts...")
    sf.bulk.Account.upsert(acct_rows, "External_Id__c", batch_size=200)

    # 2) map our account_id -> Salesforce Id
    recs = sf.query_all("SELECT Id, External_Id__c FROM Account WHERE External_Id__c != null")
    id_map = {r["External_Id__c"]: r["Id"] for r in recs["records"]}
    print(f"resolved {len(id_map)} account ids")

    # 3) children (resolve AccountId + partner lookup, then upsert)
    opp_rows = resolve_refs(opp_rows, id_map, "Account__ExternalId", "AccountId")
    opp_rows = resolve_refs(opp_rows, id_map, "Partner__ExternalId",
                            "Partner_Account__c", required=False)
    contract_rows = resolve_refs(contract_rows, id_map, "Account__ExternalId", "AccountId")
    case_rows = resolve_refs(case_rows, id_map, "Account__ExternalId", "AccountId")

    print("upserting opportunities...")
    sf.bulk.Opportunity.upsert(opp_rows, "External_Id__c", batch_size=200)
    print("upserting contracts...")
    sf.bulk.Contract.upsert(contract_rows, "External_Id__c", batch_size=200)
    print("upserting cases...")
    sf.bulk.Case.upsert(case_rows, "External_Id__c", batch_size=200)
    print("done. Data is in Salesforce; run databricks/05_ingest_salesforce.py next.")


if __name__ == "__main__":
    main()
