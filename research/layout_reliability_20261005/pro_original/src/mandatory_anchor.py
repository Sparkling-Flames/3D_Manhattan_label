"""A minimal cyclic refinement of the bottom-lock policy.
Every retained mandatory bottom breakpoint decomposes the shortest-path problem
into independent intervals. Starting at a mandatory point avoids imposing an
extra arbitrary top-only knot. No reference or image-quality score is read.
The fixed-first versions are kept as controls, not overwritten.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from compression_study import make_candidate,bottom_turns,dump
from arc_consensus import footprint
from continuous_metrics import fixed_longitude,depth_height_change,height_envelope,height_envelope_audit,witness_and_provenance
ROOT=Path(__file__).resolve().parents[1]
def run():
 rows=[];relabel=[];out=ROOT/'results/compression'
 for image in ['2t7WUuJeko7-06','7y3sRwLe3Va-04']:
  records=json.loads((ROOT/'inputs'/f'{image}.json').read_text())['records'];f=json.loads((ROOT/'results/construction'/f'{image}_exact.json').read_text());e=f['methods'][f['bev_mv50_complete_method']]
  cc=np.load(out/f'{image}_circular_costs.npy');mandatory=bottom_turns(e);env=height_envelope(records);_,base=footprint(e);newrows=[]
  for eps in [.25,.5,1.,2.]:
   candidates=[make_candidate(e,eps,cc,start,True) for start in mandatory]
   sets={tuple(sorted(c['retained_exact_knot_indices'])) for c in candidates}
   relabel.append(dict(image=image,epsilon_px=eps,mandatory_anchors_tested=len(mandatory),distinct_retained_sets=len(sets),node_min=min(c['pair_count'] for c in candidates),node_max=max(c['pair_count'] for c in candidates)))
   c=candidates[0];c['compression_policy']='bottom_locked_mandatory_anchor';c['anchor_rule']='smallest-longitude mandatory bottom coefficient turn; a different mandatory anchor is the same cyclic minimization on these data'
   name=f'{image}_bottom_locked_mandatory_anchor_{eps:g}px';dump(out/(name+'.json'),c)
   w=witness_and_provenance(c,records,len(records)//2+1);dump(out/(name+'_witnesses.json'),w)
   row=dict(image=image,policy=c['compression_policy'],epsilon_px=eps,pair_count=c['pair_count'],exact_pair_count=len(cc),bottom_turn_count=len(mandatory),certificate_px=c['maximum_vertical_curve_error_px'])
   row.update(fixed_longitude(c,e));row.update(depth_height_change(c,e));row.update(height_envelope_audit(c,env));row.update({k:v for k,v in w.items() if not isinstance(v,(list,dict))})
   _,p=footprint(c);row.update(bev_symmetric_difference_h2=base.symmetric_difference(p).area,bev_area_change_h2=p.area-base.area,bev_iou_to_exact=base.intersection(p).area/base.union(p).area);newrows.append(row)
   print(image,eps,'nodes',c['pair_count'],'witness_loss',w['longitude_share_below_exact_lower_bound'],flush=True)
  old=pd.read_csv(out/f'{image}_losses.csv');old=old[old.policy!='bottom_locked_mandatory_anchor'];pd.concat([old,pd.DataFrame(newrows)],ignore_index=True).to_csv(out/f'{image}_losses.csv',index=False)
 pd.DataFrame(relabel).to_csv(out/'mandatory_anchor_invariance.csv',index=False)
 dump(ROOT/'METHOD_UPDATE.json',dict(reason='fixed-first exact-knot compression forces an optional top knot; bottom locking creates intrinsic mandatory separators',rule='decompose at mandatory bottom breaks; evaluate all prescribed budgets and all mandatory anchors',gt_used_for_update=False,old_controls_retained=True,mathematical_scope='finite exact-knot candidate universe, not semantic or unrestricted vertex optimization'))
if __name__=='__main__':run()
