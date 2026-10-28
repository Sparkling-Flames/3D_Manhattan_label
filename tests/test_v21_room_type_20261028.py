import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/data/releases/v2.1/room_type_similarity'
BASE=ROOT/'research/statistics/room_type_similarity_20261027'

def test_v21_room_inputs_preserve_exact_identity_and_support():
    a=pd.read_csv(OUT/'inputs/annotations.csv.gz',dtype={'object_id':str},low_memory=False)
    q=pd.DataFrame(json.loads((OUT.parent/'quality_inventory.json').read_text(encoding='utf-8'))).set_index('object_id')
    a=a.set_index('object_id',verify_integrity=True)
    assert set(a.index)==set(q.index)
    assert (a.formal_quality==q.loc[a.index,'quality_usable']).all()
    m=a[(a.condition=='manual')&(a.layer=='ordinary')&a.formal_quality&a.Q.notna()&a.D10.notna()]
    assert not m.duplicated(['image_key','worker_id']).any()
    assert (m.Q-q.loc[m.index,'B8L2']).abs().max()<1e-9
    b=pd.DataFrame(json.loads((OUT.parent/'reference_bindings.json').read_text(encoding='utf-8'))).set_index('object_id')
    assert (m.reference_id==b.loc[m.index,'chosen_target_id']).all()
    assert m.groupby('image_key').reference_id.nunique().eq(1).all()
    images=pd.read_csv(OUT/'inputs/images.csv').set_index('image_key')
    means=m.groupby('image_key').Q.mean()
    assert (means-images.loc[means.index,'mean_Q']).abs().max()<1e-9
    support=pd.read_csv(OUT/'inputs/SUPPORT.csv');assert set(support.image_key)==set(means.index)
    old=pd.read_csv(BASE/'inputs/annotations.csv.gz',low_memory=False)
    previous=set(old.loc[(old.condition=='manual')&(old.layer=='ordinary')&old.formal_quality&old.Q.notna()&old.D10.notna(),'image_key'])
    assert set(support.loc[support.support=='original_support','image_key'])==set(means.index)&previous
    assert set(support.loc[support.support=='new_support','image_key'])==set(means.index)-previous


def test_personal_oof_and_protected_baselines():
    checks=json.loads((OUT/'results/protected/CHECKS.json').read_text(encoding='utf-8'))
    assert all(r['baseline_max_abs_difference']<1e-10 for r in checks['baseline_checks'])
    summary=pd.read_csv(OUT/'results/protected/SUMMARY.csv')
    assert set(summary.support)=={'all','recorded_multibuilding'}
    assert (summary.mae_gain_boot_lo<=summary.mae_gain_boot_hi).all()
    for metric in ['Q','D10','annotation_turn5']:
        p=pd.read_csv(OUT/f'results/personal/OOF_{metric}.csv.gz',dtype={'object_id':str},low_memory=False)
        assert not p.duplicated(['object_id','method']).any()
        assert p.groupby('method').object_id.nunique().nunique()==1
        folds=pd.read_csv(OUT/f'results/personal/FOLDS_{metric}.csv')
        assert all(row.held_out_building not in row.train_building_ids.split('|') for row in folds.itertuples())


def test_image_prediction_cover_and_excludes_target_building():
    p=pd.read_csv(OUT/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz')
    support=pd.read_csv(OUT/'inputs/SUPPORT.csv')
    assert not p.duplicated(['metric','method','image_key']).any()
    assert all(set(g.image_key)==set(support.image_key) for _,g in p.groupby(['metric','method']))
    images=pd.read_csv(OUT/'inputs/images.csv').set_index('image_key')
    for metric,col in [('Q','mean_Q'),('D10','mean_D10')]:
        z=p[(p.metric==metric)&(p.method=='training_mean')].set_index('image_key')
        assert (z.actual-images.loc[z.index,col]).abs().max()<1e-9
    folds=pd.read_csv(OUT/'results/image/LOBO_MODELS.csv')
    assert all(row.held_out_building not in row.train_buildings.split('|') for row in folds.itertuples())


def test_matched_three_image_support():
    base=OUT/'results/image'
    coverage=pd.read_csv(base/'MATCHING_COVERAGE.csv')
    assert set(coverage.regime)=={'source_building','source_building_difficulty','source_building_difficulty_geometry'}
    assert (coverage.common_people_min>=3).all()
    intervals=pd.read_csv(base/'MATCHED_BUILDING_INTERVALS.csv')
    assert (intervals.valid_replicates==2000).all()
    assert (intervals.p025<=intervals.p975).all()
