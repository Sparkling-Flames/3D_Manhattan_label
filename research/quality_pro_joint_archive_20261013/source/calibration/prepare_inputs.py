#!/usr/bin/env python3
"""Freeze a lightweight, explicitly versioned search table; no geometry edits."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from score import BASELINE,score_metrics

HERE=Path(__file__).resolve().parent
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=HERE.parent/'baseline')
    p.add_argument('--out',type=Path,default=HERE/'inputs')
    p.add_argument('--latest',type=Path,default=HERE.parent/'sources/main/research')
    p.add_argument('--descriptors',type=Path,default=HERE.parent/'experiments/results/real_direction_descriptors.json')
    p.add_argument('--joint-hinge',type=Path,default=HERE.parent/'experiments/results/joint_hinge_descriptors.json')
    a=p.parse_args(); source=a.source
    paths={'frozen':source/'inputs/calibration_records.json',
           'grades':source/'inputs/old24_labels_preserved.json',
           'constraints':source/'evidence_audit/results/constraints.json',
           'latest_local':a.latest/'quality_parallel_local_20261012/record_results.json',
           'u05':a.latest/'quality_parameter_audit_20261012/U05_CHAT_FEEDBACK.json',
           'descriptors':a.descriptors,'joint_hinge':a.joint_hinge}
    data=read(paths['frozen']);local={r['record_id']:r for r in read(paths['latest_local'])['rows']}
    desc={r['record_id']:r for r in read(paths['descriptors'])['rows']}
    hinge={r['record_id']:r for r in read(paths['joint_hinge'])['rows']}
    rows=[];delta=[]
    for r in data['rows']:
        d=desc[r['id']]; l=local[r['id']]
        assert r['current_points_sha256']==d['current_points_sha256']
        assert r['coordinate_hash']==l['coordinate_group']
        assert r['reference_object_id']==l['reference_id']
        assert max(abs(r['metrics'][k]-l['metrics'][k]) for k in r['metrics'])<1e-12
        q=score_metrics(r['metrics'],BASELINE)['score'];delta.append(abs(q-l['scores']['P_tied_quad08']))
        rows.append({**{k:r.get(k) for k in ['id','object_id','image_id','image_code','building_id','room_id','room_group','worker_id','reference_object_id','current_points_sha256','reference_points_sha256','coordinate_hash','pool','applicability_confirmed']},
                     'reference_version':l['reference_version'],'input_version_original':l['input_version'],
                     'dataset_sha256':sha(paths['frozen']),
                     'conditional_personnel_eligible':l['conditional_personnel_eligible'],
                     'condition':l['condition'],'use_barriers':l['use_barriers'],
                     'formal_eligibility_newly_granted':False,
                     'metrics':r['metrics'],'baseline_scores':l['scores'],
                     'descriptor':{'moment4':d['weighted_abs_moments_deg_power']['p4'],
                                   'excess2':{k:v['positive_part_m2_deg2'] for k,v in d['excess_by_threshold_deg'].items()},
                                   'abs_residual_deg':d['abs_residual_deg'],'length_weight':d['length_weight'],
                                   'joint_hinge':{k:v['value_deg2'] for k,v in hinge[r['id']]['values'].items()}},
                     'raw_alignment':d['raw_alignment']})
    assert len(rows)==922 and sum(r['conditional_personnel_eligible'] for r in rows)==143
    assert max(delta)<1e-10
    grades=[]
    for r in read(paths['grades']):
        grades.append({k:r[k] for k in ['id','case_id','grade','building_id','image_id','room_group','known_confidence','protocol','answer_original']})
        grades[-1]['scope_confounded_latest']=r['case_id'] in ('T21','T22')
        grades[-1]['uncertainty_applies_even_without_comment']=True
    constraints=read(paths['constraints'])['constraints']
    u05=read(paths['u05'])
    constraints.append(dict(constraint_id='U05:processed_overall_quality',panel='U05',dimension='processed_overall_quality',
                            evidence_type='explicit_direction',preferred_record_id=u05['A']['record_id'],other_record_id=u05['B']['record_id'],
                            record_ids=[u05['A']['record_id'],u05['B']['record_id']],source=u05['source_message_id'],
                            comment=u05['verbatim'],numeric_margin=None,confidence=None,independent_validation=False,
                            local_height_direction=None))
    provenance={k:{'file_name':str(v.relative_to(source)) if v.is_relative_to(source) else v.name,'sha256':sha(v),'bytes':v.stat().st_size} for k,v in paths.items()}
    dump(a.out/'search_inputs.json',dict(schema='joint_search_inputs_v1',rows=rows,grades=grades,constraints=constraints,
         provenance=provenance,baseline_scalar_max_delta=max(delta),main_commit='fdfc8a51ad668c83172ca4a9cf0105f417dac61c',
         all_human_evidence_is_development=True,geometry_recomputed_in_this_prepare=False,
         unknown_screen_entries_are_not_labels=True))
    dump(a.out/'INPUT_CONTRACT.json',dict(provenance=provenance,records=len(rows),conditional_personnel_eligible=143,
         raw_field_identity='X_rms_deg = 2 * Eperp_deg; neither is an automatic semantic-pairing quality label',
         source_sampling='Frozen baseline metrics retained; reference-changing evaluations record their separate precision.',
         baseline_scalar_max_delta=max(delta),additional_source_files=list(provenance)))
    print(json.dumps(dict(records=len(rows),eligible=143,baseline_max_delta=max(delta),out=str(a.out))))

if __name__=='__main__':main()
