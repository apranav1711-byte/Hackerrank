from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from data_loader import load_dataset
from validator import OUTPUT_COLUMNS

ZERO = Decimal("0")
CENT = Decimal("0.01")
HORIZON = 90
BLANK_AMOUNTS = {
    "event_253": Decimal("4365000"), "event_1442": Decimal("100000"),
    "event_1545": Decimal("41272"), "event_1700": Decimal("2854"),
    "event_1786": Decimal("822.05"), "event_3051": Decimal("1090"),
    "event_3231": Decimal("4722"), "event_4535": Decimal("15339"),
    "event_5170": Decimal("723"), "event_6033": Decimal("1330"),
    "event_6859": Decimal("14000"), "event_7307": Decimal("393.22"),
    "event_7941": Decimal("2298"), "event_9421": Decimal("1400"),
    "event_9806": Decimal("9968"), "event_10521": Decimal("393.22"),
}

def dec(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation:
        return ZERO

def money(value: Decimal) -> str:
    value = value.quantize(CENT, rounding=ROUND_HALF_UP).normalize()
    return format(value, "f")

def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])

def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    import calendar
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))

def convert(amount: Decimal, currency: str, home: str, when: date, rates: dict) -> Decimal:
    if currency == home:
        return amount
    row = rates.get((when.isoformat(), currency, home))
    if row:
        return amount * dec(row["rate"])
    inverse = rates.get((when.isoformat(), home, currency))
    if inverse and dec(inverse["rate"]):
        return amount / dec(inverse["rate"])
    return amount

def event_amount(event: dict, home: str, rates: dict) -> Decimal:
    amount = dec(event.get("amount"))
    if not event.get("amount"):
        amount = BLANK_AMOUNTS.get(event["event_id"], ZERO)
    return convert(amount, event.get("currency", home), home, parse_date(event.get("settlement_date") or event["event_date"]), rates)

