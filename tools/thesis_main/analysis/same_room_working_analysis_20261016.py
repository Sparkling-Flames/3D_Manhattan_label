"""使用统一用户关系交付重核同房面板、Q/T和已有18图曲线覆盖。"""
import json

import numpy as np
import pandas as pd

from .same_room_usage_adoption_20261016 import main as adopt_usage, LEGACY, ROOT
from .same_room_relation_adoption_20261016 import OUT as RELATIONS
from .same_room_quality_curves_20261015 import save

OUT = LEGACY / 'working_relations_v4'


def curve_coverage(relations, *, scores_path=None):
    folder = ROOT / 'research/fusion/wall_consensus_b8l2_20261016'
    snapshot = json.loads((folder / 'input_snapshot.json').read_text(encoding='utf-8'))
    scores = pd.read_csv(folder / 'usage_v2/subset_usage.csv' if scores_path is None else scores_path)
    images = {r['image_id']: r for r in snapshot['images']}
    rows = []
    for r in relations:
        if r['image_a'] not in images or r['image_b'] not in images:
            continue
        a, b = [images[r[k]] for k in ['image_a','image_b']]
        aa, bb = [scores[scores.image.eq(im['image'])].copy() for im in [a,b]]
        members = [{m['worker_id']: m['record_id'] for m in im['members']} for im in [a,b]]
        for frame, mapping, im in zip([aa,bb], members, [a,b]):
            for s in frame.itertuples():
                workers = s.worker_ids.split('|')
                assert len(workers)==s.k and set(workers)<=set(mapping)
                assert set(s.member_record_ids.split('|'))=={mapping[w] for w in workers}
                assert s.reference_id==im['reference']['target_id']
                assert (ROOT/s.geometry_source).exists()
            frame['worker_key']=frame.worker_ids.map(lambda x:'|'.join(sorted(x.split('|'))))
            assert not frame.duplicated(['worker_key','k']).any()
        paired=aa.merge(bb,on=['worker_key','k'],suffixes=('_a','_b'),validate='one_to_one')
        rows.append(dict(code_a=a['image'], code_b=b['image'], relation=r['analysis_layer'],
            physical_adopted=r['physical_adopted'], scope_comparable=r['scope_comparable'],
            candidate_ids='|'.join(r['candidates']), user_group_ids='|'.join(r['user_group_ids']),
            common_frozen_members=len(set(members[0])&set(members[1])),
            actual_subsets_a=len(aa), actual_subsets_b=len(bb), exact_same_worker_subsets=len(paired),
            exact_subsets_scene_quality_allowed=int((paired.reference_quality_scene_allowed_a & paired.reference_quality_scene_allowed_b).sum()),
            exact_subsets_both_geometry_available=int((paired.geometry_stability_available_a & paired.geometry_stability_available_b).sum()),
            scope_comparable_quality_curve=(r['analysis_layer']=='user_classified_comparable' and
                bool((paired.reference_quality_scene_allowed_a & paired.reference_quality_scene_allowed_b).any())),
            use_a=a['use'], use_b=b['use'], reference_id_a=a['reference']['target_id'], reference_id_b=b['reference']['target_id']))
        if 'D10_a' in paired:
            assert paired.B8L2_a.notna().equals(paired.D10_a.notna())
            assert paired.B8L2_b.notna().equals(paired.D10_b.notna())
            rows[-1]['exact_subsets_both_B8L2_D10_nonmissing']=int((paired.B8L2_a.notna()&paired.B8L2_b.notna()).sum())
            rows[-1]['exact_subsets_both_primary_eligible']=int((paired.primary_comparison_eligible_a&paired.primary_comparison_eligible_b).sum())
    return pd.DataFrame(rows)


