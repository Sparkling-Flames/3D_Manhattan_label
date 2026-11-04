"""Require at least two metric-valid observations to estimate member variation.

The raw MEMBER_PANELS table is preserved. A singleton's descriptive range is
mathematically zero, but that zero is excluded from variability inference.
No mean effect, endpoint, status, score or identity is changed.
"""
from pathlib import Path
import argparse,csv,gzip,json,hashlib
import numpy as np
import pandas as pd
from analyze_population_sensitivity import save
from enrich_sensitivity_amplitudes import column_stats

KEY=['scope','condition','layer','method','panel_kind','role_direction','n','m']
POOL=KEY+['pool_id','image','building']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--panels',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    src=Path(a.panels);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    meta=POOL+['panel_id','unique_pairs','unique_A_teams','unique_C_teams','distinct_D']
    d=pd.read_csv(src,usecols=lambda c:c in meta or c.endswith(('__valid','__sd','__span','__sign_flip')),low_memory=False)
    all_panel_n=len(d);single_pair_n=int(d.unique_pairs.le(1).sum());d=d[d.unique_pairs.gt(1)].copy()
    cols=[c for c in d if c.endswith(('__sd','__span','__sign_flip'))]
    corrections=[]
    for col in cols:
        metric=col.rsplit('__',1)[0];validcol=metric+'__valid'
        bad=d[validcol].lt(2)
        changed=bad & d[col].notna()
        if changed.any():
            z=d.loc[changed,meta+[validcol,col]].copy();z=z.rename(columns={validcol:'metric_valid_observations',col:'previous_descriptive_value'})
            z['metric_statistic']=col;corrections.append(z)
        d.loc[bad,col]=np.nan
    corrected=pd.concat(corrections,ignore_index=True) if corrections else pd.DataFrame()
    save(corrected,out/'SINGLE_VALID_VALUE_EXCLUDED_FROM_VARIABILITY.csv.gz')
    grouped=d.groupby(POOL,dropna=False,sort=False)
    pool=grouped[cols].mean().reset_index()
    counts=grouped[cols].count().reset_index().rename(columns={c:c+'__valid_panels' for c in cols})
    pool=pool.merge(counts,on=POOL,validate='one_to_one')
    pcounts=grouped.size().reset_index(name='registered_multi_pair_panels');pool=pool.merge(pcounts,on=POOL,validate='one_to_one')
    dest=out/'MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz';tmp=dest.with_name(dest.name+'.partial');n=0
    fields=KEY+['metric','registered_multi_pair_panels','valid_panels','registered_pools','valid_pools','registered_images','valid_images','valid_buildings',
        'image_mean','image_mean_absolute_of_image_mean','image_balanced_mean_absolute_within_pool',
        'image_median','image_p10','image_min','image_max','positive_images','negative_images','zero_images','positive_image_fraction','building_balanced_mean']
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for key,g in pool.groupby(KEY,dropna=False,sort=False):
            base=dict(zip(KEY,key));im=g.groupby(['image','building'],dropna=False)[cols].mean();bu=im.groupby(level='building').mean()
            x=column_stats(im);b=column_stats(bu);vp=g[cols].notna().sum().to_numpy()
            vn=g[[c+'__valid_panels' for c in cols]].sum().to_numpy()
            common=dict(registered_multi_pair_panels=int(g.registered_multi_pair_panels.sum()),
                registered_pools=g.pool_id.nunique(),registered_images=g.image.nunique())
            for i,col in enumerate(cols):
                r=dict(base,**common,metric=col,valid_panels=int(vn[i]),valid_pools=int(vp[i]),valid_images=int(x['count'][i]),valid_buildings=int(b['count'][i]),
                    image_mean=float(x['mean'][i]),image_mean_absolute_of_image_mean=float(x['absolute'][i]),
                    image_balanced_mean_absolute_within_pool=float(x['mean'][i]),
                    image_median=float(x['median'][i]),image_p10=float(x['p10'][i]),image_min=float(x['low'][i]),image_max=float(x['high'][i]),
                    positive_images=int(x['positive'][i]),negative_images=int(x['negative'][i]),zero_images=int(x['zero'][i]),
                    positive_image_fraction=float(x['fraction'][i]),building_balanced_mean=float(b['mean'][i]))
                writer.writerow({k:'' if pd.isna(v) else v for k,v in r.items()});n+=1
    tmp.replace(dest)
    checks=[]
    for p in [dest,out/'SINGLE_VALID_VALUE_EXCLUDED_FROM_VARIABILITY.csv.gz']:
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as stream:
            reader=csv.reader(stream);h=next(reader);nr=0
            for row in reader:assert len(row)==len(h);nr+=1
        checks.append(dict(file=p.name,rows=nr,columns=len(h),full_gzip_eof=True,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    receipt=dict(all_panels=all_panel_n,single_pair_panels_excluded=single_pair_n,multi_pair_panels=len(d),summary_rows=n,
        singleton_variability_entries_excluded=len(corrected),affected_panels=len(corrected[['pool_id','panel_id']].drop_duplicates()) if len(corrected) else 0,
        Q_singleton_panels_excluded=int(corrected.metric_statistic.eq('B8L2_CA__span').sum()) if len(corrected) else 0,
        Q_fixed_D_singleton_panels_excluded=int((corrected.metric_statistic.eq('B8L2_CA__span')&corrected.panel_kind.eq('exact_fixed_D_member_panel')).sum()) if len(corrected) else 0,
        minimum_metric_valid_observations=2,means_and_endpoints_unchanged=True,
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),files=checks)
    (out/'MEMBER_VARIABILITY_DENOMINATOR_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
