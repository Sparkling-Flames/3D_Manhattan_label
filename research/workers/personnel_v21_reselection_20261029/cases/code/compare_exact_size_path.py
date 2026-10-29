#!/usr/bin/env python3
"""Compare fixed X/Y/Z nested-D traces by exact stored original observations.
The correspondence is diagnostic; it never equates independently numbered groups.
"""
import argparse,gzip,json
from pathlib import Path
import numpy as np,pandas as pd

def read(p):
 with gzip.open(p,'rt',encoding='utf-8-sig') as f:return json.load(f)
def members(s):return set(s.split('|'))-{''}
def signature(g):return {str(v.get('id'))+':'+str(v.get('source_pair_index')) for v in g.get('members',[])}
def write(d,p):
 q=p.with_name(p.name+'.writing');d.to_csv(q,index=False,encoding='utf-8-sig');q.replace(p)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--lower',required=True,type=Path);ap.add_argument('--higher',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
 a.out.mkdir(exist_ok=True,parents=True);lo,hi=read(a.lower),read(a.higher);el,eh=lo['event'],hi['event']
 assert el['pool_id']==eh['pool_id'] and el['method']==eh['method']
 assert all(members(el[b])==members(eh[b]) for b in ['X','Y','Z'])
 assert members(el['D'])<members(eh['D'])
 added=members(eh['D'])-members(el['D']);owner={r['object_id']:r['worker_id'] for r in hi['pool']['records']}
 links=[];rows=[];totals=[]
 for arm in 'ABC':
  lr,hr=lo['arms'][arm],hi['arms'][arm]
  lg=(lr.get('full_state')or{}).get('identity_groups',[]);hg=(hr.get('full_state')or{}).get('identity_groups',[])
  old_obs=set().union(*(signature(g)for g in lg)) if lg else set()
  for g in lg:
   sig=signature(g);linked=[]
   for h in hg:
    sig2=signature(h);overlap=len(sig&sig2)
    if not overlap:continue
    added_vote_workers={m.get('worker') or owner.get(m.get('id'))for m in h.get('members',[])}&added
    shared_old=len(sig2&old_obs)
    row=dict(arm=arm,lower_event=el['event_id'],higher_event=eh['event_id'],lower_feature=g['feature_id'],higher_feature=h['feature_id'],lower_support=g['support'],higher_support=h['support'],lower_threshold=lr['minimum_support'],higher_threshold=hr['minimum_support'],lower_selected=g['selected'],higher_selected=h['selected'],overlap_observations=overlap,lower_observations=len(sig),higher_observations=len(sig2),all_lower_observations_retained_in_this_group=sig<=sig2,higher_old_observations=shared_old,higher_added_worker_votes=len(added_vote_workers),higher_added_workers='|'.join(sorted(added_vote_workers)))
    links.append(row);linked.append(row)
   main=max(linked,key=lambda r:r['overlap_observations']) if linked else None
   kind='no_surviving_observation_group'
   if main:
    retained=main['all_lower_observations_retained_in_this_group'];selected_l=bool(g['selected']);selected_h=bool(main['higher_selected'])
    if selected_l and not selected_h and retained and main['higher_support']>=lr['minimum_support'] and main['higher_support']<hr['minimum_support']:
     kind='support_meets_old_threshold_but_not_new; retained_source_group'
    elif selected_l and not selected_h:kind='selection_lost_with_group_rearrangement_or_support_change'
    elif not selected_l and selected_h:kind='selection_gained'
    elif retained:kind='selected_state_same_and_original_group_retained'
    else:kind='selected_state_same_with_group_rearrangement'
   r=dict(arm=arm,lower_feature=g['feature_id'],linked_higher_groups=len(linked),mechanism_diagnostic=kind)
   if main:r.update(main)
   rows.append(r)
  tot=dict(arm=arm,n_lower=el['n'],n_higher=eh['n'],m=el['m'],added_D='|'.join(sorted(added)),minimum_support_lower=lr.get('minimum_support'),minimum_support_higher=hr.get('minimum_support'))
  for field in ['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h','source_time_total_seconds']:
   l,h=lr.get(field),hr.get(field);tot[field+'_lower']=l;tot[field+'_higher']=h;tot[field+'_change']=float(h)-float(l)if l is not None and h is not None else None
  totals.append(tot)
 write(pd.DataFrame(links),a.out/'EXACT_SHARED_OBSERVATION_GROUP_LINKS.csv');write(pd.DataFrame(rows),a.out/'GROUP_CHANGE_DIAGNOSTICS.csv');write(pd.DataFrame(totals),a.out/'SIZE_PATH_ARM_COMPONENTS.csv')
 report={'lower_event':el['event_id'],'higher_event':eh['event_id'],'pool_id':el['pool_id'],'method':el['method'],'same_XYZ':True,'nested_D':True,'new_fusions':0,'new_scores':0,'group_link_key':'exact object_id:source_pair_index observations; group IDs are not identities across endpoints','diagnostic_note':'Threshold label applies only to linked retained observations. Output geometry/connection still inspected separately.'}
 (a.out/'SIZE_PATH_PROVENANCE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
