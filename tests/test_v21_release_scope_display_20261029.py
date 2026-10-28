import json

from tools.thesis_main.analysis.build_v21_results_page_20261029 import OUT, PAGE


def test_snapshot_release_and_scope_are_current():
    source = (PAGE / 'v21-results-data.js').read_text(encoding='utf8')
    snapshot = json.loads(source.removeprefix('window.V21_RESULTS=').strip().removesuffix(';'))
    release = json.loads((OUT / 'RELEASE.json').read_text(encoding='utf8'))
    assert snapshot['release'] == release
    assert release['completion_scope'] == 'original_current_target_263_pools_and_declared_downstream_analyses'
    assert release['other_admitted_spaces']['core_computation_complete'] is True
    assert release['full_mainline_including_other_targets_complete'] is False
    assert snapshot['current']['data_release'] == 'v2'


def test_page_separates_primary_scope_from_unfinished_extension():
    html = (PAGE / 'v21-results.html').read_text(encoding='utf8')
    js = (PAGE / 'v21-results.js').read_text(encoding='utf8')
    assert 'FULL_DELIVERY_REVIEW_20261029.md' in html
    assert '其它目标的难度、DSTRUCT及受影响选队尚未全部接续' in html
    assert '其它合法空间补充已完成核心计算' in js
    assert '原主目标范围的计算和定向检查已完成' in js
    assert '必要计算和定向检查已完成；真实浏览器' not in js
