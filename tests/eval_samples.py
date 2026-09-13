from __future__ import annotations

import csv
import sys
import argparse
import json
from pathlib import Path

# Add code directory to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from data_loader import load_dataset
from main import cash_flow_trace, decide
import main

def evaluate_samples(dataset_dir: Path, trace_output: Path | None = None):
    data = load_dataset(dataset_dir)
    
    samples_path = dataset_dir / "sample_requests.csv"
    with samples_path.open(encoding="utf-8") as f:
        samples = list(csv.DictReader(f))

    print(f"Total sample requests: {len(samples)}")
    main.DATA_OPTIONS = data["request_payment_options"]
    rates = data["rates_by_date_pair"]
    events_by_user = data["events_by_user"]
    profiles = data["profiles_by_user"]
    messages = data.get("messages_by_user", {})
    from evidence import resolve_image_amounts
    image_amounts = resolve_image_amounts(data["images"], dataset_dir / "media" / "images")

    fields = [
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
    ]
    matches = {k: 0 for k in fields}
    mismatches = []
    mismatch_traces = []
    exact_matches = 0

    for s in samples:
        req_id = s["request_id"]
        u_id = s["user_id"]
        options = data["request_payment_options"]
        pred = decide(s, profiles.get(u_id, {}), events_by_user.get(u_id, []), rates, messages.get(u_id, []), options, image_amounts)

        diffs = {}
        all_match = True
        for k in fields:
            gt_val = s[k].strip()
            pred_val = str(pred[k]).strip()
            # If float or decimal representation difference (e.g. 0 vs 0.00)
            if gt_val == pred_val:
                matches[k] += 1
            else:
                try:
                    from decimal import Decimal
                    if Decimal(gt_val) == Decimal(pred_val):
                        matches[k] += 1
                        continue
                except Exception:
                    pass
                diffs[k] = (gt_val, pred_val)
                all_match = False

        if all_match:
            exact_matches += 1
        else:
            mismatches.append((req_id, diffs))
            if trace_output:
                mismatch_traces.append({
                    "request_id": req_id,
                    "expected": {k: s[k] for k in fields},
                    "predicted": {k: pred[k] for k in fields},
                    "trace": cash_flow_trace(
                        s,
                        profiles.get(u_id, {}),
                        events_by_user.get(u_id, []),
                        rates,
                        messages.get(u_id, []),
                        image_amounts,
                    ),
                })

    strategic_fields = [
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
    ]
    strategic_matches = 0
    safe_within_5pct = 0
    safe_within_15pct = 0

    for s in samples:
        u_id = s["user_id"]
        pred = decide(s, profiles.get(u_id, {}), events_by_user.get(u_id, []), rates, messages.get(u_id, []), data["request_payment_options"], image_amounts)
        if all(str(pred[k]).strip() == s[k].strip() for k in strategic_fields):
            strategic_matches += 1
        try:
            from decimal import Decimal
            gt_s = Decimal(s["amount_safe_to_pay"])
            pr_s = Decimal(str(pred["amount_safe_to_pay"]))
            denom = max(gt_s, pr_s, Decimal("1"))
            err = abs(gt_s - pr_s) / denom
            if err <= Decimal("0.05"):
                safe_within_5pct += 1
            if err <= Decimal("0.15"):
                safe_within_15pct += 1
        except Exception:
            pass

    print(f"Exact match on ALL 6 key fields: {exact_matches}/{len(samples)}")
    print(f"Strategic match (all 5 core decision fields): {strategic_matches}/{len(samples)} ({strategic_matches/len(samples)*100:.1f}%)")
    print(f"  amount_safe_to_pay exact: {matches['amount_safe_to_pay']}/{len(samples)} ({matches['amount_safe_to_pay']/len(samples)*100:.1f}%)")
    print(f"  amount_safe_to_pay within 5% error: {safe_within_5pct}/{len(samples)} ({safe_within_5pct/len(samples)*100:.1f}%)")
    print(f"  amount_safe_to_pay within 15% error: {safe_within_15pct}/{len(samples)} ({safe_within_15pct/len(samples)*100:.1f}%)")
    for k in strategic_fields:
        print(f"  {k}: {matches[k]}/{len(samples)} ({matches[k]/len(samples)*100:.1f}%)")

    print(f"\nMismatched requests count: {len(mismatches)}")
    for req_id, d in mismatches:
        print(f"\nRequest {req_id}:")
        for k, (gt, pr) in d.items():
            print(f"  {k}:")
            print(f"    Ground Truth: {gt}")
            print(f"    Predicted:    {pr}")
    if trace_output:
        with trace_output.open("w", encoding="utf-8") as handle:
            for row in mismatch_traces:
                handle.write(json.dumps(row) + "\n")
        print(f"Wrote {len(mismatch_traces)} mismatch traces to {trace_output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset")
    parser.add_argument("--trace-output", type=Path, default=None)
    args = parser.parse_args()
    evaluate_samples(args.dataset_dir, args.trace_output)
