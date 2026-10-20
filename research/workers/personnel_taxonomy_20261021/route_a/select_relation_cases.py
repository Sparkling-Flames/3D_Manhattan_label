#!/usr/bin/env python3
"""Select a few display examples after relation validation, never for fitting."""
import itertools,json
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def main():
    pairs=pd.read_csv(HERE/'pair_observations.csv.gz')
    labels=pd.read_csv(HERE/'worker_labels_lobo.csv')
    labels=labels[labels.method.eq('A2_samecount_source_residual')&labels.class_id.ne('unknown')]
    rec=pd.read_csv(ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/clusters/records_geometry.csv.gz')
    rows=[]
    for cond in ['manual','semi']:
        mp=labels[labels.condition.eq(cond)].set_index(['target_building','worker_id']).class_id.to_dict()
        rr=rec[rec.layer.eq('ordinary_'+cond)].copy()
        rr['A_class']=[mp.get((b,w)) for b,w in zip(rr.building_id,rr.worker_id)]
        for (pool_id,n),r in rr.groupby(['pool_id','pair_count']):
            p=pairs[pairs.pool_id.eq(pool_id)&pairs.same_count.eq(1)&pairs.count_a.eq(n)].copy()
            if not len(p):continue
            maps=r.set_index('worker_id').A_class.to_dict()
            p['A_class_a']=p.worker_a.map(maps);p['A_class_b']=p.worker_b.map(maps)
            byclass={c:g for c,g in r.groupby('A_class') if len(g)>=2}
            for ca,cb in itertools.combinations(byclass,2):
                a=p[p.A_class_a.eq(ca)&p.A_class_b.eq(ca)]
                b=p[p.A_class_a.eq(cb)&p.A_class_b.eq(cb)]
                ab=p[(p.A_class_a.eq(ca)&p.A_class_b.eq(cb))|(p.A_class_a.eq(cb)&p.A_class_b.eq(ca))]
                if min(len(a),len(b),len(ab))==0:continue
                # Representative same-class pair: closest to that class's
                # median distance on this image; selected groups may include
                # additional members in the numerical contrast.
                aa=a.iloc[int(np.argmin(abs(a.bound_deg-a.bound_deg.median())))]
                bb=b.iloc[int(np.argmin(abs(b.bound_deg-b.bound_deg.median())))]
                people=[aa.worker_a,aa.worker_b,bb.worker_a,bb.worker_b]
                sub=r.set_index('worker_id').loc[people]
                rows.append(dict(condition=cond,pool_id=pool_id,image_id=r.image_id.iloc[0],image_code=r.image_code.iloc[0],building_id=r.building_id.iloc[0],
                    pair_count=n,class_a=ca,class_b=cb,workers_a='|'.join(people[:2]),workers_b='|'.join(people[2:]),
                    object_ids_a='|'.join([aa.object_a,aa.object_b]),object_ids_b='|'.join([bb.object_a,bb.object_b]),
                    within_a_deg=a.bound_deg.mean(),within_b_deg=b.bound_deg.mean(),between_deg=ab.bound_deg.mean(),
                    distance_gain=ab.bound_deg.mean()-(a.bound_deg.mean()+b.bound_deg.mean())/2,
                    selected_a_deg=aa.bound_deg,selected_b_deg=bb.bound_deg,
                    selected_Q_min=sub.B8L2.min(),selected_Q_max=sub.B8L2.max(),selected_Q_range=sub.B8L2.max()-sub.B8L2.min(),
                    selected_source_n=sub.origin.nunique(),display_selection='post_result_samecount_two_per_class_median_pair'))
    d=pd.DataFrame(rows)
    out=[]
    for cond,g in d.groupby('condition'):
        for tag,asc in [('positive',False),('counterexample',True)]:
            # Prefer comparable quality/source where feasible, explicitly
            # retain actual Q ranges instead of calling these matched trials.
            z=g[g.selected_Q_range.le(20)&g.selected_source_n.eq(1)]
            if len(z)<3:z=g
            z=z.sort_values('distance_gain',ascending=asc).drop_duplicates('pool_id').head(4).copy();z['case_kind']=tag;out.append(z)
    pd.concat(out,ignore_index=True).to_csv(HERE/'A2_case_candidates.csv',index=False)
    print(pd.concat(out,ignore_index=True)[['condition','case_kind','image_code','class_a','class_b','workers_a','workers_b','within_a_deg','within_b_deg','between_deg','distance_gain','selected_Q_range']].to_string(index=False))
    design=json.load(open(HERE/'DESIGN_AND_RECEIPT.json'))
    chosen=pd.DataFrame(design['selected'].values())
    checks=pd.read_csv(HERE/'independent_check.csv').merge(chosen[['condition','method','k']],on=['condition','method','k'])
    checks=checks[checks.panel.eq('equal_count')&checks.metric.isin(['same9','same12','bound_deg','bottom_deg','top_deg','floor_iou'])]
    lobo=pd.read_csv(HERE/'crossfit_check.csv');lobo=lobo[lobo.panel.eq('equal_count')&lobo.metric.isin(['same9','same12','bound_deg','bottom_deg','top_deg','floor_iou'])]
    match=pd.read_csv(HERE/'A_Q_source_matched_validation.csv')
    fin=pd.concat([checks,lobo,match],ignore_index=True)
    fin=fin.merge(chosen[['condition','method','development_dropbuilding_ARI_median']],on=['condition','method'],validate='many_to_one')
    fin.to_csv(HERE/'selected_method_validation.csv',index=False)

if __name__=='__main__':main()
