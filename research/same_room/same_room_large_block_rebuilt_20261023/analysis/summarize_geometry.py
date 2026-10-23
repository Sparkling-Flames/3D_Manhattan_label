"""Event-common corresponding-corner summaries from frozen geometry diagnostics."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_events import boolean,write_csv,VERSION
from summarize_conditions import CFG,subsets

ORDER=['a_AB','a_AC','a_BC','b_AB','b_AC','b_BC']

def main(events,geometry,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    meta=list(dict.fromkeys(CFG+['event_id','image_a','image_b','ordinary_comparable','layer_a','layer_b',
          'D_empty','history_Q_block_range','B8L2_extra','Q_common6','source_role_key','target_role_key']))
    e=pd.read_csv(events,usecols=meta,low_memory=False)
    keys=['event_id','view','comparison','status','same_count','complete','bev_mean_h','top_mean_h',
          'bev_max_h','top_max_h','angle_deg','high_angle_correspondence_warning','matched_reflex_disagreement_n']
    g=pd.read_csv(geometry,usecols=lambda c:c in keys,low_memory=False)
    if len(g)!=6*len(e):raise ValueError('Each event must have exactly six within-view geometry contrasts')
    g['view_comparison']=g.view+'_'+g.comparison
    if g.duplicated(['event_id','view_comparison']).any():raise ValueError('Repeated event geometry key')
    base=e.set_index('event_id')
    def matrix(name):
        return g.pivot(index='event_id',columns='view_comparison',values=name).reindex(index=base.index,columns=ORDER).to_numpy()
    status=matrix('status');unique=status=='unique_cyclic_candidate'
    cols=[]
    for metric in ['bev_mean_h','top_mean_h','bev_max_h','top_max_h','angle_deg','matched_reflex_disagreement_n']:
        x=matrix(metric).astype(float);valid=np.isfinite(x).all(axis=1)&unique.all(axis=1)
        base['geometry_common6_'+metric]=valid
        w=(x[:,0]+x[:,3])/2;c=x[:,[1,2,4,5]].mean(axis=1)
        for label,a in [('within',w),('cross',c),('extra',c-w)]:
            name='geometry_'+metric+'_'+label;base[name]=np.where(valid,a,np.nan);cols.append(name)
    base['geometry_all_unique6']=unique.all(axis=1)
    base['Q_geometry_joint6']=boolean(base.Q_common6)&base.geometry_all_unique6
    status_names=sorted(set(['different_corner_count','incomplete_geometry','missing_connected_geometry','ambiguous_cyclic_match'])|
                        (set(g.status.dropna().astype(str)) - {'unique_cyclic_candidate'}))
    for statusname in status_names:
        mask=status==statusname
        base['geometry_'+statusname+'_within']=mask[:,[0,3]].mean(axis=1)
        base['geometry_'+statusname+'_cross']=mask[:,[1,2,4,5]].mean(axis=1)
        base['geometry_'+statusname+'_extra']=base['geometry_'+statusname+'_cross']-base['geometry_'+statusname+'_within']
        cols += ['geometry_'+statusname+'_'+z for z in ['within','cross','extra']]
    warn=matrix('high_angle_correspondence_warning')
    # Non-applicable diagnostics are not interpreted as absence of a warning.
    wb=np.vectorize(lambda x:str(x).lower() in ['true','1','1.0'])(warn)
    base['geometry_any_high_angle_warning']=np.where(unique.all(axis=1),wb.any(axis=1).astype(float),np.nan)
    cols+=['geometry_any_high_angle_warning','geometry_all_unique6','Q_geometry_joint6']
    event=base.reset_index();write_csv(event,out/'EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz')
    pairrows=[];overall=[]
    for subset,method,condition,dd in subsets(event):
        for support in ['all_geometry_diagnostics','joint_Q_and_geometry']:
            dz=dd if support=='all_geometry_diagnostics' else dd[boolean(dd.Q_geometry_joint6)]
            if not len(dz):continue
            cfg=dz.groupby(CFG,dropna=False,observed=True)[cols+['B8L2_extra']].mean().reset_index()
            pair=cfg.groupby(['pair_key','building','groups'],dropna=False,observed=True)[cols+['B8L2_extra']].mean().reset_index()
            pair['subset']=subset;pair['method']=method;pair['condition']=condition;pair['support']=support
            pairrows.append(pair)
            be=pair.groupby('building',observed=True)[cols+['B8L2_extra']].mean()
            row=dict(subset=subset,method=method,condition=condition,support=support,events=len(dz),
                     pairs=dz.pair_key.nunique(),buildings=dz.building.nunique(),
                     six_unique_geometry_events=int(dz.geometry_all_unique6.sum()),
                     six_Q_and_geometry_events=int(dz.Q_geometry_joint6.sum()))
            for c in cols+['B8L2_extra']:
                row['pair_equal__'+c]=pair[c].mean();row['building_equal__'+c]=be[c].mean()
            for c in ['geometry_bev_mean_h_extra','geometry_top_mean_h_extra']:
                row['positive_pair_fraction__'+c]=float((pair[c].dropna()>0).mean())
                row['valid_pairs__'+c]=int(pair[c].notna().sum())
            overall.append(row)
    write_csv(pd.concat(pairrows,ignore_index=True),out/'GEOMETRY_PAIR_METRICS.csv.gz')
    write_csv(pd.DataFrame(overall),out/'GEOMETRY_CONDITIONS.csv')
    (out/'GEOMETRY_SUMMARY_RECEIPT.json').write_text(json.dumps({'version':VERSION,'events':len(e),
      'geometry_comparison_rows':len(g),'expected_rows':6*len(e),'new_fusion_calls':0,
      'distance_unit':'camera height h, not metres',
      'distance_support':'all six AB/AC/BC comparisons in both views have unique frozen cyclic correspondence'},ensure_ascii=False,indent=2))
    print('geometry summaries complete',len(e),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True);p.add_argument('--geometry',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.events,a.geometry,a.out)
