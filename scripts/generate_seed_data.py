#!/usr/bin/env python3
"""Generates synthetic SaaS seed data (CSVs) for the dbt project under seeds/.

Deterministic (fixed random seed) so re-running produces identical output.
Pure stdlib - no external dependencies required.
"""
import csv
import random
from datetime import date, datetime, timedelta

random.seed(42)

SEEDS_DIR = "seeds"
TODAY = date(2026, 7, 13)
EARLIEST_SIGNUP = date(2023, 1, 1)

N_CUSTOMERS = 500

INDUSTRIES = [
    "Software", "Financial Services", "Healthcare", "Retail", "Manufacturing",
    "Media & Entertainment", "Education", "Logistics", "Real Estate",
    "Professional Services", "Nonprofit", "Telecommunications",
]
COUNTRIES = [
    ("United States", 0.45), ("United Kingdom", 0.12), ("Canada", 0.10),
    ("Germany", 0.08), ("Australia", 0.07), ("India", 0.06), ("France", 0.05),
    ("Brazil", 0.04), ("Japan", 0.03),
]
ACQUISITION_CHANNELS = [
    "Organic Search", "Paid Search", "Referral", "Outbound Sales",
    "Content Marketing", "Partner", "Event", "Social Media",
]
COMPANY_PREFIXES = [
    "Brightline", "Northwind", "Vertex", "Cascade", "Summit", "Ironclad",
    "Bluepeak", "Redwood", "Silverline", "Nova", "Crestpoint", "Meridian",
    "Anchor", "Fieldstone", "Lighthouse", "Trailhead", "Orbital", "Granite",
    "Harborview", "Sterling", "Cobalt", "Junction", "Wavefront", "Pinnacle",
    "Clearwater", "Foundry", "Beacon", "Outrider", "Longview", "Catalyst",
]
COMPANY_SUFFIXES = [
    "Labs", "Technologies", "Systems", "Solutions", "Group", "Works",
    "Analytics", "Software", "Digital", "Networks", "Partners", "Studio",
]

TIERS = ["Starter", "Pro", "Enterprise"]
INTERVALS = ["Monthly", "Annual"]
TIER_PRICE_MONTHLY = {"Starter": 29, "Pro": 99, "Enterprise": 299}
TIER_ORDER = {"Starter": 0, "Pro": 1, "Enterprise": 2}

SUPPORT_CATEGORIES = [
    "Billing", "Bug Report", "Feature Request", "Onboarding", "Account Access",
    "Integration", "Performance", "General Question",
]
SUPPORT_PRIORITIES = [("Low", 0.4), ("Medium", 0.35), ("High", 0.2), ("Urgent", 0.05)]

USAGE_EVENT_NAMES = [
    ("login", "Core"), ("dashboard_viewed", "Core"), ("report_generated", "Analytics"),
    ("api_call", "Platform"), ("feature_export_used", "Analytics"),
    ("integration_connected", "Platform"), ("team_member_invited", "Collaboration"),
    ("comment_added", "Collaboration"), ("workflow_created", "Automation"),
    ("workflow_run", "Automation"),
]


def weighted_choice(pairs):
    values, weights = zip(*pairs)
    return random.choices(values, weights=weights, k=1)[0]


def random_date(start: date, end: date) -> date:
    if end <= start:
        return start
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def fmt(d):
    return d.isoformat() if d else ""


def write_csv(name, header, rows):
    path = f"{SEEDS_DIR}/{name}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {len(rows):>6} rows -> {path}")


# ---------------------------------------------------------------------------
# 1. plans
# ---------------------------------------------------------------------------
plans = []
plan_id = 1
plan_lookup = {}  # (tier, interval) -> plan_id
for tier in TIERS:
    monthly_price = TIER_PRICE_MONTHLY[tier]
    for interval in INTERVALS:
        price = monthly_price if interval == "Monthly" else round(monthly_price * 10, 2)  # ~2 months free annually
        plans.append([plan_id, f"{tier} {interval}", tier, interval, price])
        plan_lookup[(tier, interval)] = plan_id
        plan_id += 1

