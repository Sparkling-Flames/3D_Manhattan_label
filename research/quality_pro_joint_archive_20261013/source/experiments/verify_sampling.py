#!/usr/bin/env python3
"""Quantify numerical changes separately from formula/reference changes."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from export_real_descriptors import read,write,sha

sys.dont_write_bytecode = True


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    source=args.source.resolve();out=args.out.resolve()
    data=read(source/'inputs/calibration_records.json');by={r['id']:r for r in data['rows']}
    ids=set(['R00397','R00418','R02015','R00637','R00464','R00481','R01810','R01385','R03351','R03350',
             'R01033','R01022','R02447','R01973','R01609','R02297','R00341','R00796','R02049','R02244','R00404','R01579'])
    # Include extrema and quartiles of the actually cached geometric features,
    # selected independently of candidate scores or human preferences.
    for feature in ('dir','S_bottom_deg','Hmean','Hcenter'):
        ordered=sorted(data['rows'],key=lambda r:(r['metrics'][feature],r['id']))
        ids.update(ordered[i]['id'] for i in np.linspace(0,len(ordered)-1,5).round().astype(int))
    real=[{'case_id':rid,'family':'actual_response','annotation':data['geometries'][by[rid]['object_id']],
        'reference':data['geometries'][by[rid]['reference_object_id']],
        'source_frozen_metrics':by[rid]['metrics'],
        'record_provenance':{k:by[rid].get(k) for k in ('id','object_id','reference_object_id','current_points_sha256','reference_points_sha256','coordinate_hash','gate')}}
         for rid in sorted(ids)]
    synthetic=[r for r in read(out/'targeted_constructed_cases.json')['cases'] if r['annotation'] is not None]
    sys.path.insert(0,str(source/'scripts'))
    from score_frozen_geometry import evaluate
    config=read(source/'config/frozen_selected_candidates.json')['candidates']['P_tied_quad08']['parameters']
    records=[];start=time.time()
    # All 335 new controls receive 1024/2048/4096 spherical comparison.  The 39
    # actual examples additionally receive 4096/8192/16384 height comparison.
    for i,c in enumerate(real+synthetic):
        numerics=[(1024,4096),(2048,4096),(4096,4096)]
        if c['family']=='actual_response':numerics += [(4096,8192),(4096,16384)]
        computations=[]
        for sphere,height in numerics:
            v=evaluate(c['annotation'],c['reference'],config,samples=sphere,height_samples=height)
            computations.append({'spherical_samples':sphere,'height_samples':height,'status':v['status'],
                'baseline_Q':v.get('quality_score'),'metrics':{k:v.get('metrics',{}).get(k) for k in
                    ('iou_2d','S_bottom_deg','S_top_deg','dir','Hmean','Hcenter')},
                'reason_if_unavailable':v.get('legacy_result',{}).get('reason_codes')})
        record={'case_id':c['case_id'],'family':c['family'],'computations':computations,
            'record_provenance':c.get('record_provenance'),
            'source_frozen_metrics':c.get('source_frozen_metrics')}
        available=[r for r in computations if r['status']=='available']
        if len(available)==len(computations):
            one,two,four=computations[:3]
            record['abs_Q_change_sphere1024_to_2048']=abs(one['baseline_Q']-two['baseline_Q'])
            record['abs_Q_change_sphere2048_to_4096']=abs(two['baseline_Q']-four['baseline_Q'])
            record['abs_Sb_change_sphere2048_to_4096_deg']=abs(two['metrics']['S_bottom_deg']-four['metrics']['S_bottom_deg'])
            if c['family']=='actual_response':
                last=computations[-1]
                record['abs_Q_change_height4096_to_16384']=abs(four['baseline_Q']-last['baseline_Q'])
                record['abs_Hc_change_height4096_to_16384']=abs(four['metrics']['Hcenter']-last['metrics']['Hcenter'])
                record['max_frozen_metric_difference_at_2048_4096']=max(abs(two['metrics'][k]-c['source_frozen_metrics'][k])
                    for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'))
        records.append(record)
        if (i+1)%50==0 or i+1==len(real+synthetic):
            print(f'sampling {i+1}/{len(real+synthetic)} elapsed={time.time()-start:.1f}s',flush=True)
    summary={'n_actual_response_geometries':len(real),'n_constructed_geometries':len(synthetic),
        'n_geometry_evaluations':sum(len(r['computations']) for r in records),
        'all_numerics_available':all(all(v['status']=='available' for v in r['computations']) for r in records),
        'not_new_human_validation':True,'source_calibration_sha256':sha(source/'inputs/calibration_records.json')}
    for prefix,rr in [('actual',records[:len(real)]),('constructed',records[len(real):])]:
        for key in ('abs_Q_change_sphere1024_to_2048','abs_Q_change_sphere2048_to_4096','abs_Sb_change_sphere2048_to_4096_deg',
                    'abs_Q_change_height4096_to_16384','abs_Hc_change_height4096_to_16384','max_frozen_metric_difference_at_2048_4096'):
            available=[r for r in rr if key in r]
            if available:
                worst=max(available,key=lambda r:r[key]);summary[prefix+'_max_'+key]={'value':worst[key],'case_id':worst['case_id']}
    write(out/'sampling_verification.json',{'summary':summary,'rows':records});print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
