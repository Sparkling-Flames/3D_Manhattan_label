"""Read-only aggregation of already scored admitted spaces; no fusion or refitting."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'research/data/releases/v2.1'
EXT = RELEASE / 'admitted_space_extension'
OUT = EXT / 'descriptive'
METRICS = ['B8L2', 'D10', 'source_active_time_seconds']


def image_equal(frame, group, metric):
    """Average observations within target, targets within image, then images."""
    data = frame[group + ['image_id', 'reference_id', metric]].dropna(subset=[metric])
    if data.empty:
        return pd.DataFrame(columns=group + [metric, metric + '_records', metric + '_targets', metric + '_images'])
    target = data.groupby(group + ['image_id', 'reference_id'], dropna=False)[metric].mean().reset_index()
    image = target.groupby(group + ['image_id'], dropna=False)[metric].mean().reset_index()
    result = image.groupby(group, dropna=False)[metric].mean().reset_index()
    for suffix, source, column in [('records', data, metric), ('targets', target, metric), ('images', image, metric)]:
        counts = source.groupby(group, dropna=False)[column].size().rename(metric + '_' + suffix).reset_index()
        result = result.merge(counts, on=group, validate='one_to_one')
    return result


def compare(frame, group, metrics):
    keys = frame[group].drop_duplicates()
    for metric in metrics:
        keys = keys.merge(image_equal(frame, group, metric), on=group, how='left', validate='one_to_one')
    return keys


def load_json(path):
    with path.open(encoding='utf8') as f:
        return json.load(f)


def build():
    inventory = pd.DataFrame(load_json(RELEASE / 'quality_inventory.json'))
    added = pd.DataFrame(load_json(EXT / 'ANALYSIS_RECORDS.json'))
    old = inventory[inventory.quality_usable.eq(True)].copy()
    assert len(old) == 8154 and len(added) == 231
    assert old.object_id.is_unique and added.object_id.is_unique
    assert set(old.object_id).isdisjoint(added.object_id)
    assert added.quality_usable.eq(True).all() and added.extension_pool_eligible.eq(True).all()
    assert added.groupby(['condition', 'image_id', 'reference_id']).ngroups == 31
    assert old.reference_id.notna().all() and added.reference_id.notna().all()
    assert old.reference_id.ne('').all() and added.reference_id.ne('').all()
    old['scope'] = 'original'; added['scope'] = 'added'
    all_data = pd.concat([old, added], ignore_index=True)
    for metric in METRICS:
        values = all_data[metric].replace('', float('nan'))
        all_data[metric] = pd.to_numeric(values, errors='raise')
    all_data.loc[all_data.source_active_time_seconds <= 0, 'source_active_time_seconds'] = float('nan')
    assert all_data[all_data.scope.eq('added')][['B8L2', 'D10']].notna().all().all()
    all_data['difficulty_for_target'] = all_data.current_class.where(all_data.scope.eq('original'), '未分级')
    combined = all_data.copy(); combined['scope'] = 'combined'
    stacked = pd.concat([all_data, combined], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    groups = ['scope', 'condition', 'quality_use']
    summary = compare(stacked, groups, ['B8L2', 'D10'])
    summary.to_csv(OUT / 'SUMMARY.csv', index=False, encoding='utf-8-sig')
    person = compare(stacked, groups + ['worker_id'], ['B8L2', 'D10'])
    person.to_csv(OUT / 'PERSONNEL_COMPARISON.csv', index=False, encoding='utf-8-sig')
    person_keys = ['condition', 'quality_use', 'worker_id']
    wide = person.pivot(index=person_keys, columns='scope', values=[
        'B8L2', 'B8L2_records', 'B8L2_targets', 'B8L2_images', 'D10', 'D10_records', 'D10_targets', 'D10_images'])
    wide.columns = [f'{metric}_{scope}' for metric, scope in wide.columns]
    wide = wide.reset_index()
    for metric in ['B8L2', 'D10']:
        wide[metric + '_combined_minus_original'] = wide[metric + '_combined'] - wide[metric + '_original']
    wide.to_csv(OUT / 'PERSONNEL_HISTORY_CHANGE.csv', index=False, encoding='utf-8-sig')
    time = compare(stacked, groups + ['origin', 'time_provenance'], ['source_active_time_seconds'])
    time.to_csv(OUT / 'TIME_BY_SOURCE.csv', index=False, encoding='utf-8-sig')
    person_time = compare(stacked, groups + ['worker_id', 'origin', 'time_provenance'], ['source_active_time_seconds'])
    person_time.to_csv(OUT / 'PERSONNEL_TIME_BY_SOURCE.csv', index=False, encoding='utf-8-sig')
    pool_groups = ['scope', 'condition', 'quality_use', 'image_id', 'image_code', 'building_id',
                   'reference_id', 'reference_version', 'difficulty_for_target']
    pool = all_data.groupby(pool_groups, dropna=False).agg(records=('object_id', 'size'),
        people=('worker_id', 'nunique'), B8L2_mean=('B8L2', 'mean'), B8L2_n=('B8L2', 'count'),
        D10_mean=('D10', 'mean'), D10_n=('D10', 'count'),
        time_n=('source_active_time_seconds', 'count')).reset_index()
    pool.to_csv(OUT / 'POOL_SUMMARY.csv', index=False, encoding='utf-8-sig')
    pool_time = all_data.groupby(pool_groups + ['origin', 'time_provenance'], dropna=False).agg(
        records=('object_id', 'size'), time_n=('source_active_time_seconds', 'count'),
        time_mean=('source_active_time_seconds', 'mean')).reset_index()
    pool_time.to_csv(OUT / 'POOL_TIME_BY_SOURCE.csv', index=False, encoding='utf-8-sig')

    condition = pd.read_csv(RELEASE / 'condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz', low_memory=False)
    behavior = pd.read_csv(RELEASE / 'joint_history_classification/BEHAVIOR_RECORDS.csv.gz', low_memory=False)
    assert condition.object_id.is_unique and behavior.object_id.is_unique
    assert not condition.object_id.isin(added.object_id).any()
    coverage = added[['object_id', 'condition', 'image_code', 'worker_id', 'reference_id']].merge(
        behavior[['object_id', 'layer', 'behavior_usable', 'primary_expression', 'personal_comparison',
                  'quality_usable', 'turn_history', 'short_history', 'B8L2_peer_delta', 'log_time_peer_delta']],
        on='object_id', how='left', validate='one_to_one', indicator=True)
    assert coverage._merge.eq('both').all()
    coverage['condition_input_present'] = coverage.object_id.isin(condition.object_id)
    coverage['v3_behavior_training_eligible'] = coverage.behavior_usable.eq(True) & coverage.layer.eq('ordinary')
    coverage['v3_q_history_value_present'] = coverage.B8L2_peer_delta.notna()
    coverage['v3_time_history_value_present'] = coverage.v3_behavior_training_eligible & coverage.log_time_peer_delta.notna()
    coverage.drop(columns='_merge').to_csv(OUT / 'TRAINING_RECORD_IMPACT.csv', index=False, encoding='utf-8-sig')
    fields = ['condition_input_present', 'v3_behavior_training_eligible', 'v3_q_history_value_present',
              'v3_time_history_value_present']
    coverage.groupby('condition')[fields].sum().reset_index().to_csv(OUT / 'TRAINING_COVERAGE.csv', index=False, encoding='utf-8-sig')
    checks = dict(old_records=len(old), added_records=len(added), combined_records=len(all_data),
                  added_pools=31, old_added_object_overlap=0, original_inventory_unchanged=True,
                  time_source_policy='origin and time_provenance reported separately',
                  aggregate='within target then targets per image then images, separately for every metric',
                  current_target_difficulty_applied_to_added=False, fusion_run=False, classification_refit=False)
    (OUT / 'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    build()
