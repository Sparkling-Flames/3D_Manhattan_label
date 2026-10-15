"""独立复算持久化统计的关键分母与分布，不重评分或重建数据。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .descriptive_statistics_20261015 import DEFAULT_OUT


def check_summary(records, summary):
    """从逐条值直接复算；不调用原describe，避免重复同一个实现错误。"""
    for _, row in summary.iterrows():
        panel = row['panel']
        if panel.startswith('inventory_'):
            cell = records
        elif panel.startswith('scored_'):
            cell = records[records.WQ.notna()]
        elif panel.startswith('worker_'):
            cell = records[records.in_worker_931]
        elif panel.startswith('target_'):
            cell = records[records.in_target_836]
        else:
            raise ValueError('unknown panel: ' + panel)
        if 'difficulty_class' in row:
            cell = cell[cell.difficulty_class.eq(row.difficulty_class)]
        values = cell[row.metric].dropna().astype(float).to_numpy()
        assert len(cell) == row.n_records, (panel, row.metric, 'n_records')
        assert len(values) == row.n_valid, (panel, row.metric, 'n_valid')
        assert len(cell)-len(values) == row.n_missing, (panel, row.metric, 'n_missing')
        expected = {'mean': np.mean(values) if len(values) else np.nan,
                    'median': np.median(values) if len(values) else np.nan,
                    'sd': np.std(values, ddof=1) if len(values)>1 else np.nan}
        for name, value in expected.items():
            assert np.isclose(value, row[name], rtol=0, atol=1e-7, equal_nan=True), (panel, row.metric, name)
        per_image = cell.dropna(subset=[row.metric]).groupby('image_id')[row.metric].mean()
        assert np.isclose(per_image.mean(), row.image_equal_mean, rtol=0, atol=1e-7,
                          equal_nan=True), (panel, row.metric, 'image_equal_mean')
    return len(summary)


def verify(source_dir):
    source_dir = Path(source_dir)
    contract = json.loads((source_dir/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    records = pd.read_csv(source_dir/'records.csv')
    images = pd.read_csv(source_dir/'images.csv')
    assert records.object_id.is_unique
    assert images.image_id.is_unique
    assert set(records.image_id) == set(images.image_id)
    assert records.difficulty_class.notna().all()
    assert len(records) == contract['panels']['inventory']
    assert records.WQ.notna().sum() == contract['panels']['scores']
    assert records.in_worker_931.sum() == contract['panels']['workers']
    assert records.in_target_836.sum() == contract['panels']['same_target']
    assert records.loc[records.in_target_836, 'in_worker_931'].all()
    assert records.loc[records.time_status.ne('usable'), 'active_time_seconds'].isna().all()
    assert records.loc[records.time_status.eq('usable'), 'active_time_seconds'].gt(0).all()
    checked = sum(check_summary(records, pd.read_csv(source_dir/name))
                  for name in ['overview.csv', 'by_difficulty.csv'])
    for suffix in ['', '_931', '_manual_inventory']:
        relations = pd.read_csv(source_dir/f'same_room_relations{suffix}.csv')
        assert not relations.duplicated(['image_a','image_b']).any()
        assert relations[['building_a','building_b','image_code_a','image_code_b']].notna().all().all()
        pairs = pd.read_csv(source_dir/f'same_room_worker_pairs{suffix}.csv')
        paired = pairs[pairs.paired]
        assert paired[['value_a','value_b']].notna().all().all()
        assert np.allclose(paired.value_b-paired.value_a, paired.delta_b_minus_a, atol=1e-7)
        assert pairs.loc[~pairs.paired, 'delta_b_minus_a'].isna().all()
    result = dict(status='passed', independent_summary_rows=checked,
                  inventory_records=len(records), images=len(images),
                  missing_time_not_imputed=True, same_room_pair_differences_checked=True,
                  rescoring=False, original_source_mutation=False)
    (source_dir/'VERIFICATION_V2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=DEFAULT_OUT)
    print(json.dumps(verify(parser.parse_args().source_dir), ensure_ascii=False))
