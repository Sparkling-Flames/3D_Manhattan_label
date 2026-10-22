"""Quantify the new first-nearest convention against the old maximum-residual tie rule."""
from pathlib import Path
import sys,json,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[1];STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016'
OLD=ROOT/'repo/analysis_results/quality/quality_joint_closeout_review_20261015/local_replay/engine'
sys.path.insert(0,str(STUDY/'src'));sys.path.insert(0,str(OLD))
from geomscore import score_pair,shell
from run_controls import geom
from centered_height import centered_height_components
import height_revision
A=np.array([(-2,-2),(2,-2),(2,2),(.1,.1),(-.1,.1),(-.1,-.1)])
R=np.array([(-2,-2),(2,-2),(2,2),(-2,2)])
heights=np.array([2.,2.,2.,4.]);mu=shell(geom(R,heights))['mu'];rot=np.array([[0.,-1.],[1.,0.]])
rows=[]
for yaw,M in [(0,np.eye(2)),(90,rot),(180,-np.eye(2)),(270,-rot)]:
 a=geom(A@M,mu);r=geom(R@M,heights);old=centered_height_components(a,r,samples=4096,height_module=height_revision);new=score_pair(a,r)
 rows.append(dict(yaw=yaw,old=old,new_local_error=new['surface_height']['local_error'],new_QA=new['QA'],new_QB=new['QB'],new_QC=new['QC']))
result=dict(answer_xz=A.tolist(),reference_xz=R.tolist(),answer_height=mu,reference_height=heights.tolist(),old_samples=4096,new_step_h=.01,rows=rows,
            old_Hcenter_range=max(z['old']['Hcenter'] for z in rows)-min(z['old']['Hcenter'] for z in rows),new_local_range=max(z['new_local_error'] for z in rows)-min(z['new_local_error'] for z in rows),
            caveat='Synthetic geometry has a boundary segment on the reference medial-axis bisector. This isolates a real tie-set convention change, not evidence of frequent real failures.')
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists();args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
