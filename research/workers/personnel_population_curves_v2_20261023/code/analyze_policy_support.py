"""Roles that induce identical actual ordering are not independent evidence."""
from __future__ import annotations
import argparse
from itertools import combinations
from pathlib import Path
import pandas as pd
from register_population_orders import save_csv

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capacity',required=True);ap.add_argument('--orders',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    c=pd.read_csv(a.capacity);orders=pd.read_csv(a.orders,keep_default_na=False)
    o={(r.pool_id,r.policy,r.base_path_id):r.workers for r in orders[orders.policy!='natural_random'].itertuples()}
    rows=[]
    for pid,g in c[c.eligible].groupby('pool_id'):
        for left,right in combinations(g.to_dict('records'),2):
            x=set(left['target_members'].split('|'));y=set(right['target_members'].split('|'))
            baseids={base for pool,policy,base in o if pool==pid and policy==left['policy']} & {base for pool,policy,base in o if pool==pid and policy==right['policy']}
            equal=sum(o[(pid,left['policy'],base)]==o[(pid,right['policy'],base)] for base in baseids)
            rows.append(dict(pool_id=pid,image=left['image'],building=left['building'],condition=left['condition'],layer=left['layer'],
                policy_a=left['policy'],policy_b=right['policy'],target_a=left['target_members'],target_b=right['target_members'],
                target_n_a=len(x),target_n_b=len(y),target_intersection=len(x&y),target_union=len(x|y),target_jaccard=len(x&y)/len(x|y),
                equal_target_set=x==y,paired_orders=len(baseids),equal_order_pairs=equal))
    d=pd.DataFrame(rows);save_csv(d,out/'POLICY_ROLE_OVERLAP.csv')
    s=d.groupby(['condition','layer','policy_a','policy_b']).agg(pools=('pool_id','size'),equal_target_pools=('equal_target_set','sum'),
                    mean_target_jaccard=('target_jaccard','mean'),paired_orders=('paired_orders','sum'),equal_order_pairs=('equal_order_pairs','sum')).reset_index()
    save_csv(s,out/'POLICY_ROLE_OVERLAP_SUMMARY.csv')
    print(s.to_string(index=False))

if __name__=='__main__':main()
