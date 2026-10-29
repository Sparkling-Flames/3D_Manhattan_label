"""Separate no connection, fewer than four nodes and invalid scoring footprint."""
from pathlib import Path
import argparse
import pandas as pd
from measure_registered_events import save,jsave

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--endpoints',required=True);ap.add_argument('--roles',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 e=pd.read_csv(a.events,low_memory=False);s=pd.read_csv(a.endpoints,usecols=lambda c:c in ['team_key','B8L2','score_status','geometry_status','geometry_reason','complete_evaluable'],low_memory=False)
 r=pd.read_csv(a.roles,usecols=['event_id','role_direction']);e=e.merge(r,on='event_id',validate='one_to_one');rows=[]
 for arm in [x for x in 'ABC' if x+'_team_key' in e]:
  z=e[['event_id','method','pool_id','image','building','n','m','role_direction',arm+'_team_key']].rename(columns={arm+'_team_key':'team_key'}).merge(s,on='team_key',validate='many_to_one');z['arm']=arm;rows.append(z)
 d=pd.concat(rows,ignore_index=True);bad=d[d.B8L2.isna()].copy();save(out/'UNSCORABLE_EVENT_ARMS_WITH_CAUSES.csv.gz',bad)
 keys=['method','role_direction','n','m','arm','score_status','geometry_status','geometry_reason'];q=bad.groupby(keys,dropna=False).agg(event_arm_count=('event_id','size'),unique_endpoints=('team_key','nunique'),images=('image','nunique'),buildings=('building','nunique')).reset_index();save(out/'FAILURE_CAUSES_BY_CONDITION.csv',q)
 q=s[s.B8L2.isna()].groupby(['score_status','geometry_status','geometry_reason'],dropna=False).size().reset_index(name='unique_teams');save(out/'UNIQUE_ENDPOINT_FAILURE_CAUSES.csv',q)
 jsave(out/'COMPLETE.json',dict(events=len(e),endpoints=len(s),unscorable_event_arms=len(bad),unscorable_unique_endpoints=int(s.B8L2.isna().sum()),definitions='unscorable is broader than invalid footprint: score_status preserves no_connection / below_four / invalid_floor and native reasons'))
 print(q.to_string(index=False),flush=True)
if __name__=='__main__':main()
