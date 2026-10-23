"""每池/结果状态及两机制例的定向原生重融重评分；不改冻结算法。"""
from pathlib import Path
import argparse
import gzip
import importlib.util
import json
import sys
import numpy as np
import pandas as pd


def same(a,b,path=''):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b),(path,'keys')
        for k in a:same(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b),(path,'length')
        for i,(x,y) in enumerate(zip(a,b)):same(x,y,path+'/'+str(i))
    elif isinstance(a,(float,int)) and not isinstance(a,bool):
        assert b is not None and np.isclose(a,b,atol=1e-8,rtol=1e-10),(path,a,b)
    else:assert a==b,(path,a,b)


def main(root,out):
    out.mkdir(parents=True,exist_ok=True)
    s=pd.read_csv(root/'native_endpoints/ENDPOINT_SCALARS.csv.gz',low_memory=False).sort_values('team_key')
    chosen=set(s.groupby(['pool_id','score_status']).head(1).team_key)
    events=pd.read_csv(root/'design/STRICT_ABC_EVENTS.csv.gz',usecols=lambda c:c=='event_id' or c.startswith('team_'))
    case_ids=['ABC_0001066d44f97b218867','ABC_0e2d9ba183c4f886c588']
    for row in events[events.event_id.isin(case_ids)].to_dict('records'):
        chosen.update(v for k,v in row.items() if k.startswith('team_'))
    selected=s[s.team_key.isin(chosen)].copy()
    selected[['team_key','pool_id','k','score_status','geometry_shard','geometry_line_1based']].to_csv(out/'NATIVE_REPLAY_SELECTION.csv',index=False)
    saved={}
    for shard,z in selected.groupby('geometry_shard'):
        needed=set(z.geometry_line_1based)
        with gzip.open(root/'native_endpoints'/shard,'rt',encoding='utf-8') as f:
            for n,line in enumerate(f,1):
                if n in needed:
                    row=json.loads(line);saved[row['team_key']]=row
    spec=importlib.util.spec_from_file_location('audit_native_runner',root/'engine/native_team_runner.py')
    native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
    pools=native.gs.pool_lookup();results=[]
    fields=['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100','nodes',
            'fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','minimum_support','recorded_time_total_seconds']
    with native.FrozenNativeEngine(full_state=True) as engine:
        for pid,z in selected.groupby('pool_id',sort=True):
            engine.reset_pool()
            for r in z.itertuples():
                row=engine.evaluate(pools[pid],r.member_workers.split('|'))
                assert row['team_key']==r.team_key and row['score_status']==r.score_status
                assert row['complete_evaluable']==r.complete_evaluable
                errors=[]
                for c in fields:
                    a=row.get(c);b=getattr(r,c)
                    if pd.isna(b):assert a is None or pd.isna(a),(r.team_key,c,a,b)
                    else:
                        assert a is not None and np.isclose(a,b,atol=1e-8,rtol=1e-10),(r.team_key,c,a,b)
                        errors.append(abs(float(a)-float(b)))
                same(row['geometry'],saved[r.team_key]['geometry'],'geometry')
                same(row['full_state'],saved[r.team_key]['full_state'],'full_state')
                results.append(dict(team_key=r.team_key,pool_id=pid,k=r.k,score_status=r.score_status,
                                    max_scalar_abs_error=max(errors,default=0),full_state_match=True))
            print('native replay',len(results),'/',len(selected),flush=True)
    pd.DataFrame(results).to_csv(out/'NATIVE_REPLAY_RESULTS.csv',index=False)
    receipt=dict(replayed_endpoints=len(results),pools=selected.pool_id.nunique(),
                 selection='lexicographically first team in every pool/score_status plus both six-team cases',
                 statuses=selected.score_status.value_counts().to_dict(),classification_refitted=False,
                 all_311333_endpoints_rerun=False,maximum_scalar_error=max(x['max_scalar_abs_error'] for x in results))
    (out/'NATIVE_REPLAY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root.resolve(),a.out)
