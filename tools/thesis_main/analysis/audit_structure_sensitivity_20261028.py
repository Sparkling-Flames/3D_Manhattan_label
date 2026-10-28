"""Independent saved-result audit; SVD refits K3 without importing producer code."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/difficulty/difficulty_computable_comparison_20261028/structure_sensitivity_v1'
POP = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
OLD = ROOT / 'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/01'
COMP = ROOT / 'research/workers/personnel_mixture_comparison_20261022/configurations'
ST = ['turn_n', 'short_turn_edges', 'near_straight_nodes_5deg', 'unmatched_ref_9']


def read(name):
    return pd.read_csv(BASE / name)


def compare(left, right, keys, cols):
    a = left.set_index(keys).sort_index()[cols]
    b = right.set_index(keys).sort_index()[cols]
    assert a.index.is_unique and a.index.equals(b.index)
    np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-10, equal_nan=True)
    return len(a)


def refit():
    raw = pd.read_csv(OLD / 'features/RAW_CONDITION_RESPONSE_RECORDS.csv.gz', low_memory=False)
    manual = raw[raw.condition.eq('manual')].copy()
    for s in ST:
        peer = manual[s] - manual.groupby('image_id')[s].transform('median')
        np.testing.assert_allclose(peer, manual[s + '_peer'], atol=1e-10, equal_nan=True)
    raw = manual[manual.history_eligible & manual.difficulty_coarse.isin(['简单', '中等', '困难'])].copy()
    assert len(raw) == 5785 and raw.object_id.is_unique
    raw['challenge'] = (raw.ref_turn5 > 6) | (raw.ref_H > 0) | (raw.ref_short_edges > 0)
    labels = read('LABELS_ALL_LOBO.csv')
    eligibility = read('ELIGIBILITY.csv')
    fits = 0
    for fold, elig in eligibility.groupby('heldout_building'):
        d = raw if fold == 'ALL' else raw[raw.building != fold]
        workers = sorted(elig[elig.common].worker_id)
        assert len(workers) == 59
        histories = {}
        masks = {'all': np.ones(len(d), bool), 'easy': d.difficulty_coarse.eq('简单'),
                 'hard': d.difficulty_coarse.eq('困难'), 'c': d.challenge, 'p': ~d.challenge}
        for name, mask in masks.items():
            z = d[mask]
            histories[name] = z.groupby(['worker_id', 'building'])[[s+'_peer' for s in ST]].mean().groupby('worker_id').mean().reindex(workers).to_numpy()
            counts = z.groupby('worker_id').agg(images=('image_id', 'nunique'), buildings=('building', 'nunique'))
            histories[name+'_counts'] = counts.reindex(elig.worker_id).fillna(0)
        counts = histories['all_counts']
        native_all = (counts.images >= 12) & (counts.buildings >= 3)
        def enough(name, images, buildings):
            c = histories[name+'_counts']
            return (c.images >= images) & (c.buildings >= buildings)
        native_original = native_all & enough('easy', 5, 2) & enough('hard', 4, 2)
        native_geometry = native_all & enough('p', 5, 2) & enough('c', 4, 2)
        for col, expected in [('original', native_original), ('overall_native', native_all), ('geometry_native', native_geometry)]:
            assert np.array_equal(elig[col].to_numpy(), expected.to_numpy())
        domains = {
            'original_common': [histories['all'], np.column_stack([histories['hard'], histories['hard']-histories['easy']])],
            'overall_common': [histories['all']],
            'geometry_common': [histories['all'], np.column_stack([histories['c'], histories['c']-histories['p']])],
        }
        for method, blocks in domains.items():
            encoded = []
            for a in blocks:
                scale = np.quantile(a, .85, axis=0)-np.quantile(a, .15, axis=0)
                scale = np.where(scale > 1e-9, scale, a.std(axis=0))
                scale = np.where(scale > 1e-9, scale, 1.)
                z = np.clip((a-np.median(a, axis=0))/scale, -3, 3)
                z -= z.mean(axis=0)
                u, s, _ = np.linalg.svd(z, full_matrices=False)
                y = u[:, :2]*s[:2]
                y /= max(np.sqrt(np.mean(np.sum(y*y, axis=1))), 1e-9)*np.sqrt(len(blocks))
                encoded.append(y)
            cluster = cut_tree(linkage(np.column_stack(encoded), method='ward'), n_clusters=3).ravel()
            target = labels[(labels.heldout_building == fold) & (labels.method == method)].set_index('worker_id').loc[workers, 'class_id']
            assert adjusted_rand_score(cluster, target) == 1, (fold, method)
            fits += 1
    return fits


def curves():
    source = pd.read_csv(POP / 'sampling_extension_20261026/analysis_precision26/results_stage2/HYBRID_POOLED256_DISPLAY_CURVES.csv.gz')
    saved = read('CURVE_SOURCE_ROWS.csv.gz')
    source = source[(source.cohort == 'pooled256') & source.pool_id.isin(saved.pool_id)]
    qcols = ['Q_mean', 'Q_p10', 'Q_p10_inverse_cdf', 'Q_sd_display', 'actual_consensus_failure_rate', 'output_unscoreable_rate', 'reference_unavailable_rate', 'not_executed_rate']
    n = compare(source, saved, ['pool_id', 'k'], qcols + ['paths_attempted'])
    assert np.array_equal(source.set_index(['pool_id','k']).sort_index().estimator, saved.set_index(['pool_id','k']).sort_index().estimator)
    vals = read('CURVE_IMAGE_VALUES.csv.gz')
    geom = pd.read_csv(POP / 'sampling_extension_20261026/analysis_geometry26/results_stage2/GEOMETRY_PATH_PRECISION.csv.gz')
    geom = geom[(geom.cohort == 'pooled256') & geom.pool_id.isin(saved.pool_id)]
    originals = pd.concat([source.melt(id_vars=['pool_id','k'], value_vars=qcols, var_name='metric', value_name='value'),
                           geom[['pool_id','k','metric','mean']].rename(columns={'mean':'value'})])
    linked = vals.merge(originals, on=['pool_id','k','metric'], suffixes=('','_source'), validate='many_to_one')
    assert len(linked) == len(vals)
    np.testing.assert_allclose(linked.value, linked.value_source, atol=1e-10, equal_nan=True)
    groups = read('IMAGE_GROUPS.csv')
    meta = read('IMAGE_CONDITIONS.csv')
    assert np.array_equal(meta.structure_group, np.where(meta.ref_H > 0, 'H_positive', np.where(meta.ref_short_edges > 0, 'short_H0', 'plain_H0')))
    for (cap, metric), g in vals.groupby(['capacity','metric']):
        assert g.groupby('point').pool_id.apply(lambda x: tuple(sorted(x))).nunique() == 1
        assert set(g.point) == {'1', 'full'} | {str(k) for k in range(3, int(cap)+1)}
    expanded = vals.merge(groups, on='pool_id', validate='many_to_many')
    keys = ['capacity', 'scope', 'group', 'metric', 'point']
    out = expanded.groupby(keys).agg(image_equal=('value','mean'), images=('pool_id','nunique'), buildings=('building','nunique'))
    out['building_equal'] = expanded.groupby(keys+['building']).value.mean().groupby(level=keys).mean()
    rows = compare(out.reset_index(), read('CURVE_SUMMARY.csv'), keys, ['image_equal','building_equal','images','buildings'])
    # Check each published change against its own fixed-image endpoint values.
    delta = read('CURVE_IMAGE_DELTAS.csv')
    wide = vals.pivot(index=['capacity','metric','pool_id','building'], columns='point', values='value')
    pieces=[]
    for interval in delta.interval.unique():
        a,b=interval.split('->')
        z=(wide[b]-wide[a]).dropna().rename('delta').reset_index();z['interval']=interval;pieces.append(z)
    compare(pd.concat(pieces), delta, ['capacity','metric','pool_id','building','interval'], ['delta'])
    return n, rows


def teams():
    labels = read('LABELS_ALL_LOBO.csv')
    maps = {(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labels.groupby(['method','heldout_building'])}
    events = read('ABC_CACHED_SOURCE.csv.gz').set_index(['stage','event_id'])
    raw_events=[]
    for stage, folder in [('screen','02A/results/screen'),('confirm','04A1/results/confirm'),('size_paths','05/results/size_paths')]:
        e=pd.read_csv(OLD.parent/folder/'EVENT_METRICS.csv.gz',usecols=[c for c in events.columns if c not in ['frozen_primary_role']]+['event_id'],low_memory=False)
        e=e[e.method.eq('DSTRUCT_K3') & e.design.eq('strict_disjoint_ABC')].copy();e['stage']=stage;raw_events.append(e)
    original_events=pd.concat(raw_events).set_index(['stage','event_id']).sort_index()
    pd.testing.assert_frame_equal(events[original_events.columns].sort_index(),original_events,check_dtype=False,atol=1e-10,rtol=1e-10)
    evaluated = read('ABC_RELABELED.csv.gz')
    actual=[]
    for r in evaluated.itertuples():
        e = events.loc[(r.stage,r.event_id)]
        blocks = [set(str(e[k]).split('|')) if pd.notna(e[k]) else set() for k in ['D','X','Y','Z']]
        assert len(set.union(*blocks)) == sum(map(len,blocks))
        assert all(len(x)==e.m for x in blocks[1:])
        assert all(set(e[arm+'_members'].split('|')) == blocks[0]|blocks[i] for i,arm in enumerate(['A','B','C'],1))
        c=[{maps[(r.method,r.building)].get(w,'unknown') for w in x} for x in blocks[1:]]
        legal=all(len(x)==1 and 'unknown' not in x for x in c) and c[0]==c[1] and c[0]!=c[2]
        assert r.legal == legal
        a,b,cq=e.A_B8L2,e.B_B8L2,e.C_B8L2
        scored=bool(e.ABC_scored) and np.isfinite([a,b,cq]).all()
        assert r.scored == scored
        if scored:np.testing.assert_allclose([r.within,r.cross,r.CB], [abs(b-a),(abs(cq-a)+abs(cq-b))/2,cq-b])
        actual.append(legal)
    vectors = read('COMPOSITION_TEAM_LABELS.csv.gz')
    panels=pd.read_csv(COMP/'PANELS_USED.csv').set_index('panel_id')
    original_links=pd.read_csv(COMP/'PANEL_TEAMS.csv.gz')
    original_links=original_links[original_links.panel_id.isin(panels[panels.condition.eq('manual')].index)]
    expected=set(zip(original_links.panel_id,original_links.team_key))
    assert len(original_links)==213444 and len(expected)==213444
    for _,g in vectors.groupby('method'):
        assert len(g)==213444 and set(zip(g.panel_id,g.team_key))==expected
    members=pd.read_csv(COMP/'TEAM_MEMBERS.csv.gz').set_index('team_key').member_workers
    endpoints=pd.read_csv(COMP/'ENDPOINT_OUTCOMES_manual.csv.gz').set_index('team_key')
    calculated=[]
    for (panel,method),g in vectors.groupby(['panel_id','method']):
        lookup=maps[(method,panels.loc[panel,'building'])]
        conf=['|'.join(str(sum(lookup[w]==cls for w in members[k].split('|'))) for cls in ['C1','C2','C3']) for k in g.team_key]
        assert conf==g.configuration.tolist()
        for metric in ['B8L2','fusion_turn_n']:
            t=pd.DataFrame({'value':endpoints.loc[g.team_key,metric].to_numpy(),'conf':conf}).dropna()
            avg=t.groupby('conf').value.transform('mean');mu=t.value.mean()
            calculated.append(dict(panel_id=panel,method=method,metric=metric,valid=len(t),total=((t.value-mu)**2).mean(),between=((avg-mu)**2).mean(),within=((t.value-avg)**2).mean()))
    count=compare(pd.DataFrame(calculated),read('COMPOSITION_PANEL_RESULTS.csv'),['panel_id','method','metric'],['valid','total','between','within'])
    return len(evaluated),len(vectors),count


def main():
    fitted=refit();print('independent SVD/Ward fits',fitted,flush=True)
    n,curverows=curves();print('curve rows',curverows,flush=True)
    events,teams_count,panelrows=teams()
    result=dict(status='passed_independent_saved_result_audit',independent_SVD_Ward_fits=fitted,curve_source_rows=n,curve_summary_rows=curverows,ABC_method_event_rows=events,composition_team_associations=teams_count,composition_panel_metric_rows=panelrows,new_fusion=0,new_scoring=0,scope='independent raw-history centering and K3 partitions, source curve identity and summaries, block legality and endpoint-derived contrasts, member-defined composition variance; no raw fusion or geometry rescoring')
    (BASE/'INDEPENDENT_ACCEPTANCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result)


if __name__ == '__main__':
    main()
