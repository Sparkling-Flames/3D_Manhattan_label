"""Recreate per-pool endpoint containers from the nonduplicated delivery tables.

This is serialization only: no fusion, score or geometry is recomputed.
"""
import argparse,hashlib,json,math
from pathlib import Path
import pandas as pd
from run_prefix_endpoints import read,save,clean

def main():
    p=argparse.ArgumentParser();p.add_argument('--scalars',required=True);p.add_argument('--geometry',required=True)
    p.add_argument('--snapshot',required=True);p.add_argument('--out',required=True);p.add_argument('--pool',action='append');a=p.parse_args()
    data=pd.read_csv(a.scalars,low_memory=False)
    if a.pool:data=data[data.pool_id.isin(a.pool)]
    keys=set(data.team_key);geometry={r['team_key']:r for r in read(a.geometry) if r['team_key'] in keys}
    snapshot={r['pool_id']:r for r in read(a.snapshot)['images']};out=Path(a.out)
    total=0
    for pid,group in data.groupby('pool_id',sort=False):
        rows=[]
        for row in group.to_dict('records'):
            row=clean(row)
            for name in ('member_workers','member_object_ids'):
                row[name]=row[name].split('|') if row.get(name) else []
            saved=geometry.get(row['team_key'],{});row['geometry']=saved.get('geometry')
            if 'node_supports' in saved:row['node_supports']=saved['node_supports']
            elif row.get('node_supports') is not None:row['node_supports']=[int(float(x)) for x in str(row['node_supports']).split('|') if x]
            for threshold in (5,9):
                for kind in ('nodes','edges'):
                    field=f'ref_matched_{kind}_{threshold}';value=row.get(field)
                    available=row.get(f'ref_{"node" if kind=="nodes" else "edge"}_recall_{threshold}') is not None
                    row[field]=[int(float(x)) for x in str(value).split('|') if x] if value is not None else ([] if available else None)
            rows.append(row)
        digest=hashlib.sha256(json.dumps(clean(snapshot[pid]),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        save(out/'endpoints'/(pid+'.json.gz'),dict(pool_id=pid,pool_input_sha256=digest,teams=rows))
        total+=len(rows)
    save(out/'TABLE_RESTORATION.json',dict(pools=data.pool_id.nunique(),endpoints=total,new_fusions=0,new_scores=0,
        scalar_source=a.scalars,geometry_source=a.geometry))
    print('restored',total,'endpoint containers with zero fusion calls')

if __name__=='__main__':main()
