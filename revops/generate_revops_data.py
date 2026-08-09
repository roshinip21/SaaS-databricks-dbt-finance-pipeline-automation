#!/usr/bin/env python3
"""Generate synthetic, Salesforce-shaped RevOps data for the Cohere demo.

Writes CSVs to revops/data/. Deterministic (fixed random seed) and pure
stdlib -- no external dependencies -- so re-running produces identical output.

The data models a GTM motion for an enterprise-AI vendor:
  Accounts (customers + partners) -> Opportunities (new/renewal/expansion) ->
  Contracts (ARR by period) -> Cases (support) -> monthly product Usage.

Design choices that make the downstream marts meaningful:
  * ARR movement is driven by contiguous Contract "segments" (one ARR per
    period). Silver builds a month x account ARR spine from these; gold
    computes the new/expansion/contraction/churn/reactivation waterfall via
    lag(), exactly like the existing fct_mrr_monthly model.
  * Partner credit is attributed only on NET-NEW opportunities (New Business,
    Expansion, Reactivation) -- never on renewals. Partner_Influenced is the
    SUPERSET; Partner_Sourced is the SUBSET (every sourced deal is also
    influenced). That is why influenced_arr and sourced_arr are reported
    side by side and MUST NOT be summed -- summing double-counts sourced ARR.
  * A per-account latent "health" drives churn, expansion, support load, CSAT,
    and usage trend, so red-health accounts genuinely correlate with churn and
    show up as at-risk in the renewal pipeline.
"""
import calendar
import csv
import os
import random
from datetime import date, datetime, timedelta

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# "As of" anchor for the whole dataset. Renewals landing in the forward window
# after this date populate the renewal pipeline.
AS_OF = date(2026, 8, 1)
HISTORY_START = date(2023, 1, 1)
FORWARD_WINDOW_DAYS = 120  # renewals due within this window are "in pipeline"

N_CUSTOMERS = 200
N_PARTNERS = 15

INDUSTRIES = [
    "Software", "Financial Services", "Healthcare", "Retail", "Manufacturing",
    "Media & Entertainment", "Telecommunications", "Public Sector",
    "Professional Services", "Insurance", "Logistics", "Education",
]
REGIONS = [("NA", 0.5), ("EMEA", 0.28), ("APAC", 0.15), ("LATAM", 0.07)]
CSM_OWNERS = [
    "Ava Chen", "Marcus Reed", "Priya Nair", "Diego Alvarez", "Sofia Rossi",
    "Liam O'Brien", "Yuki Tanaka", "Nadia Haddad",
]
COMPANY_PREFIXES = [
    "Brightline", "Northwind", "Vertex", "Cascade", "Summit", "Ironclad",
    "Bluepeak", "Redwood", "Silverline", "Nova", "Crestpoint", "Meridian",
    "Anchor", "Fieldstone", "Lighthouse", "Trailhead", "Orbital", "Granite",
    "Harborview", "Sterling", "Cobalt", "Junction", "Wavefront", "Pinnacle",
    "Clearwater", "Foundry", "Beacon", "Outrider", "Longview", "Catalyst",
    "Kestrel", "Monarch", "Aster", "Bramble", "Cinder", "Dovetail",
]
COMPANY_SUFFIXES = [
    "Labs", "Technologies", "Systems", "Solutions", "Group", "Works",
    "Analytics", "Software", "Digital", "Networks", "Holdings", "Industries",
]
PARTNER_NAMES = [
    "Accolade Consulting", "BlueSky Cloud Partners", "Convergent SI",
    "Datawave Advisory", "Elevate Digital", "Fulcrum Integrations",
    "Greenlight Partners", "Horizon Cloud Group", "Insight GSI",
    "Junction Consulting", "Keystone Advisors", "Lumina Partners",
    "Momentum SI", "Northstar Cloud", "Optima Consulting",
]

CASE_TYPES = ["Bug", "How-To", "Feature Request", "Integration",
              "Performance", "Billing", "Onboarding", "Outage"]
