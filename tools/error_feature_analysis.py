from __future__ import annotations
import csv, math, sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from data_loader import load_dataset
from evidence import resolve_image_amounts
from main import build_flows, dec, normalize_events, parse_date, money

DATA = Path('/home/ubuntu/hackerrank-orchestrate-september26/dataset')
D = load_dataset(DATA)
IMAGES = resolve_image_amounts(D['images'], DATA / 'media/images')
with (DATA / 'sample_requests.csv').open() as f:
    samples = list(csv.DictReader(f))

def corr(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0

records = []
for request in samples:
    profile = D['profiles_by_user'][request['user_id']]
    events = normalize_events(D['events_by_user'].get(request['user_id'], []), profile['home_currency'], D['rates_by_date_pair'], IMAGES)
    start = parse_date(request['request_date'])
    balance, flows, relevant, projected = build_flows(request, profile, events, D['rates_by_date_pair'], D['messages_by_user'].get(request['user_id'], []), recurrence_estimator='minimum')
    truth = dec(request['amount_safe_to_pay'])
    opening = dec(profile['current_available_balance'])
    minimum = dec(profile['minimum_balance_to_keep'])
    first_week_end = start + timedelta(days=7)
    first7_events = [e for e in events if start <= e['cash_date'] < first_week_end]
    first7_projected = [x for x in projected if start <= x[0] < first_week_end]
    first7_known = [e for e in relevant if start <= e['cash_date'] < first_week_end]
    daily_debits = defaultdict(Decimal)
    for when, amount, _ in projected:
        daily_debits[when] += amount
    running = opening
    min_close = opening
    for offset in range(91):
        when = start + timedelta(days=offset)
        running += flows[when]
        min_close = min(min_close, running)
    predicted = min_close - minimum
    error = predicted - truth
    records.append({
        'id': request['request_id'], 'truth': truth, 'predicted': predicted,
        'error': error, 'abs_error': abs(error), 'initial_balance': opening,
        'minimum': minimum, 'requested': dec(request['requested_amount']),
        'balance_ratio': opening / dec(request['requested_amount']) if dec(request['requested_amount']) else 0,
        'first7_debits': sum((e['home_amount'] for e in first7_events if e['direction'] == 'debit'), Decimal(0)),
        'first7_credits': sum((e['home_amount'] for e in first7_events if e['direction'] == 'credit'), Decimal(0)),
        'first7_projected_debits': sum((x[1] for x in first7_projected), Decimal(0)),
        'first7_known_debits': sum((e['home_amount'] for e in first7_known if e['direction'] == 'debit'), Decimal(0)),
        'first7_projected_count': len(first7_projected), 'first7_known_count': len(first7_known),
        'max_daily_debit': max(daily_debits.values(), default=Decimal(0)),
        'projected_count': len(projected), 'projected_days': len(set(x[0] for x in projected)),
        'min_close': min_close,
    })

print('CORRELATION OF STRUCTURAL FEATURES WITH SIGNED ERROR AND ABSOLUTE ERROR')
features = ['initial_balance','minimum','requested','balance_ratio','first7_debits','first7_credits','first7_projected_debits','first7_known_debits','first7_projected_count','first7_known_count','max_daily_debit','projected_count','projected_days','min_close']
for feature in features:
    xs = [float(row[feature]) for row in records]
    print(feature, 'signed=', round(corr(xs, [float(row['error']) for row in records]), 3), 'absolute=', round(corr(xs, [float(row['abs_error']) for row in records]), 3))

print('\nREQUEST 05 AND 17 DETAIL')
for row in records:
    if row['id'] in {'request_05', 'request_17'}:
        print(row)

print('\nFIRST 7 DAYS REQUEST 03/04 USING PRODUCTION MINIMUM MODEL')
for request in samples:
    if request['request_id'] not in {'request_03', 'request_04'}:
        continue
    profile = D['profiles_by_user'][request['user_id']]
    events = normalize_events(D['events_by_user'][request['user_id']], profile['home_currency'], D['rates_by_date_pair'], IMAGES)
    start = parse_date(request['request_date'])
    balance, flows, relevant, projected = build_flows(request, profile, events, D['rates_by_date_pair'], D['messages_by_user'].get(request['user_id'], []), recurrence_estimator='minimum')
    print('\n', request['request_id'], 'opening', profile['current_available_balance'], 'minimum', profile['minimum_balance_to_keep'], 'expected_safe', request['amount_safe_to_pay'])
    running = balance
    for offset in range(8):
        when = start + timedelta(days=offset)
        net = flows[when]
        running += net
        print(when, 'net', money(net), 'closing', money(running), 'known=', [(e['event_id'], money(e['home_amount']), e['status']) for e in relevant if e['cash_date'] == when], 'projected=', [(eid, money(amount)) for d, amount, eid in projected if d == when])
    print('reference_implied_bottleneck', money(dec(profile['minimum_balance_to_keep']) + dec(request['amount_safe_to_pay'])))

with open('/tmp/error_features.csv', 'w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
