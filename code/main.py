from __future__ import annotations

import argparse
import calendar
import csv
import itertools
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from data_loader import load_dataset
from evidence import resolve_image_amounts, VERIFIED_IMAGE_AMOUNTS
from validator import OUTPUT_COLUMNS

ZERO = Decimal("0")
CENT = Decimal("0.01")
HORIZON = 90

BLANK_AMOUNTS = VERIFIED_IMAGE_AMOUNTS


def dec(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation:
        return ZERO


def money(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):.2f}"


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
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
    return convert(
        amount,
        event.get("currency", home),
        home,
        parse_date(event.get("settlement_date") or event["event_date"]),
        rates,
    )


def normalize_events(rows: list[dict], home: str, rates: dict) -> list[dict]:
    seen = set()
    result = []
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


def message_salary_info(messages: list[dict], home: str, rates: dict, request_date: date) -> tuple[Decimal | None, bool]:
    new_salary = None
    is_terminated = False
    for message in sorted(messages, key=lambda m: m.get("sent_at", "")):
        text = message.get("message_text", "")
        source = message.get("source_type", "")
        text_lower = text.lower()

        if any(w in text_lower for w in ("contract has ended", "off-season income", "terminated", "resigned", "leaving")):
            is_terminated = True
            new_salary = None
            continue

        if source not in {"employer", "financial_service"} or not any(x in text_lower for x in ("salary", "gaji", "payroll", "pay")):
            continue

        amounts = re.findall(r"\b(INR|IDR|ZAR|USD|EUR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text, flags=re.I)
        if amounts:
            currency, raw = amounts[0]
            val = convert(Decimal(raw.replace(",", "")), currency.upper(), home, request_date, rates)
            new_salary = val
            is_terminated = False

    return new_salary, is_terminated


def build_flows(request: dict, profile: dict, events: list[dict], rates: dict, messages: list[dict] | None = None):
    start = parse_date(request["request_date"])
    end = start + timedelta(days=HORIZON)
    balance = dec(profile["current_available_balance"])
    flows: dict[date, Decimal] = defaultdict(lambda: ZERO)
    projected_items: list[tuple[date, Decimal, str]] = []

    # 1. Existing events in the future forecast window
    relevant = []
    for e in events:
        d = e["cash_date"]
        if start <= d <= end:
            if e["status"] == "pending" and e["direction"] == "credit":
                continue
            sign = Decimal("1") if e["direction"] == "credit" else Decimal("-1")
            flows[d] += sign * e["home_amount"]
            relevant.append(e)
            if e["direction"] == "debit":
                projected_items.append((d, e["home_amount"], e["event_id"]))

    # 2. Confirmed & recurring salary projection
    sal_msg_override, is_terminated = message_salary_info(messages or [], profile["home_currency"], rates, start)
    all_salaries = [
        e for e in events
        if e["direction"] == "credit" and (
            e["category"] == "salary" or "salary" in e.get("description", "").lower() or "payroll" in e.get("description", "").lower()
        )
    ]

    has_terminal_event = any(any(w in e.get("description", "").lower() for w in ("final", "termination", "resigned")) for e in all_salaries)
    if is_terminated or has_terminal_event:
        pass
    elif all_salaries:
        sched_sal = [e for e in all_salaries if e["cash_date"] >= start]
        past_sal = [e for e in all_salaries if e["cash_date"] < start]

        if sal_msg_override is not None:
            base_sal_amt = sal_msg_override
        elif sched_sal:
            base_sal_amt = sched_sal[0]["home_amount"]
        else:
            reg_sal = [e for e in past_sal if not any(w in e.get("description", "").lower() for w in ("prorated", "arrears", "bonus", "advance"))]
            base_sal_amt = reg_sal[-1]["home_amount"] if reg_sal else past_sal[-1]["home_amount"]

        reg_sal = [e for e in past_sal if not any(w in e.get("description", "").lower() for w in ("prorated", "arrears", "bonus", "advance"))]
        days = [e["cash_date"].day for e in (reg_sal or past_sal)]
        if sched_sal:
            sal_day = sched_sal[0]["cash_date"].day
        elif days:
            sal_day = Counter(days).most_common(1)[0][0]
        else:
            sal_day = 15

        curr_y = start.year
        curr_m = start.month
        for _ in range(4):
            max_d = calendar.monthrange(curr_y, curr_m)[1]
            sal_d = date(curr_y, curr_m, min(sal_day, max_d))
            if start <= sal_d <= end:
                if not any(e["cash_date"] == sal_d and e["category"] == "salary" for e in relevant):
                    flows[sal_d] += base_sal_amt
            curr_m += 1
            if curr_m > 12:
                curr_m = 1
                curr_y += 1

    # 3. Recurring debits
    VARIABLE_CATS = {"groceries", "transport"}
    DISCRETIONARY_CATS = {"shopping", "entertainment", "investment_purchase", "investment", "windfall"}

    hist_debits = defaultdict(list)
    for e in events:
        if e["direction"] == "debit" and e["cash_date"] < start and e["cash_date"] >= start - timedelta(days=400):
            cat = e["category"]
            if cat in DISCRETIONARY_CATS:
                continue
            key = cat if cat in VARIABLE_CATS else (cat, e.get("description", ""))
            hist_debits[key].append(e)

    for key, items in hist_debits.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x["cash_date"])
        dates = [x["cash_date"] for x in items]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if 3 <= (b - a).days <= 370]
        if not gaps:
            continue
        gaps.sort()
        median_gap = gaps[len(gaps) // 2]

        is_var = isinstance(key, str)
        if is_var:
            cadence = median_gap
        else:
            cadence = "monthly" if 25 <= median_gap <= 35 else 7 if 6 <= median_gap <= 8 else 14 if 12 <= median_gap <= 16 else "yearly" if 330 <= median_gap <= 400 else None

        if not cadence:
            continue

        cadence_days = cadence if is_var else 30 if cadence == "monthly" else 365 if cadence == "yearly" else cadence
        max_inactivity = max(45, int(cadence_days * 2.2))
        if items[-1]["cash_date"] < start - timedelta(days=max_inactivity):
            continue

        amts = sorted(x["home_amount"] for x in items)
        amt = amts[len(amts) // 2]
        source_event_id = items[-1]["event_id"]

        curr_d = items[-1]["cash_date"]
        while True:
            curr_d = add_months(curr_d, 1) if cadence == "monthly" else add_months(curr_d, 12) if cadence == "yearly" else curr_d + timedelta(days=cadence_days)
            if curr_d > end:
                break
            if curr_d >= start:
                cat_match = key if is_var else key[0]
                desc_match = "" if is_var else key[1]
                if not any(x["cash_date"] == curr_d and x["category"] == cat_match and (is_var or x.get("description", "") == desc_match) for x in relevant):
                    flows[curr_d] -= amt
                    projected_items.append((curr_d, amt, source_event_id))

    return balance, flows, relevant, projected_items


def simulate(
    balance: Decimal,
    flows: dict[date, Decimal],
    start: date,
    payments: list[tuple[date, Decimal]],
    minimum: Decimal,
    spending_adjustments: dict[str, Decimal] | None = None,
    projected_items: list[tuple[date, Decimal, str]] | None = None,
    end_date: date | None = None,
) -> bool:
    spending_adjustments = spending_adjustments or {}
    projected_items = projected_items or []

    adjusted = defaultdict(lambda: ZERO, flows)
    for d, old_amt, event_id in projected_items:
        if event_id in spending_adjustments:
            new_amt = spending_adjustments[event_id]
            diff = old_amt - new_amt
            adjusted[d] += diff

    for d, amount in payments:
        adjusted[d] += -amount

    bal = balance
    total_days = (end_date - start).days if end_date else HORIZON
    for i in range(total_days + 1):
        d = start + timedelta(days=i)
        bal += adjusted[d]
        if bal < minimum:
            return False
    return True


def safe_amount(balance: Decimal, flows: dict[date, Decimal], start: date, requested: Decimal, minimum: Decimal) -> Decimal:
    lo, hi = 0, int((requested / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = Decimal(mid) * CENT
        if simulate(balance, flows, start, [(start, candidate)], minimum):
            lo = mid + 1
        else:
            hi = mid - 1
    return max(ZERO, Decimal(hi) * CENT)


def payment_string(payments: list[tuple[date, Decimal]]) -> str:
    return "|".join(f"{d.isoformat()}:{money(a)}" for d, a in sorted(payments)) if payments else "none"


def parse_methods(profile: dict) -> set[str]:
    return set(x for x in profile.get("payment_methods_user_will_consider", "").split("|") if x)


def find_spending_candidates(profile: dict, events: list[dict], requested: Decimal, deadline: date, balance: Decimal, flows: dict[date, Decimal], start: date, minimum: Decimal, projected_items: list[tuple[date, Decimal, str]]):
    projected_event_ids = set(item[2] for item in projected_items)
    events_by_id = {e["event_id"]: e for e in events}

    stop_cats = set(x for x in profile.get("expense_categories_user_is_willing_to_stop", "").split("|") if x)
    reduce_cats = set(x for x in profile.get("expense_categories_user_is_willing_to_reduce", "").split("|") if x)
    protect_cats = set(x for x in profile.get("expense_categories_to_protect", "").split("|") if x)

    possible_actions = []
    for eid in projected_event_ids:
        e = events_by_id.get(eid)
        if not e:
            continue
        cat = e["category"]
        if cat in protect_cats:
            continue
        flex = e.get("flexibility", "fixed")
        amt = e["home_amount"]

        if cat in stop_cats and flex in {"stoppable", "reducible_or_stoppable"}:
            possible_actions.append(("stop", eid, ZERO, amt, f"stop:{eid}"))
        if cat in reduce_cats and flex in {"reducible", "reducible_or_stoppable"}:
            min_allowed = dec(e.get("minimum_allowed_amount"))
            new_val = min_allowed if min_allowed > ZERO else max(min_allowed, amt * Decimal("0.5"))
            savings = amt - new_val
            if savings > ZERO:
                possible_actions.append(("reduce", eid, new_val, savings, f"reduce_to:{eid}:{money(new_val)}"))

    possible_actions.sort(key=lambda x: x[3], reverse=True)

    for r in [1, 2, 3]:
        for comb in itertools.combinations(possible_actions, r):
            event_ids = [act[1] for act in comb]
            if len(set(event_ids)) != len(event_ids):
                continue
            adjustments = {act[1]: act[2] for act in comb}
            labels = [act[4] for act in comb]
            if simulate(balance, flows, start, [(start, requested)], minimum, adjustments, projected_items, deadline):
                return adjustments, labels

    return None, []


def decide(request: dict, profile: dict, all_events: list[dict], rates: dict, messages: list[dict] | None = None, data_options: list[dict] | None = None) -> dict[str, str]:
    home = profile["home_currency"]
    start = parse_date(request["request_date"])
    deadline = parse_date(request["desired_completion_date"])
    amount = dec(request["requested_amount"])
    minimum = dec(profile["minimum_balance_to_keep"])

    events = normalize_events(all_events, home, rates)
    balance, flows, relevant, projected_items = build_flows(request, profile, events, rates, messages)
    safe = safe_amount(balance, flows, start, amount, minimum)

    # Earliest safe date for single full payment
    earliest = ""
    for i in range(HORIZON + 1):
        d = start + timedelta(days=i)
        if simulate(balance, flows, start, [(d, amount)], minimum, end_date=max(d, deadline)):
            earliest = d
            break

    methods = parse_methods(profile)
    max_months = int(profile["max_installment_months"]) if profile.get("max_installment_months") else None
    candidates = []

    # 1. Full payment today
    if "full_payment" in methods and simulate(balance, flows, start, [(start, amount)], minimum, end_date=deadline):
        candidates.append((0, 0, amount, start, 1, "00", "full_payment", [(start, amount)], "none"))

    # 2. Installments from request_payment_options
    opts = [x for x in (data_options or []) if x["request_id"] == request["request_id"]]
    for option in opts:
        if option["payment_method"] != "installments" or "installments" not in methods:
            continue
        n = int(option["number_of_payments"])
        first_d = parse_date(option["first_payment_date"])
        freq = int(option["payment_frequency_days"] or 0)
        p = dec(option["payment_amount"])
        payments = [(first_d + timedelta(days=freq * i), p) for i in range(n)]
        last_d = payments[-1][0]

        duration_days = (last_d - first_d).days
        duration_months = (duration_days + 29) // 30
        if max_months is not None and duration_months > max_months:
            continue

        finishes_deadline = 0 if last_d <= deadline else 1
        total_payable = dec(option["total_payable_amount"])
        opt_id = option.get("payment_option_id", "99")

        plan_end = max(last_d, deadline)
        if simulate(balance, flows, start, payments, minimum, end_date=plan_end):
            candidates.append((finishes_deadline, 0, total_payable, first_d, n, opt_id, "installments", payments, "none"))

    # 3. Partial payment
    if "partial_payment" in methods and request.get("allows_partial_payment", "").lower() == "true":
        if safe > ZERO and safe < amount and earliest and earliest <= deadline:
            payments = [(start, safe), (earliest, amount - safe)]
            if simulate(balance, flows, start, payments, minimum, end_date=deadline):
                candidates.append((0, 0, amount, start, 2, "00", "partial_payment", payments, "none"))

    # 4. Spending changes
    adjustments, labels = find_spending_candidates(profile, events, amount, deadline, balance, flows, start, minimum, projected_items)
    if adjustments and "full_payment" in methods:
        candidates.append((0, 1, amount, start, 1, "00", "full_payment", [(start, amount)], "|".join(labels)))

    # 5. Wait
    if earliest and earliest <= deadline and "full_payment" in methods:
        if simulate(balance, flows, start, [(earliest, amount)], minimum, end_date=deadline):
            candidates.append((0, 0, amount, earliest, 1, "99", "wait", [(earliest, amount)], "none"))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5]))
        finishes_dl, has_changes, cost, start_d, n_pay, opt_id, method, payments, changes_text = candidates[0]

        if method == "full_payment" and payments[0][0] == start and changes_text == "none":
            status = "affordable_now"
            explanation = f"Pay {home} {money(amount)} today. This leaves at least {home} {money(minimum)} available over the next 90 days."
        elif method == "installments":
            status = "affordable_with_plan"
            first_str = payments[0][0].strftime("%d %B %Y").lstrip("0")
            explanation = f"Use {len(payments)} installments of {home} {money(payments[0][1])}, starting {first_str}. This leaves at least {home} {money(minimum)} available."
        elif method == "partial_payment":
            status = "affordable_with_plan"
            first_amt = money(payments[0][1])
            second_amt = money(payments[1][1])
            second_date_str = payments[1][0].strftime("%d %B %Y").lstrip("0")
            explanation = f"Pay {home} {first_amt} today and the remaining {home} {second_amt} on {second_date_str}. This completes the full request and keeps the {home} {money(minimum)} minimum protected."
        elif changes_text != "none":
            status = "affordable_with_plan"
            events_by_id = {e["event_id"]: e for e in all_events}
            action_phrases = []
            for act in changes_text.split("|"):
                if act.startswith("stop:"):
                    eid = act.split(":")[1]
                    desc = events_by_id.get(eid, {}).get("description") or events_by_id.get(eid, {}).get("category") or "subscription"
                    action_phrases.append(f"Stop the {desc.lower()}")
                elif act.startswith("reduce_to:"):
                    parts = act.split(":")
                    eid = parts[1]
                    target_amt = parts[2]
                    cat = events_by_id.get(eid, {}).get("category") or "flexible spending"
                    action_phrases.append(f"Reduce {cat} to {home} {target_amt}")
            action_desc = ", and ".join(action_phrases) if action_phrases else "Apply spending adjustments"
            explanation = f"{action_desc}, then pay {home} {money(amount)} today. This leaves at least {home} {money(minimum)} available."
        elif method == "wait":
            status = "affordable_later"
            wait_date_str = payments[0][0].strftime("%d %B %Y").lstrip("0")
            explanation = f"Pay {home} {money(amount)} in full on {wait_date_str}. Paying earlier would take the balance below the {home} {money(minimum)} minimum."
        else:
            status = "affordable_with_plan"
            explanation = f"Pay {home} {money(amount)} using {method.replace('_', ' ')}."

        return {
            "request_id": request["request_id"],
            "amount_safe_to_pay": money(safe),
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": payment_string(payments),
            "earliest_date_for_full_payment": earliest.isoformat() if earliest else "",
            "spending_changes_needed": changes_text or "none",
            "decision_explanation": explanation,
        }

    deadline_str = deadline.strftime("%d %B %Y").lstrip("0")
    return {
        "request_id": request["request_id"],
        "amount_safe_to_pay": money(safe),
        "affordability_status": "not_affordable",
        "recommended_payment_method": "not_recommended",
        "payment_plan": "none",
        "earliest_date_for_full_payment": earliest.isoformat() if earliest else "",
        "spending_changes_needed": "none",
        "decision_explanation": f"Do not make this payment by {deadline_str}. None of the available options keeps the {home} {money(minimum)} minimum protected.",
    }


def run(dataset_dir: Path, output_path: Path) -> None:
    data = load_dataset(dataset_dir)
    rates = data["rates_by_date_pair"]
    events_by_user = data["events_by_user"]
    options = data["request_payment_options"]
    messages = data.get("messages_by_user", {})
    profiles = data["profiles_by_user"]

    rows = [
        decide(
            r,
            profiles.get(r["user_id"], {}),
            events_by_user.get(r["user_id"], []),
            rates,
            messages.get(r["user_id"], []),
            options,
        )
        for r in data["requests"]
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


def parse_args():
    p = argparse.ArgumentParser(description="Deterministic Buy or Wait? financial decision agent")
    p.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    p.add_argument("--output", type=Path, default=Path("output.csv"))
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.dataset_dir, args.output)
