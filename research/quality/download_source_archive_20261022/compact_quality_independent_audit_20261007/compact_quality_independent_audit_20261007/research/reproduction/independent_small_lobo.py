"""Independently verify the compact common-24-worker six-image LOBO result."""
from pathlib import Path
import argparse,itertools,json,sys

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--official-output',type=Path,default=HERE/'official_run',help='Compact reproduce.py output directory')
parser.add_argument('--audit-summary',type=Path,default=HERE/'independent_audit.json',help='JSON produced by independent_audit.py, containing the verified same-six-image panel')
parser.add_argument('--output',type=Path,default=HERE,help='Directory for independent small-LOBO outputs; existing audit outputs are replaced')
parser.add_argument('--check-paths',action='store_true',help='Validate input paths and exit without importing numeric libraries or recomputing results')
args=parser.parse_args()
RUN=args.official_output.expanduser().resolve();SUMMARY=args.audit_summary.expanduser().resolve();O=args.output.expanduser().resolve()
required=[RUN/'manual_scored.csv',RUN/'lobo_pair_orders.csv',SUMMARY]
missing=[str(p) for p in required if not p.is_file()]
if missing:parser.error('Missing required inputs:\n  '+'\n  '.join(missing))
if args.check_paths:
    print(json.dumps({'status':'paths_ok','official_output':str(RUN),'audit_summary':str(SUMMARY),'output':str(O),'required_paths_checked':len(required)},indent=2));raise SystemExit(0)
O.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True
import numpy as np,pandas as pd
d=pd.read_csv(RUN/'manual_scored.csv');codes=json.loads(SUMMARY.read_text())['worker']['same6'];q=d[d.primary_candidate&d.reference_version.eq('original')&d.image.isin(codes)]
core=['L','C','U','B'];f=core+['T','T_relative'];tol=np.array([.0001,.0001,.1,.1]);rows=[]
for held in sorted(q.building.unique()):
 tr=q[q.building!=held];te=q[q.building==held];scale=tr.groupby('image')[f].median().median().clip(lower=1e-12);av=tr.groupby('worker')[f+['LC']].mean();tv=te.groupby('worker')[core].mean();score=pd.DataFrame(index=av.index);score['S0']=av.L;score['S1']=av.LC;score['S4']=(av[core]/scale[core]).sum(axis=1);score['S5']=score.S4+av['T']/scale['T'];score['S5_relative']=score.S4+av.T_relative/scale.T_relative
 for a,b in itertools.combinations(tv.index,2):
  diff=(tv.loc[a]-tv.loc[b]).to_numpy();ab=np.all(diff>=-tol)&np.any(diff>tol);ba=np.all(diff<=tol)&np.any(diff<-tol)
  if ab==ba:continue
  better,worse=(b,a) if ab else (a,b)
  for scheme in score:
   dd=score.loc[better,scheme]-score.loc[worse,scheme];rows.append(dict(held_building=held,better_reference_core=better,worse_reference_core=worse,scheme=scheme,correct=.5 if abs(dd)<=1e-12 else float(dd<0),training_score_delta=dd))
a=pd.DataFrame(rows);a.to_csv(O/'independent_small_lobo.csv',index=False);b=pd.read_csv(RUN/'lobo_pair_orders.csv');ix=['held_building','better_reference_core','worse_reference_core','scheme'];aa=a.set_index(ix).sort_index();bb=b.set_index(ix).sort_index();assert aa.index.equals(bb.index) and np.array_equal(aa.correct,bb.correct) and np.allclose(aa.training_score_delta,bb.training_score_delta,atol=1e-12,rtol=1e-12)
result={'buildings':q.building.nunique(),'images':q.image.nunique(),'records':len(q),'pairs':len(a)//5,'all_pair_predictions_match':True,'building_equal':a.groupby(['held_building','scheme']).correct.mean().groupby('scheme').mean().to_dict()};(O/'independent_small_lobo.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