CASE_PRIORITIES = [("Low", 0.4), ("Medium", 0.35), ("High", 0.2), ("Critical", 0.05)]

RENEWAL_STAGES_OPEN = ["Renewal - Discovery", "Renewal - Negotiation",
                       "Renewal - Quoted", "Renewal - Verbal Commit"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def weighted_choice(pairs):
    values, weights = zip(*pairs)
    return random.choices(values, weights=weights, k=1)[0]


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def month_floor(d):
    return date(d.year, d.month, 1)


def round_to_1000(x):
    return max(1000, int(round(x / 1000.0)) * 1000)


def random_date(start, end):
    if end <= start:
        return start
    return start + timedelta(days=random.randint(0, (end - start).days))


def fmt(d):
    return d.isoformat() if d else ""


def write_csv(name, header, rows):
    path = os.path.join(DATA_DIR, f"{name}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {len(rows):>6} rows -> revops/data/{name}.csv")


os.makedirs(DATA_DIR, exist_ok=True)

# --------------------------------------------------------------------------- #
# 1. accounts (partners first, then customers)
# --------------------------------------------------------------------------- #
accounts = []            # csv rows
partner_ids = []
customer_meta = {}       # account_id -> dict(health, segment, employees, created)

for i, pname in enumerate(PARTNER_NAMES[:N_PARTNERS], start=1):
    acc_id = f"PRT-{i:04d}"
    partner_ids.append(acc_id)
    region = weighted_choice(REGIONS)
    accounts.append([
        acc_id, pname, "Partner", "Professional Services", region,
        "Partner", "", "", "", fmt(random_date(HISTORY_START, AS_OF)),
    ])

used_names = set()
for c in range(1, N_CUSTOMERS + 1):
    acc_id = f"ACC-{c:04d}"
    for _ in range(1000):
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"
        if name not in used_names:
            used_names.add(name)
            break
    else:
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)} {c}"
    employees = random.choice([25, 50, 100, 250, 500, 1000, 2500, 5000, 10000])
    if employees <= 100:
        segment, base_lo, base_hi = "SMB", 4_000, 20_000
    elif employees <= 1000:
        segment, base_lo, base_hi = "Mid-Market", 20_000, 90_000
    else:
        segment, base_lo, base_hi = "Enterprise", 90_000, 450_000
    industry = random.choice(INDUSTRIES)
    region = weighted_choice(REGIONS)
    csm = random.choice(CSM_OWNERS)
    annual_revenue = employees * random.randint(120_000, 400_000)
    created = random_date(HISTORY_START, AS_OF - timedelta(days=60))
    health = random.random()  # latent 0..1, drives everything downstream
    base_arr = round_to_1000(random.uniform(base_lo, base_hi))
    accounts.append([
        acc_id, name, "Customer", industry, region, segment,
        employees, annual_revenue, csm, fmt(created),
    ])
    customer_meta[acc_id] = dict(
        health=health, segment=segment, employees=employees,
        created=created, base_arr=base_arr,
    )

write_csv(
    "accounts",
    ["account_id", "account_name", "account_type", "industry", "region",
     "segment", "employee_count", "annual_revenue", "csm_owner", "created_date"],
    accounts,
)

# --------------------------------------------------------------------------- #
# 2 & 3. opportunities + contracts (driven by a per-account lifecycle)
# --------------------------------------------------------------------------- #
opportunities = []
contracts = []
opp_seq = 0
con_seq = 0
# collect (account_id, opportunity_id, partner_account_id) for campaign members
influenced_links = []


def new_opp_id():
    global opp_seq
    opp_seq += 1
    return f"OPP-{opp_seq:05d}"


def new_con_id():
    global con_seq
    con_seq += 1
    return f"CON-{con_seq:05d}"


