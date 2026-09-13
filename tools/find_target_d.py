import csv
from decimal import Decimal
import itertools

with open("dataset/sample_requests.csv", encoding="utf-8") as f:
    samples = {r["user_id"]: r for r in csv.DictReader(f)}
with open("dataset/financial_profiles.csv", encoding="utf-8") as f:
    profiles = {r["user_id"]: r for r in csv.DictReader(f)}
with open("dataset/financial_events.csv", encoding="utf-8") as f:
    events = list(csv.DictReader(f))

for uid in ["user_22", "user_18", "user_15", "user_08", "user_21"]:
    s = samples[uid]
    p = profiles[uid]
    req_date = s["request_date"]
    bal = Decimal(p["current_available_balance"])
    min_b = Decimal(p["minimum_balance_to_keep"])
    gt = Decimal(s["amount_safe_to_pay"])
    target_d = bal - min_b - gt
    print(f"=== {uid}: req_date={req_date}, target_D={target_d} ===")
    u_events = [e for e in events if e["user_id"] == uid]
    for e in u_events:
        # check future or pending or scheduled events
        s_date = e.get("settlement_date") or e.get("event_date")
        if s_date and s_date >= req_date:
            print(f"  FUTURE/PENDING: {e['event_id']} {s_date} {e['category']} {e['direction']} {e['amount']} {e['status']} {e['description']}")
