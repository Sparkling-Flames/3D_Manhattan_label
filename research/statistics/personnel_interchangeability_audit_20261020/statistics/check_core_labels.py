from pathlib import Path
from collections import Counter
import pandas as pd,json,gzip,hashlib
B=Path('/workspace/shared/interchangeability_audit_20261020/unpacked');R=B/'interchangeability_20261020';O=Path(__file__).parent
es=[x for x in json.load(gzip.open(R/'core_replay/CORE_REQUESTS.json.gz','rt'))['events'] if 'A_workers' in x];wanted={e['method_id'] for e in es};maps={};sources=[]
for p in B.rglob('worker_labels.csv.gz'):
 d=pd.read_csv(p)
 if 'known' in d:d=d[d.known.astype(str).str.lower().isin(['true','1','1.0'])]
 for mid,g in d.groupby('method_id'):
  if mid not in wanted:continue
  m=dict(zip(g.worker_id,g.class_id));assert mid not in maps or maps[mid]==m
  maps[mid]=m;sources.append(dict(path=str(p.relative_to(B)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
passed=0
for e in es:
 if e['method_id'] not in maps:continue
 for a in 'ABC':assert Counter(maps[e['method_id']].get(w,'outside_group') for w in e[a+'_workers'])==Counter(e[a+'_counts'])
 passed+=1
result=dict(paired_events=len(es),checked_events=passed,missing_methods=sorted(wanted-set(maps)),mismatch_count=0,sources=sources)
(O/'CORE_LABEL_COUNTS_RECEIPT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
