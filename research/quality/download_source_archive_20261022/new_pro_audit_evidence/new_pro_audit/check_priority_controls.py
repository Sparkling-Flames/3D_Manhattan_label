"""Recompute priority angle maps and controlled real-answer edits from received 244 inputs.
Edits are diagnostic copies, not changes to records or new human judgments.
"""
from pathlib import Path
import argparse,json,csv,sys
import numpy as np
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parents[1];STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016'
sys.path.insert(0,str(STUDY/'src'))
from geomscore import Config,score_pair,shell,simplify,turns,ordered_matching
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(exist_ok=False,parents=True)
pairs={p['object_id']:p for p in json.loads((STUDY/'inputs/current_pairs.json').read_text())}
meta={m['record_id']:m for m in csv.DictReader((STUDY/'inputs/current_metadata.csv').open())}

def shape(p,h):
 return dict(bottom3d=np.c_[p[:,0],-np.ones(len(p)),p[:,1]].tolist(),top3d=np.c_[p[:,0],h-1,p[:,1]].tolist())

maps=[];coarsened=[];deleted=[]
for rid in ['R00751','R00215','R02826','R00166','R01299','R00002']:
 m=meta[rid];raw=pairs[m['object_id']];a=shell(raw['answer']);r=shell(raw['reference']);original=score_pair(raw['answer'],raw['reference'])
 for eps in Config().simplify_h:
  pa,fa=simplify(a['p'],eps);pr,fr=simplify(r['p'],eps);aa,wa=turns(pa);ar,wr=turns(pr);pm=ordered_matching(pa,pr,aa,ar);pp=[]
  for i,j in pm:
   err=abs(float(aa[i]-ar[j]));w=min(float(wa[i]),float(wr[j]));pen=min((max(err-3,0)/20)**2,4.)
   pp.append(dict(answer_index=i,reference_index=j,answer_point=pa[i].tolist(),reference_point=pr[j].tolist(),answer_turn=float(aa[i]),reference_turn=float(ar[j]),angle_error=err,weight=w,penalty=pen,contribution_unnormalized=w*pen,euclidean_distance=float(np.linalg.norm(pa[i]-pr[j]))))
  maps.append(dict(object_id=m['object_id'],case_id=m['case_id'],record_id=rid,image_code=m['image_code'],eps=eps,nA=len(pa),nR=len(pr),pairs=pp,answer_points=pa.tolist(),reference_points=pr.tolist(),answer_turns=aa.tolist(),reference_turns=ar.tolist(),fallback=fa or fr))
 if rid not in ['R00751','R01299']:continue
 for eps in [.08,.10,.15,.20,.25,.30,.40]:
  p,fail=simplify(a['p'],eps);ids=[int(np.argmin(np.linalg.norm(a['p']-x,axis=1))) for x in p];g=shape(p,a['h'][ids]);s=score_pair(g,raw['reference']);d=Polygon(a['p']).boundary.hausdorff_distance(Polygon(p).boundary)
  coarsened.append(dict(record_id=rid,eps=eps,retained_original_canonical_vertices=ids,original_answer=raw['answer'],edited_answer=g,reference=raw['reference'],original_score=original,edited_score=s,hausdorff_to_original=d,angle_penalty=s['angle_detail']['angle_penalty'],I=s['I'],QA=s['QA'],QB=s['QB'],QC=s['QC'],n=len(p),fallback=fail))
 aa,_=turns(a['p']);shallow=[int(i) for i,x in enumerate(aa) if -40<x<0]
 variants=[('no_edit',[])]+[(f'delete_shallow_{i}',[i]) for i in shallow]+[('delete_both_shallow',shallow)]
 for name,remove in variants:
  ids=[i for i in range(len(a['p'])) if i not in remove];p=a['p'][ids];g=shape(p,a['h'][ids]);s=score_pair(g,raw['reference'])
  H=original['surface_height']['local_penalty']+original['surface_height']['mean_penalty'];hold=float(100*s['I']*np.exp(-s['angle_detail']['angle_penalty']-H)*(1-.15*s['angle_detail']['structural_loss']))
  deleted.append(dict(record_id=rid,object_id=m['object_id'],synthetic_edit=name,removed_canonical_vertices=remove,original_answer=raw['answer'],edited_answer=g,reference=raw['reference'],original_score=original,edited_score=s,QA_hold_original_height_penalty=hold,hausdorff_original_h=Polygon(a['p']).boundary.hausdorff_distance(Polygon(p).boundary),area_symmetric_difference_h2=Polygon(a['p']).symmetric_difference(Polygon(p)).area))
for name,data in [('priority_angle_correspondences.json',maps),('real_coarsening_controls.json',coarsened),('real_shallow_detail_deletions.json',deleted)]:
 (args.out/name).write_text(json.dumps(data,indent=2)+'\n')
 old=json.loads((ROOT/'new_pro_audit'/name).read_text())
 if 'coarsening' in name:delta=max(abs(a['QA']-b['QA']) for a,b in zip(old,data))
 elif 'deletions' in name:delta=max(abs(a['edited_score']['QA']-b['edited_score']['QA']) for a,b in zip(old,data))
 else:delta=max(abs(x['angle_error']-y['angle_error']) for a,b in zip(old,data) for x,y in zip(a['pairs'],b['pairs']))
 print(name,'rows',len(data),'original_rows',len(old),'max_QA_or_angle_delta',delta)
