from pathlib import Path
import subprocess,re
repo=Path('/home/ubuntu/Hackerrank'); main=repo/'code/main.py'; base=main.read_text(); needle='    safe = safe_amount(balance, safe_amount_flows, start, amount, minimum)'
variants=[('baseline','')]
for window in [2,3,5,7]:
 for threshold in ['0.05','0.10','0.15','0.20','0.25','0.30','0.40','0.50']:
  for alpha in ['0.01','0.02','0.03','0.05','0.08']:
   expr=f'''\n    daily = [abs(flows.get(start + timedelta(days=i), ZERO)) for i in range(HORIZON + 1)]\n    cluster = max((sum(daily[i:i+{window}]) for i in range(max(1, len(daily)-{window}+1))), default=ZERO)\n    avg = sum(daily, ZERO) / Decimal(max(1, len(daily)))\n    if balance > ZERO and cluster / balance >= Decimal("{threshold}"):\n        safe = max(ZERO, safe - Decimal("{alpha}") * max(ZERO, cluster - avg))'''
   variants.append((f'w{window}_t{threshold}_a{alpha}',expr))
results=[]
for name,expr in variants:
 main.write_text(base.replace(needle,needle+expr,1))
 p=subprocess.run(['python3','tests/eval_samples.py','--dataset-dir','/home/ubuntu/hackerrank-orchestrate-september26/dataset'],cwd=repo,text=True,capture_output=True)
 e=re.search(r'Exact match on ALL 6 key fields: (\d+/25)',p.stdout); a=re.search(r'amount_safe_to_pay: (\d+/25)',p.stdout); m=re.search(r'Mismatched requests count: (\d+)',p.stdout)
 results.append((name,e.group(1) if e else 'ERR',a.group(1) if a else 'ERR',m.group(1) if m else 'ERR'))
main.write_text(base)
for row in sorted(results,key=lambda x:(-int(x[1].split('/')[0]) if x[1]!='ERR' else 0,-int(x[2].split('/')[0]) if x[2]!='ERR' else 0)):
 print('|'.join(row))
