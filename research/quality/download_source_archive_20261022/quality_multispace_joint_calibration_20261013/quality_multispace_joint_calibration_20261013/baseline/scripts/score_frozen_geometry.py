"""Minimal end-to-end frozen-geometry adapter for the tentative quality family.

Input geometries must already have reliable rings and top/bottom pairing.
This adapter never repairs points, chooses another reference, or changes gates.
Use --record-id for the packaged examples, or --annotation/--reference JSONs.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'source_snapshot/research/quality_scope_comparison_20261010/frozen_engine'
sys.path.insert(0,str(ENGINE/'core'))
from quality_v11 import score_geometry as old_score_geometry
from centered_height import centered_height_components
from scoring import scalar_terms
from frozen_guard import verify_scoring_identity

def evaluate(annotation,reference,settings,samples=2048,height_samples=4096):
    old=old_score_geometry(annotation,reference,spherical_samples=samples,height_samples=height_samples,
        target_applicability='conditional_geometry')
    if old['status']!='available':
        return dict(status=old['status'],quality_score=None,legacy_result=old,scope_acceptance_not_inferred=True)
    m=dict(old['metrics']);m.update(centered_height_components(annotation,reference,samples=height_samples))
    # Hmean already uses perimeter mean. Signed ratio is supplementary only.
    from height_revision import height_moments
    m['height_mean_ratio']=height_moments(annotation)['height_mean_h']/height_moments(reference)['height_mean_h']
    terms=scalar_terms(m,settings)
    return dict(status='available',quality_score=terms['score'],components=terms,metrics=m,
        frozen_v11_score=old['quality_score'],official_corner_mean_iou3d=m.get('iou_3d_corner_mean'),
        scope_acceptance_not_inferred=True,input_pair_semantics_not_certified=True,formal_score_replaced=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--record-id');p.add_argument('--annotation',type=Path);p.add_argument('--reference',type=Path)
    p.add_argument('--candidate',default='P_tied_quad08');p.add_argument('--out',type=Path);p.add_argument('--verify-key-cases',action='store_true');a=p.parse_args()
    frozen=json.loads((ROOT/'config/frozen_selected_candidates.json').read_text());c=frozen['candidates'][a.candidate]
    verify_scoring_identity(frozen,ROOT)
    if c.get('global_coordinate')=='log':raise ValueError('This minimal adapter exposes relative-height geometry candidates; use the scalar log baseline through export_selected.py')
    if a.verify_key_cases:
        data=json.loads((ROOT/'inputs/calibration_records.json').read_text());by={r['id']:r for r in data['rows']};gg=data['geometries']
        expected={r['id']:r for r in json.loads((ROOT/'results/selected_scores.json').read_text())['rows']}
        checks=[]
        for rid in ['R00397','R00418','R02015','R00637','R01055','R00991','R00678','R02196','R03346','R00464']:
            r=by[rid];v=evaluate(gg[r['object_id']],gg[r['reference_object_id']],c['parameters'])
            assert v['status']=='available'
            difference=abs(v['quality_score']-expected[rid]['scores'][a.candidate])
            assert difference<1e-8,(rid,difference)
            checks.append(dict(id=rid,quality_score=v['quality_score'],expected=expected[rid]['scores'][a.candidate],absolute_difference=difference,
                v11_difference=abs(v['frozen_v11_score']-expected[rid]['scores']['Q_v11']),
                iou3d_x100_difference=abs(v['official_corner_mean_iou3d']*100-expected[rid]['scores']['Q_official_iou3d'])))
        out=dict(candidate=a.candidate,geometry_pairs_recomputed=len(checks),checks=checks,
            maximum_difference=max(x['absolute_difference'] for x in checks),samples=2048,height_samples=4096,
            full_geometry_replay_not_human_validation=True)
    elif a.record_id:
        data=json.loads((ROOT/'inputs/calibration_records.json').read_text());r=next(r for r in data['rows'] if r['id']==a.record_id)
        out=evaluate(data['geometries'][r['object_id']],data['geometries'][r['reference_object_id']],c['parameters']);out['record_id']=a.record_id
    else:
        if not a.annotation or not a.reference:p.error('Provide --record-id, --verify-key-cases, or --annotation and --reference')
        out=evaluate(json.loads(a.annotation.read_text()),json.loads(a.reference.read_text()),c['parameters'])
    text=json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text)
    else:print(text)

if __name__=='__main__':main()
