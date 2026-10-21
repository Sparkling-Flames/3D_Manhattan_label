"""Publish the strict matched overall results before larger slice tables finish.

This is the same frozen hierarchical mean/bootstrap as evaluate_matched_events,
restricted to its primary metrics and overall view. No endpoint is recomputed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from multin_design import HERE,gs,write_csv,sha
from evaluate_matched_events import PRIMARY


def run():
    metrics=PRIMARY+['same_B8L2','cross_B8L2','same_D10','cross_D10',
      'same_ref_node_recall_5','cross_ref_node_recall_5',
      'same_ref_edge_recall_5','cross_ref_edge_recall_5',
      'same_omission','cross_omission','same_extension','cross_extension',
      'same_recorded_time_pct','cross_recorded_time_pct']
    groups=['method_id','tier','condition','source_domain','design_scope','m_AB','n','difficulty','building','image','pool_id','panel_id']
    base=['method_id','tier','condition','source_domain','design_scope']
    needed=set(groups+metrics+['event_id','team_A','team_B','team_C','all_complete','all_scored','same_source_counts','source_and_historyQ5_matched'])
    results=[];inputs={}
    for stage in ['LARGE','PURE']:
        frames=[]
        for condition in ['manual','semi']:
            path=HERE/'matched'/f'{stage}_{condition.upper()}_COMPLETE_EVENTS.csv.gz'
            inputs[str(path.relative_to(HERE))]=sha(path)
            frames.append(pd.read_csv(path,usecols=lambda c:c in needed,low_memory=False))
        d=pd.concat(frames,ignore_index=True)
        for sensitivity,sub in [('unmatched_total_effect',d),('same_source_count',d[d.same_source_counts]),('source_history_Q5_matched',d[d.source_and_historyQ5_matched])]:
            if not len(sub):continue
            available=[c for c in metrics if c in sub]
            values=sub.groupby(groups,dropna=False)[available].mean().reset_index()
            im=values.groupby(base+['building','image','pool_id'],dropna=False)[available].mean().groupby(level=base+['building','image'],dropna=False).mean()
            buildings=im.groupby(level=base+['building'],dropna=False).mean().reset_index()
            for key,g in sub.groupby(base,dropna=False):
                meta=dict(zip(base,key));mask=np.ones(len(buildings),bool)
                for name,value in meta.items():mask &= buildings[name].eq(value).to_numpy()
                bb=buildings[mask]
                den=dict(events=len(g),all_complete_events=int(g.all_complete.sum()),all_scored_events=int(g.all_scored.sum()),
                  distinct_teams=len(set(g.team_A)|set(g.team_B)|set(g.team_C)),panels=g.panel_id.nunique(),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
                  n_min=int(g.n.min()),n_max=int(g.n.max()),m_min=int(g.m_AB.min()),m_max=int(g.m_AB.max()))
                for metric in available:
                    z=bb[metric].dropna().to_numpy(float);lo=hi=None
                    if len(z)>=3:
                        rng=np.random.default_rng(2026102187);bt=z[rng.integers(len(z),size=(2000,len(z)))].mean(axis=1);lo,hi=np.quantile(bt,[.025,.975])
                    results.append(dict(stage=stage,summary_view='overall',sensitivity=sensitivity,**meta,**den,
                      metric=metric,mean=float(z.mean()) if len(z) else None,valid_events=int(g[metric].notna().sum()),valid_buildings=len(z),lo95=lo,hi95=hi))
        print(stage,'complete',flush=True)
    target=HERE/'matched/STRICT_MATCHED_OVERVIEW.csv';write_csv(target,pd.DataFrame(results))
    receipt=dict(status='complete',rows=len(results),path=str(target.relative_to(HERE)),sha256=sha(target),bytes=target.stat().st_size,
      input_complete_event_sha256=inputs,native_calls=0,estimand='Same grouping and equal panel-cell/pool/image/building means as the full frozen matched summary; primary metrics plus directed component means, overall scope only.',
      bootstrap_resamples=2000,bootstrap_seed=2026102187)
    gs.save(target.with_suffix('.json'),receipt);print(receipt,flush=True)


if __name__=='__main__':run()
