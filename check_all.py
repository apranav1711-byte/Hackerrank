"""
check_all.py - Master Pre-Submission Quality Gate Runner for HackerRank Orchestrate
Executes full test suite, ground-truth benchmarks, dataset evaluation, validator,
packaging, and log compliance in a single automated command.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def print_step(title: str):
    print(f"\n{'='*70}\n[STEP] {title}\n{'='*70}")


def run_unit_tests() -> bool:
    print_step("1. Running Automated Unit Tests")
    res = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"], cwd=ROOT)
    return res.returncode == 0


def run_benchmark() -> bool:
    print_step("2. Running Ground-Truth Benchmark on Public Samples")
    res = subprocess.run([sys.executable, "tests/eval_samples.py"], cwd=ROOT)
    return res.returncode == 0


def run_evaluation() -> bool:
    print_step("3. Evaluating and Validating Output on Full Dataset (250 Requests)")
    res = subprocess.run(
        [sys.executable, "code/evaluate.py", "--dataset-dir", "dataset", "--output", "output.csv"],
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
    if "tool=Antigravity" not in text:
        print("ERROR: tool=Antigravity tag missing in log.txt.")
        return False
    print("Audit log verified: properly formatted and AGENTS.md compliant.")
    return True


def main():
    print(f"Starting HackerRank Orchestrate Quality Gate in {ROOT}")
    steps = [
        ("Unit Tests", run_unit_tests),
        ("Benchmark Evaluation", run_benchmark),
        ("Dataset & Validator", run_evaluation),
        ("Packaging & Archive", run_packaging),
        ("Log Verification", verify_log),
    ]

    results = []
    for name, func in steps:
        ok = func()
        results.append((name, ok))

    print(f"\n{'='*70}\nFINAL QUALITY GATE SUMMARY\n{'='*70}")
    all_passed = True
    for name, ok in results:
        status = "PASSED [OK]" if ok else "FAILED [X]"
        print(f"  * {name:<25}: {status}")
        if not ok:
            all_passed = False

    print("="*70)
    if all_passed:
        print("ALL QUALITY CHECKS PASSED - Solution is 100% submission ready!")
        print("Submission portal: https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission")
        return 0
    else:
        print("SOME CHECKS FAILED - Please review the logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
