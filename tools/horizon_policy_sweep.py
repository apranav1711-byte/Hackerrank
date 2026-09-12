from __future__ import annotations
import csv,re,sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from data_loader import load_dataset
from evidence import resolve_image_amounts
from main import build_flows,dec,normalize_events,parse_date,simulate,ZERO,CENT
ROOT=Path(__file__).resolve().parents[1]; DATA=Path('/home/ubuntu/hackerrank-orchestrate-september26/dataset'); D=load_dataset(DATA); IMAGES=resolve_image_amounts(D['images'],DATA/'media/images')
with (DATA/'sample_requests.csv').open() as f: samples=list(csv.DictReader(f))

def custom_safe(info, mode, param):
 start,req,minbal=info['start'],info['requested'],info['minimum']; base=info['flows']; modified=defaultdict(lambda:ZERO)
 for d,v in base.items():
  age=(d-start).days
  if age<0 or age>90: continue
  if mode=='cutoff' and age>param: continue
  if mode=='exp':
   w=Decimal(str(param))**age if v<0 else Decimal(1)
   modified[d]+=v*w
  elif mode=='linear':
   w=max(Decimal(0),Decimal(1)-Decimal(age)/Decimal(param)) if v<0 else Decimal(1)
   modified[d]+=v*w
  elif mode=='frontload':
   w=Decimal(str(param)) if age<=14 and v<0 else Decimal(1)
   modified[d]+=v*w
  else: modified[d]+=v
 lo,hi=0,int((req/CENT).to_integral_value())
 while lo<=hi:
  mid=(lo+hi)//2; candidate=Decimal(mid)*CENT
  end=start+timedelta(days=(param if mode=='cutoff' else 90))
  if simulate(info['balance'],modified,start,[(start,candidate)],minbal,end_date=end): lo=mid+1
  else: hi=mid-1
 return max(ZERO,Decimal(hi)*CENT)

infos=[]
for r in samples:
 p=D['profiles_by_user'][r['user_id']]; ev=normalize_events(D['events_by_user'][r['user_id']],p['home_currency'],D['rates_by_date_pair'],IMAGES); start=parse_date(r['request_date']); bal,flows,rel,proj=build_flows(r,p,ev,D['rates_by_date_pair'],D['messages_by_user'].get(r['user_id'],[]),recurrence_estimator='minimum'); infos.append({'r':r,'start':start,'requested':dec(r['requested_amount']),'minimum':dec(p['minimum_balance_to_keep']),'balance':bal,'flows':flows,'truth':dec(r['amount_safe_to_pay'])})
variants=[('baseline',None,None)]
variants += [('cutoff',x,x) for x in [14,21,30,45,60,75,90]]
variants += [('exp',x,x) for x in ['0.995','0.99','0.98','0.97','0.95','0.90']]
variants += [('linear',x,x) for x in [14,21,30,45,60,90]]
variants += [('frontload',x,x) for x in ['1.01','1.02','1.05','1.10','1.20','1.35','1.50','2.00','3.00','5.00']]
print('variant|exact_safe_matches|mae')
for mode,param,label in variants:
 vals=[]; exact=0; err=Decimal(0)
 for info in infos:
  v=custom_safe(info,'baseline',90) if mode=='baseline' else custom_safe(info,mode,param); vals.append(v); exact+=v==info['truth']; err+=abs(v-info['truth'])
 print(label or 'baseline',exact,'/25',(err/Decimal(25)).quantize(Decimal('0.01')))
