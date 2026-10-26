"""Describe frozen design overlap; this is capacity, not observed Q support."""
from pathlib import Path
import argparse, hashlib, sys
import pandas as pd


def main(base):
    base=base.resolve()
    sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json
    source=base/'design26/POOL_SAMPLING_PLAN.csv'
    plan=pd.read_csv(source)
    out=base/'analysis_reporting26/results';out.mkdir(parents=True,exist_ok=True)
    cols=['pool_id','image','building','layer','difficulty','pool_n']
    d=plan[cols].copy()
    d['ordinary_fixed_N_ge_30']=d.layer.eq('ordinary_manual')&d.pool_n.ge(30)
    d['ordinary_fixed_N_ge_35']=d.layer.eq('ordinary_manual')&d.pool_n.ge(35)
    d['historical_four_policy_support']=plan.policy_common_pool.astype(str).str.lower().eq('true')
    d['panel_relation']=['both' if a and b else 'natural30_only' if a else 'policy_only' if b else 'neither'
        for a,b in zip(d.ordinary_fixed_N_ge_30,d.historical_four_policy_support)]
    d['scope']='registered capacity/role-label support; not a quality-valid sample count'
    rows=[]
    for relation,g in d.groupby('panel_relation'):
        rows.append(dict(panel_relation=relation,pools=len(g),buildings=g.building.nunique(),
            N_min=int(g.pool_n.min()),N_max=int(g.pool_n.max()),scope=d.scope.iloc[0]))
    save_csv(d,out/'REGISTERED_PANEL_MEMBERSHIP.csv')
    save_csv(pd.DataFrame(rows),out/'REGISTERED_PANEL_OVERLAP.csv')
    assert d.ordinary_fixed_N_ge_30.sum()==157 and d.historical_four_policy_support.sum()==157
    save_json(dict(input=str(source.relative_to(base)),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        pools=len(d),same_numeric_count_is_not_same_image_set=True,
        overlapping_pools=int(d.panel_relation.eq('both').sum()),new_endpoints=0,new_orders=0),
        out/'REGISTERED_PANEL_DESCRIPTION_RECEIPT.json')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    main(ap.parse_args().base)
