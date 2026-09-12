"""
check_all.py - Master Pre-Submission Quality Gate Runner for HackerRank Orchestrate
Executes full test suite, ground-truth benchmarks, dataset evaluation, validator,
packaging, and log compliance in a single automated command.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def print_step(title: str):
    print(f"\n{'='*70}\n[STEP] {title}\n{'='*70}")


def run_unit_tests() -> bool:
    print_step("1. Running Automated Unit Tests")
    res = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"], cwd=ROOT)
    return res.returncode == 0


def run_benchmark(dataset_dir: Path) -> bool | None:
    print_step("2. Running Ground-Truth Benchmark on Public Samples")
    if not dataset_dir.exists():
        print(f"SKIPPED: dataset directory not found: {dataset_dir}")
        return None
    res = subprocess.run([sys.executable, "tests/eval_samples.py", "--dataset-dir", str(dataset_dir)], cwd=ROOT)
    return res.returncode == 0


def run_evaluation(dataset_dir: Path) -> bool | None:
    print_step("3. Evaluating and Validating Output on Full Dataset (250 Requests)")
    if not dataset_dir.exists():
        print(f"SKIPPED: dataset directory not found: {dataset_dir}")
        return None
    res = subprocess.run(
        [sys.executable, "code/evaluate.py", "--dataset-dir", str(dataset_dir), "--output", "output.csv"],
        cwd=ROOT,
    )
    return res.returncode == 0


def run_packaging() -> bool:
    print_step("4. Building Submission Package (code.zip)")
    res = subprocess.run([sys.executable, "package_submission.py"], cwd=ROOT)
    if res.returncode != 0:
        return False

    zip_path = ROOT / "code.zip"
    if not zip_path.exists():
        print("ERROR: code.zip was not created.")
        return False

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        has_dataset = any("dataset" in n for n in names)
        has_usage = any("usage_report.md" in n for n in names)

        if has_dataset:
            print("ERROR: dataset files found inside code.zip (violates challenge rules).")
            return False
        if not has_usage:
            print("ERROR: evaluation/usage_report.md missing from code.zip.")
            return False

        print(f"Archive verified: {len(names)} files cleanly packaged ({zip_path.stat().st_size / 1024:.1f} KB).")
    return True


def verify_log() -> bool:
    print_step("5. Verifying Audit Log Compliance (AGENTS.md)")
    log_path = ROOT / "log.txt"
    if not log_path.exists():
        print("ERROR: log.txt missing.")
        return False
    text = log_path.read_text(encoding="utf-8")
    if "SESSION START" not in text:
        print("ERROR: SESSION START missing in log.txt.")
        return False
    if not re.search(r"^tool=\S+", text, flags=re.MULTILINE):
        print("ERROR: a non-empty tool= tag is missing in log.txt.")
        return False
    print("Audit log verified: properly formatted and AGENTS.md compliant.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the Buy or Wait quality gate")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset")
    args = parser.parse_args()

    print(f"Starting HackerRank Orchestrate Quality Gate in {ROOT}")
    print(f"Dataset directory: {args.dataset_dir}")
    steps = [
        ("Unit Tests", run_unit_tests),
        ("Benchmark Evaluation", lambda: run_benchmark(args.dataset_dir)),
        ("Dataset & Validator", lambda: run_evaluation(args.dataset_dir)),
        ("Packaging & Archive", run_packaging),
        ("Log Verification", verify_log),
    ]

    results = []
    for name, func in steps:
        ok = func()
        results.append((name, ok))

    print(f"\n{'='*70}\nFINAL QUALITY GATE SUMMARY\n{'='*70}")
    all_passed = True
    has_skips = False
    for name, ok in results:
        if ok is None:
            status = "SKIPPED [-]"
            has_skips = True
        else:
            status = "PASSED [OK]" if ok else "FAILED [X]"
        print(f"  * {name:<25}: {status}")
        if ok is False:
            all_passed = False

    print("="*70)
    if all_passed and not has_skips:
        print("ALL QUALITY CHECKS PASSED - Solution is ready for dataset-backed review!")
        print("Submission portal: https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission")
        return 0
    elif all_passed:
        print("LOCAL QUALITY CHECKS PASSED - Dataset-backed checks remain pending.")
        return 0
    else:
        print("SOME CHECKS FAILED - Please review the logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
