"""固定当前 DSTRUCT 的同一 ABC，将楼外纯几何 RFUSE 标签接到每位成员。"""
from pathlib import Path
from collections import Counter
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'current_exchange_results/confirm'
METHODS = ['RFUSE_GEOM_K2', 'RFUSE_GEOM_K3']
METRICS = ['B8L2', 'D10', 'geometry_bev_distance', 'geometry_pair_angle',
           'geometry_bottom_angle', 'geometry_top_angle']
OUTCOMES = [f'{m}_{s}' for m in METRICS for s in ['within', 'cross', 'gap']]
IDENTITY = ['event_id', 'pool_id', 'image', 'building', 'phase', 'method',
            'source_class', 'target_class', 'n', 'm', 'block_id',
            'background_id', 'background_target_n', 'D', 'X', 'Y', 'Z']


def image_means(d, cols):
    direction = ['pool_id', 'image', 'building', 'source_class', 'target_class']
    q = d.groupby(direction + ['block_id', 'background_target_n'], dropna=False)[cols].mean().reset_index()
    q = q.groupby(direction + ['block_id'], dropna=False)[cols].mean().reset_index()
    q = q.groupby(direction, dropna=False)[cols].mean().reset_index()
    return q.groupby(['pool_id', 'image', 'building'], dropna=False)[cols].mean().reset_index()


def main():
    events = pd.read_csv(BASE / 'EVENT_METRICS.csv.gz', low_memory=False)
    events = events[(events.method == 'DSTRUCT_K3') & (events.n == 18) &
                    (events.m == 7) & (events.phase == 'selection_heldout_building')]
    roles = pd.read_csv(BASE / 'combined/summary/FOLD_CLASS_ROLE_MAP.csv')
    roles = roles[roles.method == 'DSTRUCT_K3']
    for flag, field in [('largest_class', 'source_class'), ('highest_turn', 'target_class')]:
        chosen = roles[roles[flag].eq(True)][['heldout_building', 'class_id']].rename(
            columns={'heldout_building': 'building', 'class_id': field})
        events = events.merge(chosen, on=['building', field], validate='many_to_one')
    assert events.event_id.is_unique and len(events) == 286
    assert events.image.nunique() == 33 and events.building.nunique() == 9
    labels = pd.read_csv(ROOT / 'fusion_role_classification/LABELS_ALL_LOBO.csv.gz')
    all_events, all_images, people, groups, correlations = [], [], [], [], []
    for method in METHODS:
        lm = labels[labels.method == method].set_index(['heldout_building', 'worker_id'])
        assert lm.index.is_unique
        q = events[IDENTITY + OUTCOMES].copy()
        mapped = []
        for row in q.itertuples(index=False):
            counts = {}
            for block in ['D', 'X', 'Y', 'Z']:
                workers = getattr(row, block).split('|')
                assert len(workers) == (11 if block == 'D' else 7)
                counts[block] = Counter()
                for worker in workers:
                    label = lm.loc[(row.building, worker)]
                    if block != 'D':
                        assert label['known'] == True and label.class_id != 'unknown'
                    counts[block][label.class_id] += 1
                    people.append(dict(event_id=row.event_id, image=row.image,
                        building=row.building, rfuse_method=method, block=block,
                        worker_id=worker, heldout_building=row.building,
                        rfuse_class=label.class_id, known=bool(label['known'])))
            def distance(a, b):
                return sum(abs(counts[a][c] - counts[b][c])
                           for c in counts[a].keys() | counts[b].keys()) / 2
            within = distance('X', 'Y')
            cross = (distance('X', 'Z') + distance('Y', 'Z')) / 2
            mapped.append(dict(rfuse_within_seats=within, rfuse_cross_seats=cross,
                rfuse_gap_seats=cross-within, rfuse_within_changed=float(within > 0),
                **{f'{b}_rfuse_counts': json.dumps(counts[b], sort_keys=True) for b in counts}))
        q = pd.concat([q.reset_index(drop=True), pd.DataFrame(mapped)], axis=1)
        q['rfuse_method'] = method
        all_events.append(q)
        cols = OUTCOMES + ['rfuse_within_seats', 'rfuse_cross_seats', 'rfuse_gap_seats', 'rfuse_within_changed']
        im = image_means(q, cols)
        im['rfuse_method'] = method
        im['Q_gap_group'] = np.where(im.B8L2_gap < -1e-9, 'negative_Q_gap', 'positive_Q_gap')
        assert (im.B8L2_gap < 0).sum() == 7
        all_images.append(im)
        for group, g in im.groupby('Q_gap_group'):
            row = dict(rfuse_method=method, Q_gap_group=group, images=len(g), buildings=g.building.nunique())
            row.update(g[cols].mean().to_dict())
            row.update({f'{c}_valid_images': int(g[c].notna().sum()) for c in OUTCOMES})
            groups.append(row)
        for distance_suffix in ['within', 'cross', 'gap']:
            x = im[f'rfuse_{distance_suffix}_seats']
            for metric in METRICS:
                y = im[f'{metric}_{distance_suffix}']; ok = x.notna() & y.notna()
                rho = spearmanr(x[ok], y[ok]).statistic if x[ok].nunique() > 1 and y[ok].nunique() > 1 else np.nan
                correlations.append(dict(rfuse_method=method, comparison=distance_suffix,
                    outcome=metric, images=int(ok.sum()), buildings=im.loc[ok, 'building'].nunique(),
                    spearman_rho=rho, inference='descriptive_image_level_no_independence_claim'))
    for name, frame in [('SAME_ABC_RFUSE_EVENTS.csv.gz', pd.concat(all_events)),
                        ('SAME_ABC_WORKER_LABELS.csv.gz', pd.DataFrame(people)),
                        ('SAME_ABC_IMAGE_RESULTS.csv', pd.concat(all_images)),
                        ('Q_SIGN_GROUP_DESCRIPTIVE.csv', pd.DataFrame(groups)),
                        ('IMAGE_LEVEL_ASSOCIATIONS.csv', pd.DataFrame(correlations))]:
        frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')
    im = all_images[0]
    check = dict(events=286, images=33, buildings=9, Q_valid_events=int(events.B8L2_gap.notna().sum()),
                 Q_negative_images=7, Q_positive_images=26,
                 positive_images={m: int(im[f'{m}_gap'].gt(1e-9).sum()) for m in METRICS},
                 worker_label_rows=len(people), unknown_label_rows=sum(not x['known'] for x in people),
                 unknown_replacement_label_rows=sum(not x['known'] and x['block'] != 'D' for x in people),
                 wrong_fold_labels=0,
                 reused_same_ABC=True, new_fit=False, new_fusion=False, new_score=False)
    assert check['positive_images']['B8L2'] == 26
    (OUT / 'SAME_TEAM_CHECKS.json').write_text(json.dumps(check, indent=2), encoding='utf-8')
    print(json.dumps(check, ensure_ascii=False))


if __name__ == '__main__':
    main()
