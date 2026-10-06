"""Recover one complete partition and source mapping from the compressed finite ledger."""
import argparse,gzip,json,itertools,sys
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=ROOT/'results');p.add_argument('--domain',required=True);p.add_argument('--candidate',type=int,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
if a.out.exists():raise FileExistsError(a.out)
droot=a.results/'domains';meta=json.loads((droot/(a.domain+'.json')).read_text())
state=next(s for s in json.loads((droot/'domains_summary.json').read_text()) if s['domain_id']==a.domain)
ns=json.loads((droot/'node_lookup.json').read_text())[state['image']]
base=next(s for s in json.loads((droot/'baseline_partitions.json').read_text()) if all(s[k]==state[k] for k in ['image','metric','threshold']))
candidate=None
with gzip.open(droot/meta['all_candidate_ledger'],'rt',encoding='utf-8') as f:
    for line in f:
        row=json.loads(line)
        if row['local_id']==a.candidate:candidate=row;break
if candidate is None:raise ValueError('candidate_not_found')
sys.path.insert(0,str(ROOT/'src'))
from core import distances,center
ds=distances(ns)
old_pairs={tuple(sorted((i,j))) for g in meta['domain']['baseline_blocks'] for i,j in itertools.combinations(g,2)}
new_pairs={tuple(sorted((i,j))) for g in candidate['blocks'] for i,j in itertools.combinations(g,2)}
candidate['added_coassignment_sources']=[[ns[i] for i in pair] for pair in sorted(new_pairs-old_pairs)]
candidate['lost_coassignment_sources']=[[ns[i] for i in pair] for pair in sorted(old_pairs-new_pairs)]
candidate['computed_centers']=[center(ns,g,ds['pair']) for g in candidate['blocks']]
candidate['computed_diameters_deg']=[float(ds[state['metric']][np.ix_(g,g)].max()) for g in candidate['blocks']]
fixed=[g for i,g in enumerate(base['groups']) if i not in meta['domain']['group_indices']]
full=fixed+candidate['blocks']
result=dict(domain_id=a.domain,image=state['image'],metric=state['metric'],threshold_deg=state['threshold'],threshold_calibrated=False,
    candidate=candidate,full_partition=[[ns[i] for i in g] for g in full],local_new_groups=[[ns[i] for i in g] for g in candidate['blocks']],
    fixed_outside_groups=[[ns[i] for i in g] for g in fixed],roster_denominator=base['roster_denominator'],
    total_observations=sum(map(len,full)),source_mutated=False,new_ring=None,
    limitation='complete correspondence partition conditional on a two-group local domain; not a complete layout or semantic identity certificate')
a.out.parent.mkdir(parents=True,exist_ok=True)
with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(a.out)