write_csv(
    "plans",
    ["plan_id", "plan_name", "tier", "billing_interval", "price_usd"],
    plans,
)


def plan_mrr(tier, interval):
    price = next(p[4] for p in plans if p[2] == tier and p[3] == interval)
    return round(price if interval == "Monthly" else price / 12, 2)


# ---------------------------------------------------------------------------
# 2. customers
# ---------------------------------------------------------------------------
customers = []
used_names = set()
for cid in range(1, N_CUSTOMERS + 1):
    for _attempt in range(1000):
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"
        if name not in used_names:
            used_names.add(name)
            break
    else:
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)} {cid}"
        used_names.add(name)
    industry = random.choice(INDUSTRIES)
    country = weighted_choice(COUNTRIES)
    employees = random.choice([5, 10, 25, 50, 100, 250, 500, 1000, 2500])
    channel = random.choice(ACQUISITION_CHANNELS)
    signup_date = random_date(EARLIEST_SIGNUP, TODAY - timedelta(days=3))
    customers.append([cid, name, industry, country, employees, channel, fmt(signup_date)])

write_csv(
    "customers",
    ["customer_id", "company_name", "industry", "country", "employee_count",
     "acquisition_channel", "signup_date"],
    customers,
)

# ---------------------------------------------------------------------------
# 3 & 4. subscriptions + subscription_events
# ---------------------------------------------------------------------------
subscriptions = []
subscription_events = []
sub_id = 1
event_id = 1

for cust in customers:
    customer_id, _, _, _, employees, _, signup_date_str = cust
    signup_date = date.fromisoformat(signup_date_str)

    # starting tier skews toward company size
    if employees <= 25:
        start_tier = weighted_choice([("Starter", 0.7), ("Pro", 0.3), ("Enterprise", 0.0)])
    elif employees <= 250:
        start_tier = weighted_choice([("Starter", 0.25), ("Pro", 0.6), ("Enterprise", 0.15)])
    else:
        start_tier = weighted_choice([("Starter", 0.05), ("Pro", 0.35), ("Enterprise", 0.6)])
    interval = weighted_choice([("Monthly", 0.65), ("Annual", 0.35)])

    cur_plan_id = plan_lookup[(start_tier, interval)]
    cur_start = signup_date
    cur_tier = start_tier
    subscription_events.append([
        event_id, sub_id, customer_id, "created", fmt(signup_date), "", cur_plan_id, plan_mrr(start_tier, interval),
    ])
    event_id += 1

    lifecycle_cursor = signup_date
    is_churned = False
    final_status = "active"
    active_sub_id = sub_id
    active_plan_id = cur_plan_id
    active_start = cur_start

    # simulate up to 3 lifecycle transitions (upgrade/downgrade/churn/reactivate)
    n_transitions = random.choices([0, 1, 2, 3], weights=[0.45, 0.30, 0.17, 0.08])[0]
    for _ in range(n_transitions):
        gap_days = random.randint(45, 240)
        transition_date = lifecycle_cursor + timedelta(days=gap_days)
        if transition_date >= TODAY:
            break
        lifecycle_cursor = transition_date

        action = weighted_choice([
            ("upgrade", 0.35), ("downgrade", 0.15), ("cancel", 0.25), ("reactivate", 0.25),
        ])

        if action == "reactivate" and final_status != "canceled":
            continue  # can't reactivate an active subscription

        if action in ("upgrade", "downgrade"):
            order = TIER_ORDER[cur_tier]
            if action == "upgrade" and order < 2:
                new_tier = TIERS[order + 1]
            elif action == "downgrade" and order > 0:
                new_tier = TIERS[order - 1]
            else:
                continue

            # close out current subscription row
            subscriptions.append([
                active_sub_id, customer_id, active_plan_id, fmt(active_start),
                fmt(transition_date), "canceled", plan_mrr(cur_tier, interval),
            ])
            sub_id += 1
            new_plan_id = plan_lookup[(new_tier, interval)]
            subscription_events.append([
                event_id, active_sub_id, customer_id,
                "upgraded" if action == "upgrade" else "downgraded",
                fmt(transition_date), active_plan_id, new_plan_id,
                round(plan_mrr(new_tier, interval) - plan_mrr(cur_tier, interval), 2),
            ])
            event_id += 1

            active_sub_id = sub_id
            active_plan_id = new_plan_id
            active_start = transition_date
            cur_tier = new_tier
            final_status = "active"

        elif action == "cancel":
            subscriptions.append([
                active_sub_id, customer_id, active_plan_id, fmt(active_start),
                fmt(transition_date), "canceled", plan_mrr(cur_tier, interval),
            ])
            sub_id += 1
            subscription_events.append([
                event_id, active_sub_id, customer_id, "canceled", fmt(transition_date),
                active_plan_id, "", round(-plan_mrr(cur_tier, interval), 2),
            ])
            event_id += 1
            final_status = "canceled"
            active_sub_id = sub_id
            active_plan_id = plan_lookup[(cur_tier, interval)]
            active_start = None  # no active row until reactivation

        elif action == "reactivate":
            active_start = transition_date
            subscription_events.append([
                event_id, active_sub_id, customer_id, "reactivated", fmt(transition_date),
                "", active_plan_id, plan_mrr(cur_tier, interval),
            ])
            event_id += 1
            final_status = "active"

    # close out the final subscription row
    if final_status == "active":
        subscriptions.append([
            active_sub_id, customer_id, active_plan_id, fmt(active_start), "", "active",
            plan_mrr(cur_tier, interval),
        ])
    else:
        # already appended a canceled row when the cancel action fired unless no transitions happened
        if active_start is not None:
            subscriptions.append([
                active_sub_id, customer_id, active_plan_id, fmt(active_start), "", "canceled",
                plan_mrr(cur_tier, interval),
            ])
    sub_id += 1

