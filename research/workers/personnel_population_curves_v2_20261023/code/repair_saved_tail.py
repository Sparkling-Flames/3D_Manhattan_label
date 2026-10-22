"""Repair only explicitly missing registered sets in already finished pools.

Never treats a completion receipt as proof that all endpoint rows are present.
Old saved rows are retained; only the identified missing sets are recomputed.
"""
import argparse,json
from pathlib import Path
import pandas as pd
from run_prefix_endpoints import setup,make_links,read,save,compute_pool

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True)
    p.add_argument('--orders',required=True);p.add_argument('--pool',required=True,action='append');a=p.parse_args()
    out=Path(a.out);gs,fe,fr,sg=setup(a.repo);pools=gs.pool_lookup()
    orders=pd.read_csv(a.orders,keep_default_na=False);orders=orders[orders.pool_id.isin(a.pool)]
    links,needed=make_links(orders);repairs=[]
    for pid in a.pool:
        payload=read(out/'endpoints'/(pid+'.json.gz'));present={r['team_key'] for r in payload['teams']}
        missing=sorted(set(needed[pid])-present)
        if not missing:continue
        original=read(out/'receipts'/(pid+'.json'))
        assert original['available']==original['requests'], 'Only repair already finished pools'
        save(out/'repair_original_receipts'/(pid+'.json'),original)
        result=compute_pool(a.repo,str(out),pools[pid],needed[pid],{})
        repaired=read(out/'endpoints'/(pid+'.json.gz'))
        assert {r['team_key'] for r in repaired['teams']}==set(needed[pid])
        assert result['new_native']==len(missing)
        old=dict(original);old.update(available=len(repaired['teams']),
            saved_tail_repaired=True,additional_native_calls=len(missing))
        save(out/'receipts'/(pid+'.json'),old)
        repairs.append(dict(pool_id=pid,original_saved_rows=len(present),requested=len(needed[pid]),
            restored_missing_sets=missing,additional_native_calls=len(missing),
            old_saved_rows_preserved=True,reference_and_algorithm_unchanged=True))
    save(out/'SAVED_TAIL_REPAIR.json',dict(repairs=repairs,
        additional_native_calls=sum(x['additional_native_calls'] for x in repairs),
        scope='Finished-pool receipt versus actual endpoint-table discrepancy; only absent member sets recomputed.'))
    print(json.dumps(repairs,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
