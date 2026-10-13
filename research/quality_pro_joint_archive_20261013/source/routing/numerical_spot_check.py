"""Higher-resolution spot checks chosen by numerical-risk features, not scores."""
import argparse,json,math
from pathlib import Path
import numpy as np
from run_routing import engine,dump,baseline_score
ROOT=Path(__file__).resolve().parent
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,default=ROOT/'inputs/prepared_input.json');ap.add_argument('--results',type=Path,default=ROOT/'results');ap.add_argument('--baseline',type=Path,default=ROOT.parent/'baseline');ap.add_argument('--out',type=Path,default=ROOT/'validation/numerical_spot_check.json');a=ap.parse_args()
    data=json.loads(a.inputs.read_text());rows=json.loads((a.results/'all_candidate_metrics.json').read_text())['rows'];rec={r['record_id']:r for r in data['records']};refs={c['candidate_id']:c for im in data['candidate_images'] for c in im['candidates']};au,sp,qv,ch,strict,hm=engine(a.baseline)
    full=[r for r in rows if r['Hm'] is not None];selected=[]
    for key in ['Hc','Sb_deg']:
        for r in sorted(full,key=lambda x:-x[key])[:8]:
            if (r['record_id'],r['candidate_id']) not in {(x['record_id'],x['candidate_id']) for x in selected}:selected.append(r)
    out=[]
    for r in selected:
        g=rec[r['record_id']]['geometry'];f=refs[r['candidate_id']]['full_geometry'];v={}
        for n in [2048,4096,8192,16384]:v[str(n)]=ch.centered_height_components(g,f,samples=n,height_module=hm)['Hcenter']
        sb8192=sp.spherical_sym_distance(g['bottom3d'],f['bottom3d'],8192)
        out.append({'record_id':r['record_id'],'candidate_id':r['candidate_id'],'Hc_by_samples_per_direction':v,
             'Sb_2048':r['Sb_deg'],'Sb_8192':sb8192,'Q_base':r['Q_full_baseline'],
             'Q_Hc16384_Sb8192':baseline_score(r['I'],sb8192,r['D_deg'],r['Hm'],v['16384']),
             'Q_abs_delta':abs(r['Q_full_baseline']-baseline_score(r['I'],sb8192,r['D_deg'],r['Hm'],v['16384']))})
    result={'selection':'union of eight largest Hc and eight largest Sb among available complete reference metric rows; numerical stress selection, no human accuracy inference',
        'pairs':len(out),'rows':out,'max_abs_Hc_4096_16384':max(abs(x['Hc_by_samples_per_direction']['4096']-x['Hc_by_samples_per_direction']['16384']) for x in out),
        'max_abs_Sb_2048_8192_deg':max(abs(x['Sb_2048']-x['Sb_8192']) for x in out),'max_abs_Q_delta':max(x['Q_abs_delta'] for x in out)}
    dump(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
