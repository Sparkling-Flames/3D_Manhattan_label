"""Count generated draws separately from distinct realized permutations."""
from pathlib import Path
import argparse,json,sys
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();base=a.base.resolve()
    sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json
    d=pd.read_csv(base/'design26/NEW_EXACT_ORDER_DESIGN.csv.gz',dtype={'seed':'string','master_seed':'string'},low_memory=False)
    assert len(d)==50400 and d.path_id.is_unique
    rows=[]
    for (pid,policy),g in d.groupby(['pool_id','policy']):
        for stage,h in [('all_new',g)]+[(str(s),x) for s,x in g.groupby('stage')]:
            rows.append(dict(pool_id=pid,image=h.image.iloc[0],building=h.building.iloc[0],pool_n=h.pool_n.iloc[0],
                layer=h.layer.iloc[0],policy=policy,stage=stage,generated_draw_or_derived_order_records=len(h),
                unique_realized_permutations=h.worker_order.nunique(),
                repeated_realized_permutation_records=len(h)-h.worker_order.nunique(),
                natural_independent_draws=len(h) if policy=='natural_random' else 0,
                paired_natural_bases=h.base_path_id.nunique()))
    out=base/'analysis_reporting26/results';out.mkdir(parents=True,exist_ok=True)
    z=pd.DataFrame(rows);save_csv(z,out/'REGISTERED_ORDER_DRAW_AND_DISTINCT_COUNTS.csv')
    n=d[d.policy.eq('natural_random')]
    receipt=dict(total_order_records=len(d),independent_uniform_natural_draws=len(n),
        distinct_realized_natural_permutations=int(n[['pool_id','worker_order']].drop_duplicates().shape[0]),
        derived_historical_policy_order_records=int(d.policy.ne('natural_random').sum()),
        paired_policy_bases=int(d.loc[d.policy.ne('natural_random'),['pool_id','base_path_id']].drop_duplicates().shape[0]),
        all_natural_draws_retained_with_occurrence_weight=True,
        repeated_permutations_are_legal_independent_draw_collisions=True,
        generated_independent_does_not_mean_sampling_without_replacement_across_paths=True)
    save_json(receipt,out/'REGISTERED_ORDER_COUNT_RECEIPT.json');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
