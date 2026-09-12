from __future__ import annotations
import csv,sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from data_loader import load_dataset
from evidence import resolve_image_amounts
from main import build_flows,dec,normalize_events,parse_date,money
DATA=Path('/home/ubuntu/hackerrank-orchestrate-september26/dataset'); D=load_dataset(DATA); imgs=resolve_image_amounts(D['images'],DATA/'media/images')
r=next(x for x in D['sample_requests'] if x['request_id']=='request_02'); p=D['profiles_by_user'][r['user_id']]; start=parse_date(r['request_date']); end=start+__import__('datetime').timedelta(days=90); truth=dec(r['amount_safe_to_pay']); events=normalize_events(D['events_by_user'][r['user_id']],p['home_currency'],D['rates_by_date_pair'],imgs); bal,flows,relevant,projected=build_flows(r,p,events,D['rates_by_date_pair'],D['messages_by_user'].get(r['user_id'],[])); proj_by=defaultdict(list)
for d,a,eid in projected: proj_by[d].append((eid,a))
print('REQUEST',r['request_id'],'start',start,'end',end,'balance',money(bal),'minimum',p['minimum_balance_to_keep'],'reference_safe_amount',money(truth),'engine_safe_amount','19335272.81')
print('reference_implied_reserve_delta',money(dec('19335272.81')-truth))
print('\nRAW HISTORICAL EVENTS USED AS STREAM SOURCES')
for e in sorted(events,key=lambda x:x['cash_date']):
 if e['direction']=='debit' and e['cash_date']<start and e['cash_date']>=start-__import__('datetime').timedelta(days=400): print(e['event_id'],e['cash_date'],e['category'],e['description'],money(e['home_amount']),e['flexibility'])
print('\nFORECAST TRANSACTIONS BY DATE')
running=bal; minrow=None
for d in sorted(set(flows)|set(proj_by)):
 if d<start or d>end: continue
 net=flows[d]; opening=running; running+=net
 if minrow is None or running<minrow[1]: minrow=(d,running)
 print(d,'opening',money(opening),'net',money(net),'closing',money(running),'projected',','.join(f'{eid}:{money(a)}' for eid,a in proj_by[d]))
print('\nENGINE BOTTLENECK',minrow[0],money(minrow[1]),'engine_safe_amount',money(minrow[1]-dec(p['minimum_balance_to_keep'])))
print('REFERENCE IMPLIED BOTTLENECK BALANCE',money(dec(p['minimum_balance_to_keep'])+truth))
print('\nPROJECTED SOURCE FREQUENCIES')
by=defaultdict(list)
for d,a,eid in projected: by[eid].append((d,a))
for eid,items in sorted(by.items()): print(eid,'count',len(items),'dates',','.join(str(d) for d,a in items),'amounts',','.join(money(a) for d,a in items))