def main():
    adopt_usage(OUT, RELATIONS)
    relations=json.loads((RELATIONS/'relations.json').read_text(encoding='utf-8'))
    manifest=json.loads((RELATIONS/'CROSS_MODULE_RELATIONS.json').read_text(encoding='utf-8'))
    pairs=pd.read_csv(OUT/'current_pairs.csv')
    quality=pairs[pairs.metric.eq('B8L2')&pairs.n_paired.gt(0)]
    old=pd.read_csv(LEGACY/'usage_v3/current_pairs.csv')
    old=old[old.metric.eq('B8L2')&old.n_paired.gt(0)]
    keys=['image_a','image_b','condition']
    fields=['code_a','code_b','n_paired','paired_workers','absolute_mean_gap','mean_absolute_person_delta','confirmation','user_group_ids']
    bridge=old[keys+[f for f in fields if f in old]].merge(quality[keys+fields],on=keys,
        how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one')
    both=bridge[bridge._merge.eq('both')]
    assert not bridge._merge.eq('left_only').any()
    assert both.paired_workers_old.eq(both.paired_workers_new).all()
    assert both.n_paired_old.eq(both.n_paired_new).all()
    for field in ['absolute_mean_gap','mean_absolute_person_delta']:
        assert np.allclose(both[field+'_old'],both[field+'_new'],atol=1e-8,rtol=0)
    save(OUT,'quality_pair_membership_bridge.csv',bridge)
    door=pd.read_csv(OUT/'doorway_relation_coverage.csv')
    physical=door.confirmation.isin(['user_classified_comparable','user_classified_other_scope'])
    save(OUT,'doorway_physical_quality_pairs.csv',door[physical&door.n_common_quality.gt(0)])
    curve=curve_coverage(relations);save(OUT,'actual_18_curve_relation_coverage.csv',curve)
    groups=quality.groupby(['condition','confirmation','user_group_ids'],as_index=False).agg(
        pairs=('image_a','size'), minimum_common=('n_paired','min'), maximum_common=('n_paired','max'),
        mean_gap=('absolute_mean_gap','mean'),mean_person_absolute_delta=('mean_absolute_person_delta','mean'))
    save(OUT,'quality_by_user_group.csv',groups)
    main_quality=quality[quality.confirmation.eq('user_classified_comparable')&quality.n_paired.ge(4)]
    save(OUT,'quality_main_ge4_by_user_group.csv',main_quality.groupby('user_group_ids',as_index=False).agg(
        pairs=('image_a','size'),mean_gap=('absolute_mean_gap','mean'),person_gap=('mean_absolute_person_delta','mean')))
    controls=pd.read_csv(OUT/'matched_single_source_controls.csv')
    target=controls[controls.control_images.gt(0)].groupby(['building','condition','metric','target'],as_index=False).agg(
        source_error=('same_room_error','mean'),control_error=('one_control_expected_error','mean'))
    save(OUT,'controls_by_target.csv',target)
    save(OUT,'controls_by_building.csv',target.groupby(['building','condition','metric'],as_index=False).agg(
        targets=('target','size'),source_error=('source_error','mean'),control_error=('control_error','mean')))
    summary=json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
    summary.update(stage='working_user_classification_adopted', relation_version=manifest['version'],
        relation_manifest=(RELATIONS/'CROSS_MODULE_RELATIONS.json').relative_to(ROOT).as_posix(),
        old_40_quality_pairs_retained=len(both), old_40_quality_members_values_unchanged=True,
        new_quality_pair_observations=int(bridge._merge.eq('right_only').sum()),
        quality_pair_counts=quality.groupby(['condition','confirmation']).n_paired.agg(
            pairs='size',common_ge4=lambda x:int((x>=4).sum())).reset_index().to_dict('records'),
        doorway_physical_quality_pairs=int((physical&door.n_common_quality.gt(0)).sum()),
        doorway_scope_comparable_quality_pairs=int(door.quality_comparable.sum()),
        actual_curve_physical_pairs=int(curve.physical_adopted.sum()),
        actual_curve_scope_comparable_pairs=int((curve.physical_adopted&curve.scope_comparable).sum()),
        actual_curve_scope_comparable_quality_curves=int(curve.scope_comparable_quality_curve.sum()),
        relation_stage_inference='working user groups, no new physical room certification; all/other-scope vs comparable layers separate')
    for obsolete in ['old_pair_members_and_values_unchanged','doorway_direct_confirmed_edges','doorway_legal_quality_pairs']:
        summary.pop(obsolete)
    save(OUT,'SUMMARY.json',summary)
    save(OUT,'RELATION_INPUTS.json',manifest)
    contract=json.loads((OUT/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    contract.update(relation_version=manifest['version'],
        relation='all existing reviewed classifications; status never gates; physical/scope/difficulty and score availability separate',
        curves='actual saved subsets only; exact worker sets counted, scene eligibility is not all member/holdout eligibility; no new fusion',
        table_columns={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')})
    save(OUT,'FIELD_CONTRACT.json',contract)
    print(json.dumps({k:summary[k] for k in ['relation_version','old_40_quality_pairs_retained',
        'new_quality_pair_observations','quality_pair_counts','doorway_physical_quality_pairs',
        'doorway_scope_comparable_quality_pairs','actual_curve_physical_pairs','actual_curve_scope_comparable_quality_curves']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
