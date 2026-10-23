"""Describe Q-near block subdomains against their own shared design support.

The broader comparator includes the near-Q events. This is a conditional
association, not a causal removal of historical quality or an explained share.
No new teams, scoring, classification or fitted model is used.
"""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_events import boolean,write_csv,VERSION
from summarize_conditions import CFG

METRICS=['B8L2_within','B8L2_cross','B8L2_extra','B8L2_CA','B8L2_CB','B8L2_CS',
 'D10_extra','fusion_turn_n_extra','fusion_turn_n_CS','fusion_short_turn_edges_extra',
 'fusion_short_turn_edges_CS','fusion_redundancy_n_extra','fusion_redundancy_n_CS',
 'S_bottom_deg_extra','S_bottom_deg_CS','dir_extra','dir_CS','Hmean_extra','Hcenter_extra',
 'geometry_area_h2_extra','height_mean_h_extra','top_y_mean_px_extra','bottom_y_mean_px_extra',
 'score_failure_fraction','incomplete_fraction','CA_loss_gt5_fraction','CB_loss_gt5_fraction',
 'QT_time_ratio_CA','QT_time_ratio_CB']

def main(events,geometry,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    meta=list(dict.fromkeys(CFG+['event_id','ordinary_comparable','D_members','D_class_counts',
                  'X_members','Y_members','Z_members','source_role_key','target_role_key',
                  'history_Q_block_range','Q_common6']))
    e=pd.read_csv(events,usecols=lambda c:c in meta+METRICS,low_memory=False)
    e=e[boolean(e.ordinary_comparable)].copy();e['D_members']=e.D_members.fillna('')
    g=pd.read_csv(geometry,usecols=lambda c:c=='event_id' or c.startswith('geometry_') and c.endswith(('_within','_cross','_extra')),low_memory=False)
    e=e.merge(g,on='event_id',how='left',validate='one_to_one')
    metrics=METRICS+[c for c in g if c!='event_id']
    allstrata=[];outrows=[];support=[]
    for (method,condition),dd in e.groupby(['method','condition'],observed=True):
      for threshold in [2,5]:
        near=dd[dd.history_Q_block_range<=threshold]
        if not len(near):continue
        for mode,keys in [('same_configuration',CFG),('same_configuration_exact_D',CFG+['D_members'])]:
            means_all=dd.groupby(keys,dropna=False,observed=True)[metrics].mean().reset_index()
            means_near=near.groupby(keys,dropna=False,observed=True)[metrics].mean().reset_index()
            counts_all=dd.groupby(keys,dropna=False,observed=True).agg(events=('event_id','size'),quality_events=('Q_common6','sum')).reset_index()
            counts_near=near.groupby(keys,dropna=False,observed=True).agg(events=('event_id','size'),quality_events=('Q_common6','sum')).reset_index()
            means_all=means_all.merge(counts_all,on=keys,validate='one_to_one')
            means_near=means_near.merge(counts_near,on=keys,validate='one_to_one')
            match=means_near.merge(means_all,on=keys,suffixes=('_near','_all_on_support'),validate='one_to_one')
            match['threshold']=threshold;match['matching']=mode;allstrata.append(match)
            all_selected=dd.merge(near[keys].drop_duplicates(),on=keys,validate='many_to_one')
            support.append(dict(method=method,condition=condition,threshold=threshold,matching=mode,
                near_events=len(near),all_on_support_events=len(all_selected),near_Q_events=int(near.Q_common6.sum()),
                all_on_support_Q_events=int(all_selected.Q_common6.sum()),pairs=near.pair_key.nunique(),
                buildings=near.building.nunique(),configurations=len(near[CFG].drop_duplicates()),
                matched_strata=len(match),unique_near_Z_blocks=near.Z_members.nunique(),
                unique_near_XYZ_blocks=len(near[['X_members','Y_members','Z_members']].drop_duplicates()),
                unique_near_D_sets=near.D_members.nunique()))
            for metric in metrics:
                ns,alls=metric+'_near',metric+'_all_on_support'
                valid=match.dropna(subset=[ns,alls])
                if not len(valid):continue
                # Exact-D strata are averaged within each n/m configuration,
                # then configurations within physical pair, then optional building.
                cfg=valid.groupby(CFG,dropna=False,observed=True)[[ns,alls]].mean().reset_index()
                pair=cfg.groupby(['pair_key','building'],observed=True)[[ns,alls]].mean()
                b=pair.groupby('building').mean()
                r=dict(method=method,condition=condition,threshold=threshold,matching=mode,metric=metric,
                       valid_strata=len(valid),configurations=len(cfg),pairs=len(pair),buildings=len(b),
                       near_events=int(valid.events_near.sum()),all_on_support_events=int(valid.events_all_on_support.sum()),
                       near_Q_events=int(valid.quality_events_near.sum()),all_on_support_Q_events=int(valid.quality_events_all_on_support.sum()))
                for label,z in [('pair_equal',pair),('building_equal',b)]:
                    r[label+'_near']=float(z[ns].mean());r[label+'_all_on_support']=float(z[alls].mean())
                    r[label+'_difference']=float((z[ns]-z[alls]).mean())
                r['positive_near_pair_fraction']=float((pair[ns]>0).mean())
                outrows.append(r)
    write_csv(pd.concat(allstrata,ignore_index=True),out/'HISTORY_Q_MATCHED_STRATA.csv.gz')
    write_csv(pd.DataFrame(outrows),out/'HISTORY_Q_COMMON_SUPPORT_RESULTS.csv')
    write_csv(pd.DataFrame(support),out/'HISTORY_Q_DOMAIN_SUPPORT.csv')
    (out/'HISTORY_Q_ANALYSIS_RECEIPT.json').write_text(json.dumps({'version':VERSION,
      'new_fusion':0,'new_models':0,'thresholds':[2,5],
      'support_selection':'historical block Q range, pair/direction/n/m and optionally exact D; target quality used only for metric availability',
      'weighting':'strata -> configuration -> physical pair -> optional building',
      'interpretation':'Nested conditional comparison; no percentage of overall effect explained.'},ensure_ascii=False,indent=2)+'\n')
    print('history Q comparisons complete',len(outrows),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True);p.add_argument('--geometry',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.events,a.geometry,a.out)
