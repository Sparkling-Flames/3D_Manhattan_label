"""Numerical representation check for the pre-existing same-image pair."""
import argparse,json,sys,itertools
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,required=True);args=ap.parse_args();root=args.bundle
 sys.path.insert(0,str(root/'frozen/scope_engine/core'))
 from quality_v11 import score_geometry,Parameters
 rows={r['record_id']:r for r in json.loads((root/'results/current_components.json').read_text())};geos=json.loads((root/'inputs/current_geometry_compact.json').read_text())['geometries'];out=[]
 for rid in ['R01973','R02447']:
  r=rows[rid];a,g=geos[r['object_id']],geos[r['reference_object_id']]
  def variant(v,shift=0,rev=False):
   d={}
   for k in ['top3d','bottom3d']:
    q=v[k][::-1] if rev else v[k][:];s=shift%len(q);d[k]=q[s:]+q[:s]
   return d
  configs=[('base',a,g),('a_shift',variant(a,1),g),('g_shift',a,variant(g,1)),('a_reverse',variant(a,rev=True),g),('g_reverse',a,variant(g,rev=True)),('both',variant(a,1,True),variant(g,1,True))]
  for name,aa,gg in configs:
   q=score_geometry(aa,gg,Parameters(intrinsic_max_discount=.3),spherical_samples=2048,height_samples=4096)
   assert q['status']=='available';out.append({'record_id':rid,'variant':name,'Q_alpha30':q['quality_score']})
 x=[r['Q_alpha30'] for r in out if r['record_id']=='R01973'];y=[r['Q_alpha30'] for r in out if r['record_id']=='R02447'];d=[b-a for a,b in itertools.product(x,y)]
 result={'same_image':'wc2JMjhGNzB-18','records':['R01973','R02447'],'alpha':.3,'independent_pairwise_representation_combinations':len(d),'Q_second_minus_first_min':min(d),'Q_second_minus_first_max':max(d),'sign_stays_negative':max(d)<0,'does_not_validate_human_rank':True,'scores':out}
 Path(__file__).with_name('pair_representation_audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='scores'})
if __name__=='__main__':main()
