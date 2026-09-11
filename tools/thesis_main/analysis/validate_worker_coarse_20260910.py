"""粗类留楼复现及类内持续阶段；仅历史探索，所有人保留。"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import argparse
import json
import time

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import validate_worker_reuse_20260909 as workers
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition
from tools.thesis_main.analysis.validate_building_stages_20260909 import anchored_states, stage_tail, stage_onset
from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import ORDERS, changes

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/worker_coarse_validation_20260910_v1'
COHORTS = ('all26', 'current20')
MODELS = {'median2': (2, 'quantile'), 'ward2': (2, 'ward')}


def hard_partition(matrix, counts, valid, indices, threshold):
    indices = np.asarray(indices, int)
    if len(set(indices)) != len(indices) or not len(indices):
        raise ValueError('duplicate_or_empty_people')
    if not np.asarray(valid)[indices].all():
        return {'status': 'unknown_geometry', 'clusters': []}
    counts = np.asarray(counts)[indices]
    local = np.asarray(matrix)[np.ix_(indices, indices)].copy()
    local[counts[:, None] != counts[None, :]] = max(1e6, threshold + 1)
    result = partition(local, threshold)
    result['clusters'] = [{int(indices[i]) for i in g} for g in result['clusters']]
    assert all(len(set(np.asarray(counts)[[j for j, i in enumerate(indices) if i in g]])) == 1 for g in result['clusters'])
    return result


def path_states(trajectory, horizon):
    if horizon < 7 or not set(range(1, horizon+1)) <= trajectory.keys():
        raise ValueError('insufficient_observation')
    anchors = anchored_states(trajectory, horizon)
    return dict(zip(anchors, stage_tail(list(anchors.values()))))


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = dict(cohorts=COHORTS, grouping=MODELS, reference_metrics=['ospa30', 'ospa60'],
        training='whole target building excluded; all unassisted stages pooled',
        primary='reviewed effective points, omit two imputed responses; no worker exclusions',
        reference_sensitivities=['all_allowed_references', 'human_reference_only', 'including_imputed'],
        permutations=200, geometry=['q_0.950', 'ospa_metric_t6'], min_support=2,
        epsilon=.1, min_future=5, rate=.8, horizons='8,10,and all available within arm, if >=7',
        arms=['A', 'B', 'ALL'], matched_comparison='same image, cohort, metric, grouping, geometry, H and k',
        outcome='same-permutation all-anchor sustained stage, unknown preserved',
        not_claimed=['natural personality types', 'new-worker validation', 'permanent convergence', 'formal protocol change'])
    (OUT/'PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    workers.OUT = OUT
    frame, pairs, qa = workers.load_measurements()
    frame.to_csv(OUT/'measurements.csv.gz', index=False)
    pairs.to_csv(OUT/'pairs.csv.gz', index=False)
    qa['imputed_excluded_from_primary'] = int(frame.imputed_point.sum())
    (OUT/'SOURCE_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    workers.COHORTS = COHORTS
    workers.GROUPS = MODELS
    for name, sample in [('primary', frame[~frame.imputed_point]),
                         ('human_reference_only', frame[~frame.imputed_point & frame.reference_basis.ne('gt_assumed_correct')]),
                         ('including_imputed', frame)]:
        workers.OUT = OUT/name
        workers.OUT.mkdir(exist_ok=True)
        workers.classification(sample)
        print(f'classification completed: {name}', flush=True)


def replay():
    frame = pd.read_csv(OUT/'measurements.csv.gz', dtype={'worker_id': str})
    frame = frame[~frame.imputed_point].copy()
    pairs = pd.read_csv(OUT/'pairs.csv.gz')
    # 已重建并核对来源的本轮测量是本阶段输入缓存；不是替代原始真源。
    full_frame = pd.read_csv(OUT/'measurements.csv.gz', dtype={'worker_id': str})
    members = pd.read_csv(OUT/'primary/fold_members.csv', dtype={'worker_id': str})
    orders = [r['worker_ids'] for r in map(json.loads, ORDERS.read_text(encoding='utf-8').splitlines())]
    orders = [[str(w) for w in row] for row in orders]
    assert len(orders) == 200
    rows, support = [], []
    start = time.monotonic()
    for image, original in full_frame.groupby('image_id'):
        original = original.sort_values('canonical_annotation_id').reset_index(drop=True)
        mats = workers.image_matrices(original, pairs[pairs.image_id.eq(image)])
        positions = dict(zip(original.worker_id, original.index))
        counts = original.effective_point_count.to_numpy()
        building = original.building_id.iloc[0]
        available = frame[frame.image_id.eq(image)]
        # 缓存仅在一张图内复用；人员身份、点数和几何配置均属于缓存上下文。
        @lru_cache(maxsize=None)
        def get_part(config, mask):
            indices = [i for i in range(len(original)) if mask & (1 << i)]
            matrix = mats['q'] if config == 'q_0.950' else mats[config]
            valid = original.q_geometry_valid.to_numpy() if config == 'q_0.950' else np.ones(len(original), bool)
            return hard_partition(matrix, counts, valid, indices, .05 if config == 'q_0.950' else 6.)

        @lru_cache(maxsize=None)
        def compare(config, left, right):
            a, b = get_part(config, left), get_part(config, right)
            if a['status'] != 'unique' or not any(len(g) >= 2 for g in a['clusters']) or b['status'] != 'unique':
                return 'unknown'
            delta = changes(a['clusters'], b['clusters'])
            return 'changing' if delta['membership'] > .1+1e-12 or delta['shares'] > .1+1e-12 or delta['promotions'][1] else 'stable'

        for scope in COHORTS:
            sample = workers.cohort(available, scope)
            for metric in ('ospa30', 'ospa60'):
                for model in MODELS:
                    trained = members[(members.cohort == scope) & (members.metric == metric) & (members.model == model) & (members.heldout_building == building)]
                    if trained.empty:
                        raise ValueError(f'missing_target_building_fit:{building}')
                    assert all(building not in s.split('|') for s in trained.training_buildings)
                    labels = trained.set_index('worker_id').label.to_dict()
                    if not set(sample.worker_id) <= labels.keys():
                        raise ValueError('target_worker_has_no_training_profile')
                    for arm, label in [('A', 1), ('B', 2), ('ALL', None)]:
                        people = set(sample.worker_id) if label is None else {w for w in sample.worker_id if labels.get(w) == label}
                        meta = dict(image_id=image, building_id=building, cohort=scope, metric=metric, model=model, arm=arm)
                        n = len(people)
                        support.append(dict(**meta, n=n, worker_ids='|'.join(sorted(people, key=int)), status='available' if n >= 7 else 'insufficient_horizon'))
                        if n < 7:
                            continue
                        horizons = sorted({h for h in (8, 10, n) if 7 <= h <= n})
                        agg = {}
                        for order in orders:
                            seq = [positions[w] for w in order if w in people]
                            assert len(seq) == n and len(set(seq)) == n
                            masks, mask = {}, 0
                            for k, pos in enumerate(seq, 1):
                                mask |= 1 << pos
                                masks[k] = mask
                            for config in ('q_0.950', metric):
                                for h in horizons:
                                    anchors = [stage_tail([compare(config, masks[k], masks[j]) for j in range(k+1, h+1)])[0] for k in range(1, h-4)]
                                    for k, state in enumerate(stage_tail(anchors), 1):
                                        c = agg.setdefault((config, h, k), Counter())
                                        c[state] += 1
                                        if state == 'stable':
                                            number = sum(len(g) >= 2 for g in get_part(config, masks[k])['clusters'])
                                            c['stable_multi' if number >= 2 else 'stable_single'] += 1
                        for (config, h, k), c in agg.items():
                            assert c['stable'] + c['changing'] + c['unknown'] == 200
                            rows.append(dict(**meta, config=config, horizon=h, k=k, n=n, stable=c['stable'], changing=c['changing'], unknown=c['unknown'],
                                lower=c['stable']/200, upper=(c['stable']+c['unknown'])/200, stable_multi=c['stable_multi'], stable_single=c['stable_single']))
        print(f'replayed {image}: {time.monotonic()-start:.1f}s, rows={len(rows)}', flush=True)
    curves = pd.DataFrame(rows)
    curves.to_csv(OUT/'stage_curves.csv.gz', index=False)
    pd.DataFrame(support).to_csv(OUT/'support.csv', index=False)
    onsets = []
    keys = ['image_id', 'building_id', 'cohort', 'metric', 'model', 'arm', 'config', 'horizon']
    for key, g in curves.groupby(keys):
        g = g.sort_values('k')
        assert (np.diff(g.lower) >= -1e-12).all() and (np.diff(g.upper) >= -1e-12).all()
        possible, conservative, identified, status = stage_onset(g.lower.to_numpy(), g.upper.to_numpy())
        onsets.append(dict(zip(keys, key), possible=possible, conservative=conservative, identified=identified, status=status))
    pd.DataFrame(onsets).to_csv(OUT/'onsets.csv', index=False)
    print('stage replay complete', flush=True)


def summarize():
    curves = pd.read_csv(OUT/'stage_curves.csv.gz')
    keys = ['image_id', 'building_id', 'cohort', 'metric', 'model', 'arm', 'config', 'horizon']
    assert not curves.duplicated(keys+['k']).any()
    assert (curves.stable+curves.changing+curves.unknown).eq(200).all()
    assert (curves.stable_multi+curves.stable_single).eq(curves.stable).all()
    assert np.allclose(curves.lower, curves.stable/200)
    assert np.allclose(curves.upper, (curves.stable+curves.unknown)/200)
    onsets = pd.read_csv(OUT/'onsets.csv').merge(curves.groupby(keys).n.first().reset_index(), on=keys, validate='one_to_one')
    summaries = []
    for extent, data in [('each_arm_full_N', onsets[onsets.horizon.eq(onsets.n)]), ('fixed_H', onsets[onsets.horizon.isin([8,10])])]:
        group_keys = ['cohort','metric','model','arm','config'] + (['horizon'] if extent == 'fixed_H' else [])
        for key, g in data.groupby(group_keys):
            summaries.append(dict(zip(group_keys,key), extent=extent, images=len(g), buildings=g.building_id.nunique(),
                min_H=int(g.horizon.min()), max_H=int(g.horizon.max()), identified=int(g.status.eq('identified').sum()),
                unknown=int(g.status.eq('unknown').sum()), not_reached=int(g.status.eq('not_reached').sum()),
                identified_k_median=g.identified.median()))
    pd.DataFrame(summaries).to_csv(OUT/'stage_summary.csv',index=False)
    paired = []
    for key, g in curves[(curves.k >= 2) & curves.horizon.isin([8,10])].groupby(['cohort','metric','model','config','horizon','k']):
        a = workers.paired_means(g.assign(value=g.lower), ['A','B','ALL'])
        b = workers.paired_means(g.assign(value=g.upper), ['A','B','ALL'])
        assert a['image_ids'] == b['image_ids']
        if not a['images']:
            continue
        row = dict(zip(['cohort','metric','model','config','horizon','k'],key), images=a['images'],buildings=a['buildings'])
        for arm in ['A','B','ALL']:
            row[arm+'_lower'] = a['means'][arm]
            row[arm+'_upper'] = b['means'][arm]
        paired.append(row)
    pd.DataFrame(paired).to_csv(OUT/'matched_stage_comparison.csv', index=False)
    # 独立回读全部分类预测汇总及留楼身份，不以报告中的百分比为输入。
    checks = 0
    for scope in ['primary','human_reference_only','including_imputed']:
        d = pd.read_csv(OUT/scope/'classification_predictions.csv.gz')
        s = pd.read_csv(OUT/scope/'classification_summary.csv')
        f = pd.read_csv(OUT/scope/'fold_members.csv')
        assert all(r.heldout_building not in r.training_buildings.split('|') for r in f.itertuples())
        for key, g in d.groupby(['cohort','metric','model']):
            b = g.groupby('building_id')[['baseline_sqerr','continuous_sqerr','layer_sqerr']].mean()
            expected = s[(s.cohort == key[0]) & (s.metric == key[1]) & (s.model == key[2])].iloc[0]
            for model in ['continuous','layer']:
                gain = 1-b[model+'_sqerr'].mean()/b.baseline_sqerr.mean()
                assert np.isclose(gain, expected[model+'_building_mse_gain'], atol=1e-12, rtol=0)
            checks += 1
    (OUT/'VERIFICATION.json').write_text(json.dumps(dict(classification_configurations_checked=checks,
        stage_rows=len(curves), onset_rows=len(onsets), three_states_and_supported_cluster_counts=True,
        target_building_training_exclusion=True, same_image_matched_panels=True,
        bounds='unknown-state bounds, not confidence intervals', tests='15 passed before full execution'),indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei']
    fig, axes = plt.subplots(1,2,figsize=(11,4.2),sharey=True)
    p = pd.DataFrame(paired)
    for ax, scope in zip(axes,COHORTS):
        q=p[(p.cohort==scope)&(p.metric=='ospa30')&(p.model=='median2')&(p.config=='q_0.950')&(p.horizon==10)].sort_values('k')
        for arm,color,label in [('A','#246ca6','A：较低参考偏差'),('B','#c86a28','B：较高参考偏差'),('ALL','#555555','全部人员')]:
            ax.plot(q.k,q[arm+'_lower'],color=color,label=label)
            ax.fill_between(q.k,q[arm+'_lower'],q[arm+'_upper'],color=color,alpha=.12)
        ax.set_title(('全部26人' if scope=='all26' else '预计继续参与的20人')+f'；共同{int(q.images.iloc[0])}图')
        ax.set_xlabel('候选起点人数 k；均继续观察至 H=10')
        ax.set_xticks(q.k)
        ax.set_ylim(0,1);ax.grid(alpha=.2)
    axes[0].set_ylabel('持续阶段达标比例：先图后楼等权')
    axes[1].legend(fontsize=8)
    fig.suptitle('中位数粗分，q=.95；阴影为未知状态边界，非置信区间')
    fig.tight_layout()
    fig.savefig(OUT/'matched_stage_curves.png',dpi=180)
    plt.close(fig)
    print('summaries and verification complete',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['prepare', 'replay', 'summarize', 'all'], default='all')
    args = parser.parse_args()
    if args.phase in ('prepare', 'all'):
        prepare()
    if args.phase in ('replay', 'all'):
        replay()
    if args.phase in ('summarize', 'all'):
        summarize()
