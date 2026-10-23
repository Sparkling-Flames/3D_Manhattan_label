"""Matched presence/absence subdomains of already registered ABC events.

Presence means the worker is in the union D/X/Y/Z. No new teams are generated
to make deletion possible. Selection uses capacity and participation, never Q.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_events import boolean,write_csv,VERSION

KEY=['pair_key','building','source_class','target_class','n','m','D_class_counts']
MET=['B8L2_within','B8L2_cross','B8L2_extra','B8L2_CA','B8L2_CB',
 'fusion_turn_n_extra','S_bottom_deg_extra','dir_extra','QT_time_ratio_CA',
 'CA_loss_gt5_fraction','score_failure_fraction','incomplete_fraction']

def pair_then_building(d,metric):
    p=d.groupby(['pair_key','building'],observed=True)[metric].mean()
    return float(p.mean()),float(p.groupby('building').mean().mean())

def main(events,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    e=pd.read_csv(events,low_memory=False)
    e=e[boolean(e.ordinary_comparable)&(e.method=='V3_BEHAVIOR')&(e.condition=='manual')].copy()
    e['universe_members']=(e.D_members.fillna('')+'|'+e.X_members+'|'+e.Y_members+'|'+e.Z_members).map(lambda x:set(str(x).split('|')))
    # The candidate list includes every observed member of a target class whose
    # common-pair capacity is <=10. This is a design capacity cutoff, not an outcome threshold.
    small=e[e.target_n<=10]
    workers=sorted(set('|'.join(small.Z_members).split('|'))-{''})
    selected=[];strata_all=[];summaries=[];roles=[]
    for worker in workers:
        target_mask=e.Z_members.map(lambda x:worker in str(x).split('|'))
        relevant=e.loc[target_mask,['pair_key','source_class','target_class']].drop_duplicates()
        dd=e.merge(relevant,on=['pair_key','source_class','target_class'],validate='many_to_one')
        if not len(dd):continue
        dd['present']=dd.universe_members.map(lambda x:worker in x)
        selected.append(dict(worker_id=worker,selection='target_class_capacity_le_10',
            relevant_events=len(dd),present_events=int(dd.present.sum()),absent_events=int((~dd.present).sum()),
            relevant_pairs=dd.pair_key.nunique(),relevant_buildings=dd.building.nunique(),
            observed_target_events=int(target_mask.sum()),minimum_target_capacity=int(dd.target_n.min()),
            maximum_target_capacity=int(dd.target_n.max()),has_any_legal_absence=bool((~dd.present).any())))
        rr=dd[['building','source_class','target_class','source_role','target_role']].drop_duplicates().copy();rr['worker_id']=worker;roles.append(rr)
        for mode,keys in [('class_composition_background',KEY),('exact_D',KEY+['D_members'])]:
            dd['D_members']=dd.D_members.fillna('')
            agg=dd.groupby(keys+['present'],dropna=False,observed=True)[MET].mean().reset_index()
            counts=dd.groupby(keys+['present'],dropna=False,observed=True).agg(
              events=('event_id','size'),quality_events=('Q_common6','sum')).reset_index()
            agg=agg.merge(counts,on=keys+['present'],validate='one_to_one')
            yes=agg[agg.present].drop(columns='present');no=agg[~agg.present].drop(columns='present')
            match=yes.merge(no,on=keys,suffixes=('_present','_absent'),validate='one_to_one')
            match['worker_id']=worker;match['matching']=mode
            strata_all.append(match)
            row=dict(worker_id=worker,matching=mode,relevant_events=len(dd),
                relevant_Q_events=int(dd.Q_common6.sum()),relevant_pairs=dd.pair_key.nunique(),
                relevant_buildings=dd.building.nunique(),matched_strata=len(match),
                matched_pairs=match.pair_key.nunique(),matched_buildings=match.building.nunique(),
                present_events_retained=int(match.events_present.sum()),
                absent_events_retained=int(match.events_absent.sum()),
                events_retained=int(match.events_present.sum()+match.events_absent.sum()),
                status='matched_subdomain' if len(match) else 'capacity_or_design_limited_no_legal_matched_absence')
            row['event_retention_fraction']=row['events_retained']/len(dd)
            qmatch=match.dropna(subset=['B8L2_extra_present','B8L2_extra_absent'])
            row['matched_Q_strata']=len(qmatch)
            original=dd.groupby(['pair_key','building','source_class','target_class','n','m'],observed=True)[MET].mean().reset_index()
            for metric in MET:
                pe,be=pair_then_building(original,metric)
                row['original_pair_equal__'+metric]=pe;row['original_building_equal__'+metric]=be
                common_metric=match.dropna(subset=[metric+'_present',metric+'_absent'])
                for state in ['present','absent']:
                    if len(common_metric):pe,be=pair_then_building(common_metric,metric+'_'+state)
                    else:pe=be=np.nan
                    row[f'matched_{state}_pair_equal__{metric}']=pe
                    row[f'matched_{state}_building_equal__{metric}']=be
            if len(qmatch):
                pp=qmatch.groupby(['pair_key','building'],observed=True)[['B8L2_extra_present','B8L2_extra_absent']].mean()
                row['matched_absent_positive_pair_fraction']=float((pp.B8L2_extra_absent.dropna()>0).mean())
                row['matched_present_positive_pair_fraction']=float((pp.B8L2_extra_present.dropna()>0).mean())
                row['matched_Q_pairs']=int(pp.dropna().shape[0])
                row['matched_Q_buildings']=pp.dropna().reset_index().building.nunique()
                row['Q_events_retained']=int(qmatch.quality_events_present.sum()+qmatch.quality_events_absent.sum())
            else:
                row['matched_Q_pairs']=row['matched_Q_buildings']=row['Q_events_retained']=0
            summaries.append(row)
    write_csv(pd.DataFrame(selected),out/'MEMBER_SELECTION_AND_CAPACITY.csv')
    write_csv(pd.concat(roles,ignore_index=True) if roles else pd.DataFrame(),out/'MEMBER_FOLD_ROLES.csv')
    write_csv(pd.concat(strata_all,ignore_index=True) if strata_all else pd.DataFrame(),out/'MEMBER_MATCHED_STRATA.csv.gz')
    write_csv(pd.DataFrame(summaries),out/'MEMBER_MATCHED_SUMMARY.csv')
    (out/'MEMBER_ANALYSIS_RECEIPT.json').write_text(json.dumps({'version':VERSION,
        'candidate_members':len(workers),'new_teams_generated':0,'presence_definition':'union(D,X,Y,Z)',
        'matching_wide':KEY,'matching_exact':KEY+['D_members'],
        'interpretation':'Only legal matched subdomains; no general deletion robustness claim.'},ensure_ascii=False,indent=2))
    print('member summaries complete',len(workers),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.events,a.out)
