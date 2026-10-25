"""Direct AC only: never create a fictitious same-class B comparison."""
import argparse
import numpy as np
import pandas as pd
from run_native import ROOT,POP,read,save,csv
from measure_events import METRICS,geometry_metrics,refdiagnostic

def compute(ev,rows,pool):
    for r in rows.values():refdiagnostic(r,pool)
    scalars=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows.values()]).set_index('team_key')
    avail=[m for m in METRICS if m in scalars];extra={}
    assert not any(c.startswith('B_team') or c.startswith('B_members') for c in ev.columns)
    for arm in ['A','C']:
        ar=scalars.reindex(ev[arm+'_team_key']);ar.index=ev.index
        extra[arm+'_failed']=~ar.B8L2.notna()
        extra[arm+'_incomplete']=~ar.complete_evaluable.fillna(False).astype(bool)
        for metric in avail:extra[arm+'_'+metric]=pd.to_numeric(ar[metric],errors='coerce')
    for metric in avail:
        delta=extra['C_'+metric]-extra['A_'+metric]
        extra[metric+'_CA']=delta;extra[metric+'_abs_CA']=delta.abs()
    extra['AC_scored']=~(extra['A_failed']|extra['C_failed'])
    q=extra['B8L2_CA']
    extra['C_loss10_CA']=np.where(q.notna(),(q<-10).astype(float),np.nan)
    extra['C_improved_CA']=np.where(q.notna(),(q>0).astype(float),np.nan)
    extra['C_failure_or_loss10_CA']=np.where(~extra['A_failed'],(extra['C_failed']|pd.Series(extra['C_loss10_CA'],index=ev.index).eq(1)).astype(float),np.nan)
    extra['record_time_CA_pct']=100*(extra['C_source_time_total_seconds']/extra['A_source_time_total_seconds']-1)
    geos=[];cache={}
    for event in ev.to_dict('records'):
        key=tuple(sorted([event['A_team_key'],event['C_team_key']]))
        if key not in cache:cache[key]=geometry_metrics(rows[key[0]],rows[key[1]])
        geos.append({k+'_AC':v for k,v in cache[key].items()})
    return pd.concat([ev,pd.DataFrame(extra,index=ev.index),pd.DataFrame(geos,index=ev.index)],axis=1)

def main(args):
    events=pd.read_csv(ROOT/'design'/args.stage/'EVENTS_EXACT.csv.gz',low_memory=False)
    pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    out=ROOT/'results'/args.stage;out.mkdir(parents=True,exist_ok=True);done=[];pending=[]
    for pid,g in events.groupby('pool_id',sort=False):
        target=out/'metric_shards'/(pid+'.csv.gz')
        if target.exists():done.append(pd.read_csv(target,low_memory=False));continue
        p=ROOT/'native/endpoints'/(pid+'.json.gz')
        if not p.exists():pending.append(pid);continue
        rows={r['team_key']:r for r in read(p)['teams']};needed=set(g.A_team_key)|set(g.C_team_key)
        if not needed<=rows.keys():pending.append(pid);continue
        d=compute(g,{k:rows[k] for k in needed},pools[pid]);csv(target,d);done.append(d)
        print('MEASURED_DIRECT_AC',pid,len(d),flush=True)
    if done:csv(out/'EVENT_METRICS.csv.gz',pd.concat(done,ignore_index=True))
    save(out/'COMPLETION.json',dict(stage=args.stage,design='direct_AC_without_B',registered_events=len(events),measured_events=sum(len(x) for x in done),complete=not pending,pending_pools=pending,pools=len(done),same_class_comparison_available=False))
    if pending and not args.partial:raise RuntimeError(f'{len(pending)} pools pending')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',default='large_team_ac_tail');p.add_argument('--partial',action='store_true');main(p.parse_args())
