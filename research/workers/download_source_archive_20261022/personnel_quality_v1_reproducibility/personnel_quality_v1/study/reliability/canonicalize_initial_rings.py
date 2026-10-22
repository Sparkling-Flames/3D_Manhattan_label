"""Transfer existing confirmed rings only between exactly equal coordinate multisets.

An initializer's serialized array is not automatically a confirmed wall cycle.
No new coordinates, reference selection, or geometric optimization is performed.
"""
from pathlib import Path
from collections import defaultdict
import json
import numpy as np,pandas as pd
from paths import ROOT,REPO,OUT,STUDY

def multiset(x):return sorted(tuple(round(float(v),6) for v in p) for p in x)
def ring_key(x):
 pairs=[tuple(round(float(v),6) for p in x[i:i+2] for v in p) for i in range(0,len(x),2)]
 if not pairs:return ()
 return min(tuple(v[k:]+v[:k]) for v in [pairs,pairs[::-1]] for k in range(len(v)))
def main():
 objs={o['object_id']:o for o in json.loads((OUT/'validated_annotations.json').read_text())}
 ev=pd.read_csv(OUT/'initialization_evidence_574.csv').set_index('object_id').to_dict('index')
 geom={g['object_id']:g for g in json.loads((OUT/'initialization_geometry_574.json').read_text())}
 groups=defaultdict(list)
 for oid,e in ev.items():groups[(e['image_id'],e['initialization_hash'])].append(oid)
 ledger=[];out=[]
 for (image,h),ids in groups.items():
  initial=geom[ids[0]]['initial_points_1024x512'];candidates=[]
  for oid in ids:
   o=objs[oid];p=o['points_1024x512']
   if o['ring_confirmed'] and p and multiset(p)==multiset(initial) and multiset(o['original_export_points'])==multiset(initial):
    candidates.append((oid,p))
  keys={ring_key(p) for oid,p in candidates}
  if len(keys)>1:
   status='conflicting_existing_rings';selected=None
  elif candidates:
   status='existing_confirmed_ring_exact_point_identity';selected=candidates[0][1]
  else:
   status='native_initialization_ring_unconfirmed';selected=initial
  changed=selected is not None and ring_key(selected)!=ring_key(initial)
  ledger.append(dict(image_id=image,initialization_hash=h,records=len(ids),existing_ring_sources=[oid for oid,p in candidates],n_existing_rings=len(candidates),n_distinct_existing_rings=len(keys),initial_ring_status=status,initial_ring_changed_from_payload=changed))
  for oid in ids:out.append(dict(**geom[oid],initial_payload_points_1024x512=geom[oid]['initial_points_1024x512'],initial_canonical_points_1024x512=selected,initial_ring_status=status,initial_ring_changed_from_payload=changed,initial_ring_source_object_ids=[a for a,p in candidates]))
 df=pd.DataFrame(ledger);df.existing_ring_sources=df.existing_ring_sources.map(json.dumps)
 df.to_csv(OUT/'initialization_ring_provenance.csv',index=False,encoding='utf-8-sig')
 (OUT/'initialization_geometry_canonical_574.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf8')
 print(df.groupby(['initial_ring_status','initial_ring_changed_from_payload']).agg(initializers=('image_id','size'),rows=('records','sum')).to_string())
 print(df[df.initial_ring_changed_from_payload][['image_id','records','existing_ring_sources']].to_string(index=False))
if __name__=='__main__':main()
