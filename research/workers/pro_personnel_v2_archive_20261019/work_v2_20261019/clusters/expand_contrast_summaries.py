"""Common-image and frozen-difficulty sensitivities of paired effects."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_fusion_clusters import bs
HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'fusion_analysis';cover=[]
    for family in ['replacement','cross_route','composition']:
        path=out/(family+'_image_effects.csv')
        if not path.exists():continue
        d=pd.read_csv(path);sums=[]
        for (cut,metric),a in d.groupby(['threshold_deg','metric']):
            common=a.groupby('pool_id').k.nunique();common=set(common[common.eq(4)].index)
            panels={'all_matched':a,'common_matched_every_k':a[a.pool_id.isin(common)]}
            for name,value in [('easy','简单'),('medium','中等'),('hard','困难')]:panels['difficulty_'+name]=a[a.difficulty.eq(value)]
            cover.append(dict(family=family,threshold_deg=cut,metric=metric,any_k_images=a.pool_id.nunique(),common_matched_every_k_images=len(common)))
            for panel,g in panels.items():
                for k in ['all',8,12,16,24]:
                    h=g if k=='all' else g[g.k.eq(k)]
                    if not len(h):continue
                    image=h.groupby(['pool_id','building_id']).difference.mean();b=image.groupby('building_id').mean();z=bs(b)
                    sums.append(dict(panel=panel,threshold_deg=cut,metric=metric,k=k,images=h.pool_id.nunique(),measurable_images=h[h.difference.notna()].pool_id.nunique(),
                        buildings=z['n'],building_equal_difference=z['mean'],low=z['low'],high=z['high'],positive_buildings=int(b.gt(0).sum()),negative_buildings=int(b.lt(0).sum()),
                        left_attempts=int(h.left_attempts.sum()),right_attempts=int(h.right_attempts.sum())))
        pd.DataFrame(sums).to_csv(out/(family+'_sensitivity_panels.csv'),index=False)
    pd.DataFrame(cover).to_csv(out/'common_matched_image_coverage.csv',index=False)
    path=out/'replacement_cluster_details.csv.gz'
    if path.exists():
        cols=['threshold_deg','k','pool_id','image_id','building_id','relation','abs_B8L2_change','abs_D10_change','floor_jaccard_difference',
              'joint_geometric_stable','joint_with_shared_connections','joint_with_shared_connections_and_retention','any_failure','node_changed','quality_within_2']
        d=pd.read_csv(path,usecols=cols);metrics=cols[6:];sums=[]
        for key,g in d.groupby(['threshold_deg','k','relation']):
            for metric in metrics:
                x=pd.to_numeric(g[metric],errors='coerce').dropna().astype(float)
                b=g.groupby(['building_id','pool_id'])[metric].mean().groupby('building_id').mean();z=bs(b)
                sums.append(dict(zip(['threshold_deg','k','relation'],key),metric=metric,attempts=len(g),observed=len(x),images=g.pool_id.nunique(),buildings=z['n'],
                    attempt_equal_mean=x.mean(),attempt_q10=x.quantile(.1),attempt_median=x.median(),attempt_q90=x.quantile(.9),attempt_q95=x.quantile(.95),
                    building_equal_mean=z['mean'],low=z['low'],high=z['high']))
        pd.DataFrame(sums).to_csv(out/'replacement_relation_distributions.csv',index=False)
    print(json.dumps(dict(families=sorted(set(r['family'] for r in cover)),images_common_coverage_rows=len(cover)),indent=2))

if __name__=='__main__':main()
