"""Merge retrieval receipts into a compact immutable-source catalog."""
import csv,json
from pathlib import Path
BASE=Path(__file__).resolve().parent
WORK=BASE.parents[2].parent/'profile_research_work'
records={}
if (BASE/'SOURCE_INDEX.csv').exists():
 with (BASE/'SOURCE_INDEX.csv').open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):records[r['path']]=r
for name in ['FETCH_mixtures.jsonl','FETCH_curves.jsonl','FETCH_c13.jsonl','FETCH_mixture_native_imports.jsonl','FETCH_mixture_root.jsonl']:
 p=WORK/name
 if not p.exists():continue
 for line in p.read_text().splitlines():
  r=json.loads(line);records[r['path']]={**r,'retrieval_receipt':name}
for r in json.loads((BASE/'curves/NATURAL_SOURCE_MANIFEST.json').read_text()):records[r['path']]={**r,'retrieval_receipt':'curves/NATURAL_SOURCE_MANIFEST.json'}
# Include sources reused from earlier accepted batches rather than newly fetched.
with (BASE/'mixtures/FINAL_SOURCE_MANIFEST.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  path=r['canonical_source_path'] or r['local_path']
  records[path]={'path':path,'commit':r['source_commit'],'bytes':r['bytes'],'sha256':r['sha256'],'url':r['url'],'retrieval':r['source_kind'],'retrieval_receipt':'mixtures/FINAL_SOURCE_MANIFEST.csv'}
with (BASE/'curves/OTHER_INPUT_SOURCE_HASHES.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['path'] not in records:records[r['path']]={**r,'commit':'accepted_prior_delivery; see curve README','url':'','retrieval':'reused_local_dependency','retrieval_receipt':'curves/OTHER_INPUT_SOURCE_HASHES.csv'}
fields=['path','commit','bytes','sha256','url','retrieval','retrieval_receipt']
with (BASE/'SOURCE_INDEX.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for p in sorted(records):w.writerow({c:records[p].get(c,'') for c in fields})
print('sources',len(records))
