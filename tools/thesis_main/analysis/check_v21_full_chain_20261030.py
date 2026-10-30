"""在隔离副本重算交付汇总，数值比较原件；不运行新融合或覆盖作者结果。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'research/workers/personnel_full_chain_v21_20261030'
STUDY = ARCHIVE / 'HOHONET_v21_full_chain_20261030'
QT = ARCHIVE / 'common_support/v21_q_qt_common_support_20261030'
OUT = ARCHIVE / 'local_review'


def compare_tables(expected, actual):
    a, b = pd.read_csv(expected, low_memory=False), pd.read_csv(actual, low_memory=False)
    assert list(a.columns) == list(b.columns), (expected, 'columns')
    assert a.shape == b.shape, (expected, a.shape, b.shape)
    largest = 0.0
    for col in a:
        assert a[col].isna().equals(b[col].isna()), (expected, col, 'missing support changed')
        if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]):
            x, y = a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float)
            assert np.allclose(x, y, atol=1e-8, rtol=1e-10, equal_nan=True), (expected, col)
            finite = np.isfinite(x) & np.isfinite(y)
            if finite.any():
                largest = max(largest, float(np.max(np.abs(x[finite] - y[finite]))))
        else:
            assert a[col].fillna('<NA>').equals(b[col].fillna('<NA>')), (expected, col)
    return dict(rows=len(a), columns=len(a.columns), max_absolute_error=largest)


def check_headlines():
    """从下层表独立计算主要口径，尤其是六端共同支持和成本比。"""
    results = {}
    snap = Path('research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')
    assert (STUDY / 'source' / snap).read_bytes() == (ROOT / snap).read_bytes()
    events = Path('research/data/releases/v2.1/final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz')
    assert (STUDY / 'source' / events).read_bytes() == (ROOT / events).read_bytes()
    results['source_identity'] = 'pool snapshot and final main events byte-identical to local repository'
    e = pd.read_csv(STUDY / 'source' / events)
    e = e[e.n.eq(14)].copy()
    good = e[['B8L2_BA', 'B8L2_CA', 'B8L2_CB']].notna().all(axis=1)
    e['GA'] = (e.B8L2_CA.abs() - e.B8L2_BA.abs()).where(good)
    e['GS'] = ((e.B8L2_CA.abs() + e.B8L2_CB.abs()) / 2 - e.B8L2_BA.abs()).where(good)
    levels = ['building', 'image', 'pool_id', 'block_id', 'background_id']
    v = e.groupby(levels)[['GA', 'GS', 'B8L2_CB']].mean()
    for keep in (levels[:-1], levels[:-2], levels[:2]):
        v = v.groupby(level=keep).mean()
    assert len(e) == 197 and v.GS.notna().sum() == 83
    assert (v.GA > 1e-9).sum() == 61 and (v.GS > 1e-9).sum() == 62
    results['half'] = dict(events=len(e), scored_images=int(v.GS.notna().sum()),
                           GA=float(v.GA.mean()), GS=float(v.GS.mean()), CB=float(v.B8L2_CB.mean()))
    ids = pd.read_csv(STUDY / 'stage02_same_room/abc/EVENT_IDENTITIES.csv.gz')
    ids = ids[ids.final_method.eq('TARGET_DSTRUCT_K3') & ids.analysis_scope.eq('ordinary_comparable')
              & ids.condition.eq('manual') & ids.role_direction.eq('2→3')]
    raw = pd.read_csv(STUDY / 'stage02_same_room/EXISTING_VALID_EVENT_SOURCE.csv.gz', low_memory=False)
    for n, count, valid, pairs in [(10, 268, 237, 19), (14, 10, 6, 2)]:
        z = ids[ids.n.eq(n) & ids.m.eq(n/2)].merge(raw, on='event_id', suffixes=('', '_raw'), validate='one_to_one')
        qcols = [f'Q_{arm}_{view}' for view in 'ab' for arm in 'ABC']
        ok = z[qcols].notna().all(axis=1)
        assert len(z) == count and ok.sum() == valid and z.pair_key.nunique() == pairs
        assert np.array_equal(ok, z.Q_common6)
        results[f'same_room_{n}'] = dict(events=count, six_endpoints_scored=valid, pairs=pairs,
                                        distinct_target_blocks=z.Z_members.nunique())
    pred = STUDY / 'stage02_same_room/prediction'
    rel = pd.read_csv(pred / 'v21_all/DIRECT_PAIRS.csv')
    goodrel = rel[rel.metric.eq('B8L2') & rel.condition.eq('manual') & rel.origin.eq('all')
                  & rel.layer.eq('ordinary') & rel.scope_comparable & ~rel.substantive_conflict
                  & ~rel.oos_pending & rel.n_common.ge(4)]
    d = pd.read_csv(pred / 'v21_all/DIRECT_MEAN_VALUES.csv.gz')
    d = d[d.metric.eq('B8L2') & d.pair_id.isin(goodrel.pair_id)].copy()
    for col in ['source_mean', 'external_image_mean']:
        d[col] = (d[col] - d.actual).abs()
    im = d.groupby(['building', 'target_image'])[['source_mean', 'external_image_mean']].mean()
    bu = im.groupby('building').mean()
    assert d.pair_id.nunique() == 128 and len(im) == 65 and len(bu) == 13
    assert np.isclose(bu.source_mean.mean(), 6.463518, atol=1e-6)
    results['same_room_mean'] = dict(pairs=128, images=65, buildings=13, source_mae=bu.source_mean.mean(),
        baseline_mae=bu.external_image_mean.mean(), improved_images=int((im.source_mean < im.external_image_mean).sum()),
        improved_buildings=int((bu.source_mean < bu.external_image_mean).sum()))
    speed = pd.read_csv(STUDY / 'stage03_speed_difficulty/CURRENT_SAME_PEOPLE.csv.gz')
    speed = speed[speed.method.eq('TARGET_DSTRUCT_K3') & speed.condition.eq('manual') & speed.origin.eq('new')]
    results['speed_current'] = {}
    for metric in ['turn_n', 'short_turn_edges', 'B8L2']:
        z = speed[speed.metric.eq(metric)]
        assert len(z) == 105 and np.allclose(z.hard_minus_easy, z.hard_mean-z.easy_mean)
        results['speed_current'][metric] = dict(pairs=len(z), mean=z.hard_minus_easy.mean(), positive=int(z.hard_minus_easy.gt(1e-9).sum()))
    stop = STUDY / 'stage05_selection_stop/stopping'
    d = pd.read_csv(stop / 'source_acquisition_group_actual_m.csv')
    flags = pd.read_csv(stop / 'GROUP_RELATION_FLAGS.csv')
    d = d.merge(flags[['group_id', 'panel', 'any_relation_pending']], on=['group_id', 'panel'], validate='many_to_one')
    z = d[d.panel.eq('whole_group') & d.policy.eq('source_within2_min3_geometry') & d.m.eq(d.N-1)
          & d.activity_all_new_complete & ~d.any_relation_pending]
    assert len(z) == 3 and z.project_ratio_to_fixed7_geometry.gt(1).all()
    ratio = z.groupby('building').project_ratio_to_fixed7_geometry.mean().mean()
    assert np.isclose(ratio, 2.115261, atol=1e-6)
    results['cold_cost'] = dict(groups=3, project_ratio_to_fixed7=ratio, all_groups_above_one=True,
        interpretation='total project labor relative to fixed7; not historical acquisition cost divided by labor saved')
    inp = QT / 'inputs/HOHONET_v21_full_chain_20261030/stage05_selection_stop/selection'
    for name in ['POLICY_EVENT_RESULTS.csv.gz', 'QT_N_SENSITIVITY.csv', 'RELATION_FLAGS.csv']:
        assert (inp/name).read_bytes() == (STUDY/'stage05_selection_stop/selection'/name).read_bytes(), name
    results['common_support_input_identity'] = 'all three inputs byte-identical to Pro delivery'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'HEADLINE_CHECKS.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    return results


def main():
    check_headlines()
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    tasks = [
        ('half', ['scripts/prepare_half_team.py'], ['stage01_half_team/MAIN_CHECKED_SUMMARY.csv']),
        ('same_room_abc', ['scripts/same_room_abc.py'], ['stage02_same_room/abc/SUMMARY.csv']),
        ('same_room_prediction_scope', ['scripts/same_room_scope_finalize.py'], [
            'stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv',
            'stage02_same_room/prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv']),
        ('speed_difficulty', ['scripts/speed_difficulty.py'], [
            'stage03_speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv',
            'stage03_speed_difficulty/V21_FIXED_V2_SAME_PEOPLE_SUMMARY.csv']),
        ('selection_stopping', ['scripts/selection_stop_analyze.py', 'all'], [
            'stage05_selection_stop/selection/POLICY_SUMMARY.csv',
            'stage05_selection_stop/stopping/stopping_summary.csv',
            'stage05_selection_stop/stopping/source_acquisition_summary.csv']),
        ('old_reference_scores', ['scripts/selection_stop_validate.py'], [
            'stage05_selection_stop/validation/ORIGINAL_POLICY_REPRODUCTION.csv',
            'stage05_selection_stop/validation/STOPPING_OLD_SCORE_PARITY.csv.gz']),
    ]
    # Windows sandbox TEMP is too long for the archived source paths.
    with tempfile.TemporaryDirectory(prefix='.v21_check_', dir=ROOT) as td:
        work = Path(td) / 'study'
        shutil.copytree(STUDY, work, ignore=shutil.ignore_patterns('__pycache__'))
        env['MPLCONFIGDIR'] = str(Path(td) / 'mpl')
        env['XDG_CACHE_HOME'] = str(Path(td) / 'cache')
        for label, args, tables in tasks:
            print('START', label, flush=True)
            with (OUT / (label + '.log')).open('w', encoding='utf-8') as log:
                result = subprocess.run([sys.executable, '-B', *args], cwd=work, env=env,
                                        stdout=log, stderr=subprocess.STDOUT)
            item = dict(task=label, returncode=result.returncode, tables={})
            if result.returncode == 0:
                for name in tables:
                    try:
                        item['tables'][name] = compare_tables(STUDY / name, work / name)
                    except (AssertionError, FileNotFoundError) as exc:
                        item['tables'][name] = dict(error=str(exc))
                if label == 'old_reference_scores':
                    receipt = work / 'stage05_selection_stop/validation/NUMERIC_RECONSTRUCTION_CHECKS.json'
                    shutil.copy2(receipt, OUT / 'OLD_REFERENCE_LOCAL_CHECKS.json')
            checks.append(item)
            (OUT / 'RERUN_CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
            print('END', label, json.dumps(item, ensure_ascii=False), flush=True)
        qtout = Path(td) / 'qt_output'
        print('START common_support', flush=True)
        with (OUT / 'common_support.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([sys.executable, '-B', str(QT / 'scripts/analyze_common_support.py'),
                                     '--output', str(qtout)], env=env, stdout=log, stderr=subprocess.STDOUT)
        item = dict(task='common_support', returncode=result.returncode, tables={})
        if result.returncode == 0:
            for name in ['COMMON_SUPPORT_SUMMARY.csv', 'COMMON_CONTEXT_ROSTER.csv',
                         'ADJACENT_SIZE_PAIRED_CHANGES.csv', 'EXPLORATORY_N5_N13_ABSOLUTE_CONTRAST.csv']:
                item['tables'][name] = compare_tables(QT / 'results' / name, qtout / name)
        checks.append(item)
        (OUT / 'RERUN_CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    assert all(c['returncode'] == 0 and all('error' not in t for t in c['tables'].values()) for c in checks), checks
    print('All isolated reruns passed; temporary copy removed.', flush=True)


if __name__ == '__main__':
    main()
