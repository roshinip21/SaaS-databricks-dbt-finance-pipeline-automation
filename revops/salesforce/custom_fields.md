# Salesforce custom fields to create before loading

The synthetic data carries RevOps attributes that aren't standard Salesforce
fields (ARR, partner attribution, segment, health inputs). Create these custom
fields **once** in your Developer org before running `load_salesforce.py`.
Everything is stored on standard objects (Account, Opportunity, Contract, Case)
so the model still "looks like Salesforce."

Two ways to create them:
- **Clicks:** Setup → Object Manager → *object* → Fields & Relationships → New.
- **Metadata/CLI:** `sf project deploy` a set of `CustomField` metadata (faster
  if you're comfortable with the CLI).

Every object gets an **`External_Id__c`** (Text, **External ID**, **Unique**) —
the loader upserts on it, which makes loads idempotent and lets child records
resolve their parent by our synthetic id.

### Account
| Field | Type | Notes |
|---|---|---|
| `External_Id__c` | Text(20), External ID, Unique | = our `account_id` (e.g. `ACC-0007`) |
| `Account_Category__c` | Picklist: `Customer`, `Partner` | distinguishes partners from customers |
| `Segment__c` | Picklist: `SMB`, `Mid-Market`, `Enterprise` | |
| `Region__c` | Text(20) | NA / EMEA / APAC / LATAM |
| `Industry__c` | Text(60) | custom (avoids the restricted standard Industry picklist) |
| `CSM_Owner__c` | Text(120) | customer success owner |

*(Standard fields used as-is: `Name`, `NumberOfEmployees`, `AnnualRevenue`.)*

### Opportunity
| Field | Type | Notes |
|---|---|---|
| `External_Id__c` | Text(20), External ID, Unique | = our `opportunity_id` |
| `ARR__c` | Currency(14,2) | annual recurring revenue for the deal |
| `Opportunity_Category__c` | Picklist: `New Business`, `Renewal`, `Expansion` | our `opportunity_type` |
| `Partner_Sourced__c` | Checkbox | partner originated the deal |
| `Partner_Influenced__c` | Checkbox | partner touched the deal (superset of sourced) |
| `Partner_Account__c` | Lookup(Account) | the crediting partner |
| `Renewal_Stage__c` | Text(60) | detailed stage for open renewals |

*(Standard: `Name`, `CloseDate`, `Amount`. `StageName` is mapped to a standard
value — `Closed Won` / `Closed Lost` / `Negotiation/Review` — by the loader.)*

### Contract
| Field | Type | Notes |
|---|---|---|
| `External_Id__c` | Text(20), External ID, Unique | = our `contract_id` |
| `Total_ARR__c` | Currency(14,2) | |
| `Renewal_Date__c` | Date | |
| `Lifecycle_Status__c` | Picklist: `Active`, `Renewed`, `Churned` | our `status` (standard `Status` stays `Draft`) |
| `Movement_Type__c` | Text(30) | New Business / Renewal / Expansion / Contraction / Reactivation |

*(Standard: `AccountId`, `StartDate`, `ContractTerm`. Contracts load as `Draft`;
you do not need to Activate them for the demo.)*

### Case
| Field | Type | Notes |
|---|---|---|
| `External_Id__c` | Text(20), External ID, Unique | = our `case_id` |
| `CSAT__c` | Number(1,0) | 1–5 satisfaction, blank if open |
| `Case_Category__c` | Text(40) | our `case_type` |

*(Standard: `AccountId`, `Priority` [Critical→High mapped], `Status`
[Open→`New`, Closed→`Closed`].)*
