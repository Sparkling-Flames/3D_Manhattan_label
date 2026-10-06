"""Export lossless canonical candidate references from an upstream delivered archive.
These are validation fixtures, not additional data or independently computed truth.
"""
import argparse,gzip,hashlib,json,shutil
from pathlib import Path
import numpy as np
from run_sensitivity import canonical_mask,IMAGE,dump
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False);(a.out/'inputs').mkdir();d=a.out/'results/domains';d.mkdir(parents=True)
for name in [f'{IMAGE}.json','human_review.json']:shutil.copyfile(a.source/'inputs'/name,a.out/'inputs'/name)
old=a.source/'results/domains';idx=json.loads((old/'domains_summary.json').read_text());idx=[s for s in idx if s['image']==IMAGE and s.get('domain_id')]
dump(d/'domains_summary.json',idx);ns=json.loads((old/'node_lookup.json').read_text());dump(d/'node_lookup.json',{IMAGE:ns[IMAGE]});manifest=[]
for s in idx:
 name=s['domain_id'];original=old/(name+'.json');obj=json.loads(original.read_text());ledger=old/obj['all_candidate_ledger'];u=obj['domain']['union'];rows=[]
 for line in gzip.open(ledger,'rt'):
  r=json.loads(line);rows.append((canonical_mask(r['blocks'],u),r['local_id'],r['cost']))
 ref=name+'_reference.npz';np.savez_compressed(d/ref,mask=np.asarray([x[0] for x in rows],np.uint32),id=np.asarray([x[1] for x in rows],np.uint32),cost=np.asarray([x[2] for x in rows],float))
 obj['compact_reference']=ref;dump(d/(name+'.json'),obj)
 manifest.append({'domain':name,'source_domain_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'source_ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),'canonical_reference_sha256':hashlib.sha256((d/ref).read_bytes()).hexdigest(),'candidate_count':len(rows)})
dump(a.out/'REFERENCE_PROVENANCE.json',{'meaning':'Lossless compact encoding of original candidate membership, ID and W. Independent solver must equal these assignments; references are not semantic truth. Other source fields remain in domain JSON.','domains':manifest})
