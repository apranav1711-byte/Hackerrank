from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


CSV_NAMES = (
    "requests.csv",
    "sample_requests.csv",
    "financial_profiles.csv",
    "financial_events.csv",
    "request_payment_options.csv",
    "messages.csv",
    "images.csv",
    "exchange_rates.csv",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_dataset(dataset_dir: Path) -> dict[str, Any]:
    missing = [name for name in CSV_NAMES if not (dataset_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing dataset files in {dataset_dir}: {', '.join(missing)}"
        )

    data = {name.removesuffix(".csv"): read_csv(dataset_dir / name) for name in CSV_NAMES}
    data["profiles_by_user"] = {row["user_id"]: row for row in data["financial_profiles"]}

    def group(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row.get(key):
                result[row[key]].append(row)
        return dict(result)

    data["events_by_user"] = group(data["financial_events"], "user_id")
    data["options_by_request"] = group(data["request_payment_options"], "request_id")
    data["messages_by_request"] = group(data["messages"], "request_id")
    data["messages_by_event"] = group(data["messages"], "related_event_id")
    data["messages_by_user"] = group(data["messages"], "user_id")
    data["images_by_event"] = group(data["images"], "related_event_id")
    data["rates_by_date_pair"] = {
        (row["rate_date"], row["from_currency"], row["to_currency"]): row
        for row in data["exchange_rates"]
    }
    return data
