"""冻结难度交接；只核对标签/目标/参考，不评分或改共同入口。"""
import copy
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/difficulty/difficulty_b8l2_handoff_20261016'


def changes(old,new):
    label=old['current_class']!=new['current_class']
    target=old['target_version']!=new['target_version'] or old['selected']['floor']!=new['selected']['floor']
    eligibility=any(old.get(k)!=new.get(k) for k in ['gt_error_excluded','difficulty_analysis_eligible','difficulty_analysis_exclusion'])
    return dict(class_changed=label,target_changed=target,gt_or_eligibility_changed=eligibility,
        class_only=label and not target and not eligibility)


def main():
    pointer_path=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    pointer_bytes=pointer_path.read_bytes();pointer=json.loads(pointer_bytes)
    current_path=(pointer_path.parent/pointer['details']).resolve()
    current=json.loads(current_path.read_text(encoding='utf-8'));version=current['version']
    base=ROOT/'research/difficulty'
    paths=[base/'difficulty_user_adoption_20261016/current_259.json',base/'difficulty_pair_display_20261016/current_259.json',current_path]
    snapshots=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    assert snapshots[-1]['version'].endswith('_v6'),'inspect new version before handoff'
    ref_path=ROOT/'research/data/scope_quality_rescore_20261016/reference_catalog.json'
    refs={r['target_id']:r for r in json.loads(ref_path.read_text(encoding='utf-8'))}
    overlay_path=base/'difficulty_scope_resolution_20261016/new_scope_references.json'
    overlays=json.loads(overlay_path.read_text(encoding='utf-8'))
    scope_path=ROOT/'analysis_results/research_input_20260929/floor_scope_update_20261015.json'
    scopes={r['reference_id']:r for r in json.loads(scope_path.read_text(encoding='utf-8'))['records']}
    for x in overlays:
        ref=copy.deepcopy(x['reference']);s=scopes[ref['target_id']]
        assert s['image_id']==ref['image_id']
        ref.update(floor_xz_h=s['floor_xz_h'],reference_version='scope_resolution_20261016_v6',role='confirmed_scope')
        refs[ref['target_id']]=ref
    current_targets={r['target_version'] for r in current['records']}
    for ref in refs.values():ref['current_target']=ref['target_id'] in current_targets
    OUT.mkdir(exist_ok=True)
    def write(name,obj):
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    stable=copy.deepcopy(current)
    for r in stable['records']:
        for k in ['card','old_card','scope_comparison']:
            if r.get(k):r[k]=(current_path.parent/r[k]).resolve().as_posix()
    write('difficulty_snapshot.json',stable)
    write('current_pointer_snapshot.json',pointer)
    write('reference_catalog_snapshot.json',list(refs.values()))
    delta=[]
    for before,after in zip(snapshots,snapshots[1:]):
        old={r['image_id']:r for r in before['records']}
        for r in after['records']:
            o=old[r['image_id']];flags=changes(o,r)
            if not any(flags.values()):continue
            delta.append(dict(image=r['image'],image_id=r['image_id'],from_version=before['version'],to_version=after['version'],
                old_class=o['current_class'],new_class=r['current_class'],old_target=o['target_version'],new_target=r['target_version'],
                old_exclusion=o['difficulty_analysis_exclusion'],new_exclusion=r['difficulty_analysis_exclusion'],**flags))
    inventory=[]
    for r in current['records']:
        ref=refs[r['target_version']]
        assert ref['image_id']==r['image_id']
        assert np.allclose(ref['floor_xz_h'],r['selected']['floor'],atol=1e-8,rtol=0)
        f=r['selected']['features'];assert f['N_floor']==len(r['selected']['floor']) and f['N_turn']==r['N_turn']
        initial=r['candidates'][0]['features']
        evidence=r.get('user_scope_ambiguity_note')
        inventory.append(dict(image=r['image'],image_id=r['image_id'],difficulty_version=version,difficulty_target_id=r['target_version'],
            difficulty_class=r['current_class'],difficulty_analysis_eligible=r['difficulty_analysis_eligible'],
            difficulty_analysis_exclusion=r['difficulty_analysis_exclusion'],gt_error_excluded=r['gt_error_excluded'],
            original_candidate_vertex_count=initial['N_floor'],selected_vertex_count=f['N_floor'],effective_turn_count=f['N_turn'],
            straight_vertices_1based=f['straight_vertices_1based'],H=r['H'],reference_full_available=ref['full_reference_available'],
            reference_status=ref.get('status',ref['method']),reference_gap=ref.get('minimal_gap',''),
            reference_method=ref['method'],introduced_scope_edges=ref.get('introduced_scope_edges'),
            vertex_sources=ref.get('vertex_sources'),physical_wall_asserted=ref.get('physical_wall_asserted'),
            edge_metadata_present='introduced_scope_edges' in ref,
            edge_origin_status='construction_metadata_available' if ref['full_reference_available'] and 'introduced_scope_edges' in ref else 'not_established',
            answer_exposure_status='referenced_answers_scope' if evidence else 'unknown',
            answer_exposure_evidence=evidence or '',label_basis=r['classification_basis'],
            ordinary_candidate_only_not_final_score_eligibility=True))
    for name,records in [('image_inventory',inventory),('version_changes',delta)]:
        write(name+'.json',records)
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader()
            for r in records:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    assert pointer_path.read_bytes()==pointer_bytes,'CURRENT changed during capture'
    ordinary=[r for r in inventory if r['difficulty_analysis_eligible']]
    scope_ids={r['target_version'] for r in current['records'] if r['selected']['role']=='confirmed_scope'}
    checks=dict(difficulty_version=version,images=len(inventory),ordinary_candidates=len(ordinary),
        ordinary_counts=dict(Counter(r['difficulty_class'] for r in ordinary)),version_changes=len(delta),
        class_only=sum(r['class_only'] for r in delta),target_changes=sum(r['target_changed'] for r in delta),
        gt_or_eligibility_changes=sum(r['gt_or_eligibility_changed'] for r in delta),
        scope_full_available=sum(refs[x]['full_reference_available'] for x in scope_ids),scope_pending=sum(not refs[x]['full_reference_available'] for x in scope_ids),
        vertex_turn_differences=[r['image'] for r in inventory if r['selected_vertex_count']!=r['effective_turn_count']],
        exposure_counts=dict(Counter(r['answer_exposure_status'] for r in inventory)),current_unchanged=True,scores_read=False,scores_recomputed=False)
    write('CHECKS.json',checks)
    write('INPUT_MANIFEST.json',dict(difficulty_version=version,source_paths=[str(p.relative_to(ROOT)) for p in paths]+[str(ref_path.relative_to(ROOT)),str(overlay_path.relative_to(ROOT)),str(scope_path.relative_to(ROOT))],
        stable_difficulty='difficulty_snapshot.json',stable_references='reference_catalog_snapshot.json',stable_inventory='image_inventory.json',
        intended_score='WQ-B8L2-20261015 original parameters; no score computed here',
        registration_pending=['research/difficulty/difficulty_b8l2_handoff_20261016','tools/thesis_main/analysis/difficulty_b8l2_handoff_20261016.py','tests/test_difficulty_b8l2_handoff_20261016.py']))
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':main()
