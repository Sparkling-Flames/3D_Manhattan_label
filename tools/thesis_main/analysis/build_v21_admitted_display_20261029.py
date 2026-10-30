"""Export completed admitted-space summary for the offline v2.1 page."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/data/releases/v2.1/admitted_space_extension'
TARGET = ROOT / 'research/statistics/research_explorer_v1_r2_20261017/v21-admitted-data.js'


def build():
    contract = json.loads((SOURCE / 'SCOPE_CONTRACT.json').read_text(encoding='utf8'))
    checks = json.loads((SOURCE / 'CURVE_CHECKS.json').read_text(encoding='utf8'))
    assert checks['complete'] and checks['pools'] == contract['pools'] == 31
    assert checks['records'] == contract['admitted_records'] == 231
    data = pd.read_csv(SOURCE / 'SUMMARY.csv')
    selected = data[(data.condition == 'manual') & (data.layer == 'ordinary_manual')
                    & (data.weighting == 'image_equal')
                    & data.support.isin(['original_current_target', 'other_admitted_target', 'combined'])
                    & (((data.panel == 'available_at_k') & data.k.eq(3))
                       | ((data.panel == 'fixed_N_ge_6') & data.k.isin([3, 6])))
                    & data.metric.isin(['Q_mean', 'actual_consensus_failure_rate'])].copy()
    assert len(selected) == 18
    assert not selected.duplicated(['support', 'panel', 'k', 'metric']).any()
    columns = ['support', 'panel', 'k', 'metric', 'estimate', 'pools', 'images', 'eligible_pools', 'missing_pools']
    assert selected[columns].notna().all().all()
    added = selected[(selected.support == 'other_admitted_target') & (selected.panel == 'available_at_k')
                     & (selected.metric == 'Q_mean')].iloc[0]
    assert added.pools == 30 and added.images == 28
    result = {'contract': contract, 'checks': checks, 'rows': selected[columns].to_dict('records')}
    updated = SOURCE / 'image_difficulty_20261030'
    if (updated / 'INPUT_CHECKS.json').exists():
        result['image_difficulty_update'] = json.loads((updated / 'INPUT_CHECKS.json').read_text(encoding='utf8'))
        result['contract']['difficulty'] = 'one confirmed grade per image; target-specific references and scoring remain separate'
        result['image_difficulty_curves'] = json.loads(pd.read_csv(updated / 'CURVES_BY_DIFFICULTY.csv').to_json(orient='records'))
    TARGET.write_text('window.V21_ADMITTED=' + json.dumps(result, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')) + ';\n', encoding='utf8')
    print('18 saved summary rows; original, added and combined remain separate')


if __name__ == '__main__':
    build()
