"""沿用原RFUSE的24条自然路径与嵌套楼外模型，接入更新评分和新增空间。"""
import argparse
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .prepare_v21_natural_inputs_20261028 import TARGET as INPUT

SOURCE = ROOT / 'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse'
TARGET = OUT / 'fusion_role_classification'


def modules():
    sys.path.insert(0, str(SOURCE / 'code'))
    import prepare_natural_training as prep
    import learn_natural_fusion_roles as core
    return prep, core


def prepare():
    prep, _ = modules()
    old = pd.read_csv(SOURCE / 'inputs/NATURAL_TRAINING_ENDPOINTS.csv.gz', low_memory=False)
    old['support_origin'] = 'original_pool'
    changed = {r['pool_id'] for r in read(OUT / 'pools/DEPENDENCIES.json') if r['action'] == 'reuse_geometry_rescore'}
    for pid in sorted(changed & set(old.pool_id)):
        d = pd.read_csv(INPUT / (pid + '.csv.gz'), low_memory=False).drop_duplicates('team_key').set_index('team_key')
        mask = old.pool_id.eq(pid); keys = old.loc[mask, 'team_key']
        assert keys.isin(d.index).all()
        for c in ['B8L2', 'D10', 'IoU3D100', 'boundary_loss', 'direction_loss', 'height_loss',
                  'score_available', 'score_status', 'difficulty']:
            old.loc[mask, c] = keys.map(d[c]).to_numpy()
        old.loc[mask, 'iou2d100'] = keys.map(d.iou_2d).to_numpy() * 100
    additions = []
    pools = {p['pool_id']: p for p in read(OUT / 'pools/INPUT_SNAPSHOT.json')['images']}
    expected = {r['pool_id'] for r in read(OUT / 'pools/DEPENDENCIES.json')
                if r['action'] == 'new_or_changed_pool' and r['layer'] == 'ordinary_manual'}
    for pid in sorted(expected):
        assert (INPUT / (pid + '.csv.gz')).exists(), ('New pool prefixes still pending', pid)
        d = pd.read_csv(INPUT / (pid + '.csv.gz'), low_memory=False)
        d = d[d.path_index.lt(24) & d.k.isin(prep.NS)].copy()
        if d.empty: continue
        count = d.groupby('team_key').agg(path_occurrences=('path_id', 'size'), natural_path_n=('path_id', 'nunique'))
        d = d.drop_duplicates('team_key').merge(count, on='team_key', validate='one_to_one')
        d['iou2d100'] = 100 * d.iou_2d
        d['log_floor_area'] = np.log(d.floor_area_camera_h2.where(d.floor_area_camera_h2.gt(0)))
        d['log_height_mean'] = np.log(d.height_mean_h.where(d.height_mean_h.gt(0)))
        d['support_origin'] = 'new_pool'; additions.append(d)
    full = pd.concat([old] + additions, ignore_index=True)
    assert full.team_key.is_unique
    full['group_id'] = full.pool_id + '__n' + full.k.astype(str)
    full['group_unique_teams'] = full.groupby('group_id').team_key.transform('size')
    full['complete_model_outputs'] = full[prep.GEOM + prep.QUALITY].notna().all(axis=1)
    full['training_eligible'] = full.complete_model_outputs & full.group_unique_teams.ge(4)
    full['fusion_failure'] = ~full.score_available.astype(bool)
    full['raw_mc_weight'] = full.path_occurrences
    full['data_release'] = 'v2.1'
    TARGET.mkdir(exist_ok=True)
    prep.save_csv(full, TARGET / 'NATURAL_TRAINING_ENDPOINTS.csv.gz')
    (TARGET / 'INPUT_CHECKS.json').write_text(json.dumps(dict(
        rows=len(full), eligible=int(full.training_eligible.sum()), original_rows=len(old),
        added_rows=len(full)-len(old), new_pools_registered=len(expected),
        paths_per_pool=24, team_sizes=prep.NS, weighting='原池沿用原24条；新增池使用已注册256条的前24条',
        no_new_fusion_in_this_stage=True), ensure_ascii=False, indent=2), encoding='utf-8')


def fit():
    prep, core = modules()
    study = core.Study(TARGET / 'NATURAL_TRAINING_ENDPOINTS.csv.gz')
    roster = pd.read_csv(OUT / 'condition_classification/LABELS_ALL_LOBO.csv.gz')[['worker_id', 'origin']].drop_duplicates()
    tables = {key: [] for key in ['LABELS', 'CENTERS', 'REGISTRY', 'SELECTION', 'INNER_ERRORS', 'FEATURES']}; encodings = {}
    for outer in ['ALL'] + study.buildings:
        selected, selection, checks = study.select(outer)
        tables['SELECTION'].append(selection); tables['INNER_ERRORS'].append(checks)
        for family, alpha in selected.items():
            features = study.response_features(outer, alpha); features['family'] = family
            labels, centers, registry, encoding = core.labels_for(features, family, roster)
            labels['underlying_data_version'] = 'v2.1'
            for key, data in [('LABELS', labels), ('CENTERS', centers), ('REGISTRY', registry), ('FEATURES', features)]:
                tables[key].append(data)
            encodings[outer + ':' + family] = encoding
        print('RFUSE', outer, selected, flush=True)
    for key, frames in tables.items():
        prep.save_csv(pd.concat(frames, ignore_index=True), TARGET / (key + '_ALL_LOBO.csv.gz'))
    (TARGET / 'TRANSFORMS.json').write_text(json.dumps(encodings, ensure_ascii=False), encoding='utf-8')
    (TARGET / 'CHECKS.json').write_text(json.dumps(dict(data_release='v2.1', folds=len(study.buildings)+1,
        training_rows=len(study.data), buildings=len(study.buildings), images=study.data.image_id.nunique(),
        target_building_excluded=True, method='原嵌套LOBO多输出ridge、Ward K2/K3，原支持门槛'),
        ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('part', choices=['prepare', 'fit']); args = parser.parse_args()
    prepare() if args.part == 'prepare' else fit()
