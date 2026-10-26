"""Read-only timing and old48 equivalence check, using delivered actual paths."""
from pathlib import Path
import importlib.util,json,pickle,time
import numpy as np
import pandas as pd
from geometry_extension import distance_matrices,ustat,save_json,COHORTS

def main(root):
    prior=root.parent/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    spec=importlib.util.spec_from_file_location('prior_geo',prior/'analysis_geometry/geometry_sampling_precision.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    m=pd.read_csv(root/'POOL_META.csv')
    image_names=['2t7WUuJeko7-06','2t7WUuJeko7-07','VFuaQ6m2Qom-04','rPc6DW4iMge-06','wc2JMjhGNzB-46','2t7WUuJeko7-03']
    links=pd.read_csv(root/'BASELINE_NATURAL_LINKS.csv.gz')
    saved=pd.read_csv(prior/'analysis_geometry/results/GEOMETRY_PATH_PRECISION.csv.gz')
    saved=saved[saved.cohort.eq('combined48')].set_index(['pool_id','k','metric'])
    result=[]
    for meta in m[m.image.isin(image_names)].to_dict('records'):
        pid=meta['pool_id']
        with (root/'cache/baseline'/(pid+'.pkl')).open('rb') as f:rows=pickle.load(f)
        for k,g in links[links.pool_id.eq(pid)].groupby('k'):
            if k==2:continue
            g=g.sort_values('path_id').reset_index(drop=True)
            start=time.monotonic();d,account=distance_matrices(g.team_key.tolist(),rows);elapsed=time.monotonic()-start
            mask=g.batch.isin(COHORTS['old48']).to_numpy()
            largest_value=0.;largest_se=0.
            for metric,a in d.items():
                v,j=ustat(a[np.ix_(mask,mask)])
                s=saved.loc[(pid,k,metric)]
                assert np.isnan(v['mean'])==pd.isna(s['mean'])
                assert np.isnan(v['mcse'])==pd.isna(s['mcse'])
                if np.isfinite(v['mean']):largest_value=max(largest_value,abs(v['mean']-s['mean']))
                if np.isfinite(v['mcse']):largest_se=max(largest_se,abs(v['mcse']-s['mcse']))
            if k in [3,10,20,meta['pool_n']-1]:
                before=old.distance_matrices(g.team_key.tolist(),rows)
                for metric in d:assert np.allclose(before[metric],d[metric],atol=1e-13,rtol=1e-13,equal_nan=True),(pid,k,metric)
            result.append(dict(**meta,k=k,elapsed_seconds=elapsed,**account,max_point_difference_from_saved_old48=largest_value,max_mcse_difference_from_saved_old48=largest_se))
        print('BENCHMARK',meta['image'],flush=True)
    df=pd.DataFrame(result);df.to_csv(root/'GEOMETRY_TIMING_EQUIVALENCE.csv',index=False)
    assert df.max_point_difference_from_saved_old48.max()<1e-11
    assert df.max_mcse_difference_from_saved_old48.max()<1e-11
    pair_seconds=df.elapsed_seconds.sum()/df.distinct_polygon_pair_evaluations.sum()
    save_json(root/'GEOMETRY_TIMING_RECEIPT.json',dict(actual_images=len(image_names),actual_pool_k=len(df),
        max_old48_point_difference=float(df.max_point_difference_from_saved_old48.max()),
        max_old48_mcse_difference=float(df.max_mcse_difference_from_saved_old48.max()),
        seconds_per_distinct_polygon_pair=pair_seconds,
        estimated_194x32x304pairs_core_seconds=194*32*(304*303/2)*pair_seconds,
        timing_only_no_random_path_added=True,new_fusions=0))
    print((root/'GEOMETRY_TIMING_RECEIPT.json').read_text(),flush=True)

if __name__=='__main__':main(Path(__file__).resolve().parent)
