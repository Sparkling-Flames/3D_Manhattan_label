"""Display randomization only; does not modify the approved selection."""
import hashlib,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SEED=2026101130
p=ROOT/'results/selection_private.json';d=json.loads(p.read_text());ids=[r['case_id'] for r in d['records']];random.Random(SEED).shuffle(ids)
out={'display_order_version':'quality_review30_display_order_v1','selection_version':d['selection_version'],'selection_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'seed':SEED,'generator':'Python random.Random(seed).shuffle, frozen explicit result authoritative','primary_display_order':ids,'case_ids_unchanged':True,'optional_pair_after_primary':'P01','primary_answer_count':30,'selection_modified':False}
q=ROOT/'results/display_order.json';raw=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
if q.exists():assert q.read_text()==raw,'Frozen order exists and differs; do not overwrite'
else:q.write_text(raw,encoding='utf-8')
print('seed',SEED,'order',','.join(ids))