def assign_partner(net_new=True):
    """Return (sourced, influenced, partner_id). Influenced is the superset."""
    if net_new and random.random() < 0.42:
        influenced = True
        partner_id = random.choice(partner_ids)
        sourced = random.random() < 0.45  # subset of influenced
        return sourced, influenced, partner_id
    return False, False, ""


def decide_outcome(health):
    if random.random() < 0.16 + (1 - health) * 0.22:
        return "churn"
    r = random.random()
    p_expand = 0.25 + health * 0.35
    p_contract = 0.05 + (1 - health) * 0.15
    if r < p_expand:
        return "expand"
    if r < p_expand + p_contract:
        return "contract"
    return "flat"


def add_opp(account_id, otype, stage, amount, arr, close_date,
            is_won, is_closed, net_new):
    sourced, influenced, partner_id = (assign_partner(net_new)
                                       if is_won and net_new else (False, False, ""))
    oid = new_opp_id()
    created = close_date - timedelta(days=random.randint(20, 90))
    opportunities.append([
        oid, account_id, f"{account_id} - {otype}", otype, stage,
        round(amount, 2), round(arr, 2), fmt(close_date),
        "true" if is_won else "false", "true" if is_closed else "false",
        "true" if sourced else "false", "true" if influenced else "false",
        partner_id, fmt(created),
    ])
    if influenced:
        influenced_links.append((account_id, oid, partner_id))
    return oid


# per-account latent store, and current-state facts for later marts
account_state = {}  # account_id -> dict(current_arr, status, renewal_date, health, ...)

for acc_id, meta in customer_meta.items():
    health = meta["health"]
    created = meta["created"]
    cur_arr = meta["base_arr"]
    term = weighted_choice([(12, 0.72), (24, 0.18), (36, 0.10)])
    billing = weighted_choice([("Annual", 0.6), ("Monthly", 0.4)])
    cur_start = created
    seg_type = "New Business"
    churned = False
    guard = 0

    # opening New Business win
    add_opp(acc_id, "New Business", "Closed Won",
            cur_arr * term / 12.0, cur_arr, cur_start, True, True, net_new=True)

    while guard < 12:
        guard += 1
        cur_end = add_months(cur_start, term)

        # ---- record the contract segment covering [cur_start, cur_end) ----
        if cur_end > AS_OF:
            status = "Active"
        else:
            status = "Renewed"  # provisionally; may become Churned below
        contracts.append([
            new_con_id(), acc_id, fmt(cur_start), fmt(cur_end), term, billing,
            round(cur_arr, 2), status, fmt(cur_end), seg_type,
        ])
        seg_index = len(contracts) - 1

        if cur_end > AS_OF:
            # current active contract; open renewal opp if renewal is imminent
            renewal_date = cur_end
            if cur_end <= AS_OF + timedelta(days=FORWARD_WINDOW_DAYS):
                prob = round(min(0.95, max(0.15, 0.45 + (health - 0.5) * 0.8)), 2)
                add_opp(acc_id, "Renewal", random.choice(RENEWAL_STAGES_OPEN),
                        cur_arr, cur_arr, cur_end, False, False, net_new=False)
                account_state.setdefault(acc_id, {})["renewal_probability"] = prob
            account_state.setdefault(acc_id, {}).update(
                current_arr=cur_arr, status="Active", renewal_date=renewal_date,
            )
            break

        # ---- contract ended in the past: decide renewal outcome ----
        outcome = decide_outcome(health)
        if outcome == "churn":
            contracts[seg_index][7] = "Churned"       # status
            add_opp(acc_id, "Renewal", "Closed Lost", cur_arr, cur_arr,
                    cur_end, False, True, net_new=False)
            # small chance of win-back later
            if random.random() < 0.15:
                gap = random.randint(2, 10)
                react_start = add_months(cur_end, gap)
                if react_start < AS_OF:
                    cur_start = react_start
                    cur_arr = round_to_1000(cur_arr * random.uniform(0.7, 1.1))
                    seg_type = "Reactivation"
                    add_opp(acc_id, "New Business", "Closed Won",
                            cur_arr * term / 12.0, cur_arr, react_start,
                            True, True, net_new=True)
                    continue
            churned = True
            account_state.setdefault(acc_id, {}).update(
                current_arr=0, status="Churned", renewal_date=cur_end,
            )
            break

        # renewed: base renewal win at prior ARR
        add_opp(acc_id, "Renewal", "Closed Won", cur_arr, cur_arr,
                cur_end, True, True, net_new=False)
        if outcome == "expand":
            increment = round_to_1000(cur_arr * random.uniform(0.12, 0.45))
            add_opp(acc_id, "Expansion", "Closed Won",
                    increment, increment, cur_end, True, True, net_new=True)
            cur_arr = cur_arr + increment
            seg_type = "Expansion"
        elif outcome == "contract":
            cur_arr = round_to_1000(cur_arr * random.uniform(0.6, 0.88))
            seg_type = "Contraction"
        else:
            seg_type = "Renewal"
        cur_start = cur_end

    account_state.setdefault(acc_id, {})
    account_state[acc_id].setdefault("current_arr", cur_arr if not churned else 0)
    account_state[acc_id].setdefault("status", "Active")
    account_state[acc_id]["health"] = health

