"""有限B3验收：重聚合Part A，并将冻结逐楼类别接入已计算的B线面板。"""
from pathlib import Path
import importlib.util
import io
import json

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('validation', HERE/'personnel_type_validation_20261019.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
SOURCE = v.ROOT/'research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019'
OUT = v.OUT/'part_a_acceptance'
METHODS = ['Q2', 'old_QT', 'old_QTD_supported', 'forward_selected', 'forward_full',
           'forward_base_plus_difficulty', 'reverse_selected', 'reverse_selected_swap',
           'reverse_selected_difficulty']


def read_table(path, **kwargs):
    if path.exists():
        return pd.read_csv(path, **kwargs)
    parts = sorted(path.parent.glob(path.name+'.part*'))
    assert parts, f'missing_table:{path}'
    return pd.read_csv(io.BytesIO(b''.join(p.read_bytes() for p in parts)), compression='gzip', **kwargs)


def attach_labels(events, labels):
    """Missing exported rows are errors; an explicitly unknown class remains unknown."""
    d = events.copy()
    d['label_domain'] = 'global' if set(labels.difficulty) == {'global'} else d.difficulty.replace(
        {'简单': 'easy', '中等': 'medium', '困难': 'hard'})
    keys = ['heldout_building', 'difficulty', 'worker_id']
    for side in ['a', 'b']:
        table = labels[keys+['class_id']].rename(columns={
            'heldout_building': 'building', 'difficulty': 'label_domain',
            'worker_id': f'worker_{side}', 'class_id': f'class_{side}'})
        d = d.merge(table, on=['building', 'label_domain', f'worker_{side}'],
                    how='left', validate='many_to_one', indicator=True)
        assert d._merge.eq('both').all(), 'missing_label_row'
        d = d.drop(columns='_merge')
    known = d[['class_a', 'class_b']].notna().all(axis=1)
    known &= ~d.class_a.eq('unknown') & ~d.class_b.eq('unknown')
    d['relation'] = np.where(known, np.where(d.class_a.eq(d.class_b), 'within', 'between'), 'unknown')
    return d


def matched_cells(events, metric):
    h = events[events.relation.ne('unknown')]
    piv = h.groupby(['building', 'pool_id', 'context', 'relation'])[metric].agg(
        lambda x: x.astype(float).mean() if x.notna().all() else np.nan).unstack('relation')
    return piv.reindex(columns=['within', 'between']).rename(
        columns={'within': 'near', 'between': 'far'}).dropna().reset_index()


def paired_summary(cells):
    result = v.paired_summary(cells, 'near', 'far')
    if result['buildings'] < 2:
        result.update(low=None, high=None)
    return result


def audit_a():
    fields = ['event_id', 'panel_id', 'pool_id', 'image_id', 'building', 'k', 'background_id',
              'worker_a', 'worker_b', 'both_complete', 'abs_B8L2_change', 'floor_jaccard_difference',
              'node_count_difference', 'structure_bound_cyclic_deg', 'stable_main']
    e = read_table(SOURCE/'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz', usecols=fields)
    assert e.event_id.is_unique
    recomputed = (e.both_complete & e.abs_B8L2_change.le(2) & e.floor_jaccard_difference.le(.05)
                  & e.node_count_difference.eq(0) & e.structure_bound_cyclic_deg.le(3))
    assert recomputed.eq(e.stable_main).all()
    cols = ['event_id', 'p__old_QT', 'p__reverse_selected', 'rel__reverse_selected']
    pred = read_table(SOURCE/'assessment/EVENT_PREDICTIONS_WIDE.csv.gz', usecols=cols)
    assert pred.event_id.is_unique and set(pred.event_id) == set(e.event_id)
    e = e.merge(pred, on='event_id', validate='one_to_one')
    q = e[e.panel_id.eq('A_nested_even_v1') & e.k.eq(16)].copy()
    q['gain'] = (q.p__old_QT-q.stable_main)**2-(q.p__reverse_selected-q.stable_main)**2
    b = q.groupby(['building', 'image_id']).gain.mean().groupby('building').mean()
    draws = np.random.default_rng(20261019).choice(b.to_numpy(), (2000, len(b)), replace=True).mean(axis=1)
    published = read_table(SOURCE/'assessment/PAIRED_METHOD_BRIER_COMPARISONS.csv.gz')
    row = published[published.method_id.eq('reverse_selected') & published.reference_method.eq('old_QT')
                    & published.panel_id.eq('A_nested_even_v1') & published.k.eq(16)
                    & published.stratum.eq('all_events_unknown_fallback')].iloc[0]
    assert abs(b.mean()-row.building_mean) < 1e-12
    original = e[e.panel_id.eq('Pro_exact_fixed_background_v1') & e.k.eq(16)].rename(
        columns={'background_id': 'context', 'rel__reverse_selected': 'relation'})
    cells = matched_cells(original, 'stable_main')
    im = cells.groupby(['building', 'pool_id'])[['near', 'far']].mean()
    published_coverage = pd.read_csv(SOURCE/'assessment/PRACTICAL_MATCHED_IMAGE_COVERAGE.csv')
    cover = published_coverage[published_coverage.method_id.eq('reverse_selected')
                              & published_coverage.panel_id.eq('Pro_exact_fixed_background_v1')
                              & published_coverage.k.eq(16) & published_coverage.stratum.eq('all')].iloc[0]
    counts = dict(images=len(im), within_better=int(im.near.gt(im.far+1e-12).sum()),
                  equal=int(np.isclose(im.near, im.far, rtol=0, atol=1e-12).sum()),
                  within_worse=int(im.near.lt(im.far-1e-12).sum()))
    assert counts['images'] == cover.matched_images
    assert counts['within_better'] == cover.images_with_within_better
    assert counts['within_worse'] == cover.images_with_within_worse
    pair = e.assign(pair=e.apply(lambda r:'|'.join(sorted([r.worker_a, r.worker_b])), axis=1))
    support = pair.groupby('pair').agg(images=('image_id', 'nunique'), buildings=('building', 'nunique'))
    return dict(events=len(e), stable_flags_all_match=True, same_event_ids=True,
                nested_k16=dict(events=len(q), images=q.image_id.nunique(), buildings=len(b),
                                brier_improvement=b.mean(), low=np.quantile(draws,.025), high=np.quantile(draws,.975)),
                old_k16_direct=dict(counts, **paired_summary(cells)),
                repeated_pair_support=dict(distinct_pairs=len(support), at_least_3_images=int(support.images.ge(3).sum()),
                    at_least_3_buildings=int(support.buildings.ge(3).sum())),
                limits='Recomputed flags and aggregates from frozen predictions; no refit, recalibration or fresh fusion.')


def main():
    assert (OUT/'SPEC.json').exists(), 'save_spec_before_results'
    labels = pd.read_csv(SOURCE/'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz', low_memory=False)
    swaps = pd.read_csv(v.OUT/'SWAPS.csv.gz')
    assert swaps.event_id.is_unique
    events = pd.concat([attach_labels(swaps, labels[labels.method_id.eq(m)]).assign(method_id=m)
                        for m in METHODS], ignore_index=True)
    assert len(events) == len(swaps)*len(METHODS)
    # Restrict comparisons to events with explicit labels for every declared method.
    common = events.groupby('event_id').relation.agg(lambda x:x.ne('unknown').all())
    events['common_known'] = events.event_id.map(common)
    metrics = ['stable_main', 'stable_strict', 'stable_wide', 'abs_B8L2_change', 'both_complete']
    summaries, coverage, practical = [], [], []
    for support in ['method_known', 'all_methods_known']:
        d = events if support == 'method_known' else events[events.common_known]
        for (method, k), g in d.groupby(['method_id', 'k']):
            for rel, h in g.groupby('relation'):
                coverage.append(dict(support=support, method_id=method, k=k, relation=rel,
                    events=len(h), images=h.pool_id.nunique(), buildings=h.building.nunique(),
                    scored=int(h.abs_B8L2_change.notna().sum()), delta_Q_gt5=int(h.abs_B8L2_change.gt(5).sum()),
                    failed_pair=int((~h.both_complete).sum())))
            for metric in metrics:
                cells = matched_cells(g, metric)
                summaries.append(dict(support=support, method_id=method, k=k, metric=metric,
                                      **paired_summary(cells)))
                if metric == 'stable_main':
                    im = cells.groupby(['building', 'pool_id'])[['near', 'far']].mean()
                    practical.append(dict(support=support, method_id=method, k=k, images=len(im),
                        within_better=int(im.near.gt(im.far+1e-12).sum()),
                        equal=int(np.isclose(im.near,im.far,rtol=0,atol=1e-12).sum()),
                        within_worse=int(im.near.lt(im.far-1e-12).sum()),
                        within_over_half=int(im.near.gt(.5).sum()), between_over_half=int(im.far.gt(.5).sum())))
    chains = events.groupby(['method_id','building','pool_id','context','worker_a','worker_b','relation']).agg(
        nodes=('k', 'nunique'), stable_fraction=('stable_main','mean'), all12=('stable_main','all'),
        any_incomplete=('both_complete',lambda x:not x.all())).reset_index()
    assert chains.nodes.eq(12).all()
    chain_summary = []
    for method, g in chains.groupby('method_id'):
        for metric in ['stable_fraction','all12','any_incomplete']:
            chain_summary.append(dict(method_id=method, metric=metric,
                                     **paired_summary(matched_cells(g,metric))))
    origins = pd.read_csv(SOURCE/'assessment/WORKER_PORTRAITS_60.csv').set_index('worker_id').person_origin
    assert origins.index.is_unique
    oa, ob = events.worker_a.map(origins), events.worker_b.map(origins)
    assert oa.notna().all() and ob.notna().all()
    events['pair_origin'] = np.where(oa.eq(ob), oa+'-'+ob, 'mixed')
    filters = {'all_methods_known': events.common_known,
               'Q_gap_le3': (events.q_a-events.q_b).abs().le(3),
               'same_origin': oa.eq(ob)}
    sensitivity = []
    for name, mask in filters.items():
        for method, g in events[mask].groupby('method_id'):
            rates = g.groupby(['building','pool_id','context','worker_a','worker_b','relation']).stable_main.mean().reset_index()
            sensitivity.append(dict(stratum=name, method_id=method,
                                    **paired_summary(matched_cells(rates,'stable_main'))))
    pd.DataFrame(sensitivity).to_csv(OUT/'B_SENSITIVITY.csv',index=False,encoding='utf-8-sig')
    events.groupby(['method_id','relation','pair_origin']).agg(events=('event_id','size'),
        images=('pool_id','nunique')).reset_index().to_csv(OUT/'B_ORIGIN_COVERAGE.csv',index=False,encoding='utf-8-sig')
    keep = ['event_id','method_id','class_a','class_b','relation','common_known']
    events[keep].to_csv(OUT/'B_EVENT_LABELS.csv.gz',index=False)
    for filename, rows in [('B_MATCHED_SUMMARY.csv',summaries),('B_COVERAGE.csv',coverage),
                           ('B_PRACTICAL_IMAGES.csv',practical),('B_CHAIN_SUMMARY.csv',chain_summary)]:
        pd.DataFrame(rows).to_csv(OUT/filename,index=False,encoding='utf-8-sig')
    chains.to_csv(OUT/'B_CHAINS.csv.gz',index=False)
    audit = audit_a()
    audit['B'] = dict(events=len(swaps), methods=METHODS, label_rows=len(events),
        all_methods_known_events=int(common.sum()), new_fusions=0, classes_refit=False,
        conditional_layers_used=False, new_external_blind_test=False)
    (OUT/'CHECKS.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main()
