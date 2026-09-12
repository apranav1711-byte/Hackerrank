from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path("/home/ubuntu/hackerrank-orchestrate-september26/dataset")
sys.path.insert(0, str(ROOT / "code"))
from data_loader import load_dataset
from evidence import resolve_image_amounts
from main import build_flows, dec, normalize_events, parse_date, safe_amount, ZERO

EXACT_DIFF = Decimal("968384.49")

data = load_dataset(DATASET)
images = resolve_image_amounts(data["images"], DATASET / "media" / "images")
with (DATASET / "sample_requests.csv").open(encoding="utf-8", newline="") as handle:
    samples = list(csv.DictReader(handle))


def baseline(request):
    profile = data["profiles_by_user"][request["user_id"]]
    events = normalize_events(
        data["events_by_user"].get(request["user_id"], []),
        profile["home_currency"], data["rates_by_date_pair"], images,
    )
    start = parse_date(request["request_date"])
    end = start + timedelta(days=90)
    balance, flows, relevant, projected = build_flows(
        request, profile, events, data["rates_by_date_pair"],
        data.get("messages_by_user", {}).get(request["user_id"], []),
    )
    running = balance
    records = []
    projected_by_date = defaultdict(list)
    for when, amount, event_id in projected:
        projected_by_date[when].append((event_id, amount))
    known_by_date = defaultdict(list)
    for event in relevant:
        known_by_date[event["cash_date"]].append((event["event_id"], event["home_amount"]))
    for offset in range(91):
        when = start + timedelta(days=offset)
        opening = running
        net = flows[when]
        running += net
        records.append({
            "date": when,
            "opening": opening,
            "net": net,
            "closing": running,
            "projected": list(projected_by_date[when]),
            "known": list(known_by_date[when]),
        })
    bottleneck = min(records, key=lambda row: row["closing"])
    minimum = dec(profile["minimum_balance_to_keep"])
    truth = dec(request["amount_safe_to_pay"])
    return {
        "request": request,
        "profile": profile,
        "events": events,
        "balance": balance,
        "minimum": minimum,
        "truth": truth,
        "start": start,
        "records": records,
        "bottleneck": bottleneck,
        "projected": projected,
        "safe": bottleneck["closing"] - minimum,
    }


def safe_with_offset(info, offset):
    # Test a reserve offset as an abstract policy adjustment without changing production.
    target_minimum = info["minimum"] + offset
    return safe_amount(
        info["balance"],
        {row["date"]: row["net"] for row in info["records"]},
        info["start"],
        dec(info["request"]["requested_amount"]),
        target_minimum,
    )


infos = [baseline(request) for request in samples]
print("BOTTLENECK SCAN")
print("===============")
print("request|truth|engine_bottleneck|engine_safe|reference_delta|bottleneck_date|projected_ids")
for info in infos:
    b = info["bottleneck"]
    delta = info["safe"] - info["truth"]
    ids = "|".join(event_id for event_id, _ in b["projected"])
    print(
        f"{info['request']['request_id']}|{info['truth']}|{b['closing']}|{info['safe']}|{delta}|{b['date']}|{ids}"
    )

print("\nEXACT 968384.49 OFFSET EXPERIMENT")
print("scope|exact_safe_amount_matches|mean_absolute_error")
for scope in ("none", "all_cases", "cases_with_positive_overestimate", "request_02_only"):
    exact = 0
    error = ZERO
    for info in infos:
        apply = scope == "all_cases" or (scope == "request_02_only" and info["request"]["request_id"] == "request_02") or (scope == "cases_with_positive_overestimate" and info["safe"] > info["truth"])
        value = safe_with_offset(info, EXACT_DIFF if apply else ZERO)
        exact += value == info["truth"]
        error += abs(value - info["truth"])
    print(f"{scope}|{exact}/{len(infos)}|{(error/Decimal(len(infos))).quantize(Decimal('0.01'))}")

print("\nBOTTLENECK CONTRIBUTORS FOR FAILING CASES")
for info in infos:
    if info["safe"] == info["truth"]:
        continue
    b = info["bottleneck"]
    contributors = []
    for event_id, amount in b["projected"]:
        contributors.append(f"{event_id}:-{amount}")
    for event_id, amount in b["known"]:
        contributors.append(f"known:{event_id}:-{amount}")
    print(
        info["request"]["request_id"],
        "truth=", info["truth"],
        "delta=", info["safe"] - info["truth"],
        "bottleneck=", b["date"],
        "contributors=", ",".join(contributors) or "none",
    )

print("\nEVENT_162_AND_175_TIMING")
for info in infos:
    streams = defaultdict(list)
    for when, amount, event_id in info["projected"]:
        if event_id in {"event_162", "event_175"}:
            streams[event_id].append((when, amount))
    if streams:
        parts = []
        for event_id in ("event_162", "event_175"):
            items = streams[event_id]
            if not items:
                continue
            gaps = [(b[0] - a[0]).days for a, b in zip(items, items[1:])]
            parts.append(f"{event_id}:dates={[x[0].isoformat() for x in items]},gaps={gaps},amounts={[str(x[1]) for x in items]}")
        print(info["request"]["request_id"], " ".join(parts))

print("\nREQUEST_02_DATE_LEVEL_DETAIL")
info = next(x for x in infos if x["request"]["request_id"] == "request_02")
for row in info["records"]:
    if row["net"] or row["projected"] or row["known"]:
        print(row["date"], "opening=", row["opening"], "net=", row["net"], "closing=", row["closing"], "projected=", row["projected"], "known=", row["known"])