write_csv(
    "subscriptions",
    ["subscription_id", "customer_id", "plan_id", "start_date", "end_date", "status", "mrr_usd"],
    subscriptions,
)
write_csv(
    "subscription_events",
    ["event_id", "subscription_id", "customer_id", "event_type", "event_date",
     "previous_plan_id", "new_plan_id", "mrr_delta_usd"],
    subscription_events,
)

# ---------------------------------------------------------------------------
# 5 & 6. invoices + payments (billed monthly across each subscription's life)
# ---------------------------------------------------------------------------
invoices = []
payments = []
invoice_id = 1
payment_id = 1

for sub in subscriptions:
    subscription_id, customer_id, plan_id, start_date_str, end_date_str, status, mrr_usd = sub
    if not start_date_str:
        continue
    period_start = date.fromisoformat(start_date_str)
    period_end = date.fromisoformat(end_date_str) if end_date_str else TODAY

    billing_date = period_start
    while billing_date < period_end:
        next_period = min(billing_date + timedelta(days=30), period_end)
        invoice_date = billing_date
        due_date = invoice_date + timedelta(days=14)

        if due_date > TODAY:
            invoice_status = "pending"
        else:
            invoice_status = weighted_choice([
                ("paid", 0.93), ("failed", 0.04), ("refunded", 0.03),
            ])

        invoices.append([
            invoice_id, customer_id, subscription_id, fmt(invoice_date), fmt(due_date),
            fmt(billing_date), fmt(next_period), mrr_usd, invoice_status,
        ])

        if invoice_status in ("paid", "refunded"):
            pay_lag = random.randint(0, 10)
            payment_date = min(invoice_date + timedelta(days=pay_lag), TODAY)
            payments.append([
                payment_id, invoice_id, customer_id, fmt(payment_date), mrr_usd,
                random.choice(["credit_card", "ach", "wire", "paypal"]),
                "refunded" if invoice_status == "refunded" else "succeeded",
            ])
            payment_id += 1
        elif invoice_status == "failed":
            payment_date = min(invoice_date + timedelta(days=random.randint(0, 5)), TODAY)
            payments.append([
                payment_id, invoice_id, customer_id, fmt(payment_date), mrr_usd,
                random.choice(["credit_card", "ach", "wire", "paypal"]), "failed",
            ])
            payment_id += 1

        invoice_id += 1
        billing_date = next_period

