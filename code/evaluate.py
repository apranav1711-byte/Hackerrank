from __future__ import annotations

import argparse
from pathlib import Path

from data_loader import load_dataset
from main import run
from validator import validate_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and validate the Buy or Wait? agent")
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--output", type=Path, default=Path("output.csv"))
    args = parser.parse_args()
    data = load_dataset(args.dataset_dir)
    run(args.dataset_dir, args.output)
    errors = validate_output(args.output, data["requests"])
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"VALIDATION PASSED: {len(data['requests'])} request rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
