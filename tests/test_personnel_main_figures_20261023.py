"""展示资产的语义连接：名单阶段、失败分母与指标提示不能在接入时丢失。"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/workers/personnel_main_figures_v2_20261023'


def test_exchange_diagram_allows_mixed_replacement_blocks(monkeypatch):
    from tools.thesis_main.analysis import build_personnel_main_figures_20261023 as builder
    labels = []

    def capture(fig, *args, **kwargs):
        labels.extend(text.get_text() for ax in fig.axes for text in ax.texts)
        builder.plt.close(fig)

    monkeypatch.setattr(builder, 'finish', capture)
    builder.exchange_design()
    assert 'Y：同构成\n其他成员' in labels
    assert 'Z：不同构成\n替换成员' in labels
    assert any('X/Y/Z均可包含多个类别' in label for label in labels)


def test_figure_and_hint_contract():
    manifest = json.loads((BASE / 'FIGURE_MANIFEST.json').read_text(encoding='utf-8'))
    glossary = json.loads((BASE / 'GLOSSARY.json').read_text(encoding='utf-8'))
    interface = json.loads((BASE / 'CONSUMER_INTERFACE.json').read_text(encoding='utf-8'))
    terms = {t['id']: t for t in glossary['terms']}
    assert len(terms) == len(glossary['terms'])
    assert len(manifest['figures']) == 18
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


def test_natural_population_plot_preserves_single_baseline_and_unrun_gap(monkeypatch):
    import numpy as np
    from tools.thesis_main.analysis import build_personnel_main_figures_20261023 as builder
    lines = []

    def capture(fig, fid, *args, **kwargs):
        if fid == 'F5_natural':
            lines.extend((line.get_xdata(), line.get_ydata()) for ax in fig.axes[:5] for line in ax.lines)
        builder.plt.close(fig)

    monkeypatch.setattr(builder, 'finish', capture)
    monkeypatch.setattr(builder, 'export_data', lambda *args: None)
    builder.late_population_figures()
    assert len(lines) == 15
    for x, y in lines:
        assert np.isfinite(y[np.asarray(x) == 1]).all()
        assert np.isnan(y[np.asarray(x) == 2]).all()
        assert np.isfinite(y[np.asarray(x) >= 3]).any()


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


def test_ordinary_classification_sources_are_in_the_display_contract():
    interface = json.loads((BASE / 'CONSUMER_INTERFACE.json').read_text(encoding='utf-8'))
    specs = {s['id']: s for s in interface['tables']}
    for name, count in {
        'CLASSIFICATION_METHOD_COVERAGE': 11,
        'MIXTURE_ALL_MANUAL': 10094, 'MIXTURE_ALL_SEMI': 3312,
        'ORDINARY_EXCHANGE_CONDITIONS': 18, 'ORDINARY_STRICT_CONDITIONS': 85,
        'ORDINARY_DIRECT_AC': 461, 'ORDINARY_CONDITION_MEMBERS': 523,
    }.items():
        assert specs[name]['rows'] == count
        assert specs[name]['group'] in {'F1', 'F2', 'F3'}
    selected = pd.read_csv(ROOT / specs['ORDINARY_EXCHANGE_CONDITIONS']['path'])
    full = pd.read_csv(ROOT / specs['ORDINARY_STRICT_CONDITIONS']['path'])
    joined = selected.merge(full, left_on='精确条件键', right_on='condition_id', validate='many_to_one')
    ordinary = joined[joined['难度'].eq('全部当前难度')]
    assert (ordinary['C减B_Q'] - ordinary.net_B8L2).abs().max() < 1e-10
    assert ordinary['净Q可评图'].eq(ordinary.image_net_B8L2_known).all()
    # 难度条件共享总体键，页面不能据键把总体22图当成困难9图的支持。
    hard = joined[joined['编号'].eq('D01')].iloc[0]
    assert hard['净Q可评图'] == 9 and hard.image_net_B8L2_known == 22


def test_exchange_plot_keeps_saved_replacement_sizes(monkeypatch):
    from tools.thesis_main.analysis import build_personnel_main_figures_20261023 as builder
    labels = []

    def capture(fig, fid, *args, **kwargs):
        if fid == 'F3_general_magnitude':
            labels.extend(t.get_text() for ax in fig.axes for t in ax.get_yticklabels())
        builder.plt.close(fig)

    monkeypatch.setattr(builder, 'finish', capture)
    monkeypatch.setattr(builder, 'export_data', lambda *args: None)
    builder.exchange()
    assert len(labels) == 12
    assert any('m=3' in x for x in labels)
    assert any('m=6' in x for x in labels)
    assert sum('固定父类改细配比' in x for x in labels) == 3
