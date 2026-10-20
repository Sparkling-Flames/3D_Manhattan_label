import itertools,json
import numpy as np,pandas as pd
from learn_block_types import Objective,BlockAnchors,METRICS,BASE
rows=[];workers=['W'+str(i) for i in range(12)];l=np.repeat([0,1,2],4)
for b in range(4):
 for j,(x,y) in enumerate(itertools.combinations(list(itertools.combinations(workers,2)),2)):
  if set(x)&set(y):continue
  d=.01+((j*7+b)%19)/1000
  rows.append(dict(left_tuple=x,right_tuple=y,distance=d,building=str(b),pool_id=str(b)+'p',n=5,anchor_id=str(b)+'a'))
f=pd.DataFrame(rows);o=Objective(f,workers);same=o.same(l)
assert all(s== (sorted(l[workers.index(w)] for w in row.left_tuple)==sorted(l[workers.index(w)] for w in row.right_tuple)) for s,row in zip([sorted(l[workers.index(w)] for w in a)==sorted(l[workers.index(w)] for w in b) for a,b in zip(f.left_tuple,f.right_tuple)],f.itertuples()))
for j in range(12):
 for c in range(3):
  ll=l.copy();ll[j]=c;ids=o.related[j];s=o.same(ll);old=o.same(l);partial=old.copy();partial[ids]=o.same(ll,ids);assert np.array_equal(s,partial)
start=np.arange(12)%3;end,loss,tr=o.optimize(start,3);assert min(np.bincount(end))>=4;assert all(b['objective']<a['objective'] for a,b in zip(tr,tr[1:]));assert len(tr)<=30
for m in METRICS:
 if m not in f:f[m]=f.distance if m.startswith(('distance','bev','top')) else 0.
f['k']=5;f['background_id']=f.anchor_id
ba=BlockAnchors(f,workers);z=ba.expand(l)
assert np.array_equal(z[ba.base.a]==z[ba.base.b],np.array([sorted(l[workers.index(w)] for w in a)==sorted(l[workers.index(w)] for w in b) for a,b in zip(f.left_tuple,f.right_tuple)]))
r=ba.evaluate(l);assert len(r)==4 and all(x['matched_anchors']==1 for x in r)
(BASE/'BLOCK_OBJECTIVE_SYNTHETIC_RECEIPT.json').write_text(json.dumps({'exact_count_vector_encoding':True,'incremental_move_matches_full':True,'class_minimum_preserved':True,'strict_descent':True,'anchor_evaluator_equivalence':True,'synthetic_pairs':len(f)},indent=2));print('passed')
