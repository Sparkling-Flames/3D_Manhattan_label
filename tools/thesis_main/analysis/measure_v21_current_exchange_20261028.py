"""原生严格ABC指标；仅汇总端点齐全的池，可复用已完成统计分片。"""
import argparse
import gzip
import importlib.util
import json
import sys
import types
from collections import defaultdict
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .register_v21_exchange_20261028 import SOURCE
from .fuse_v21_new_pools_20261028 import adapter


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main(partial=False):
    source=types.ModuleType('run_native');source.ROOT=OUT/'current_exchange_design';source.POP=ROOT
    source.read=read;source.save=lambda p,v:None;source.csv=lambda p,v:None
    sys.modules['run_native']=source
    measurement=load(SOURCE/'measure_events.py','v21_measurement')
    prefix=load(ROOT/'research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py','v21_prefix_geometry')
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    reused=defaultdict(dict)
    with gzip.open(OUT/'current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);reused[r['pool_id']][r['team_key']]=r
    native=adapter()
    with native.Engine(full_state=False) as engine:
        for stage in ['confirm','reverse_confirm']:
            events=pd.read_csv(OUT/f'current_exchange_design/design/{stage}/EVENTS_EXACT.csv.gz')
            target=OUT/'current_exchange_results'/stage;(target/'metric_shards').mkdir(parents=True,exist_ok=True)
            done=[];pending=[]
            for pid,ev in events.groupby('pool_id',sort=False):
                path=target/'metric_shards'/(pid+'.csv.gz')
                if path.exists():
                    d=pd.read_csv(path,low_memory=False)
                    assert list(d.event_id)==list(ev.event_id)
                    done.append(d);continue
                rows=dict(reused[pid])
                for p in (OUT/'current_exchange_endpoints'/pid).glob('part_*.jsonl.gz'):
                    with gzip.open(p,'rt',encoding='utf8') as f:
                        for line in f:
                            r=json.loads(line);assert r['team_key'] not in rows;rows[r['team_key']]=r
                needed=set(ev.A_team_key)|set(ev.B_team_key)|set(ev.C_team_key)
                if not needed<=rows.keys():pending.append(pid);continue
                pool=pools[pid];ready={}
                for key in sorted(needed):
                    r=prefix.normalize(rows[key],pool);assert r['team_key']==key and r['k']>=3
                    ready[key]=prefix.geometry_enrich(r,pool,engine.fr)
                d=measurement.compute_events(ev,ready,pool)
                assert len(d)==len(ev) and d.event_id.is_unique
                d['data_release']='v2.1';tmp=path.with_name(path.name+'.tmp')
                d.to_csv(tmp,index=False,encoding='utf-8-sig',compression='gzip');tmp.replace(path)
                done.append(d);print(stage,pid,len(d),flush=True)
            merged=pd.concat(done,ignore_index=True) if done else pd.DataFrame()
            if len(merged):merged.to_csv(target/'EVENT_METRICS.csv.gz',index=False,encoding='utf-8-sig')
            receipt=dict(data_release='v2.1',stage=stage,registered_events=len(events),measured_events=len(merged),pending_pools=pending,complete=not pending,actual_teams='current_LOBO_labels_frozen_confirmation_grid',metrics='unchanged_native_strict_ABC_CA_CB_BA_and_geometry')
            (target/'COMPLETION.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
            print(json.dumps(receipt),flush=True)
            if pending and not partial:raise RuntimeError('端点尚未齐全；不可将部分结果发布为完整结果')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');main(p.parse_args().partial)
