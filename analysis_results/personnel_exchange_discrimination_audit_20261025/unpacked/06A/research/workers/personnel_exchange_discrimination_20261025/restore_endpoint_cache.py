"""Rehydrate delivered scalar/geometry batches into native per-pool cache files."""
import argparse,collections,hashlib,json
from pathlib import Path
import pandas as pd
from run_native import ROOT,POP,read,save,base,team_key

BATCHES={
 'screen':('results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz','results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz'),
 'batch02':('results/batch02/ENDPOINT_SCALARS.csv.gz','results/batch02/ENDPOINT_GEOMETRY.json.gz'),
 'size_paths':('results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz','results/size_paths/NATIVE_ENDPOINT_GEOMETRY.json.gz'),
 'large_team_ac_tail':('results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz','results/large_team_ac_tail/NATIVE_ENDPOINT_GEOMETRY.json.gz')}

def main(a):
    scalar,geometry=[ROOT/x for x in BATCHES[a.batch]]
    pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    if a.pool and not set(a.pool)<=pools.keys():raise ValueError('Unknown pool_id; read the saved pool inventory rather than inventing an ID.')
    records=collections.defaultdict(dict)
    for chunk in pd.read_csv(scalar,low_memory=False,chunksize=15000):
        if a.pool:chunk=chunk[chunk.pool_id.isin(a.pool)]
        for row in chunk.to_dict('records'):
            for field in ['member_workers','member_object_ids']:
                if isinstance(row.get(field),str):row[field]=row[field].split('|')
            for field in ['node_supports','ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9']:
                if isinstance(row.get(field),str):row[field]=[int(float(x)) for x in row[field].split('|') if x]
            row=base.clean(row);assert team_key(row['pool_id'],row['member_workers'])==row['team_key']
            row['geometry']=None;records[row['pool_id']][row['team_key']]=row
    for geo in read(geometry):
        pid=geo['pool_id'];key=geo['team_key']
        if key in records.get(pid,{}):records[pid][key].update(geometry=geo['geometry'],node_supports=geo.get('node_supports'))
    out=Path(a.output) if a.output else ROOT/'native';receipt=[]
    for pid,rows in records.items():
        # Exact frozen global_study.digest contract, without initializing scoring.
        digest=hashlib.sha256(json.dumps(base.clean(pools[pid]),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        dest=out/'endpoints'/(pid+'.json.gz');merged={}
        if dest.exists():
            old=read(dest);assert old['pool_input_sha256']==digest
            merged={r['team_key']:r for r in old['teams']}
        before=len(merged);merged.update(rows)
        save(dest,{'pool_id':pid,'pool_input_sha256':digest,'teams':list(merged.values())})
        receipt.append({'pool_id':pid,'batch_rows':len(rows),'previous_rows':before,'result_rows':len(merged)})
    save(out/('RESTORE_'+a.batch+'.json'),{'batch':a.batch,'scalar':str(scalar),'geometry':str(geometry),'fused_new_teams':0,'pools':receipt})
    print(json.dumps({'batch':a.batch,'pools':len(receipt),'restored_rows':sum(len(v) for v in records.values()),'fused_new_teams':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',choices=BATCHES,required=True);p.add_argument('--pool',action='append');p.add_argument('--output');main(p.parse_args())
