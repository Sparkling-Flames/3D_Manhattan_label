"""人数与构成研究的纯数值计算；不读取文件、不加载几何或绘图依赖。"""

from collections import defaultdict

import numpy as np


FIELDS = ('omission_ref', 'extension_ref', 'ref_symdiff_ref', 'member_symdiff_union',
          'squared_bias_union', 'add_one_symdiff_union', 'next_person_loss_union', 'higher_fraction')


def fit_labels(rows, workers, target_building):
    train = [r for r in rows if r['building'] != target_building]
    scores = np.array([[float(r[w]) for w in workers] for r in train]).mean(axis=0)
    ordered = np.sort(scores)
    mid = len(workers)//2
    if np.isclose(ordered[mid-1], ordered[mid], rtol=0, atol=1e-12):
        raise ValueError('calibration_cutoff_tie')
    return dict(zip(workers, (scores > np.median(scores)).tolist())), [r['image'] for r in train]


def feasible_compositions(higher_n, lower_n, k):
    low, high = max(0, k-lower_n), min(k, higher_n)
    return dict(lower_rich=low, balanced=min(high, max(low, k//2)), higher_rich=high)


def area_summary(area, inside, reference_area, q):
    omission = float(reference_area - inside @ q)
    extension = float((area-inside) @ q)
    variance = float(area @ (q*(1-q)))
    union = float(area.sum())
    return dict(omission_h2=omission, extension_h2=extension,
                ref_symdiff_h2=omission+extension, member_symdiff_h2=2*variance,
                omission_ref=omission/reference_area, extension_ref=extension/reference_area,
                ref_symdiff_ref=(omission+extension)/reference_area,
                member_symdiff_union=2*variance/union,
                squared_bias_union=(omission+extension-variance)/union)


def summarize(rows, panels):
    output = []
    for panel, (images, limit) in panels.items():
        paired = {r['image'] for r in rows if r['image'] in images and r['version']=='manual_revision'}
        for suffix, pool, versions in [('', images, ('original',)),
                                       ('_dualref', paired, ('original', 'manual_revision'))]:
            buckets = defaultdict(list)
            for r in rows:
                if r['image'] in pool and r['k'] <= limit and r['version'] in versions:
                    key = tuple(r[k] for k in ('scenario','policy','method','version','k','strategy'))
                    buckets[key].append(r)
            for key, members in buckets.items():
                for weighting in ('image', 'building'):
                    row = dict(zip(('scenario','policy','method','version','k','strategy'), key))
                    row.update(panel=panel+suffix, max_k=limit, weighting=weighting,
                               image_n=len(members), building_n=len({r['building'] for r in members}),
                               images='|'.join(sorted(r['image'] for r in members)))
                    for field in FIELDS:
                        valid = [r for r in members if r.get(field) is not None]
                        if not valid or (field in ('add_one_symdiff_union','next_person_loss_union') and len(valid)!=len(members)):
                            row[field] = None
                        elif weighting=='image':
                            row[field] = float(np.mean([r[field] for r in valid]))
                        else:
                            bs = {r['building'] for r in valid}
                            row[field] = float(np.mean([np.mean([r[field] for r in valid if r['building']==b]) for b in bs]))
                    output.append(row)
    return output
