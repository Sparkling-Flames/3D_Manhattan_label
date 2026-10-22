"""Run compact API regression checks and fresh raw-coordinate case integrals."""
from pathlib import Path
import argparse,copy,json,sys

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=PROJECT/'unpacked/quality_compact_20261007',help='Extracted compact package root containing inputs/, src/ and vendor/')
parser.add_argument('--official-output',type=Path,default=HERE/'official_run',help='Compact reproduce.py output containing selected_case_metrics.csv')
parser.add_argument('--output',type=Path,default=HERE,help='Directory for independent API/case outputs; existing audit outputs are replaced')
parser.add_argument('--check-paths',action='store_true',help='Validate input paths and exit without importing numeric libraries or recomputing results')
args=parser.parse_args()
ROOT=args.source.expanduser().resolve();RUN=args.official_output.expanduser().resolve();OUT=args.output.expanduser().resolve()
required=[ROOT/'inputs/panel.json',ROOT/'src/quality_compact.py',ROOT/'vendor/arc_excerpt.py',ROOT/'vendor/quality.py',ROOT/'vendor/components_reused.py',ROOT/'vendor/geometry.py',RUN/'selected_case_metrics.csv']
missing=[str(p) for p in required if not p.is_file()]
if missing:parser.error('Missing required inputs:\n  '+'\n  '.join(missing))
if args.check_paths:
    print(json.dumps({'status':'paths_ok','source':str(ROOT),'official_output':str(RUN),'output':str(OUT),'required_paths_checked':len(required)},indent=2));raise SystemExit(0)
OUT.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True
import numpy as np,pandas as pd
from scipy.integrate import quad
sys.path.insert(0,str(ROOT/'src'))
from quality_compact import evaluate
panel=json.loads((ROOT/'inputs/panel.json').read_text());ims={r['code']:r for r in panel['images']};selected={'rPc6DW4iMge-01':['R01127','R00391'],'yqstnuAEVhm-34':['R00428','R01065'],'wc2JMjhGNzB-15':['R01288','R01099']}
checks=[]
def check(name,ok,**detail):
 checks.append(dict(check=name,passed=bool(ok),**detail));assert ok,name
im=ims['rPc6DW4iMge-01'];a=copy.deepcopy(next(r for r in im['annotations'] if r['id']=='R00391'));good=copy.deepcopy(a);good.update(id='audit_good_ref',version='audit_v1')
blank=evaluate(a,[],three_d=True);check('empty_references_no_rank_ready_or_scoring',blank['reference_status']=='no_reference' and blank['comparisons']==[] and 'rank_ready' not in blank and blank['overall_human_quality']=='not_inferred')
bad={'id':'audit_bad_ref','version':'audit_v1','points':[[0,256],[0,256],[200,256],[200,256],[400,256],[400,256]]}
res=evaluate(a,[good,bad],three_d=True);r0,r1=res['comparisons'];check('invalid_reference_cannot_inherit_valid_reference_readiness',r0['all_core_computable'] and not r1['all_core_computable'] and r1['core']['iou'] is None and 'rank_ready' not in res)
check('computation_not_human_quality',all(r['geometry_computable_is_not_human_quality_certification'] and r['evidence_context']['reference_usable_for_human_quality']=='unknown' for r in res['comparisons']) and res['overall_human_quality']=='not_inferred')
check('eligibility_and_expression_preserved',res['source_eligibility']['quality_candidate']==a['quality_candidate'] and res['expression']['source_point_indices']==a['source_point_indices'] and res['expression']['source_pair_indices']==a['source_pair_indices'])
raw_before=json.dumps([a,good,bad],sort_keys=True);evaluate(a,[good,bad],three_d=True,intrinsic_diagnostics=True);check('no_input_mutation',raw_before==json.dumps([a,good,bad],sort_keys=True))
for label,context in [('wrong_layout',{'layout_id':'wrong','reference_id':good['id'],'reference_version':'audit_v1'}),('wrong_reference_version',{'layout_id':a['id'],'reference_id':good['id'],'reference_version':'audit_v2'})]:
 try:evaluate(a,[good],contexts=[context]);caught=False
 except ValueError:caught=True
 check(label+'_context_rejected',caught)
