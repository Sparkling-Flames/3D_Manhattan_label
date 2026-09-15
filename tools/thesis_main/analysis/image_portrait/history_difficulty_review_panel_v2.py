"""Exactly shared people panel and explicitly supplemental candidate sensitivity."""
import json,itertools
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,cluster_static,one_replay,csv,js

def main():
 p=pd.read_csv(OUT/'proposal/per_image_draft_for_user.csv');idx=json.loads((OUT/'cache/group_index.json').read_text());lookup={(r['image_id'],r['condition']):r for r in idx};z=np.load(OUT/'cache/pairwise_geometry.npz',allow_pickle=False)
 anchors=p[p.expert_tag.isin(['中等','困难'])&(p.n_valid>=10)&(p.condition=='manual')]
 common=set.intersection(*(set(z[lookup[r.image_id,r.condition]['key']+'_workers'])for _,r in anchors.iterrows()));assert len(common)==18
 rows=[];rps=[];curves=[]
 for _,r in anchors.iterrows():
  key=lookup[r.image_id,r.condition]['key'];workers=z[key+'_workers'];ix=np.array([np.flatnonzero(workers==w)[0]for w in sorted(common)]);dm=z[key+'_dm'][np.ix_(ix,ix)];pcs=z[key+'_pcs'][ix]
  for cut in[.075,.10,.125,.15]:
   st,_,_,_=cluster_static(dm,pcs,cut);rows.append(dict(image_id=r.image_id,expert_tag=r.expert_tag,condition='manual',cut=cut,common_workers=';'.join(sorted(common)),canonical_ids=';'.join(z[key+'_ids'][ix]),original_valid_people=int(r.n_valid),**st))
   if cut==.1:
    # Identical actual worker orders across all eight images: only picture changes.
    a,b,_=one_replay(dm,pcs,cut,200,'common18_fixed_order_panel','manual')
    for item in a+b:item['image_id']=r.image_id;item['expert_tag']=r.expert_tag
    rps+=a;curves+=b
 csv('extra/exact_common18_panel.csv',rows);csv('extra/exact_common18_replays.csv.gz',rps);csv('extra/exact_common18_mean_curves.csv',curves)
 js('extra/exact_common18_method.json',dict(real_worker_ids=sorted(common),images=anchors.image_id.tolist(),n=18,order_shared_across_images=True,scope='8 expert-labelled high-support manual images only; not independent validation of expert tags',cannot_remove='building, stage and scene-selection differences',conditional_effective_geometry=True))
 # Newly suggested unlabelled candidates were not in the first targeted cut audit.
 # Fill the missing nearby cuts; record selection rather than hiding the coverage.
 replay=pd.read_csv(OUT/'process/per_order_onsets.csv.gz');cur=pd.read_csv(OUT/'process/mean_prefix_curves.csv.gz');present=set(zip(replay.image_id,replay.condition,replay.cut));add=[];addc=[];run=[]
 for _,r in p[p.draft_grade.notna()&(p.n_valid>=10)].iterrows():
  key=lookup[r.image_id,r.condition]['key'];dm=z[key+'_dm'];pcs=z[key+'_pcs']
  for cut in[.075,.125]:
   if (r.image_id,r.condition,cut) in present:continue
   a,b,_=one_replay(dm,pcs,cut,100,r.image_id,r.condition);add+=a;addc+=b;run.append(dict(image_id=r.image_id,condition=r.condition,cut=cut,orders=100,reason='newly proposed class needs nearby-cut check; explicit post-hoc supplement'))
 if add:
  csv('process/per_order_onsets.csv.gz',pd.concat([replay,pd.DataFrame(add)],ignore_index=True));csv('process/mean_prefix_curves.csv.gz',pd.concat([cur,pd.DataFrame(addc)],ignore_index=True))
 csv('audit/supplemental_nearby_cut_runs.csv',run)
 print('shared18 images',len(anchors),'supplemental cut-runs',len(run),flush=True)
if __name__=='__main__':main()
