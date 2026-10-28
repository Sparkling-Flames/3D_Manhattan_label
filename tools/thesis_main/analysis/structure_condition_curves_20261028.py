"""Regroup frozen natural256/exact marginal estimates; never run fusion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/difficulty/difficulty_computable_comparison_20261028/structure_sensitivity_v1'
POP=ROOT/'research/workers/personnel_population_curves_v2_20261023'
EXT=POP/'sampling_extension_20261026'
QMET=['Q_mean','Q_p10','Q_p10_inverse_cdf','Q_sd_display','actual_consensus_failure_rate',
      'output_unscoreable_rate','reference_unavailable_rate','not_executed_rate']


def save(name, frame):
    frame.to_csv(OUT/name,index=False,encoding='utf-8')


def condition(frame):
    assert frame[['ref_turn5','ref_H','ref_short_edges']].notna().all().all()
    return np.where(frame.ref_H.gt(0),'H_positive',np.where(frame.ref_short_edges.gt(0),'short_H0','plain_H0'))


def grouped_images(meta):
    rows=[]
    for r in meta.to_dict('records'):
        groups=[('all','all'),('turn_band','4' if r['ref_turn5']==4 else '6' if r['ref_turn5']==6 else 'ge8'),
                ('mechanism',r['structure_group']),('turn'+str(int(r['ref_turn5'])),r['structure_group'])]
        for scope,group in groups:rows.append(dict(pool_id=r['pool_id'],scope=scope,group=group))
    return pd.DataFrame(rows)


def complete_curve(frame, points):
    valid=frame.pivot(index='pool_id',columns='point',values='value').reindex(columns=points)
    return set(valid.index[valid.notna().all(axis=1)])


def main():
    assert (OUT/'PLAN.json').exists()
    pools=pd.read_csv(POP/'design/ACTUAL_POOLS.csv');pools=pools[pools.layer.eq('ordinary_manual')]
    f=pd.read_csv(POP/'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
    cols=['image_id','reference_id','ref_turn5','ref_H','ref_short_edges','ref_min_horizontal_deg','ref_short_min_horizontal_deg']
    meta=pools.merge(f[cols],on=['image_id','reference_id'],validate='one_to_one')
    assert len(meta)==177
    meta['structure_group']=condition(meta)
    meta['geometry_challenge']=(meta.ref_turn5.gt(6)|meta.ref_H.gt(0)|meta.ref_short_edges.gt(0))
    save('IMAGE_CONDITIONS.csv',meta)
    groups=grouped_images(meta);save('IMAGE_GROUPS.csv',groups)
    h=pd.read_csv(EXT/'analysis_precision26/results_stage2/HYBRID_POOLED256_DISPLAY_CURVES.csv.gz')
    h=h[h.pool_id.isin(meta.pool_id)&h.cohort.eq('pooled256')].copy()
    assert not h.duplicated(['pool_id','k']).any() and h.pool_id.nunique()==177
    assert h.paths_attempted.eq(256).all()
    save('CURVE_SOURCE_ROWS.csv.gz',h)
    g=pd.read_csv(EXT/'analysis_geometry26/results_stage2/GEOMETRY_PATH_PRECISION.csv.gz')
    g=g[g.pool_id.isin(meta.pool_id)&g.cohort.eq('pooled256')].copy()
    assert not g.duplicated(['pool_id','k','metric']).any()
    save('GEOMETRY_SOURCE_ROWS.csv.gz',g)
    long=h.melt(id_vars=['pool_id','k'],value_vars=QMET,var_name='metric',value_name='value')
    long=pd.concat([long,g[['pool_id','k','metric','mean']].rename(columns={'mean':'value'})],ignore_index=True)
    long=long.merge(meta[['pool_id','building','pool_n']],on='pool_id',validate='many_to_one')
    curves=[];ledger=[]
    for cap in [30,35]:
        z=long[long.pool_n.ge(cap)]
        steps=[1,*range(3,cap+1)]
        part=z[z.k.isin(steps)].copy();part['point']=part.k.astype(str)
        full=z[z.k.eq(z.pool_n)].copy();full['point']='full'
        part=pd.concat([part,full],ignore_index=True);part['capacity']=cap
        for metric,df in part.groupby('metric'):
            keep=complete_curve(df,[str(k) for k in steps]+['full'])
            for pool,pg in df.groupby('pool_id'):
                ledger.append(dict(capacity=cap,metric=metric,pool_id=pool,common_curve=pool in keep,
                    missing_points='|'.join(pg.loc[pg.value.isna(),'point']),candidate_points=len(pg)))
            curves.append(df[df.pool_id.isin(keep)])
    curve=pd.concat(curves,ignore_index=True);save('CURVE_COMMON_SUPPORT.csv',pd.DataFrame(ledger))
    save('CURVE_IMAGE_VALUES.csv.gz',curve)
    expanded=curve.merge(groups,on='pool_id',validate='many_to_many')
    keys=['capacity','scope','group','metric','point']
    building=expanded.groupby(keys+['building']).agg(value=('value','mean'),images=('pool_id','nunique')).reset_index()
    image=expanded.groupby(keys).agg(image_equal=('value','mean'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
    bmean=building.groupby(keys).value.mean().rename('building_equal').reset_index()
    save('CURVE_BUILDING.csv',building);save('CURVE_SUMMARY.csv',image.merge(bmean,on=keys))
    support=meta.merge(groups,on='pool_id');save('GROUP_SUPPORT.csv',support.groupby(['scope','group']).agg(images=('pool_id','nunique'),buildings=('building','nunique'),min_N=('pool_n','min'),max_N=('pool_n','max')).reset_index())
    deltas=[]
    for (cap,metric),df in curve.groupby(['capacity','metric']):
        wide=df.pivot(index=['pool_id','building'],columns='point',values='value')
        for a,b in [('1','6'),('6','10'),('10','20'),('6','30'),('20','30'),('30','35'),('30','full'),('35','full')]:
            if a not in wide or b not in wide:continue
            t=(wide[b]-wide[a]).rename('delta').reset_index();t['capacity']=cap;t['metric']=metric;t['interval']=a+'->'+b;deltas.append(t)
    delta=pd.concat(deltas,ignore_index=True);save('CURVE_IMAGE_DELTAS.csv',delta)
    dx=delta.merge(groups,on='pool_id');keys=['capacity','scope','group','metric','interval']
    db=dx.groupby(keys+['building']).agg(delta=('delta','mean'),images=('pool_id','nunique')).reset_index()
    ds=dx.groupby(keys).agg(image_equal=('delta','mean'),images=('pool_id','nunique'),buildings=('building','nunique'),positive_images=('delta',lambda x:int((x>1e-10).sum())),negative_images=('delta',lambda x:int((x< -1e-10).sum())))
    bs=db.groupby(keys).agg(building_equal=('delta','mean'),positive_buildings=('delta',lambda x:int((x>1e-10).sum())),negative_buildings=('delta',lambda x:int((x< -1e-10).sum())))
    save('DELTA_BUILDING.csv',db);save('DELTA_SUMMARY.csv',ds.join(bs).reset_index())
    corr=[];cd=delta[(delta.capacity==30)&delta.interval.eq('6->30')].merge(meta,on=['pool_id','building'])
    for scope,df in [('all',cd),('turn6',cd[cd.ref_turn5.eq(6)])]:
        for metric,m in df.groupby('metric'):
            for feature in ['ref_turn5','ref_H','ref_short_edges','ref_min_horizontal_deg']:
                estimable=m[feature].nunique()>1 and m.delta.nunique()>1
                corr.append(dict(scope=scope,metric=metric,feature=feature,images=len(m),buildings=m.building.nunique(),spearman=m[feature].corr(m.delta,method='spearman') if estimable else np.nan))
    save('CURVE_CONDITION_ASSOCIATIONS.csv',pd.DataFrame(corr))
    checks=dict(images=177,capacity30=int(meta.pool_n.ge(30).sum()),capacity35=int(meta.pool_n.ge(35).sum()),source_rows=len(h),geometry_rows=len(g),new_paths=0,new_fusion=0,exact_sources_preserved=h.estimator.value_counts().to_dict(),full_V_max=float(g.loc[g.k.eq(g.pool_n),'mean'].abs().max()))
    (OUT/'CURVE_CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(checks)


if __name__=='__main__':main()