# No imported geometry/integral/ring functions for following calculations.
def xyz(r):
 p=np.array(r['points']);u=(p[1::2,0]/1024-.5)*2*np.pi;rho=1/np.tan((p[1::2,1]-256)*np.pi/512);x=rho*np.sin(u);z=-rho*np.cos(u)
 return np.c_[x,rho*np.tan((256-p[::2,1])*np.pi/512),z],np.c_[x,-np.ones(len(x)),z]
def distance(point,vertices):
 e=np.roll(vertices,-1,axis=0)-vertices;v=point-vertices;t=np.clip(np.sum(v*e,axis=1)/np.sum(e*e,axis=1),0,1)
 return np.sqrt(np.min(np.sum((v-e*t[:,None])**2,axis=1)))
def curve(a,b):
 directed=[];err=0.
 for s,t in [(a,b),(b,a)]:
  lengths=np.linalg.norm(np.roll(s,-1,axis=0)-s,axis=1);tot=0.;error=0.
  for i,L in enumerate(lengths):
   v,e=s[i],s[(i+1)%len(s)]-s[i];val,er=quad(lambda x:distance(v+x*e,t),0,1,epsabs=1e-10,epsrel=1e-10,limit=500);tot+=L*val;error+=L*er
  directed.append(tot/sum(lengths));err+=error/sum(lengths)/2
 return sum(directed)/2,err
def angles(r,u):
 p=np.array(r['points']);lon=p[::2,0]/1024*2*np.pi;out=np.empty((2,len(u)));covered=np.zeros(len(u),int)
 for i,l in enumerate(lon):
  j=(i+1)%len(lon);span=(lon[j]-l+np.pi)%(2*np.pi)-np.pi;off=(u-l+np.pi)%(2*np.pi)-np.pi;t=off/span;mask=(t>=0)&(t<1);covered[mask]+=1
  for side in [0,1]:
   v0=np.tan((256-p[2*i+side,1])*np.pi/512);v1=np.tan((256-p[2*j+side,1])*np.pi/512)
   out[side,mask]=np.arctan((np.sin(span-off[mask])*v0+np.sin(off[mask])*v1)/np.sin(span))
 assert np.all(covered==1)
 return out
stored=pd.read_csv(RUN/'selected_case_metrics.csv').set_index(['image','id']);rows=[];u=(np.arange(131072)+.5)/131072*2*np.pi
for image,ids in selected.items():
 g=next(r for r in ims[image]['references'] if r['version']=='original');gt,gb=xyz(g);ga=angles(g,u)
 for rid in ids:
  r=next(r for r in ims[image]['annotations'] if r['id']==rid);rt,rb=xyz(r);T,err=curve(rt,gt);F,errf=curve(rb,gb);ra=angles(r,u);U,B=np.mean(abs(ra-ga),axis=1)*180/np.pi
  rho=-1/np.tan(ra[1]);rhog=-1/np.tan(ga[1]);qa=np.tan(ra[0]);qg=np.tan(ga[0]);angle=.5*(rho+rhog)*(qa-qg);depth=.5*(qa+qg)*(rho-rhog);total=rho*qa-rhog*qg;old=stored.loc[(image,rid)]
  rows.append(dict(image=image,id=rid,T=T,F=F,U=U,B=B,T_error_vs_case=T-old.T_adaptive,T_error_vs_historical=T-old.T_saved,U_error_vs_case=U-old.U,B_error_vs_case=B-old.B,integral_error=err,identity_error=max(abs(total-angle-depth)),angle_rms=np.sqrt(np.mean(angle**2)),depth_rms=np.sqrt(np.mean(depth**2)),total_rms=np.sqrt(np.mean(total**2)),cancellation_fraction=1-np.mean(total**2)/np.mean(angle**2+depth**2)))
cases=pd.DataFrame(rows);cases.to_csv(OUT/'independent_case_geometry.csv',index=False)
check('six_case_threeD_matches_with_fresh_integral',cases.T_error_vs_case.abs().max()<1e-7,max_difference=float(cases.T_error_vs_case.abs().max()))
check('six_case_angular_matches_with_dense_samples',max(cases.U_error_vs_case.abs().max(),cases.B_error_vs_case.abs().max())<1e-6,max_difference=float(max(cases.U_error_vs_case.abs().max(),cases.B_error_vs_case.abs().max())))
check('six_case_product_identity',cases.identity_error.max()<1e-12,max_identity_error=float(cases.identity_error.max()))
(OUT/'api_and_case_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2));print(cases.to_string(index=False))
