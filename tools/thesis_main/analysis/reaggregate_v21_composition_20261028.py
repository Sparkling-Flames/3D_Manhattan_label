"""同一组924有限团队：分离参考评分更新与DSTRUCT标签更新。"""
import gzip
import importlib.util
import json
from collections import Counter
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read

SOURCE=ROOT/'research/workers/dstruct_composition_bridge_20261026'
C=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
TARGET=OUT/'composition_variance'


def main():
    TARGET.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('frozen_bridge',SOURCE/'build_bridge.py')
    bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
    panels=pd.read_csv(C/'PANELS_USED.csv').query('condition=="manual"')
    links=pd.read_csv(C/'PANEL_TEAMS.csv.gz');links=links[links.panel_id.isin(panels.panel_id)]
    assert len(panels)==231 and links.groupby('panel_id').size().eq(924).all()
    members=pd.read_csv(C/'TEAM_MEMBERS.csv.gz').set_index('team_key')
    before=pd.read_csv(C/'ENDPOINT_OUTCOMES_manual.csv.gz').set_index('team_key')
    for d in [before]:
        d['log_recorded_time']=np.log(d.recorded_time_total_seconds.where(d.recorded_time_eligible & d.recorded_time_total_seconds.gt(0)))
        d['not_complete_evaluable']=(~d.complete_evaluable).astype(float)
    after=before.copy();updated=set()
    for path in sorted((OUT/'composition_rescore').rglob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                r=json.loads(line);key=r['team_key']
                if key not in after.index:continue
                assert key not in updated;updated.add(key)
                assert r['k']==after.at[key,'k']
                for field in ['B8L2','D10','fusion_turn_n']:
                    after.at[key,field]=r.get(field)
                after.at[key,'not_complete_evaluable']=float(not r['complete_evaluable'])
    deps=read(OUT/'pools/DEPENDENCIES.json')
    affected={r['pool_id'] for r in deps if r['action']=='reuse_geometry_rescore'}
    assert updated==set(before[before.pool_id.isin(affected)].index)
    labels=pd.read_csv(OUT/'condition_classification/LABELS_ALL_LOBO.csv.gz')
    maps={m:{(b,w):str(c) for b,w,c in labels[labels.method.eq(m)&labels.known&labels.heldout_building.ne('ALL')][['heldout_building','worker_id','class_id']].itertuples(index=False,name=None)} for m in ['DSTRUCT_K2','DSTRUCT_K3']}
    frozen={m:pd.read_csv(SOURCE/f'TEAM_CONFIGURATION_LINKS_{m}.csv.gz').set_index(['panel_id','team_key']).class_counts for m in bridge.METHODS}
    prior=pd.read_csv(SOURCE/'PANEL_VARIANCE.csv').set_index(['panel_id','method','metric'])
    pools={p['pool_id']:p['meta'] for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    rows=[];configs=[];vectors=[];baseline_errors=[];coverage=[]
    for panel in panels.itertuples():
        keys=links.loc[links.panel_id.eq(panel.panel_id),'team_key'].tolist()
        original=before.loc[keys];current=after.loc[keys]
        assert original.k.eq(panel.n).all()
        meta={c:getattr(panel,c) for c in ['panel_id','image','building','n','source_domain']}
        meta['difficulty']=pools[original.pool_id.iloc[0]]['difficulty']
        vecs={m:frozen[m].loc[[(panel.panel_id,k) for k in keys]].to_numpy() for m in bridge.METHODS}
        for m in maps:
            lm=maps[m];classes=sorted({v for (b,w),v in lm.items() if b==panel.building});vs=[]
            for key in keys:
                ws=members.at[key,'member_workers'].split('|')
                assert all((panel.building,w) in lm for w in ws),(panel.panel_id,m,key)
                counts=Counter(lm[panel.building,w] for w in ws)
                vs.append('|'.join(f'{c}:{counts[c]}' for c in classes))
            vecs[m+'_V21']=np.array(vs)
            vectors.extend(dict(panel_id=panel.panel_id,team_key=k,method=m,class_counts=v) for k,v in zip(keys,vs))
        coverage.append(dict(panel_id=panel.panel_id,teams=len(keys),shared_known_teams=len(keys),updated_endpoints=sum(k in updated for k in keys)))
        for m,vec in vecs.items():
            for metric in bridge.METRICS:
                if m in bridge.METHODS:
                    baseline=bridge.decompose(original[metric].to_numpy(float),vec)
                    old=prior.loc[(panel.panel_id,m,metric)]
                    for field in ['total_variance','within_variance','between_variance']:
                        assert np.isclose(baseline[field],old[field],atol=1e-10,equal_nan=True)
                        if np.isfinite(baseline[field]):baseline_errors.append(abs(baseline[field]-old[field]))
                vals=current[metric].to_numpy(float);d=bridge.decompose(vals,vec)
                rows.append(dict(**meta,method=m,metric=metric,teams=len(keys),**d))
                for v in sorted(set(vec)):
                    selected=vals[vec==v];y=selected[np.isfinite(selected)];q=np.quantile(y,[.05,.25,.5,.75,.95]) if len(y) else [np.nan]*5
                    configs.append(dict(**meta,method=m,metric=metric,class_counts=v,teams=len(selected),valid_teams=len(y),missing_teams=len(selected)-len(y),mean=np.mean(y) if len(y) else np.nan,p05=q[0],p25=q[1],median=q[2],p75=q[3],p95=q[4],sd=np.std(y) if len(y)>1 else np.nan))
    d=pd.DataFrame(rows)
    assert np.allclose(d.total_variance,d.within_variance+d.between_variance,atol=1e-10,equal_nan=True)
    pivot=d.pivot(index=['panel_id','metric'],columns='method',values='between_variance')
    assert (pivot.DSTRUCT_K3_V21-pivot.DSTRUCT_K2_V21).dropna().ge(-1e-9).all()
    for name,frame in [('PANEL_VARIANCE',d),('SUMMARY',bridge.macro(d)),('CONFIGURATIONS',pd.DataFrame(configs)),('PANEL_COVERAGE',pd.DataFrame(coverage)),('TEAM_CONFIGURATION_LINKS',pd.DataFrame(vectors))]:
        frame.to_csv(TARGET/(name+'.csv.gz'),index=False,encoding='utf-8-sig')
    receipt=dict(panels=len(panels),images=panels.image.nunique(),buildings=panels.building.nunique(),team_links=len(links),unique_endpoints=links.team_key.nunique(),updated_unique_endpoints=len(updated),baseline_rows_verified=len(prior),baseline_max_error=max(baseline_errors),variance_identity_max_error=float((d.total_variance-d.within_variance-d.between_variance).abs().max()),unknown_label_teams=0,design='frozen_actual_teams_old_and_current_labels',new_pool_panels_included=False)
    (TARGET/'CHECKS.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True)
    print(bridge.macro(d).query('scope=="all" and metric=="B8L2"')[['method','between_share']].to_string(index=False),flush=True)


if __name__=='__main__':main()
