from __future__ import annotations

import csv
import sys
import argparse
from pathlib import Path

# Add code directory to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from data_loader import load_dataset
from main import decide
import main

def evaluate_samples(dataset_dir: Path):
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

    print(f"Exact match on ALL 6 key fields: {exact_matches}/{len(samples)}")
    for k in fields:
        print(f"  {k}: {matches[k]}/{len(samples)} ({matches[k]/len(samples)*100:.1f}%)")

    print(f"\nMismatched requests count: {len(mismatches)}")
    for req_id, d in mismatches:
        print(f"\nRequest {req_id}:")
        for k, (gt, pr) in d.items():
            print(f"  {k}:")
            print(f"    Ground Truth: {gt}")
            print(f"    Predicted:    {pr}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset")
    evaluate_samples(parser.parse_args().dataset_dir)
