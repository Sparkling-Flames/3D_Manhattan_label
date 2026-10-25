"""Incrementally analyze each completed native pool; every pool is saved first.

This waits only for the already registered endpoint requests. It does not add
requests, change any random sequence, or select successful prefixes.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
from pathlib import Path
import time
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()
from geometry_sampling_precision import META,pool_run


def save_frame(frame,path):
    temp=path.with_name(path.name+'.tmp')
    frame.to_csv(temp,index=False,compression='gzip')
    temp.replace(path)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True);ap.add_argument('--results',required=True);ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--once',action='store_true');a=ap.parse_args()
    root=Path(a.study).resolve();out=Path(a.results).resolve();stage=out/'completed_pool_checkpoints';stage.mkdir(exist_ok=True)
    old=pd.read_csv(out/'OLD_NATURAL_LINKS.csv.gz',low_memory=False)
    new=pd.read_csv(root/'design/NEW_PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    new=new[new.policy.eq('natural_random')].copy();new['batch']=new.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
    links=pd.concat([old,new],ignore_index=True)
    orders=pd.read_csv(out/'OLD_NATURAL_ORDERS.csv.gz',low_memory=False)
    metas=orders.groupby('pool_id').first()[[c for c in META if c!='pool_id']].to_dict('index')
    by={pid:g for pid,g in links.groupby('pool_id',sort=False)}
    done={p.name.removesuffix('.precision.csv.gz') for p in stage.glob('*.precision.csv.gz') if p.with_name(p.name.replace('.precision.csv.gz','.intervals.csv.gz')).exists()}
    print('Resuming completed geometry pools',len(done),'/',len(by),flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        while len(done)<len(by):
            ready=[pid for pid in by if pid not in done and (root/'new_endpoints/parts'/pid/'POOL_RECEIPT.json').exists()]
            if ready:
                tasks={ex.submit(pool_run,pid,dict(pool_id=pid,**metas[pid]),by[pid],out/'old_pool_geometry_cache',[root/'new_endpoints',root/'engine/benchmark']):pid for pid in ready}
                for f in concurrent.futures.as_completed(tasks):
                    pid=tasks[f];ss,ii,mm=f.result()
                    if mm:raise ValueError('Completed pool still lacks exact endpoints: '+pid+' '+str(len(mm)))
                    save_frame(pd.DataFrame(ss),stage/(pid+'.precision.csv.gz'))
                    save_frame(pd.DataFrame(ii),stage/(pid+'.intervals.csv.gz'))
                    done.add(pid)
                    print('GEOMETRY_COMPLETE',len(done),len(by),pid,flush=True)
                (out/'INCREMENTAL_GEOMETRY_PROGRESS.json').write_text(json.dumps(dict(completed_pools=len(done),total_pools=len(by),completed_ids=sorted(done)),indent=2))
            if a.once:break
            if len(done)<len(by):time.sleep(15)
    if len(done)==len(by):
        stats=pd.concat([pd.read_csv(stage/(pid+'.precision.csv.gz')) for pid in sorted(done)],ignore_index=True)
        intervals=pd.concat([pd.read_csv(stage/(pid+'.intervals.csv.gz')) for pid in sorted(done)],ignore_index=True)
        save_frame(stats,out/'GEOMETRY_PATH_PRECISION.csv.gz')
        save_frame(intervals,out/'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz')
        pd.DataFrame(columns=['pool_id','path_id','k','team_key','batch']).to_csv(out/'GEOMETRY_UNCOMPUTED_LINKS.csv.gz',index=False)
        (out/'RUN_RECEIPT.json').write_text(json.dumps(dict(pools=len(done),geometry_metric_rows=len(stats),paired_interval_rows=len(intervals),uncomputed_links=0,fusion_calls=0,incremental_pool_checkpointing=True,uncertainty='whole-path delete-one jackknife'),indent=2))
        print('ALL_GEOMETRY_COMPLETE',len(stats),len(intervals),flush=True)


if __name__=='__main__':main()
