"""独立重聚合保存面板和F01成员结果；不调用作者汇总、不重跑融合。"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import json
import math

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_mixture_audit_20261022'
V3 = ROOT / 'research/workers/personnel_v3_20261021'


def macro(frame, fields):
    """面板先到图，再到楼；楼等权。"""
    return frame.groupby(['building', 'image'])[fields].mean().groupby('building').mean()


def variance_parts(values, configuration):
    f = pd.DataFrame({'y': values, 'c': configuration}).dropna(subset=['y'])
    total = float(f.y.var(ddof=0))
    within = float(((f.y - f.groupby('c').y.transform('mean')) ** 2).mean())
    return total, within, total - within


def response_audit():
    decomposition, predictions, checks = [], [], []
    for condition in ['manual', 'semi']:
        for domain in ['geometry_common', 'qt_common']:
            folder = OUT / 'source_response' / condition / domain
            d = pd.read_csv(folder / 'PANEL_CONFIGURATION_DECOMPOSITION.csv.gz')
            p = pd.read_csv(folder / 'PANEL_PREDICTION.csv.gz')
            assert d.condition.eq(condition).all() and p.condition.eq(condition).all()
            assert d.domain.eq(domain).all() and p.domain.eq(domain).all()
            assert not d.duplicated(['panel_id', 'method', 'outcome']).any()
            assert not p.duplicated(['panel_id', 'model', 'outcome']).any()
            np.testing.assert_allclose(d.total_variance, d.within_configuration_variance + d.between_configuration_variance, atol=1e-9)
            assert (d.valid_teams <= d.teams).all()
            assert (d.substitutable_configurations + d.single_member_configurations == d.configurations).all()
            # 不将source模型的误差冒称重新拟合；这里只验证保存基准与同面板总方差相同。
            base = p[p.model.eq('source')].merge(d[d.method.eq('old_coarse')], on=['panel_id', 'outcome'], suffixes=('_p', '_d'), validate='one_to_one')
            assert len(base) == len(p[p.model.eq('source')])
            np.testing.assert_allclose(base.baseline_mse, base.total_variance, atol=1e-9)
            local_d, local_p = [], []
            strata = [('all', 'all', d, p)] + [('difficulty', v, d[d.difficulty.eq(v)], p[p.difficulty.eq(v)]) for v in sorted(d.difficulty.unique())]
            for sk, sv, ds, ps in strata:
                for (method, outcome), g in ds.groupby(['method', 'outcome']):
                    b = macro(g, ['total_variance', 'within_configuration_variance', 'between_configuration_variance'])
                    total, within, between = b.mean()
                    local_d.append(dict(condition=condition, domain=domain, method=method, outcome=outcome, stratum=sk, stratum_value=sv,
                        panels=g.panel_id.nunique(), images=g.image.nunique(), buildings=len(b), total_variance=total,
                        within_variance=within, between_variance=between, between_share=between/total if total > 1e-12 else np.nan,
                        substitutable_configurations=int(g.substitutable_configurations.sum()), single_member_configurations=int(g.single_member_configurations.sum())))
                for (model, outcome), g in ps.groupby(['model', 'outcome']):
                    b = macro(g, ['mse', 'baseline_mse', 'mae'])
                    mse, baseline, mae = b.mean()
                    local_p.append(dict(condition=condition, domain=domain, model=model, outcome=outcome, stratum=sk, stratum_value=sv,
                        panels=g.panel_id.nunique(), images=g.image.nunique(), buildings=len(b), mse=mse, baseline_mse=baseline,
                        response_r2=1-mse/baseline if baseline > 1e-12 else np.nan, mae=mae,
                        positive_buildings=int((b.mse < b.baseline_mse - 1e-12).sum())))
            dd, pp = pd.DataFrame(local_d), pd.DataFrame(local_p)
            errors = []
            for actual, filename, keys, fields in [
                (dd[dd.stratum.eq('all')], 'DECOMPOSITION_SUMMARY.csv', ['condition','domain','method','outcome'], ['total_variance','within_variance','between_variance','between_share','panels','images','buildings']),
                (pp, 'PREDICTION_SUMMARY.csv', ['condition','domain','model','outcome','stratum','stratum_value'], ['mse','baseline_mse','response_r2','mae','panels','images','buildings'])]:
                expected = pd.read_csv(folder / filename)
                joined = actual.merge(expected, on=keys, suffixes=('_a','_e'), validate='one_to_one')
                assert len(joined) == len(actual)
                for field in fields:
                    np.testing.assert_allclose(joined[field+'_a'], joined[field+'_e'], atol=1e-9, equal_nan=True)
                    errors.append(float((joined[field+'_a']-joined[field+'_e']).abs().max()))
            checks.append(dict(condition=condition, domain=domain, decomposition_rows=len(d), prediction_rows=len(p), max_summary_difference=max(errors)))
            decomposition.extend(local_d); predictions.extend(local_p)
    pd.DataFrame(decomposition).to_csv(OUT/'RECOMPUTED_DECOMPOSITION.csv', index=False)
    pd.DataFrame(predictions).to_csv(OUT/'RECOMPUTED_PREDICTION.csv', index=False)
    return checks


def f01_audit():
    folder = V3/'f01_utility/utility'
    d = pd.read_csv(folder/'F01_CONFIGURATION_MEMBERS.csv.gz')
    expected = pd.read_csv(folder/'F01_COMPLETE_CONFIGURATION_CURVE.csv').set_index(['panel_id','fast_C01_n'])
    assert not d.team_key.duplicated().any()
    assert d.complete_evaluable.equals(d.B8L2.notna())
    assert d.source_time_known_n.eq(d.k).all() and d.source_time_total_seconds.gt(0).all()
    assert not d.time_source_kinds.str.contains('|', regex=False).any()
    errors, curves, contrasts, variance = [], [], [], []
    for pid, panel in d.groupby('panel_id'):
        n = int(panel.k.iloc[0]); sets = [frozenset(s.split('|')) for s in panel.member_workers]
        assert all(len(s)==n for s in sets) and len(set(sets))==len(sets)
        pool = set().union(*sets)
        assert len(sets)==math.comb(len(pool), n)
        assert set(sets)=={frozenset(s) for s in combinations(sorted(pool), n)}
        pc = []
        for fast, g in panel.groupby('fast_C01_n'):
            e = expected.loc[(pid, fast)]
            assert len(g)==math.comb(int(e.fast_C01_capacity),int(fast))*math.comb(int(e.slow_C02_capacity),n-int(fast))
            assert g.slow_C02_n.eq(n-fast).all()
            assert g.F01_counts.eq(f'C01:{fast}|C02:{n-fast}').all()
            q = g.B8L2.dropna()
            r = dict(panel_id=pid, building=e.building, image=e.image, difficulty=e.difficulty, fast_C01_n=fast,
                member_sets=len(g), successful_member_sets=len(q), complete_failures=int((~g.complete_evaluable).sum()),
                failure_rate=float((~g.complete_evaluable).mean()), B8L2=q.mean(), D10=g.D10.mean(), nodes=g.nodes.mean(),
                B8L2_std=q.std(ddof=0), time_seconds=g.source_time_total_seconds.mean())
            for suffix, quantile in [('p10',.1),('p50',.5),('p90',.9)]: r['B8L2_'+suffix]=q.quantile(quantile)
            for suffix, quantile in [('p10',.1),('p90',.9)]: r['time_seconds_'+suffix]=g.source_time_total_seconds.quantile(quantile)
            for k,v in r.items():
                if k not in ['panel_id','building','image','difficulty','fast_C01_n']:
                    np.testing.assert_allclose(v,e[k],atol=1e-9,equal_nan=True);errors.append(abs(v-e[k]))
            inclusion=Counter(w for s in g.member_workers for w in s.split('|'))
            saved=json.loads(e.worker_inclusion_probabilities)
            assert set(inclusion)==set(saved)
            for w in inclusion: np.testing.assert_allclose(inclusion[w]/len(g),saved[w],atol=1e-12)
            curves.append(r);pc.append(r)
        if len(pc)<2: continue
        lo,hi=pc[0],pc[-1]
        contrasts.append(dict(panel_id=pid,building=lo['building'],image=lo['image'],difficulty=lo['difficulty'],
            delta_Q=hi['B8L2']-lo['B8L2'],delta_D10=hi['D10']-lo['D10'],
            time_percent=100*(hi['time_seconds']/lo['time_seconds']-1),failure_delta_pp=100*(hi['failure_rate']-lo['failure_rate'])))
        for outcome in ['B8L2','D10','nodes','source_time_total_seconds','failure']:
            y=(~panel.complete_evaluable).astype(float) if outcome=='failure' else panel[outcome]
            total,within,between=variance_parts(y,panel.fast_C01_n)
            variance.append(dict(panel_id=pid,building=lo['building'],image=lo['image'],difficulty=lo['difficulty'],outcome=outcome,
                total_variance=total,within_variance=within,between_variance=between,between_share=between/total if total>1e-12 else np.nan))
    c,v=pd.DataFrame(contrasts),pd.DataFrame(variance)
    summaries=[]
    for scope,g in [('all',c)]+list(c.groupby('difficulty')):
        fields=['delta_Q','delta_D10','time_percent','failure_delta_pp']; b=macro(g,fields)
        summaries.append(dict(stratum=scope,images=g.image.nunique(),buildings=len(b),**b.mean().to_dict(),
            time_decreasing_images=int(g.time_percent.lt(0).sum()),quality_increasing_images=int(g.delta_Q.gt(0).sum())))
    vs=[]
    for scope,g in [('all',v)]+list(v.groupby('difficulty')):
        for outcome,z in g.groupby('outcome'):
            b=macro(z,['total_variance','within_variance','between_variance']); total,within,between=b.mean()
            vs.append(dict(stratum=scope,outcome=outcome,images=z.image.nunique(),buildings=len(b),total_variance=total,
                within_variance=within,between_variance=between,between_share=between/total if total>1e-12 else np.nan))
    pd.DataFrame(curves).to_csv(OUT/'F01_RECOMPUTED_CONFIGURATIONS.csv',index=False)
    c.to_csv(OUT/'F01_RECOMPUTED_CONTRASTS.csv',index=False)
    v.to_csv(OUT/'F01_PANEL_VARIANCE.csv',index=False)
    pd.DataFrame(vs).to_csv(OUT/'F01_VARIANCE_SUMMARY.csv',index=False)
    return dict(member_rows=len(d),configurations=len(curves),images=d.image.nunique(),buildings=d.building.nunique(),
        failure_rows=int((~d.complete_evaluable).sum()),max_curve_difference=float(np.nanmax(errors)),extreme_contrasts=summaries,
        label_assignment_refitted=False,score_recomputed=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    panels = pd.read_csv(ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021/composition/PANELS.csv')
    difficulty = pd.read_csv(ROOT/'research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv')
    linked = panels.merge(difficulty[['image','target_id','coarse_class','is_oos','is_doorway','target_full_status']], on='image', how='left', validate='many_to_one')
    assert linked.target_id.notna().all()
    assert linked.difficulty.eq(linked.coarse_class).all()
    linked.to_csv(OUT/'PANEL_DIFFICULTY_LINK.csv',index=False)
    result=dict(response=response_audit(),f01=f01_audit(),scope='saved_panel_reaggregation_and_F01_member_reaggregation',
        no_native_fusion_or_model_refit=True,
        difficulty_link=dict(panels=len(linked),images=linked.image.nunique(),label_mismatches=0,
            doorway_panels=int(linked.is_doorway.sum()),oos_panels=int(linked.is_oos.sum()),
            reference_identity_note='current difficulty target attached; source panel table does not declare endpoint reference'))
    recomputed=pd.read_csv(OUT/'RECOMPUTED_DECOMPOSITION.csv').query("stratum == 'all'")
    integrated=pd.read_csv(V3/'integrated_report/response/COMPLETED_RESPONSE_DECOMPOSITION.csv')
    keys=['condition','domain','method','outcome']
    merged=recomputed.merge(integrated,on=keys,suffixes=('_a','_e'),validate='one_to_one')
    assert len(merged)==len(integrated)==len(recomputed)
    for field in ['total_variance','within_variance','between_variance','between_share']:
        np.testing.assert_allclose(merged[field+'_a'],merged[field+'_e'],atol=1e-9,equal_nan=True)
    result['integrated_decomposition_rows_verified']=len(merged)
    (OUT/'CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
