#!/usr/bin/env python3
"""Independent projection/old-result crosschecks and fixed-engine sampling audit."""
import argparse,copy,json,sys
from pathlib import Path
import numpy as np
from recompute import ROOT,read,save,sha,project,score_geometry

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);a=p.parse_args();repo=a.repo.resolve()
    frozen_path=repo/'research/quality_scope_comparison_20261010/inputs/current_geometry_three_images.json'
    anchors=[]
    for im in read(frozen_path)['images']:
        for r in im['annotations']+im['groundtruths']:
            o=r['source_record']; anchors.append({'id':r['id'],'image_code':im['code'],'object_id':o['canonical_object_id'],'points_1024x512':o['points_1024x512'],'ordered_source_point_indices':o['ordered_source_point_indices'],'ordered_source_pair_indices':o['ordered_source_pair_indices'],'top3d':r['top3d'],'bottom3d':r['bottom3d']})
    save(ROOT/'inputs/frozen_projection_anchors.json',{'source_path':str(frozen_path.relative_to(repo)),'source_sha256':sha(frozen_path),'records':anchors})
    projection=[]
    for r in anchors:
        g=project(r);e=max(float(np.max(np.abs(np.asarray(g[k])-r[k]))) for k in ('top3d','bottom3d'));assert e<1e-12
        projection.append({'id':r['id'],'image':r['image_code'],'max_abs_error':e})
    current=read(ROOT/'inputs/new_formal.json');om={o['object_id']:o for o in read(ROOT/'inputs/old_formal.json')['objects']};nm={o['object_id']:o for o in current['objects']}
    sys.path.insert(0,str(repo))
    from tools.thesis_main.analysis.research_round_20260929 import reconstruct
    declared=[]
    for o in nm.values():
        rr={'points':o['points_1024x512'],'source_point_indices':o['ordered_source_point_indices'],'source_pair_indices':o['ordered_source_pair_indices'],'order_status':o['order_status'],'ring_confirmed':o['ring_confirmed']}
        q=reconstruct(rr);g=project(o);assert q['status']=='ok'
        assert np.allclose(q['floor'],np.asarray(g['bottom3d'])[:,[0,2]],atol=1e-12,rtol=0)
        assert np.allclose(q['heights']-1,np.asarray(g['top3d'])[:,1],atol=1e-12,rtol=0)
        declared.append({'record_id':current['aliases'][o['object_id']],'status':q['status'],'floor_max_error':float(np.max(np.abs(q['floor']-np.asarray(g['bottom3d'])[:,[0,2]]))),'top_height_max_error':float(np.max(np.abs(q['heights']-1-np.asarray(g['top3d'])[:,1])))})
    full=read(ROOT/'results/full_old_new_results.json');oldscope=read(repo/'analysis_results/image_difficulty_full_review_20261010/all_scope_evidence.json');saved=next(x for x in oldscope if x['image']=='yqstnuAEVhm-07');save(ROOT/'inputs/saved_old_image_scope_evidence.json',saved)
    oldcheck=[]
    for r in saved['observations']:
        oid=r['object_id'];assert r['points']==om[oid]['points_1024x512']
        errors={k:abs(r['selected_gt_metrics'][k]-full[oid]['old']['independent_shapely_area'][k]) for k in ('symmetric_difference','excess','missing')};assert max(errors.values())<1e-12
        oldcheck.append({'record_id':r['record_id'],'area_metric_errors':errors})
    reference=read(ROOT/'results/fixed_GT.json');sensitivity=[]
    for oid in read(ROOT/'inputs/confirmed_orders.json')['records']:
        for snapshot in ('old','new'):
            low=full[oid][snapshot]['result'];high=score_geometry(full[oid][snapshot]['geometry'],reference,spherical_samples=4096,height_samples=8192)
            diff=high['quality_score']-low['quality_score'];assert abs(diff)<0.005
            sensitivity.append({'record_id':current['aliases'][oid],'snapshot':snapshot,'primary_Q_2048_4096':low['quality_score'],'double_sample_Q_4096_8192':high['quality_score'],'delta':diff})
        deliberately_sorted=copy.deepcopy(nm[oid]);pairs=np.asarray(deliberately_sorted['points_1024x512']).reshape(-1,2,2);deliberately_sorted['points_1024x512']=pairs[np.argsort(pairs[:,0,0])].reshape(-1,2).tolist();g=project(deliberately_sorted)
        for k in ('top3d','bottom3d'):assert np.array_equal(g[k],full[oid]['old']['geometry'][k])
        negative=score_geometry(g,reference);assert abs(negative['quality_score']-full[oid]['old']['result']['quality_score'])<1e-12
    save(ROOT/'results/independent_validation.json',{'passed':True,'frozen_projection_anchors':projection,'frozen_projection_max_abs_error':max(r['max_abs_error'] for r in projection),'formal_declared_projection_comparison':declared,'saved_old_scope_metrics_crosscheck':oldcheck,'deliberate_x_sort_restores_old_scores_for_all_three':True,'sampling_sensitivity':sensitivity,'max_abs_sampling_Q_change':max(abs(r['delta']) for r in sensitivity)})
    print('Independent validation passed. Frozen projection max:',max(r['max_abs_error'] for r in projection),'Sampling max Q difference:',max(abs(r['delta']) for r in sensitivity))
if __name__=='__main__':main()
