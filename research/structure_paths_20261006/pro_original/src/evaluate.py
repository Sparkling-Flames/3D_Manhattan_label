"""Post-construction reference comparison, never candidate selection.

This delivery has only the previous four-image original-reference file; no
current-local-worktree reference or e9z reference has been supplied.
"""
from pathlib import Path
import json,gzip,hashlib,csv
from collections import defaultdict
import numpy as np
from shapely.geometry import Polygon
from frechet import rays
from run import ROOT,dump

def poly_from_points(points):
    q=np.asarray(points,float).reshape(-1,2,2)
    if len(q)<3:return None,'insufficient_geometry_vertices'
    r=rays(q[:,1])
    if np.any(r[:,1]>=-1e-12):return None,'bottom_horizon_failure'
    p=Polygon((-r/r[:,1,None])[:,[0,2]])
    return (p,None) if p.is_valid and p.area>0 else (None,'invalid_polygon')

def score(p,g):
    u=p.union(g).area
    return {'iou':float(p.intersection(g).area/u),'omission_h2':float(g.difference(p).area),
            'extension_h2':float(p.difference(g).area),'centroid_dx_h':float(p.centroid.x-g.centroid.x),
            'centroid_dz_h':float(p.centroid.y-g.centroid.y)}

def evaluate(out):
    out=Path(out);d=out/'evaluation';d.mkdir(exist_ok=False)
    # Commit all automatic, assisted and alternative candidates before first GT read.
    files=[p for p in out.rglob('*') if p.is_file() and 'evaluation' not in p.relative_to(out).parts]
    dump(d/'pre_reference_candidate_digest.json',{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})
    refs=json.loads((ROOT/'evaluation/references.json').read_text())
    reference={r['image']:r['references'] for r in refs['images']}
    rows=[];patchrows=[]
    for image,versions in reference.items():
        folder=out/image
        if not folder.exists():continue
        for ref in versions:
            g,reason=poly_from_points(ref['points'])
            if reason:
                rows.append({'image':image,'reference':ref['version'],'status':'reference_'+reason});continue
            for metric in ['pair','bottom','top']:
                for tau in [5,9,12]:
                    state=json.loads((folder/f'{metric}_{tau}.json').read_text())
                    policies={p:state[p] for p in ['raw_MV','path_witness_MV']}
                    policies['three_state_MV']=json.loads((out/'analysis'/f'{image}_{metric}_{tau}_three_state.json').read_text())
                    ass=out/'analysis'/f'{image}_{metric}_{tau}_human_assisted.json'
                    if ass.exists():
                        a=json.loads(ass.read_text())
                        if a.get('ring'):policies['human_assisted_MV']={'ring':a['ring']}
                    for name,obj in policies.items():
                        c=obj['ring']['x_diagnostic'];p,r=poly_from_points(c['points'])
                        row={'image':image,'metric':metric,'threshold_deg':tau,'policy':name,'reference':ref['version'],
                             'evaluation_object':'unconfirmed_center_x_diagnostic_not_observed_order_or_complete_layout_truth',
                             'selected_pairs':obj['ring']['selected_pair_count'],'status':r or 'ok',
                             'reference_caveats':ref.get('geometry_issues',[])}
                        if not r:row.update(score(p,g))
                        rows.append(row)
            for tau in [5,9,12]:
                for line in gzip.open(out/'patches'/f'{image}_{tau}_candidate_rings.jsonl.gz','rt'):
                    c=json.loads(line);row={'candidate':c['id'],'image':image,'threshold_deg':tau,'status':c['status'],'reference':ref['version']}
                    if c['status']=='geometry_candidate_unreviewed':
                        p,r=poly_from_points(c['points'])
                        if r:row['status']=r
                        else:
                            row.update(score(p,g))
                            a,ar=poly_from_points(c['anchor_only_control_points'])
                            row['anchor_only_control_status']=ar or 'ok'
                            if not ar:
                                sc=score(a,g);row['anchor_only_control_iou']=sc['iou']
                                row['iou_change_beyond_anchor_only']=row['iou']-sc['iou']
                    patchrows.append(row)
    dump(d/'MV_reference_scores.json',rows);dump(d/'all_path_patch_reference_scores.json',patchrows)
    for name,data in [('MV_reference_scores',rows),('path_patch_reference_scores',patchrows)]:
        if data:
            keys=list(dict.fromkeys(k for r in data for k in r))
            with (d/(name+'.csv')).open('w',newline='') as f:
                w=csv.DictWriter(f,keys);w.writeheader();w.writerows(data)
    dump(d/'policy.json',{'input':'previous_four_image_original_reference_only','new_local_evaluation_folder_received':False,
        'selection_by_reference':False,'all_candidates_scored_where_computable':True,'null_not_zero':True,
        'not_blind_new_validation':True})
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);evaluate(a.parse_args().out)
