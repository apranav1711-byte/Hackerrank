from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "code/main.py"
DATASET = Path("/home/ubuntu/hackerrank-orchestrate-september26/dataset")
BASE = MAIN.read_text()

variants = {
    "baseline": [],
    "variable_by_description": [
        (
            'key = cat if cat in VARIABLE_CATS else (cat, e.get("description", ""))',
            'key = (cat, e.get("description", ""))',
        ),
    ],
    "variable_by_description_mean": [
        (
            'key = cat if cat in VARIABLE_CATS else (cat, e.get("description", ""))',
            'key = (cat, e.get("description", ""))',
        ),
        (
            'if recurrence_estimator == "minimum":\n            amt = amts[0]',
            'if recurrence_estimator == "minimum":\n            amt = sum(amts, ZERO) / Decimal(len(amts))',
        ),
    ],
    "variable_by_description_latest": [
        (
            'key = cat if cat in VARIABLE_CATS else (cat, e.get("description", ""))',
            'key = (cat, e.get("description", ""))',
        ),
        (
            'if recurrence_estimator == "minimum":\n            amt = amts[0]',
            'if recurrence_estimator == "minimum":\n            amt = items[-1]["home_amount"]',
        ),
    ],
    "variable_by_description_strict_gap": [
        (
            'key = cat if cat in VARIABLE_CATS else (cat, e.get("description", ""))',
            'key = (cat, e.get("description", ""))',
        ),
        (
            'gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if 3 <= (b - a).days <= 370]',
            'gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if 6 <= (b - a).days <= 370]',
        ),
    ],
}


def run_variant(name, replacements):
    text = BASE
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"pattern not found for {name}: {old[:60]}")
        text = text.replace(old, new, 1)
    MAIN.write_text(text)
    proc = subprocess.run(
        ["python3", "tests/eval_samples.py", "--dataset-dir", str(DATASET)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    exact = re.search(r"Exact match on ALL 6 key fields: (\d+/25)", proc.stdout)
    amount = re.search(r"amount_safe_to_pay: (\d+/25)", proc.stdout)
    mismatches = re.search(r"Mismatched requests count: (\d+)", proc.stdout)
    request_02 = []
    lines = proc.stdout.splitlines()
    for i, line in enumerate(lines):
        if line == "Request request_02:":
            request_02 = lines[i:i+8]
            break
    return (
        exact.group(1) if exact else "ERROR",
        amount.group(1) if amount else "ERROR",
        mismatches.group(1) if mismatches else "ERROR",
        request_02,
    )


try:
    print("variant|exact|amount_exact|mismatches")
    for name, replacements in variants.items():
        exact, amount, mismatches, request_02 = run_variant(name, replacements)
        print(f"{name}|{exact}|{amount}|{mismatches}")
        if name in {"baseline", "variable_by_description"}:
            print("request_02_snapshot")
            print("\n".join(request_02))
finally:
    MAIN.write_text(BASE)
