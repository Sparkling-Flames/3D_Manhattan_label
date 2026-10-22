"""Create an explicitly partial analysis input from atomically finished pools."""
from __future__ import annotations
import argparse,gzip,hashlib,json
from pathlib import Path
import pandas as pd
from register_population_orders import save_csv,write_bytes

def main():
    p=argparse.ArgumentParser();p.add_argument('--results-dir',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();source=Path(a.results_dir);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    receipts=sorted((source/'receipts').glob('*.json'))
    ids={p.stem for p in receipts}
    links=pd.read_csv(source/'PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    links=links[links.pool_id.isin(ids)]
    rows=[]
    for pid in sorted(ids):
        data=json.load(gzip.open(source/'endpoints'/(pid+'.json.gz'),'rt'))
        for r in data['teams']:
            s={k:v for k,v in r.items() if not isinstance(v,(list,dict))}
            s['member_workers']='|'.join(r['member_workers'])
            rows.append(s)
    scalars=pd.DataFrame(rows)
    assert not scalars.team_key.duplicated().any()
    joined=links.merge(scalars[[x for x in scalars if x not in links or x=='team_key']],on='team_key',how='left',validate='many_to_one')
    assert joined.image.notna().all()
    save_csv(joined,out/'PREFIX_RESULTS_PARTIAL.csv.gz')
    receipt=dict(status='PARTIAL_finished_pools_only_not_population_final',pools=len(ids),pool_ids=sorted(ids),
                 paths=joined.path_id.nunique(),prefixes=len(joined),unique_endpoints=joined.team_key.nunique(),
                 selection='which pools had atomically completed when this snapshot was materialized; not a representative subset',
                 completed_receipts_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in receipts})
    write_bytes(out/'PARTIAL_INPUT_RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print({k:receipt[k] for k in ['status','pools','paths','prefixes','unique_endpoints']},flush=True)

if __name__=='__main__':main()
