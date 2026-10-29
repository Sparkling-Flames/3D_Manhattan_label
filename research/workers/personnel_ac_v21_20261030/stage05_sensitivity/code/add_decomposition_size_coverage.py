"""Attach actual registered/valid n and m ranges to three-leg common support."""
from pathlib import Path
import argparse,json,hashlib,gzip,csv
import numpy as np
import pandas as pd
from analyze_population_sensitivity import METRICS,save,pipe
from summarize_complete_decomposition_support import KEY


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--paths',required=True);ap.add_argument('--capacity',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);src=Path(a.paths)
    fields=[k for k in KEY if k!='parent_background_stratum']+['pool_id','image','building','parent_contrast_id','parent_D_workers','n_small','n_large']+[m+'__'+s for m in METRICS for s in ['total','equal','addition']]
    d=pd.read_csv(src,usecols=fields,low_memory=False)
    cap=pd.read_csv(a.capacity,usecols=['pool_id','pool_n']).drop_duplicates('pool_id').set_index('pool_id').pool_n
    d['D_n']=d.parent_D_workers.map(lambda v:len(pipe(v)));d['pool_n']=d.pool_id.map(cap)
    d['small_class_n']=d.n_small-d.D_n;d['large_class_n']=d.n_large-d.D_n
    d['outside_available_n']=d.pool_n-d.small_class_n-d.large_class_n
    d['parent_background_stratum']=np.where(d.D_n.eq(0),'zero_D',np.where(d.D_n.eq(d.outside_available_n),'all_outside_D','partial_outside_D'))
    d['delta_n']=d.n_large-d.n_small;d['equal_replacement_fraction']=d.small_class_n/d.n_small
    sizes=['pool_n','n_small','n_large','small_class_n','large_class_n','D_n','delta_n','equal_replacement_fraction']
    rows=[]
    for metric in METRICS:
        vals=[metric+'__'+s for s in ['total','equal','addition']]
        for key,g in d.groupby(KEY,dropna=False,sort=False):
            valid=g[np.isfinite(g[vals]).all(axis=1)];r=dict(zip(KEY,key));r['metric']=metric
            for label,frame in [('registered',g),('common_valid',valid)]:
                parents=frame.drop_duplicates('parent_contrast_id')
                r[label+'_parents']=len(parents);r[label+'_images']=parents.image.nunique();r[label+'_buildings']=parents.building.nunique()
                for size in sizes:
                    r[label+'_'+size+'_min']=parents[size].min() if len(parents) else np.nan
                    r[label+'_'+size+'_max']=parents[size].max() if len(parents) else np.nan
                r[label+'_n_small_values']='|'.join(str(int(v)) for v in sorted(parents.n_small.unique()))
                r[label+'_n_large_values']='|'.join(str(int(v)) for v in sorted(parents.n_large.unique()))
                r[label+'_small_class_n_values']='|'.join(str(int(v)) for v in sorted(parents.small_class_n.unique()))
            rows.append(r)
    frame=pd.DataFrame(rows);save(frame,out/'COMMON_VALID_DECOMPOSITION_SIZE_COVERAGE.csv.gz')
    effect=pd.read_csv(out/'COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz')
    joined=effect.merge(frame,on=KEY+['metric'],how='left',validate='one_to_one')
    assert joined.common_valid_images.eq(joined.valid_images).all()
    wanted=((joined.method.isin(['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'])&joined.role_direction.eq('3->2'))|
        (joined.method.eq('OPPJOINT_K3')&joined.role_direction.isin(['3->1','3->2']))|
        (joined.method.eq('OPPJOINT_K4')&joined.role_direction.str.startswith('4->')))
    sub=joined[wanted&joined.scope.eq('primary')&joined.condition.eq('manual')&
        joined.background_profile.eq('outside_swapped_classes_neutral_members_0')&joined.parent_background_stratum.eq('all_outside_D')]
    save(sub,out/'REQUESTED_ALL_OUTSIDE_D_DIRECTIONS_WITH_SIZES.csv.gz')
    checks=[]
    for p in [out/'COMMON_VALID_DECOMPOSITION_SIZE_COVERAGE.csv.gz',out/'REQUESTED_ALL_OUTSIDE_D_DIRECTIONS_WITH_SIZES.csv.gz']:
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            rr=csv.reader(f);h=next(rr);n=0
            for row in rr:assert len(row)==len(h);n+=1
        checks.append(dict(file=p.name,rows=n,columns=len(h),full_gzip_eof=True,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    receipt={'selection':'Root requested whole smaller-class departure: TARGET/RAW3 3->2; JOINT3 3->1 and 3->2; all existing JOINT4 4->*; primary Manual/all outside D/neutral0. Every metric and missing outcome row retained.',
        'join_key':KEY+['metric'],'equal_anchor_m':'small_class_n = n_small - D_n; equal anchor n = n_small',
        'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'files':checks,'new_teams':0}
    (out/'SIZE_COVERAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(sub[sub.metric.eq('B8L2_CA')][['method','role_direction','valid_images','valid_buildings','common_valid_n_small_min','common_valid_n_small_max','common_valid_n_large_min','common_valid_n_large_max','common_valid_small_class_n_min','common_valid_small_class_n_max','total_image_mean','equal_image_mean','addition_image_mean']].to_string(index=False))


if __name__=='__main__':main()
