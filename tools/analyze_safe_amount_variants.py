from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path("/home/ubuntu/hackerrank-orchestrate-september26/dataset")
sys.path.insert(0, str(ROOT / "code"))

from data_loader import load_dataset  # noqa: E402
from evidence import resolve_image_amounts  # noqa: E402
from main import (  # noqa: E402
    HORIZON,
    ZERO,
    build_flows,
    dec,
    money,
    normalize_events,
    parse_date,
    safe_amount,
    simulate,
)


def sample_rows(dataset_dir: Path) -> list[dict[str, str]]:
    with (dataset_dir / "sample_requests.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def flow_without_projections(flows, projected_items):
    result = defaultdict(lambda: ZERO, flows)
    for when, amount, _ in projected_items:
        result[when] += amount
    return result


def variant_amounts(request, profile, events, rates, messages, image_amounts, options):
    start = parse_date(request["request_date"])
    deadline = parse_date(request["desired_completion_date"])
    requested = dec(request["requested_amount"])
    minimum = dec(profile["minimum_balance_to_keep"])
    balance, median_flows, relevant, projected = build_flows(request, profile, events, rates, messages)
    _, conservative_flows, _, _ = build_flows(
        request, profile, events, rates, messages, recurrence_estimator="minimum"
    )
    variants = {}
    for name, flows in {
        "current_minimum_90d": conservative_flows,
        "median_90d": median_flows,
        "known_only_90d": flow_without_projections(median_flows, projected),
    }.items():
        variants[name] = safe_amount(balance, flows, start, requested, minimum)
        variants[f"{name}_deadline"] = safe_amount_for_end(
            balance, flows, start, requested, minimum, min(HORIZON, max(0, (deadline - start).days))
        )
        variants[f"{name}_30d"] = safe_amount_for_end(balance, flows, start, requested, minimum, 30)
        variants[f"{name}_60d"] = safe_amount_for_end(balance, flows, start, requested, minimum, 60)
    return variants, balance, median_flows, conservative_flows, relevant, projected


def safe_amount_for_end(balance, flows, start, requested, minimum, days):
    lo, hi = 0, int(requested * 100)
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = Decimal(mid) / Decimal(100)
        if simulate(balance, flows, start, [(start, candidate)], minimum, end_date=start + timedelta(days=days)):
            lo = mid + 1
        else:
            hi = mid - 1
    return max(ZERO, Decimal(hi) / Decimal(100))


def first_minimum_date(balance, flows, start, minimum):
    running = balance
    for offset in range(HORIZON + 1):
        when = start + timedelta(days=offset)
        running += flows[when]
        if running <= minimum:
            return when.isoformat(), running
    return "none", min(balance + sum(flows[d] for d in flows), balance)


def main():
    dataset_dir = DATASET
    data = load_dataset(dataset_dir)
    rates = data["rates_by_date_pair"]
    profiles = data["profiles_by_user"]
    events_by_user = data["events_by_user"]
    messages = data.get("messages_by_user", {})
    options = data["request_payment_options"]
    images = resolve_image_amounts(data["images"], dataset_dir / "media" / "images")

    rows = sample_rows(dataset_dir)
    totals = defaultdict(int)
    absolute_errors = defaultdict(Decimal)
    exact = defaultdict(int)
    request_details = {}

    for request in rows:
        profile = profiles[request["user_id"]]
        events = normalize_events(events_by_user.get(request["user_id"], []), profile["home_currency"], rates, images)
        variants, balance, median_flows, conservative_flows, relevant, projected = variant_amounts(
            request, profile, events, rates, messages.get(request["user_id"], []), images, options
        )
        truth = dec(request["amount_safe_to_pay"])
        for name, value in variants.items():
            totals[name] += 1
            absolute_errors[name] += abs(value - truth)
            if value == truth:
                exact[name] += 1
        if request["request_id"] in {"request_02", "request_03"}:
            start = parse_date(request["request_date"])
            deadline = parse_date(request["desired_completion_date"])
            request_details[request["request_id"]] = {
                "truth": money(truth),
                "balance": money(balance),
                "minimum": profile["minimum_balance_to_keep"],
                "deadline": deadline.isoformat(),
                "variants": {key: money(value) for key, value in variants.items()},
                "median_bottleneck": first_minimum_date(balance, median_flows, start, dec(profile["minimum_balance_to_keep"])),
                "conservative_bottleneck": first_minimum_date(balance, conservative_flows, start, dec(profile["minimum_balance_to_keep"])),
                "known_future": [
                    {"event_id": event["event_id"], "date": event["cash_date"].isoformat(), "amount": money(event["home_amount"]), "category": event["category"]}
                    for event in relevant
                    if event["direction"] == "debit"
                ],
                "projected": [
                    {"event_id": event_id, "date": when.isoformat(), "amount": money(amount)}
                    for when, amount, event_id in sorted(projected)
                ],
            }

    print("SAFE-AMOUNT VARIANT DIFFERENTIAL REPORT")
    print("========================================")
    print(f"Public cases: {len(rows)}")
    print("\nVariant summary:")
    print("variant|exact/25|mean_absolute_error")
    for name in sorted(totals):
        mae = absolute_errors[name] / Decimal(len(rows))
        print(f"{name}|{exact[name]}/{len(rows)}|{mae.quantize(Decimal('0.01'))}")

    for request_id in ("request_02", "request_03"):
        detail = request_details[request_id]
        print(f"\n=== {request_id} divergence ===")
        print(f"truth={detail['truth']} balance={detail['balance']} minimum={detail['minimum']} deadline={detail['deadline']}")
        print("variants=" + " ".join(f"{k}:{v}" for k, v in sorted(detail["variants"].items())))
        print(f"median_bottleneck={detail['median_bottleneck']} conservative_bottleneck={detail['conservative_bottleneck']}")
        print("known_future_debits:")
        for item in detail["known_future"]:
            print(f"  {item}")
        print("projected_debits:")
        for item in detail["projected"]:
            print(f"  {item}")


if __name__ == "__main__":
    main()
