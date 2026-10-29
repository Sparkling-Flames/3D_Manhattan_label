"""Three-leg decomposition on common metric-valid paths with parent weighting."""
from pathlib import Path
import argparse,json,hashlib,csv,gzip
import numpy as np
import pandas as pd
from analyze_population_sensitivity import METRICS,kind,save,pipe

KEY=['scope','condition','layer','method','role_direction','background_profile','parent_background_stratum']
META=KEY+['pool_id','image','building','parent_contrast_id']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--paths',required=True);ap.add_argument('--capacity',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    src=Path(a.paths);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    fields=[m for m in META if m!='parent_background_stratum']+['parent_D_workers','n_small','n_large']+[m+'__'+s for m in METRICS for s in ['total','equal','addition','closure_error']]
    d=pd.read_csv(src,usecols=fields,low_memory=False);rows=[];perpool=[]
    cap=pd.read_csv(a.capacity,usecols=['pool_id','pool_n']).drop_duplicates('pool_id').set_index('pool_id').pool_n
    d['parent_D_n']=d.parent_D_workers.map(lambda v:len(pipe(v)))
    d['parent_pool_n']=d.pool_id.map(cap);assert d.parent_pool_n.notna().all()
    d['parent_outside_available_n']=d.parent_pool_n-d.n_small-d.n_large+2*d.parent_D_n
    assert (d.parent_outside_available_n>=d.parent_D_n).all()
    d['parent_background_stratum']=np.where(d.parent_D_n.eq(0),'zero_D',
        np.where(d.parent_D_n.eq(d.parent_outside_available_n),'all_outside_D','partial_outside_D'))
    for metric in METRICS:
        vals=[metric+'__'+s for s in ['total','equal','addition']]
        q=d[META+vals].copy();q['valid_complete_path']=np.isfinite(q[vals]).all(axis=1)
        for key,registered in q.groupby(KEY,sort=False,dropna=False):
            base=dict(zip(KEY,key));g=registered[registered.valid_complete_path].copy()
            r=dict(base,metric=metric,metric_kind=kind(metric),registered_paths=len(registered),registered_parents=registered.parent_contrast_id.nunique(),
                registered_images=registered.image.nunique(),valid_paths=len(g),valid_parents=g.parent_contrast_id.nunique(),valid_images=0,valid_buildings=0)
            if g.empty:rows.append(r);continue
            for leg,col in zip(['total','equal','addition'],vals):
                g[leg]=g[col];g[leg+'_abs_before_parent_mean']=g[col].abs()
            g['opposite_equal_addition_signs']=((g.equal*g.addition)< -1e-18).astype(float)
            means=['total','equal','addition']+[leg+'_abs_before_parent_mean' for leg in ['total','equal','addition']]+['opposite_equal_addition_signs']
            parent=g.groupby(['pool_id','image','building','parent_contrast_id'],sort=False,dropna=False)[means].mean().reset_index()
            pool=parent.groupby(['pool_id','image','building'],sort=False,dropna=False)[means].mean().reset_index()
            for _,pr in pool.iterrows():perpool.append(dict(base,metric=metric,**pr.to_dict()))
            im=pool.groupby(['image','building'],dropna=False)[means].mean();bu=im.groupby(level='building').mean()
            r.update(valid_images=len(im),valid_buildings=len(bu),opposite_equal_addition_path_fraction_image_balanced=float(im.opposite_equal_addition_signs.mean()))
            for leg in ['total','equal','addition']:
                v=im[leg];r.update({leg+'_image_mean':float(v.mean()),leg+'_image_mean_abs_of_mean':float(v.abs().mean()),
                    leg+'_image_balanced_path_abs_mean':float(im[leg+'_abs_before_parent_mean'].mean()),
                    leg+'_building_balanced_mean':float(bu[leg].mean()),leg+'_positive_images':int((v>1e-9).sum()),
                    leg+'_negative_images':int((v< -1e-9).sum()),leg+'_zero_images':int((v.abs()<=1e-9).sum()),
                    leg+'_image_p10':float(v.quantile(.1)),leg+'_image_min':float(v.min()),leg+'_image_max':float(v.max())})
            if kind(metric)=='additive_difference':
                error=g.total-g.equal-g.addition;assert error.abs().max()<1e-6
                r['max_raw_path_closure_error']=float(error.abs().max())
                r['image_balanced_mean_closure_error']=r['total_image_mean']-r['equal_image_mean']-r['addition_image_mean']
                assert abs(r['image_balanced_mean_closure_error'])<1e-6
            rows.append(r)
    save(pd.DataFrame(rows),out/'COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz')
    save(pd.DataFrame(perpool),out/'COMMON_VALID_THREE_LEG_POOL_SUMMARY.csv.gz')
    checks=[]
    for p in out.glob('*.csv.gz'):
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            rd=csv.reader(f);h=next(rd);n=0
            for row in rd:assert len(row)==len(h);n+=1
        checks.append(dict(file=p.name,rows=n,full_gzip_eof=True,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    receipt={'raw_paths':len(d),'raw_parents':d.parent_contrast_id.nunique(),'summary_rows':len(rows),
        'support':'each metric requires all three legs finite on the same path; average middle paths within parent before pools/images/buildings',
        'causal_limit':'addition is adding these remaining members of the target class on this registered path, not a universal number-only effect',
        'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
        'capacity_sha256':hashlib.sha256(Path(a.capacity).read_bytes()).hexdigest(),
        'parent_background_strata':['zero_D','partial_outside_D','all_outside_D'],
        'files':checks,'new_fusions':0,'new_teams':0}
    (out/'COMMON_VALID_DECOMPOSITION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
