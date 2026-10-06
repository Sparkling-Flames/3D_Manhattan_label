"""Extract a saved local candidate without changing coordinates or reading GT."""
from pathlib import Path
import argparse,gzip,json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--results',type=Path,default=Path('results'))
p.add_argument('--id',required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
if a.out.exists(): raise SystemExit('Refusing to overwrite: '+str(a.out))
found=[]
for f in (a.results/'patches').glob('*_candidate_rings.jsonl.gz'):
 with gzip.open(f,'rt',encoding='utf-8') as rows:
  for line in rows:
   row=json.loads(line)
   if row.get('id')==a.id: found.append(row)
if len(found)!=1:raise SystemExit('Expected exactly one candidate, got '+str(len(found)))
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps(found[0],ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(a.out)