write_csv(
    "opportunities",
    ["opportunity_id", "account_id", "opportunity_name", "opportunity_type",
     "stage_name", "amount", "arr", "close_date", "is_won", "is_closed",
     "partner_sourced", "partner_influenced", "partner_account_id", "created_date"],
    opportunities,
)
write_csv(
    "contracts",
    ["contract_id", "account_id", "start_date", "end_date", "term_months",
     "billing_frequency", "total_arr", "status", "renewal_date", "movement_type"],
    contracts,
)

# --------------------------------------------------------------------------- #
# recent-risk cohort: active accounts that are deteriorating RIGHT NOW (usage
# dip + fresh high-sev cases) even though they haven't churned. This is exactly
# what a health score should catch early, and gives the demo a real Red/Amber
# at-risk segment. Drawn here (after all ARR/contract logic) so it perturbs only
# cases + usage, never ARR -- the headline ARR stays deterministic.
# --------------------------------------------------------------------------- #
recent_risk = {}
for acc_id in customer_meta:
    if account_state[acc_id]["status"] == "Active" and random.random() < 0.17:
        recent_risk[acc_id] = True

# --------------------------------------------------------------------------- #
# 4. cases (support signal; low health -> more, higher priority, lower CSAT)
# --------------------------------------------------------------------------- #
cases = []
case_seq = 0
# quick lookup of an account's overall active window for scattering activity
acct_first_start = {}
acct_last_cov_end = {}
for row in contracts:
    aid, s, e = row[1], date.fromisoformat(row[2]), date.fromisoformat(row[3])
    acct_first_start[aid] = min(acct_first_start.get(aid, s), s)
    acct_last_cov_end[aid] = max(acct_last_cov_end.get(aid, e), e)

for acc_id, meta in customer_meta.items():
    health = meta["health"]
    first = acct_first_start.get(acc_id, meta["created"])
    last = min(acct_last_cov_end.get(acc_id, AS_OF), AS_OF)
    if last <= first:
        continue
    as_of_dt = datetime.combine(AS_OF, datetime.min.time())
    n_cases = random.randint(0, 3 + int((1 - health) * 10))
    for _ in range(n_cases):
        case_seq += 1
        created_day = random_date(first, last)
        created = datetime.combine(created_day, datetime.min.time()) + timedelta(
            hours=random.randint(0, 23), minutes=random.randint(0, 59))
        priority = weighted_choice(CASE_PRIORITIES)
        ctype = random.choice(CASE_TYPES)
        # unhealthy accounts leave more cases open, especially recent/high sev
        close_prob = 0.6 + health * 0.35
        recent = (AS_OF - created_day).days <= 45
        if recent and health < 0.4 and priority in ("High", "Critical"):
            close_prob = 0.2
        if random.random() < close_prob:
            resolve_hours = {"Critical": 6, "High": 36, "Medium": 96, "Low": 240}[priority]
            closed = min(created + timedelta(hours=random.randint(2, resolve_hours)), as_of_dt)
            status = "Closed"
            csat = max(1, min(5, round(random.gauss(2.6 + health * 2.0, 0.8))))
        else:
            closed = None
            status = "Open"
            csat = ""
        cases.append([
            f"CAS-{case_seq:05d}", acc_id, created.isoformat(sep=" "),
            closed.isoformat(sep=" ") if closed else "",
            priority, status, ctype, csat,
        ])

