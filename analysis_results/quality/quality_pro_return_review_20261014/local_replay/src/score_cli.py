"""Score one permitted snapshot row, never infer a missing reference.
Examples: python src/score_cli.py --record R03274 --rebuild
          python src/score_cli.py --record R03332
The default is storage-metric rescoring. --rebuild reconstructs the same frozen
points and reference. A conditional score is not an admission or human grade.
"""
import argparse
from core import *

def main(rid,rebuild):
    co=read(INPUT/'data/cohorts.json');found=[(k,r) for k in ['ordinary','severe','doorway','historical_only'] for r in co[k] if r['record_id']==rid]
    if len(found)!=1:raise ValueError('unknown_or_duplicate_record_id:'+rid)
    layer,r=found[0];out=dict(record_id=rid,source_layer=layer,formal_eligibility_changed=False,source_points_changed=False,
                             reference_selected_by_this_function=False,human_grade=None)
    if r.get('status')=='held':
        out.update(status='held',reason_codes=r['reason_codes'],score=None)
    else:
        ref=r.get('reference_object_id') or r['reference']['object_id'];m=r['metrics']
        if rebuild:
            oo={o['object_id']:o for o in read(INPUT/'data/objects.json')['objects']}
            m=full_measure(geometry(oo[r['object_id']]['points_1024x512']),geometry(oo[ref]['points_1024x512']),with_diagnostics=False)['metrics']
        config=read(ROOT/'configs/WORKING_FINAL.json')['config']
        out.update(method='from_frozen_points' if rebuild else 'stored_metrics_rescore',reference_object_id=ref,metrics=m,components=components(m,config))
        if r['image_id']=='B6ByNegPMKs_d2dcbd73533446dcaf50e6be98c30386':
            out.update(interpretation='broad-reference conditional diagnostic only; permitted small room has no precise small-room reference',same_target_worker_quality=None)
        else:out['interpretation']='conditional geometric research score; not an absolute severity grade'
    print(json.dumps(clean(out),ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--record',required=True);p.add_argument('--rebuild',action='store_true');a=p.parse_args();main(a.record,a.rebuild)