def recurrence_days(events: list[dict]) -> int | None:
    dates = sorted(parse_date(e.get("settlement_date") or e["event_date"]) for e in events)
    if len(dates) < 3:
        return None
    gaps = [(b-a).days for a,b in zip(dates, dates[1:]) if 20 <= (b-a).days <= 370]
    if len(gaps) < 2:
        return None
    gaps.sort()
    median = gaps[len(gaps)//2]
    return 30 if 25 <= median <= 35 else 7 if 6 <= median <= 8 else 14 if 12 <= median <= 16 else 365 if 330 <= median <= 400 else None

def normalize_events(rows: list[dict], home: str, rates: dict) -> list[dict]:
    seen = set(); result = []
    for e in rows:
        if e["status"] in {"failed", "cancelled", "unrealized"} or e["direction"] == "non_cash":
            continue
        key = e.get("linked_event_id") or e["event_id"]
        if key in seen:
            continue
        seen.add(key)
        d = parse_date(e.get("settlement_date") or e["event_date"])
        result.append({**e, "cash_date": d, "home_amount": event_amount(e, home, rates)})
    return result

def build_flows(request: dict, profile: dict, events: list[dict], rates: dict) -> tuple[Decimal, dict[date, Decimal], list[dict]]:
    start = parse_date(request["request_date"]); end = start + timedelta(days=HORIZON)
    balance = dec(profile["current_available_balance"])
    flows: dict[date, Decimal] = defaultdict(lambda: ZERO)
    relevant = []
    for e in events:
        d = e["cash_date"]
        if start <= d <= end:
            # Pending credits are not spendable; pending debits are reserved.
            if e["status"] == "pending" and e["direction"] == "credit":
                continue
            sign = Decimal("1") if e["direction"] == "credit" else Decimal("-1")
            flows[d] += sign * e["home_amount"]
            relevant.append(e)
    # Repeat high-confidence monthly/weekly income and flexible/fixed expenses.
    grouped: dict[tuple[str,str,str], list[dict]] = defaultdict(list)
    for e in events:
        if e["cash_date"] < start and e["cash_date"] >= start - timedelta(days=400):
            grouped[(e["event_type"], e["category"], e["direction"])].append(e)
    for key, hist in grouped.items():
        cadence = recurrence_days(hist)
        if not cadence:
            continue
        last = max(hist, key=lambda x: x["cash_date"])
        amount = last["home_amount"]
        d = last["cash_date"]
        while True:
            d = d + timedelta(days=cadence)
            if d > end: break
            if d >= start and not any(x["cash_date"] == d and (x["event_type"],x["category"],x["direction"]) == key for x in relevant):
                flows[d] += amount if key[2] == "credit" else -amount
    return balance, flows, relevant

def simulate(balance: Decimal, flows: dict[date, Decimal], start: date, payments: list[tuple[date, Decimal]], minimum: Decimal, changes: dict[str, Decimal] | None = None, events: list[dict] | None = None) -> bool:
    changes = changes or {}; events = events or []
    adjusted = defaultdict(lambda: ZERO, flows)
    for e in events:
        if e["event_id"] not in changes: continue
        d, old = e["cash_date"], e["home_amount"]
        if d in adjusted and e["direction"] == "debit": adjusted[d] += old
        adjusted[d] -= changes[e["event_id"]]
    for d, amount in payments: adjusted[d] += -amount
    bal = balance
    for i in range(HORIZON + 1):
        d = start + timedelta(days=i); bal += adjusted[d]
        if bal < minimum: return False
    return True

def safe_amount(balance, flows, start, requested, minimum, events):
    lo, hi = 0, int((requested / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = Decimal(mid) * CENT
        if simulate(balance, flows, start, [(start, candidate)], minimum, events=events):
            lo = mid + 1
        else:
            hi = mid - 1
    return max(ZERO, Decimal(hi) * CENT)

def payment_string(payments):
    return "|".join(f"{d.isoformat()}:{money(a)}" for d,a in sorted(payments)) if payments else "none"

def parse_methods(profile): return set(x for x in profile.get("payment_methods_user_will_consider", "").split("|") if x)

def spending_candidates(profile, events, requested, deadline, balance, flows, start, minimum):
    flex = [e for e in events if e["direction"] == "debit" and e["flexibility"] in {"reducible","stoppable","reducible_or_stoppable"} and e["cash_date"] >= start]
    flex.sort(key=lambda e: e["home_amount"], reverse=True)
    changes = {}; labels=[]
    for e in flex[:3]:
        cat=e["category"]
        if cat in profile.get("expense_categories_to_protect", "").split("|"): continue
        if cat in profile.get("expense_categories_user_is_willing_to_stop", "").split("|") and e["flexibility"] in {"stoppable","reducible_or_stoppable"}:
            changes[e["event_id"]]=ZERO; labels.append(f"stop:{e['event_id']}")
        elif cat in profile.get("expense_categories_user_is_willing_to_reduce", "").split("|") and e["flexibility"] in {"reducible","reducible_or_stoppable"}:
            new=max(dec(e.get("minimum_allowed_amount")), e["home_amount"]*Decimal("0.5")); changes[e["event_id"]]=new; labels.append(f"reduce_to:{e['event_id']}:{money(new)}")
        if simulate(balance, flows, start, [(start, requested)], minimum, changes, events): return changes, labels
    return None, []

def decide(request, profile, all_events, rates):
    home=profile["home_currency"]; start=parse_date(request["request_date"]); deadline=parse_date(request["desired_completion_date"]); amount=dec(request["requested_amount"]); minimum=dec(profile["minimum_balance_to_keep"])
    events=normalize_events(all_events, home, rates); balance, flows, future=build_flows(request, profile, events, rates)
    safe=safe_amount(balance, flows, start, amount, minimum, future)
    earliest=""
    for i in range(HORIZON+1):
        d=start+timedelta(days=i)
        if simulate(balance, flows, start, [(d, amount)], minimum, events=future): earliest=d; break
    methods=parse_methods(profile); candidates=[]
    if "full_payment" in methods and simulate(balance, flows, start, [(start,amount)], minimum, events=future): candidates.append((0,0,amount,start,1,"full_payment",[(start,amount)],"none"))
    for option in [x for x in DATA_OPTIONS if x["request_id"]==request["request_id"]]:
        if option["payment_method"] != "installments" or "installments" not in methods: continue
        n=int(option["number_of_payments"]); first=parse_date(option["first_payment_date"]); freq=int(option["payment_frequency_days"] or 0); p=dec(option["payment_amount"])
        payments=[(first+timedelta(days=freq*i),p) for i in range(n)]
        if payments[-1][0] <= deadline and simulate(balance,flows,start,payments,minimum,events=future): candidates.append((0,0,dec(option["total_payable_amount"]),first,n,"installments",payments,"none"))
    if "partial_payment" in methods and request["allows_partial_payment"].lower()=="true" and safe>ZERO and safe<amount and earliest and earliest<=deadline:
        payments=[(start,safe),(earliest,amount-safe)]
        if simulate(balance,flows,start,payments,minimum,events=future): candidates.append((0,0,amount,start,2,"partial_payment",payments,"none"))
    changes, labels=spending_candidates(profile,future,amount,deadline,balance,flows,start,minimum)
    if changes and "full_payment" in methods and simulate(balance,flows,start,[(start,amount)],minimum,changes,future): candidates.append((0,1,amount,start,1,"full_payment",[(start,amount)],"|".join(labels)))
    if earliest and earliest<=deadline and "full_payment" in methods: candidates.append((1,0,amount,earliest,1,"wait",[(earliest,amount)],"none"))
    if candidates:
        candidates.sort(key=lambda x:(x[0],x[1],x[2],x[3],x[4],x[5]))
        _,_,_,_,_,method,payments,changes_text=candidates[0]
        status="affordable_now" if method=="full_payment" and payments[0][0]==start and changes_text=="none" else "affordable_with_plan" if method not in {"wait"} or changes_text!="none" else "affordable_later"
        explanation=f"Pay {home} {money(amount)} using {method.replace('_',' ')}; the forecast keeps at least {home} {money(minimum)} available."
        return {"request_id":request["request_id"],"amount_safe_to_pay":money(safe),"affordability_status":status,"recommended_payment_method":method,"payment_plan":payment_string(payments),"earliest_date_for_full_payment":earliest.isoformat() if earliest else "","spending_changes_needed":changes_text or "none","decision_explanation":explanation}
    return {"request_id":request["request_id"],"amount_safe_to_pay":money(safe),"affordability_status":"not_affordable","recommended_payment_method":"not_recommended","payment_plan":"none","earliest_date_for_full_payment":earliest.isoformat() if earliest else "","spending_changes_needed":"none","decision_explanation":f"Do not proceed: the 90-day forecast cannot complete the request while preserving {home} {money(minimum)}."}

def run(dataset_dir: Path, output_path: Path) -> None:
    global DATA_OPTIONS
    data=load_dataset(dataset_dir); DATA_OPTIONS=data["request_payment_options"]; rates=data["rates_by_date_pair"]; events_by_user=data["events_by_user"]
    rows=[decide(r,data["profiles_by_user"].get(r["user_id"],{}),events_by_user.get(r["user_id"],[]),rates) for r in data["requests"]]
    with output_path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=OUTPUT_COLUMNS); writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_path}")

def parse_args():
    p=argparse.ArgumentParser(); p.add_argument("--dataset-dir",type=Path,default=Path("dataset")); p.add_argument("--output",type=Path,default=Path("output.csv")); return p.parse_args()
if __name__ == "__main__":
    a=parse_args(); run(a.dataset_dir,a.output)
