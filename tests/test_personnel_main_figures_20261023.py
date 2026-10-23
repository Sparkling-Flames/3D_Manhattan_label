"""展示资产的语义连接：名单阶段、失败分母与指标提示不能在接入时丢失。"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/workers/personnel_main_figures_v2_20261023'


def test_figure_and_hint_contract():
    manifest = json.loads((BASE / 'FIGURE_MANIFEST.json').read_text(encoding='utf-8'))
    glossary = json.loads((BASE / 'GLOSSARY.json').read_text(encoding='utf-8'))
    interface = json.loads((BASE / 'CONSUMER_INTERFACE.json').read_text(encoding='utf-8'))
    terms = {t['id']: t for t in glossary['terms']}
    assert len(terms) == len(glossary['terms'])
    assert len(manifest['figures']) == 16
    assert {f['group'] for f in manifest['figures']} == {'F1', 'F2', 'F3', 'F4', 'F5', 'F6'}
    for f in manifest['figures']:
        assert f['data_release'] == 'v2'
        assert set(f['term_ids']) <= terms.keys()
        for field in ('image', 'vector'):
            assert (BASE / f[field]).stat().st_size > 1000
        assert all((ROOT / p).exists() for p in f['source_paths'])
        assert all((BASE / p).exists() for p in f['data_paths'])
    for t in terms.values():
        assert all(t[k] for k in ('short', 'detail', 'unit', 'denominator_or_support', 'avoid_confusion', 'source_paths'))
        assert all((ROOT / p).exists() for p in t['source_paths'])
    for x in interface['tables']:
        d = pd.read_csv(ROOT / x['path'], low_memory=False)
        assert len(d) == x['rows'] and list(d.columns) == x['columns']
    for x in interface['case_assets']:
        assert (ROOT / x['image_path']).exists() and (ROOT / x['details_path']).exists()
    for x in interface['detail_sources']:
        assert (ROOT / x['path']).exists()
    # 页面直接消费的元数据保持中性，历史研究说明不由此追改。
    for obj in [manifest, glossary, interface]:
        assert '导师' not in json.dumps(obj, ensure_ascii=False)


def test_roster_and_configuration_denominators():
    people = pd.read_csv(BASE / 'data/CLASSIFICATION_MEMBERS.csv')
    assert not people.duplicated(['scheme_id', 'worker_id']).any()
    assert people.groupby('scheme_id').size().eq(62).all()
    assert people.groupby('scheme_id')['known'].sum().to_dict() == {
        'manual_structure': 59, 'manual_joint_qt': 57,
        'semi_structure': 59, 'semi_joint_qt': 54,
    }
    cells = pd.read_csv(BASE / 'data/MIXTURE_EXAMPLE_CONFIGURATIONS.csv')
    # 同一7y-21面板分别按结构/联合类解释，不是两批独立团队。
    assert cells.panel_id.nunique() == 6
    assert cells.groupby(['example_id', 'panel_id']).teams.sum().eq(924).all()
    assert (cells.teams == cells.scorable_teams + cells.failed_teams).all()
    failing = cells[cells.example_id.eq('semi_failure')]
    assert failing.failed_teams.sum() == 205
    assert (failing.B8L2_mean > 0).all()
