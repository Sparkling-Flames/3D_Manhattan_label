#!/usr/bin/env python3
"""Re-score fixed, previously computed fusion outputs; never recompute fusion."""
from __future__ import annotations
import argparse,collections,csv,importlib.util,itertools,sys
from pathlib import Path
import numpy as np
from apply_exposure_and_audit import read,write,sha,exposure_barriers
from recheck_comparisons import csvout


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'structure_height_preference_20261012/evidence';O=E/'fixed_fusion_demo';O.mkdir(parents=True,exist_ok=True)
    protocol=read(E/'fixed_fusion_demo_protocol.json');sp=W/'top_structure_20261012/evidence/results/fixed_demo_features.json'
    assert sha(sp)==protocol['source_features_sha256']
    cp=W/'structure_height_preference_20261012/height/candidate_config.json';assert sha(cp)==protocol['candidate_config_sha256']
    spec=importlib.util.spec_from_file_location('new_cf',cp.parent/'candidate_functions.py');cf=importlib.util.module_from_spec(spec);spec.loader.exec_module(cf)
    B=W/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    components={r['record_id']:r for r in read(B/'results/current_components.json')};objects={r['object_id']:r for r in read(B/'inputs/current_formal_loader_data.json')['objects']}
    hold={r['record_id']:r for r in csv.DictReader((B/'results/room_holdout_manifest.csv').open(encoding='utf-8-sig'))}
    reg=read(B/'inputs/reference_exclusion_registry_20261010.json');overlay=read(W/'new_main_snapshot/research/quality_severe_feedback_20261011/feedback_overlay.json')
    ex=read(W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    sys.path.insert(0,str(W/'top_structure_20261012/evidence'));from development_filter import record_barriers
    source=read(sp);members=[r for r in source if r['kind']=='member'];eps=[r for r in source if r['kind']=='endpoint']
    assert len(members)==67 and len(eps)==4 and sum(r['independent_output'] for r in eps)==3
    source_audit=read(W/'top_structure_20261012/evidence/results/fixed_fusion_source_audit.json')
    for m in source_audit['source_manifest']:assert sha(W/m['path'])==m['sha256']
    fm=read(W/'top_structure_20261012/evidence/results/fixed_demo_feature_manifest.json')
    for rel,h in fm['source_sha256'].items():assert sha(W/rel)==h
    ledger=[]
    for r in members:
        c=components[r['record_id']];o=objects[c['object_id']];h=hold[r['record_id']]
        barriers=record_barriers(c,o,h,reg,overlay)+exposure_barriers(r['record_id'],h['room_group'],h['held_out_of_sample_and_future_calibration']=='True',ex)
        assert not barriers,(r['record_id'],barriers)
        assert r['reference_object_id']==c['reference_object_id']
        assert r['worker_id']!='W019'
        ledger.append(dict(record_id=r['record_id'],worker_id=r['worker_id'],image_code=r['image_code'],room_group=h['room_group'],
            existing_barriers=barriers,explicit_applicability=(o.get('scene_oos_status')=='not_oos' and o.get('scene_doorway_status')=='none'),
            new_reference_acceptance=False,new_human_quality_label=False))
    frozen_new_names=[c['name'] for c in read(cp)['candidates']]
    assert len(frozen_new_names)==15
    methods=cf.prior.PRIMARY_METHODS+cf.prior.DIAGNOSTIC_METHODS+frozen_new_names
    scored=[{**r,**{k:v for k,v in cf.score(r).items() if k in methods}} for r in source];m=[r for r in scored if r['kind']=='member'];ep=[r for r in scored if r['kind']=='endpoint']
    for r in ep:assert r['Q_no_top_Xrms8'] is None and r['Q_no_top_Xmax8'] is None
    common=[x for x in methods if all(r[x] is not None for r in ep)]
    write(O/'scored_fixed_rows_71.json',scored);csvout(O/'scored_fixed_rows_71.csv',scored);write(O/'source_qualification_67.json',ledger)
    epcompare=[];pair_summary=[];pair_changes=[]
    for img in sorted({r['image_code'] for r in m}):
        ss=[r for r in m if r['image_code']==img]
        for method in common:
            for r in ep:
                if r['image_code']!=img:continue
                diff=[r[method]-v[method] for v in ss]
                epcompare.append(dict(endpoint=r['identity'],image_code=img,method=method,n_members=len(ss),score=r[method],
                    strict_members_below=sum(d>1e-10 for d in diff),ties=sum(abs(d)<=1e-10 for d in diff),strict_members_above=sum(d < -1e-10 for d in diff),
                    independent_output=r['independent_output'],duplicate_of=r['duplicate_of'],status=r['endpoint_status'],
                    no_truth_of_better_quality_from_rank=True))
            for baseline in ['Q_v11','Q_no_topS']:
                count=ties=rev=newties=0
                for x,y in itertools.combinations(ss,2):
                    a0=x[baseline]-y[baseline];b0=x[method]-y[method]
                    if abs(a0)<=1e-10:ties+=1;continue
                    count+=1
                    if abs(b0)<=1e-10:newties+=1
                    elif a0*b0<0:
                        rev+=1;pair_changes.append(dict(image_code=img,baseline=baseline,method=method,record_a=x['record_id'],record_b=y['record_id'],old_delta=a0,new_delta=b0))
                pair_summary.append(dict(image_code=img,method=method,baseline=baseline,all_pairs=len(ss)*(len(ss)-1)//2,
                    baseline_strict_pairs=count,baseline_ties=ties,new_ties_of_old_strict=newties,strict_reversals=rev))
    csvout(O/'endpoint_relative_to_members.csv',epcompare);csvout(O/'within_image_rank_change_summary.csv',pair_summary);csvout(O/'within_image_changed_pairs.csv',pair_changes)
    images={r['image_code'] for r in m};workers=collections.defaultdict(list)
    for r in m:workers[r['worker_id']].append(r)
    balanced={w:rs for w,rs in workers.items() if len(rs)==3 and {r['image_code'] for r in rs}==images}
    assert len(balanced)==19
    worker_rows=[]
    for w,rs in sorted(balanced.items()):
        for method in methods:
            v=np.array([r[method] for r in rs])
            worker_rows.append(dict(worker_id=w,method=method,images=sorted(images),records=3,
                equal_image_mean=float(v.mean()),three_condition_population_sd=float(v.std(ddof=0)),minimum=float(v.min()),maximum=float(v.max()),
                not_long_term_personnel_ability=True,not_repeat_annotation_noise=True))
    csvout(O/'balanced_three_image_worker_descriptives.csv',worker_rows)
    wmap={(r['worker_id'],r['method']):r for r in worker_rows};ws=[]
    for method in methods:
        for baseline in ['Q_v11','Q_no_topS']:
            count=ties=rev=0
            for wa,wb in itertools.combinations(sorted(balanced),2):
                d0=wmap[(wa,baseline)]['equal_image_mean']-wmap[(wb,baseline)]['equal_image_mean']
                d1=wmap[(wa,method)]['equal_image_mean']-wmap[(wb,method)]['equal_image_mean']
                if abs(d0)<=1e-10:ties+=1
                else:count+=1;rev+=int(d0*d1<0)
            ws.append(dict(method=method,baseline=baseline,balanced_workers=19,pair_count=171,baseline_strict_pairs=count,baseline_ties=ties,
                mean_score_strict_order_reversals=rev,
                median_three_condition_sd=float(np.median([wmap[(w,method)]['three_condition_population_sd'] for w in balanced])),
                scale_changes_not_worker_stability_improvements=True))
    csvout(O/'balanced_worker_rank_change_summary.csv',ws)
    summary=dict(source_features_sha256=sha(sp),candidate_config_sha256=sha(cp),protocol_sha256=sha(E/'fixed_fusion_demo_protocol.json'),
        members=67,workers=24,images=3,endpoint_rows=4,distinct_endpoint_geometries=3,
        explicit_applicability_among_members=sum(r['explicit_applicability'] for r in ledger),
        known_source_barriers=0,holdout_or_exposed_groups_used=0,formal_W019_restored=False,
        balanced_three_image_workers=19,balanced_records=57,workers_with_only_two_images=5,
        all_partial_workers_retained_in_source_ledger=True,complete_count_trajectories=0,fusion_recomputed=False,
        main_parameters_refitted_for_demo=False,rawX_for_aggregate_imputed=False,independent_validation=False,
        unique_endpoint_scores=[{k:r[k] for k in ['identity','image_code','n','endpoint_status','iou_2d','dir','flat','Hmean','Hcenter']+common} for r in ep if r['independent_output']],
        interpretation=['Geometry_review endpoints and unknown image applicability remain conditional examples, not a confirmed final benchmark.',
            'Within-image and balanced worker order changes are formula sensitivity, not verified personnel accuracy.',
            'Three-condition SD cannot separate person ability, image conditions or reconstruction propagation.',
            'Only one fixed team output per image is available; no number-of-members or team-composition curve is inferred.',
            'Original-input residuals and processed-output scores have different targets; absent aggregate raw pairs are not zero residual.'])
    write(O/'summary.json',summary)
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
