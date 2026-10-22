"""Image/building-equal component effects at key process positions."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from register_population_orders import save_csv,write_bytes


def phase_components(mt,perk):
    cols=['pool_id','image','building','condition','layer','difficulty','pool_n','policy','metric']
    means=['natural_mean','priority_mean','paired_mean_delta','paired_abs_delta',
           'natural_p10','priority_p10','natural_sd','priority_sd']
    tables=[]
    for phase,mask in [('k3',mt.k.eq(3)),('k6',mt.k.eq(6)),('k10',mt.k.eq(10)),('k20',mt.k.eq(20)),
                       ('first_half_average_k3plus',mt.k.ge(3)&mt.k.le(np.floor(mt.pool_n/2))),
                       ('terminal_full_pool',mt.k.eq(mt.pool_n))]:
        g=mt[mask].copy();g['any_pair']=g.paired.gt(0).astype(int)
        gb=g.groupby(cols,dropna=False,sort=False)
        r=gb[means].mean();r['paired_paths_across_k']=gb.paired.sum();r['attempted_paths_across_k']=gb.attempted.sum()
        r['paired_k_n']=gb.any_pair.sum();r['observed_k_n']=gb.size()
        r['k_min']=gb.k.min();r['k_max']=gb.k.max();r['phase']=phase
        tables.append(r.reset_index())
    p=pd.concat(tables,ignore_index=True)
    support=perk[['pool_id','pool_source_time_complete','structure_opportunity']].drop_duplicates('pool_id')
    return p.merge(support,on='pool_id',how='left',validate='many_to_one')


def summarize(p):
    common=set(p.groupby('pool_id').policy.nunique().loc[lambda x:x.eq(4)].index)
    c=p[p.pool_id.isin(common)]
    frames=[('own_supported_pools',p),('all_four_policies_common_pools',c),
            ('all_four_common_Nge20',c[c.pool_n.ge(20)]),
            ('own_supported_full_pool_time_complete',p[p.pool_source_time_complete]),
            ('all_four_common_full_pool_time_complete',c[c.pool_source_time_complete]),
            ('all_four_common_Nge20_time_complete',c[c.pool_source_time_complete&c.pool_n.ge(20)])]
    rows=[];buildings=[]
    metrics=['natural_mean','priority_mean','paired_mean_delta','paired_abs_delta','natural_p10','priority_p10','natural_sd','priority_sd']
    for cohort,frame in frames:
        for stratum in ['all','difficulty','structure_opportunity']:
            keys=['condition','layer','policy','phase','metric']+([] if stratum=='all' else [stratum])
            work=frame.assign(_valid=frame.paired_mean_delta.notna().astype(int),
                              _positive=frame.paired_mean_delta.gt(0).astype(int),
                              _negative=frame.paired_mean_delta.lt(0).astype(int))
            gb=work.groupby(keys,dropna=False,sort=False)
            image_means=gb[metrics].mean()
            row=gb.agg(images=('image','nunique'),buildings=('building','nunique'),
                images_with_pair=('_valid','sum'),images_delta_positive=('_positive','sum'),
                images_delta_negative=('_negative','sum'),paired_paths_across_k=('paired_paths_across_k','sum'),
                attempted_paths_across_k=('attempted_paths_across_k','sum'))
            bg=work.groupby(keys+['building'],dropna=False,sort=False)[metrics].mean().reset_index()
            bg['_valid']=bg.paired_mean_delta.notna().astype(int);bg['_positive']=bg.paired_mean_delta.gt(0).astype(int)
            bgb=bg.groupby(keys,dropna=False,sort=False);building_means=bgb[metrics].mean()
            row['buildings_with_pair']=bgb._valid.sum();row['buildings_delta_positive']=bgb._positive.sum()
            for m in metrics:
                row[m+'_image_equal']=image_means[m];row[m+'_building_equal']=building_means[m]
            row=row.reset_index();row['cohort']=cohort;row['stratum']=stratum;rows.append(row)
            bg=bg.drop(columns=['_valid','_positive']);bg['cohort']=cohort;bg['stratum']=stratum;buildings.append(bg)
    return pd.concat(rows,ignore_index=True),pd.concat(buildings,ignore_index=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metrics',required=True);ap.add_argument('--perk',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    mt=pd.read_csv(a.metrics,low_memory=False);perk=pd.read_csv(a.perk,low_memory=False)
    p=phase_components(mt,perk);save_csv(p,out/'POLICY_COMPONENT_PHASE_PER_IMAGE.csv.gz')
    s,b=summarize(p);save_csv(s,out/'POLICY_COMPONENT_PHASE_SUMMARY.csv.gz');save_csv(b,out/'POLICY_COMPONENT_PHASE_PER_BUILDING.csv.gz')
    write_bytes(out/'POLICY_COMPONENT_RECEIPT.json',json.dumps(dict(image_rows=len(p),summary_rows=len(s),building_rows=len(b),
        metrics=sorted(p.metric.unique()),weight='within image equal k, then images/buildings equal; per-metric available pairs',
        direction='priority minus paired natural; metric sign is not uniformly improvement'),ensure_ascii=False,indent=2).encode())
    print({'image_rows':len(p),'summary_rows':len(s)},flush=True)


if __name__=='__main__':main()
