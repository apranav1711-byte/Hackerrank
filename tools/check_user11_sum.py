import csv
from decimal import Decimal

with open("dataset/financial_events.csv", encoding="utf-8") as f:
    events = [e for e in csv.DictReader(f) if e["user_id"] == "user_11" and e["direction"] == "debit"]

target = Decimal("16880550")
print("Target:", target)

apr_evts = [e for e in events if e["settlement_date"] >= "2025-04-01" and e["settlement_date"] <= "2025-04-30"]
print("April debits:")
total = Decimal("0")
for e in apr_evts:
    a = Decimal(e["amount"])
    total += a
    print(f"  {e['event_id']} {e['settlement_date']} {e['category']} {a} {e['description']}")

print("Sum of all April debits:", total)
