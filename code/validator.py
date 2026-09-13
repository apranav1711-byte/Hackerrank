from __future__ import annotations

import csv
from datetime import date, timedelta
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


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid ISO date: {value!r}") from exc


def validate_output(
    output_path: Path,
    requests: list[dict[str, str]],
    profiles_by_user: dict[str, dict[str, str]] | None = None,
    options: list[dict[str, str]] | None = None,
) -> list[str]:
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
    options_by_request = {}
    if options:
        for opt in options:
            options_by_request.setdefault(opt["request_id"], []).append(opt)

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

        status = row.get("affordability_status")
        method = row.get("recommended_payment_method")
        plan = row.get("payment_plan", "")
        changes = row.get("spending_changes_needed", "")
        earliest = row.get("earliest_date_for_full_payment", "").strip()

        if status not in STATUSES:
            errors.append(f"row {number}: invalid affordability_status '{status}'")
        if method not in METHODS:
            errors.append(f"row {number}: invalid recommended_payment_method '{method}'")
        if not row.get("decision_explanation", "").strip():
            errors.append(f"row {number}: empty decision_explanation")

        # 1. Consistency between status, method, and plan (Matthew-style invariants)
        if status == "affordable_now":
            if method != "full_payment":
                errors.append(f"row {number}: affordable_now must use full_payment method")
            if changes != "none":
                errors.append(f"row {number}: affordable_now cannot require spending changes")
            if safe != requested:
                errors.append(f"row {number}: affordable_now requires amount_safe_to_pay == requested_amount ({safe} != {requested})")
            if earliest != request.get("request_date", ""):
                errors.append(f"row {number}: affordable_now requires earliest_date_for_full_payment == request_date ({earliest} != {request.get('request_date')})")

        elif status == "not_affordable":
            if method != "not_recommended":
                errors.append(f"row {number}: not_affordable must recommend not_recommended")
            if plan != "none":
                errors.append(f"row {number}: not_affordable must have payment_plan='none'")
            if earliest != "":
                errors.append(f"row {number}: not_affordable requires empty earliest_date_for_full_payment, got '{earliest}'")

        elif status == "affordable_later":
            if method != "wait":
                errors.append(f"row {number}: affordable_later must use wait method")
            if not earliest:
                errors.append(f"row {number}: affordable_later requires earliest_date_for_full_payment")

        # Invariant for wait
        if method == "wait":
            if status != "affordable_later":
                errors.append(f"row {number}: wait requires status affordable_later, got '{status}'")
            if not earliest:
                errors.append(f"row {number}: wait requires non-empty earliest_date_for_full_payment")

        # Invariant for full_payment
        if method == "full_payment":
            if status not in ("affordable_now", "affordable_with_plan"):
                errors.append(f"row {number}: full_payment requires affordable_now or affordable_with_plan, got '{status}'")

        # 2. Validate partial payment sums and dates
        if method == "partial_payment":
            if status != "affordable_with_plan":
                errors.append(f"row {number}: partial_payment requires status affordable_with_plan, got '{status}'")
            if plan == "none":
                errors.append(f"row {number}: partial_payment method requires a valid payment_plan")
            else:
                entries = plan.split("|")
                if len(entries) != 2:
                    errors.append(f"row {number}: partial_payment plan must have exactly 2 entries")
                total_sum = Decimal("0")
                prev_date = None
                for entry in entries:
                    if ":" not in entry:
                        errors.append(f"row {number}: invalid plan entry '{entry}'")
                        continue
                    d_str, a_str = entry.split(":", 1)
                    try:
                        d_val = parse_iso_date(d_str)
                        amt_val = decimal(a_str)
                        total_sum += amt_val
                        if prev_date and d_val <= prev_date:
                            errors.append(f"row {number}: payment plan dates must be strictly chronological")
                        prev_date = d_val
                    except ValueError as exc:
                        errors.append(f"row {number}: {exc} in payment_plan")
                if abs(total_sum - decimal(request["requested_amount"])) > Decimal("0.01"):
                    errors.append(f"row {number}: partial payment plan sum {total_sum} does not equal requested {request['requested_amount']}")

        # 3. Validate installment plan against options
        if method == "installments":
            if status != "affordable_with_plan":
                errors.append(f"row {number}: installments requires status affordable_with_plan, got '{status}'")
            if options_by_request:
                req_opts = options_by_request.get(request["request_id"], [])
                valid_opt_plans = [
                    "|".join(f"{parse_iso_date(opt['first_payment_date']) + timedelta(days=int(opt['payment_frequency_days'] or 0)*i)}:{decimal(opt['payment_amount']):.2f}" for i in range(int(opt["number_of_payments"])))
                    for opt in req_opts if opt["payment_method"] == "installments"
                ]
                # Verify plan syntax
                entries = plan.split("|")
                for entry in entries:
                    if ":" not in entry:
                        errors.append(f"row {number}: invalid plan entry '{entry}'")
                        continue
                    d_str, a_str = entry.split(":", 1)
                    try:
                        parse_iso_date(d_str)
                        decimal(a_str)
                    except ValueError as exc:
                        errors.append(f"row {number}: {exc} in installment plan")

        # 4. Validate spending changes syntax and invariants (Checks 11..14)
        if changes != "none":
            actions = changes.split("|")
            if len(actions) > 3:
                errors.append(f"row {number}: spending_changes_needed has {len(actions)} actions; maximum allowed is 3")
            seen_stop = set()
            seen_reduce = set()
            for act in actions:
                parts = act.split(":")
                kind = parts[0]
                if kind == "stop" and len(parts) == 2:
                    eid = parts[1]
                    seen_stop.add(eid)
                elif kind == "reduce_to" and len(parts) == 3:
                    eid = parts[1]
                    try:
                        decimal(parts[2])
                    except ValueError:
                        errors.append(f"row {number}: invalid amount in reduce_to action '{act}'")
                    seen_reduce.add(eid)
                else:
                    errors.append(f"row {number}: invalid spending_changes_needed action '{act}'")
            conflict = seen_stop & seen_reduce
            if conflict:
                errors.append(f"row {number}: event {sorted(conflict)} is both stopped and reduced")

        # 5. Validate earliest date format and forecast range
        if earliest:
            try:
                e_date = parse_iso_date(earliest)
                r_date = parse_iso_date(request["request_date"])
                if not (r_date <= e_date <= r_date + timedelta(days=90)):
                    errors.append(f"row {number}: earliest_date_for_full_payment '{earliest}' is outside 90-day forecast horizon")
            except ValueError as exc:
                errors.append(f"row {number}: invalid earliest_date_for_full_payment '{earliest}'")

    return errors