write_csv(
    "invoices",
    ["invoice_id", "customer_id", "subscription_id", "invoice_date", "due_date",
     "period_start", "period_end", "amount_usd", "status"],
    invoices,
)
write_csv(
    "payments",
    ["payment_id", "invoice_id", "customer_id", "payment_date", "amount_usd",
     "payment_method", "status"],
    payments,
)

# ---------------------------------------------------------------------------
# 7. usage_events
# ---------------------------------------------------------------------------
usage_events = []
usage_event_id = 1
for cust in customers:
    customer_id, _, _, _, employees, _, signup_date_str = cust
    signup_date = date.fromisoformat(signup_date_str)
    n_users = max(1, employees // 20)
    n_users = min(n_users, 40)
    active_days = (TODAY - signup_date).days
    if active_days <= 0:
        continue
    # more engaged customers (proxy: more employees) generate more events
    n_events = random.randint(10, 60) * (1 if employees <= 100 else 2)

    for _ in range(n_events):
        user_id = f"{customer_id}-u{random.randint(1, n_users)}"
        event_name, feature_area = random.choice(USAGE_EVENT_NAMES)
        offset_days = random.randint(0, active_days - 1)
        event_dt = datetime.combine(signup_date, datetime.min.time()) + timedelta(
            days=offset_days, hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )
        if event_dt.date() > TODAY:
            continue
        usage_events.append([
            usage_event_id, customer_id, user_id, event_name, event_dt.isoformat(sep=" "), feature_area,
        ])
        usage_event_id += 1

write_csv(
    "usage_events",
    ["event_id", "customer_id", "user_id", "event_name", "event_timestamp", "feature_area"],
    usage_events,
)

# ---------------------------------------------------------------------------
# 8. support_tickets
# ---------------------------------------------------------------------------
support_tickets = []
ticket_id = 1
for cust in customers:
    customer_id, _, _, _, employees, _, signup_date_str = cust
    signup_date = date.fromisoformat(signup_date_str)
    active_days = (TODAY - signup_date).days
    if active_days <= 0:
        continue
    n_tickets = random.randint(0, 8)
    for _ in range(n_tickets):
        created = datetime.combine(signup_date, datetime.min.time()) + timedelta(
            days=random.randint(0, active_days - 1), hours=random.randint(0, 23)
        )
        if created.date() > TODAY:
            continue
        priority = weighted_choice(SUPPORT_PRIORITIES)
        category = random.choice(SUPPORT_CATEGORIES)
        is_resolved = random.random() < 0.88
        resolved = None
        satisfaction = ""
        status = "open"
        if is_resolved:
            resolve_hours = {"Urgent": 4, "High": 24, "Medium": 72, "Low": 168}[priority]
            resolved_dt = created + timedelta(hours=random.randint(1, resolve_hours))
            if resolved_dt <= datetime.combine(TODAY, datetime.min.time()):
                resolved = resolved_dt
                status = "resolved"
                satisfaction = random.randint(1, 5)
        support_tickets.append([
            ticket_id, customer_id, created.isoformat(sep=" "),
            resolved.isoformat(sep=" ") if resolved else "", priority, category,
            satisfaction, status,
        ])
        ticket_id += 1

write_csv(
    "support_tickets",
    ["ticket_id", "customer_id", "created_at", "resolved_at", "priority", "category",
     "satisfaction_score", "status"],
    support_tickets,
)

print("done.")
