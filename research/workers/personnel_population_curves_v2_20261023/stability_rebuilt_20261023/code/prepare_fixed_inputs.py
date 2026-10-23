#!/usr/bin/env python3
"""Column-select actual e92 population inputs; do not run fusion or rescore.

This script is a new fixed-design analysis implementation, not recovered bootstrap code.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, shutil
import numpy as np
import pandas as pd

COMMIT='e92abe8631d7f01dc192ee796b46f295ece37a6d'
BASE='research/workers/personnel_population_curves_v2_20261023/'
META=['pool_id','image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version']
METRICS=['B8L2','D10','nodes','floor_turn5_n','floor_redundant5_n','source_time_total_seconds','source_time_known_n','target_time_total_seconds','target_time_known_n','score_available','score_failure_nonpolicy','incomplete_nonpolicy','policy_deferred','complete_evaluable','geometry_status','order_status','connection_available','below_four']

def save(d,p):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,'wt',encoding='utf-8',newline='') as f:d.to_csv(f,index=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--originals',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    orders_path=a.originals/'design/EXACT_ORDER_DESIGN.csv.gz';orders=pd.read_csv(orders_path,low_memory=False)
    links_path=a.cache/'results/PREFIX_TEAM_LINKS.csv.gz';links=pd.read_csv(links_path,low_memory=False)
    scalar_path=a.cache/'results/ENDPOINT_SCALARS.csv.gz'
    chunks=[];n=0
    for part in pd.read_csv(scalar_path,usecols=lambda c:c in ['team_key','k']+META+METRICS,chunksize=50000,low_memory=False):
        chunks.append(part);n+=len(part);print('read_endpoint_rows',n,flush=True)
    s=pd.concat(chunks,ignore_index=True);assert len(s)==318816 and s.team_key.is_unique
    assert len(links)==404082 and not links.duplicated(['path_id','k']).any()
    q=links.merge(s.drop(columns=['pool_id','k']),on='team_key',how='left',validate='many_to_one',indicator=True)
    assert q._merge.eq('both').all();q=q.drop(columns='_merge')
    expected=orders[['path_id','pool_id','pool_n','policy','base_path_id']].set_index('path_id')
    for pid,g in q.groupby('path_id',sort=False):
        r=expected.loc[pid];assert len(g)==r.pool_n and set(g.k)==set(range(1,int(r.pool_n)+1))
        assert g.pool_id.eq(r.pool_id).all() and g.policy.eq(r.policy).all()
    assert len(expected)==q.path_id.nunique()==12398
    # Read the formal restored 04C to EOF, confirm all paired keys and saved quality.
    evp=a.cache/'events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz'
    ev=pd.read_csv(evp,usecols=['path_id','base_path_id','k','priority_team_key','natural_team_key','B8L2_priority','B8L2_natural','B8L2_delta'],low_memory=False)
    assert len(ev)==229050 and not ev.duplicated(['path_id','k']).any()
    nat=q[q.policy.eq('natural_random')][['path_id','k','team_key','B8L2']].rename(columns={'path_id':'base_path_id','team_key':'natural_team_key','B8L2':'B8L2_natural'})
    pol=q[~q.policy.eq('natural_random')][['path_id','base_path_id','k','team_key','B8L2']].rename(columns={'team_key':'priority_team_key','B8L2':'B8L2_priority'})
    pol=pol.merge(nat,on=['base_path_id','k'],validate='many_to_one');pol['B8L2_delta']=pol.B8L2_priority-pol.B8L2_natural
    ch=ev.merge(pol,on=['path_id','base_path_id','k'],suffixes=('_04c','_join'),validate='one_to_one')
    assert len(ch)==len(ev)
    for c in ['priority_team_key','natural_team_key']:assert ch[c+'_04c'].equals(ch[c+'_join'])
    for c in ['B8L2_priority','B8L2_natural','B8L2_delta']:assert np.allclose(ch[c+'_04c'],ch[c+'_join'],rtol=0,atol=1e-10,equal_nan=True)
    save(q,a.out/'PREFIX_VALUES_COMPACT.csv.gz')
    shutil.copyfile(orders_path,a.out/'EXACT_ORDER_DESIGN.csv.gz')
    shutil.copyfile(a.originals/'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv',a.out/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
    files=[]
    for p in [orders_path,links_path,scalar_path,evp]:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        files.append(dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest(),read_csv_to_eof=True))
    rec=dict(source_commit=COMMIT,operation='new_column_selection_and_full_join_of_fixed_original_design',new_fusion=0,new_design=0,new_scoring=0,endpoint_rows=len(s),prefix_rows=len(q),path_rows=len(orders),natural_paths=int(orders.policy.eq('natural_random').sum()),formal_04c_rows=len(ev),formal_04c_keys_and_quality_match=True,prefix_columns=list(q),sources=files)
    (a.out/'INPUT_READ_RECEIPT.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in rec.items() if k not in ['prefix_columns','sources']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
