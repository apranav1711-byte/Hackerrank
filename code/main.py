from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from data_loader import load_dataset
from validator import OUTPUT_COLUMNS


def money(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def baseline_decision(request: dict[str, str], profile: dict[str, str] | None) -> dict[str, str]:
    """Conservative scaffold decision.

    This is intentionally a safe starting point, not the final leaderboard engine.
    Replace it with the simulator and planner described in docs/IMPLEMENTATION_PLAN.md.
    """
    amount = money(request["requested_amount"])
    balance = money((profile or {}).get("current_available_balance", "0"))
    minimum = money((profile or {}).get("minimum_balance_to_keep", "0"))
    safe = max(Decimal("0"), min(amount, balance - minimum))
    currency = (profile or {}).get("home_currency", "")
    date = request["request_date"]
    if safe >= amount and "full_payment" in (profile or {}).get("payment_methods_user_will_consider", "").split("|"):
        status = "affordable_now"
        method = "full_payment"
        plan = f"{date}:{amount}"
        earliest = date
        explanation = f"Pay {currency} {amount} today; the baseline reserve check leaves at least {currency} {minimum} available."
    else:
        status = "not_affordable"
        method = "not_recommended"
        plan = "none"
        earliest = ""
        explanation = f"Do not proceed in the baseline engine; future obligations and the minimum reserve require a full forecast before approval."
    return {
        "request_id": request["request_id"],
        "amount_safe_to_pay": str(safe),
        "affordability_status": status,
        "recommended_payment_method": method,
        "payment_plan": plan,
        "earliest_date_for_full_payment": earliest,
        "spending_changes_needed": "none",
        "decision_explanation": explanation,
    }


def run(dataset_dir: Path, output_path: Path) -> None:
    data = load_dataset(dataset_dir)
    rows = [
        baseline_decision(request, data["profiles_by_user"].get(request["user_id"]))
        for request in data["requests"]
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buy or Wait? agent entry point")
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--output", type=Path, default=Path("output.csv"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.dataset_dir, args.output)
