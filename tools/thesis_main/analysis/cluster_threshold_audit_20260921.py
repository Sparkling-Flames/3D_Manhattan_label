"""当前有限人员池的阈值诊断；不选择正式阈值，不改变人员资格。"""
from collections import Counter
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.clustering_release.local_points import partition

ROOT = Path(__file__).resolve().parents[3]
RECEIVED = ROOT / 'analysis_results/panorama_research_received_20260921'
OUT = ROOT / 'analysis_results/worker_cluster_sensitivity_20260921/threshold'
CUTS = (12.8, 6 * 1024 / 360, 25.6, 12 * 1024 / 360, 51.2)


def partition_stats(d, ids, method, cut):
    labels, _ = partition(d, ids, cut, method)
    d = np.round(d, 8)
    sizes = Counter(labels)
    near = d <= cut
    same = labels[:, None] == labels[None, :]
    tri = np.triu_indices(len(ids), 1)
    reasons = Counter(count_unique=0, geometry_isolated=0, partition_isolated=0)
    for i, label in enumerate(labels):
        if sizes[label] != 1:
            continue
        if (d[i] < 1e6).sum() == 1:
            reasons['count_unique'] += 1
        elif near[i].sum() == 1:
            reasons['geometry_isolated'] += 1
        else:
            reasons['partition_isolated'] += 1
    return dict(K=len(sizes), singleton_mass=sum(reasons.values()) / len(ids),
                near_pairs=int(near[tri].sum()), far_pairs=int((~near)[tri].sum()),
                near_split_pairs=int((near & ~same)[tri].sum()),
                far_join_pairs=int((~near & same)[tri].sum()),
                singleton_reasons=dict(reasons))


def main():
    sys.path.insert(0, str(RECEIVED / 'original_package/code'))
    import common as c
    c.configure(RECEIVED / 'local_recompute/source_work')
    _, _, views, _, _ = c.load()
    rows = []
    for v in views.values():
        for cut in CUTS:
            for method in ('complete', 'representative'):
                z = partition_stats(v['d'], v['ids'], method, cut)
                reasons = z.pop('singleton_reasons')
                rows.append(dict(image_id=v['image_id'], code=v['code'], building=v['building'],
                                 N=v['N'], method=method, cut=cut, **z,
                                 **{'singleton_' + k: val for k, val in reasons.items()},
                                 U8=c.next_uncovered(v['d'], 8, cut)))
    frame = pd.DataFrame(rows)
    summaries = []
    for minimum in (1, 8):
        for (method, cut), g in frame[frame.N >= minimum].groupby(['method', 'cut']):
            summaries.append(dict(minimum_N=minimum, method=method, cut=cut, images=len(g),
                responses=int(g.N.sum()), median_K=float(g.K.median()),
                mean_singleton_mass=float(g.singleton_mass.mean()),
                pooled_singleton_mass=float((g.singleton_mass * g.N).sum() / g.N.sum()),
                one_cluster=int((g.K == 1).sum()), at_most_3_clusters=int((g.K <= 3).sum()),
                at_most_3_and_single_mass_le20=int(((g.K <= 3) & (g.singleton_mass <= .2)).sum()),
                mean_U8=float(g.U8.mean()), U8_images=int(g.U8.notna().sum()),
                **{key: int(g[key].sum()) for key in ['near_pairs', 'far_pairs', 'near_split_pairs',
                    'far_join_pairs', 'singleton_count_unique', 'singleton_geometry_isolated',
                    'singleton_partition_isolated']}))
    baseline = pd.read_csv(RECEIVED / 'original_package/results/image_metrics.csv').set_index('image_id')
    for row in frame[frame.cut.isin([12.8, 25.6, 51.2])].itertuples():
        prefix = f'{row.method}_{row.cut:g}'
        assert row.K == baseline.loc[row.image_id, prefix + '_K']
        assert np.isclose(row.singleton_mass, baseline.loc[row.image_id, prefix + '_single_mass'])
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / 'image_thresholds.csv', index=False)
    pd.DataFrame(summaries).to_csv(OUT / 'summary.csv', index=False)
    manifest = dict(images=len(views), responses=sum(v['N'] for v in views.values()), cuts=CUTS,
        baseline_reproduced=True, source=str(c.SOURCE.relative_to(ROOT)),
        unit='1024x512周期横坐标的成对端点最大欧氏距离；点数不同为不相容哨兵',
        selection='复用已有12.8/25.6/51.2和早期6/12度的像素探针；并非优化搜索',
        singleton_reasons='只有自己的点数/有同点数但无近邻/有近邻但被分区孤立，互斥且穷尽；N=1也归只有自己的点数，主要解释N>=8',
        limitations='近邻拆分与远邻同簇是几何定义的代价，不等于人工语义错误率；图均值与作答加权值分列；U8只在N>8有定义。',
        formal_threshold_selected=False, raw_data_changed=False)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    print(pd.DataFrame(summaries).query('minimum_N == 8').to_string(index=False))


if __name__ == '__main__':
    main()