# fresh high-severity OPEN cases for the recent-risk cohort (last 30 days)
for acc_id in recent_risk:
    for _ in range(random.randint(1, 2)):
        case_seq += 1
        created_day = AS_OF - timedelta(days=random.randint(3, 30))
        created = datetime.combine(created_day, datetime.min.time()) + timedelta(
            hours=random.randint(0, 23), minutes=random.randint(0, 59))
        cases.append([
            f"CAS-{case_seq:05d}", acc_id, created.isoformat(sep=" "), "",
            random.choice(["High", "Critical"]), "Open",
            random.choice(CASE_TYPES), "",
        ])

write_csv(
    "cases",
    ["case_id", "account_id", "created_date", "closed_date", "priority",
     "status", "case_type", "csat"],
    cases,
)

# --------------------------------------------------------------------------- #
# 5. usage_monthly (adoption signal; declines before churn)
# --------------------------------------------------------------------------- #
usage = []
# build per-account month->arr coverage from contracts to know active months
coverage = {}  # account_id -> list of (start, end, arr)
for row in contracts:
    coverage.setdefault(row[1], []).append(
        (date.fromisoformat(row[2]), date.fromisoformat(row[3]), float(row[6])))

for acc_id, meta in customer_meta.items():
    health = meta["health"]
    employees = meta["employees"]
    segs = sorted(coverage.get(acc_id, []))
    if not segs:
        continue
    first = segs[0][0]
    churned = account_state[acc_id]["status"] == "Churned"
    last_end = min(segs[-1][1], AS_OF)
    # active months = months with ARR coverage, up to AS_OF
    months = []
    m = month_floor(first)
    while m <= month_floor(min(last_end, AS_OF)):
        covered = any(s <= m < e for (s, e, _a) in segs)
        if covered:
            months.append(m)
        m = add_months(m, 1)
    if not months:
        continue
    at_risk_now = acc_id in recent_risk
    base_users = max(2, min(400, employees // random.randint(15, 40)))
    n = len(months)
    for idx, mth in enumerate(months):
        trend = 1.0 + (idx / max(1, n)) * (health - 0.4)  # healthy grow, weak decline
        if churned and idx >= n - 4:  # ramp down in final months before churn
            trend *= max(0.25, 1 - (idx - (n - 4)) * 0.22)
        elif at_risk_now and idx >= n - 3:  # recent, sharp usage dip (still active)
            trend *= max(0.30, 1 - (idx - (n - 3)) * 0.28)
        active_users = max(1, int(base_users * trend * random.uniform(0.85, 1.15)))
        adoption = round(min(0.98, max(0.05, 0.30 + health * 0.5
                                       + random.uniform(-0.08, 0.08))), 3)
        if at_risk_now and idx >= n - 2:  # adoption falls off in the last months
            adoption = round(max(0.05, adoption * 0.5), 3)
        logins = active_users * random.randint(8, 25)
        events = logins * random.randint(3, 12)
        usage.append([acc_id, fmt(mth), active_users, adoption, logins, events])

write_csv(
    "usage_monthly",
    ["account_id", "usage_month", "active_users", "feature_adoption_pct",
     "logins", "events"],
    usage,
)

# --------------------------------------------------------------------------- #
# 6. campaigns + campaign_members (partner/marketing influence signal)
# --------------------------------------------------------------------------- #
campaigns = []
campaign_of_partner = {}
cid = 0
for pid in partner_ids:
    cid += 1
    camp_id = f"CMP-{cid:04d}"
    campaign_of_partner[pid] = camp_id
    pname = next(a[1] for a in accounts if a[0] == pid)
    campaigns.append([camp_id, f"{pname} Co-Sell", "Partner", pid,
                      fmt(random_date(HISTORY_START, AS_OF)), "Completed"])
for mkt in ["Enterprise AI Webinar", "GenAI Roadshow", "Analyst Briefing",
            "Product Launch", "Field Event - Summit"]:
    cid += 1
    campaigns.append([f"CMP-{cid:04d}", mkt, "Marketing", "",
                      fmt(random_date(HISTORY_START, AS_OF)), "Completed"])

write_csv(
    "campaigns",
    ["campaign_id", "campaign_name", "campaign_type", "partner_account_id",
     "start_date", "status"],
    campaigns,
)

campaign_members = []
cm_seq = 0
for acc_id, opp_id, partner_id in influenced_links:
    cm_seq += 1
    camp_id = campaign_of_partner.get(partner_id)
    if not camp_id:
        continue
    campaign_members.append([
        f"CM-{cm_seq:05d}", camp_id, acc_id, opp_id,
        "true" if random.random() < 0.8 else "false",
    ])

write_csv(
    "campaign_members",
    ["campaign_member_id", "campaign_id", "account_id", "opportunity_id", "responded"],
    campaign_members,
)

# --------------------------------------------------------------------------- #
# self-check: referential integrity + headline sanity (this is the local
# verification step -- the script fails loudly if the data is inconsistent)
# --------------------------------------------------------------------------- #
account_ids = {a[0] for a in accounts}
customer_ids = {a[0] for a in accounts if a[2] == "Customer"}
partner_id_set = set(partner_ids)

for o in opportunities:
    assert o[1] in customer_ids, f"opp {o[0]} bad account {o[1]}"
    if o[12]:
        assert o[12] in partner_id_set, f"opp {o[0]} bad partner {o[12]}"
    # sourced implies influenced (subset invariant)
    if o[10] == "true":
        assert o[11] == "true", f"opp {o[0]} sourced but not influenced"
for c in contracts:
    assert c[1] in customer_ids, f"contract {c[0]} bad account {c[1]}"
    assert float(c[6]) >= 0, f"contract {c[0]} negative ARR"
for c in cases:
    assert c[1] in customer_ids, f"case {c[0]} bad account {c[1]}"
for u in usage:
    assert u[0] in customer_ids, f"usage bad account {u[0]}"
for cm in campaign_members:
    assert cm[2] in account_ids and cm[3] in {o[0] for o in opportunities}

# headline numbers (mirrors what 40_validation.sql should report)
current_arr = sum(s["current_arr"] for s in account_state.values())
active = sum(1 for s in account_state.values() if s["status"] == "Active")
churned = sum(1 for s in account_state.values() if s["status"] == "Churned")
won = [o for o in opportunities if o[8] == "true"]
influenced_arr = sum(float(o[6]) for o in won if o[11] == "true")
sourced_arr = sum(float(o[6]) for o in won if o[10] == "true")

print("-" * 60)
print(f"accounts: {len(customer_ids)} customers + {len(partner_id_set)} partners")
print(f"opportunities: {len(opportunities)}  (won: {len(won)})")
print(f"contracts: {len(contracts)}   cases: {len(cases)}   usage rows: {len(usage)}")
print(f"active customers: {active}   churned: {churned}")
print(f"current total ARR:  ${current_arr:,.0f}")
print(f"partner INFLUENCED ARR (net-new): ${influenced_arr:,.0f}")
print(f"partner SOURCED ARR (subset):     ${sourced_arr:,.0f}")
assert sourced_arr <= influenced_arr, "sourced must be a subset of influenced"
print("integrity checks passed.")
