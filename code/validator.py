from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path


OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]
STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}


def decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc


def validate_output(output_path: Path, requests: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != OUTPUT_COLUMNS:
            errors.append(f"columns must be exactly {OUTPUT_COLUMNS}; got {reader.fieldnames}")
        rows = list(reader)

    request_ids = [row["request_id"] for row in requests]
    output_ids = [row.get("request_id", "") for row in rows]
    if len(rows) != len(requests):
        errors.append(f"expected {len(requests)} rows, got {len(rows)}")
    if len(set(output_ids)) != len(output_ids):
        errors.append("duplicate request_id values")
    if set(output_ids) != set(request_ids):
        errors.append("output request IDs do not match input request IDs")

    requests_by_id = {row["request_id"]: row for row in requests}
    for number, row in enumerate(rows, start=2):
        request = requests_by_id.get(row.get("request_id", ""))
        if request is None:
            continue
        try:
            safe = decimal(row["amount_safe_to_pay"])
            requested = decimal(request["requested_amount"])
            if not (Decimal("0") <= safe <= requested):
                errors.append(f"row {number}: safe amount is outside [0, requested_amount]")
        except ValueError as exc:
            errors.append(f"row {number}: {exc}")
        if row.get("affordability_status") not in STATUSES:
            errors.append(f"row {number}: invalid affordability_status")
        if row.get("recommended_payment_method") not in METHODS:
            errors.append(f"row {number}: invalid recommended_payment_method")
        if not row.get("decision_explanation", "").strip():
            errors.append(f"row {number}: empty decision_explanation")

    return errors
