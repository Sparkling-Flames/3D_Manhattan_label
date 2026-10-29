"""Audit what the previous same-pool Q baseline actually held fixed."""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np

def main(repo,history,out):
    w=Path(repo)/'research/workers/personnel_v21_reselection_20261029';out=Path(out);out.mkdir(parents=True,exist_ok=True)
    e=pd.read_csv(w/'analysis/joint_baseline_comparison/ALL_TARGETED_BASELINE_EVENT_LINKS.csv.gz')
    l=pd.read_csv(w/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    q=l[l.method.eq('Q_MEDIAN2')].set_index(['heldout_building','worker_id']).axis_score
    h=pd.read_csv(history).set_index(['heldout_building','worker_id'])
    features={'official_q':q,'target_q':h.m_all_B8L2,'target_q_p20':h.m_all_B8L2_p20,'log_time':h.m_all_log_time}
    for label in ['D','X','Y','Z']:
        for feature,lookup in features.items():
            e[label+'_'+feature]=[np.mean([lookup.loc[(b,x)] for x in s.split('|')]) for s,b in zip(e[label],e.building)]
    for feature in features:
        e['ZX_'+feature]=e['Z_'+feature]-e['X_'+feature]
        e['ZY_'+feature]=e['Z_'+feature]-e['Y_'+feature]
    cols=[c for c in e if any(c.endswith('_'+f) for f in features)]
    p=e.groupby(['comparison_method','pool_id','image','building'])[cols].mean().reset_index()
    i=p.groupby(['comparison_method','image','building'])[cols].mean().reset_index()
    b=i.groupby(['comparison_method','building'])[cols].mean().reset_index()
    tables=[]
    for weight,table in [('image_equal',i),('building_equal',b)]:
        z=table.groupby('comparison_method')[cols].mean().reset_index();z['weighting']=weight;tables.append(z)
    pd.concat(tables,ignore_index=True).to_csv(out/'EXISTING_BASELINE_BLOCK_HISTORY_SUMMARY.csv',index=False)
    e.to_csv(out/'EXISTING_BASELINE_EVENT_HISTORY.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    a=e[e.comparison_method.eq('OPPJOINT_K4_selected_direction')];rows=[]
    for other in e.comparison_method.unique():
        if other=='OPPJOINT_K4_selected_direction':continue
        z=e[e.comparison_method.eq(other)]
        for keys in [['pool_id'],['pool_id','D'],['pool_id','A_team_key'],['pool_id','D','X','Y']]:
            j=a.merge(z,on=keys,suffixes=('_K4','_other'))
            rows.append(dict(other=other,keys='|'.join(keys),paired_links=len(j),K4_events=j.event_id_K4.nunique(),other_events=j.event_id_other.nunique(),pools=j.pool_id.nunique()))
    pd.DataFrame(rows).to_csv(out/'EXISTING_BASELINE_EXACT_CONTROL_OVERLAP.csv',index=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--history',required=True);p.add_argument('--out',required=True);a=p.parse_args();main(a.repo,a.history,a.out)
