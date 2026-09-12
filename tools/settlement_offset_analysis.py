from __future__ import annotations
import csv,re,subprocess,sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from data_loader import load_dataset
from evidence import resolve_image_amounts
from main import build_flows,dec,normalize_events,parse_date,money
ROOT=Path(__file__).resolve().parents[1]; DATA=Path('/home/ubuntu/hackerrank-orchestrate-september26/dataset'); D=load_dataset(DATA); IMAGES=resolve_image_amounts(D['images'],DATA/'media/images')
with (DATA/'sample_requests.csv').open() as f: samples=list(csv.DictReader(f))

def ledger(r):
 p=D['profiles_by_user'][r['user_id']]; ev=normalize_events(D['events_by_user'][r['user_id']],p['home_currency'],D['rates_by_date_pair'],IMAGES); start=parse_date(r['request_date']); bal,flows,rel,proj=build_flows(r,p,ev,D['rates_by_date_pair'],D['messages_by_user'].get(r['user_id'],[]),recurrence_estimator='minimum'); by=defaultdict(list)
 for e in rel: by[e['cash_date']].append(('known',e['event_id'],e['direction'],e['home_amount'],e['status']))
 for d,a,eid in proj: by[d].append(('projected',eid,'debit',a,''))
 running=bal
 print('\n===',r['request_id'],'opening=',money(bal),'minimum=',p['minimum_balance_to_keep'],'expected=',r['amount_safe_to_pay'],'===')
 for i in range(91):
  d=start+timedelta(days=i); opening=running; net=flows[d]; running+=net
  if net or by[d]: print(d,'open=',money(opening),'net=',money(net),'close=',money(running),'items=',[(x[0],x[1],x[2],money(x[3]),x[4]) for x in by[d]])

for rid in ['request_02','request_04','request_10','request_25']:
 ledger(next(x for x in samples if x['request_id']==rid))

# Spec cross-check for minimum-floor semantics and raw request event status.
print('\n=== SPEC-RELEVANT RAW EVENTS request_10/request_25 ===')
for rid in ['request_10','request_25']:
 r=next(x for x in samples if x['request_id']==rid); p=D['profiles_by_user'][r['user_id']]; start=parse_date(r['request_date']); print(rid,'profile_balance',p['current_available_balance'],'minimum',p['minimum_balance_to_keep'],'request_date',start)
 for e in D['events_by_user'][r['user_id']]:
  d=e.get('settlement_date') or e.get('event_date')
  if d and parse_date(d)>=start and parse_date(d)<=start+timedelta(days=7): print(e)

# Variant sweep: offset every generated recurring debit from its source date. This is a diagnostic only.
main=ROOT/'code/main.py'; base=main.read_text(); needle='''if curr_d >= start:\n                cat_match = key if is_var else key[0]'''
print('\n=== SETTLEMENT OFFSET SWEEP ===')
for offset in [-3,-2,-1,0,1,2,3]:
 replacement=f'''if curr_d >= start:\n                curr_d = curr_d + timedelta(days={offset})\n                cat_match = key if is_var else key[0]'''
 if needle not in base: raise SystemExit('pattern missing')
 main.write_text(base.replace(needle,replacement,1))
 p=subprocess.run(['python3','tests/eval_samples.py','--dataset-dir',str(DATA)],cwd=ROOT,capture_output=True,text=True)
 ex=re.search(r'Exact match on ALL 6 key fields: (\d+/25)',p.stdout); am=re.search(r'amount_safe_to_pay: (\d+/25)',p.stdout); mm=re.search(r'Mismatched requests count: (\d+)',p.stdout)
 print('offset_days',offset,'exact',ex.group(1) if ex else 'ERR','amount',am.group(1) if am else 'ERR','mismatches',mm.group(1) if mm else 'ERR')
main.write_text(base)
