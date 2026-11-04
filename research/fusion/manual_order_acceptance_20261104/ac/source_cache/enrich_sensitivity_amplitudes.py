"""Distinguish absolute image-mean effects from within-pool absolute amplitude.

Uses saved pool summaries only. No raw event, fusion, score or selection changes.
The original image-balanced summary remains intact for transparent versioning.
"""
from pathlib import Path
import argparse,csv,gzip,json,hashlib,math,itertools,warnings
import numpy as np
import pandas as pd
from analyze_population_sensitivity import TABLES,summary_spec

FIELDS=['analysis_table','scope','condition','layer','method','panel_kind','role_direction','n','m',
 'comparison','background_profile','n_from','n_to','m_from','m_to','number_condition','unknown_background_included',
 'metric','registered_pools','valid_pools','registered_images','valid_images','valid_buildings','analysis_rows',
 'image_mean','image_mean_absolute_of_image_mean','image_balanced_mean_absolute_within_pool',
 'building_balanced_mean_absolute_within_pool','image_median','image_p10','image_min','image_max',
 'observed_analysis_row_min','observed_analysis_row_max','positive_images','negative_images','zero_images',
 'positive_image_fraction','building_balanced_mean']

def column_stats(array):
    """Vectorized finite-value statistics; a column is one saved metric."""
    array=np.asarray(array,dtype=float);valid=np.isfinite(array)
    x=np.where(valid,array,np.nan);count=valid.sum(axis=0)
    mean=np.divide(np.nansum(x,axis=0),count,out=np.full(x.shape[1],np.nan),where=count>0)
    absolute=np.divide(np.nansum(np.abs(x),axis=0),count,out=np.full(x.shape[1],np.nan),where=count>0)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        median=np.nanmedian(x,axis=0);p10=np.nanquantile(x,.1,axis=0)
        low=np.nanmin(x,axis=0);high=np.nanmax(x,axis=0)
    positive=(x>1e-9).sum(axis=0);negative=(x< -1e-9).sum(axis=0);zero=(np.abs(x)<=1e-9).sum(axis=0)
    fraction=np.divide(positive,count,out=np.full(x.shape[1],np.nan),where=count>0)
    return dict(count=count,mean=mean,absolute=absolute,median=median,p10=p10,low=low,high=high,
                positive=positive,negative=negative,zero=zero,fraction=fraction)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--results',required=True);args=ap.parse_args()
    out=Path(args.results);dest=out/'SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz';tmp=dest.with_name(dest.name+'.partial')
    count=0;sources=[]
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
        for name in TABLES:
            p=out/(name+'_POOL_SUMMARY.csv.gz')
            if not p.exists():continue
            d=pd.read_csv(p,low_memory=False);keys,_=summary_spec(name,d)
            cols=[c for c in d if c.endswith('__pool_mean')]
            abscols=[c[:-11]+'__pool_mean_abs' for c in cols]
            mincols=[c[:-11]+'__pool_min' for c in cols];maxcols=[c[:-11]+'__pool_max' for c in cols]
            sources.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
            for key,g in d.groupby(keys,dropna=False,sort=False):
                base=dict(zip(keys,key));base['analysis_table']=name
                image=g.groupby(['image','building'],dropna=False)[cols+abscols].mean()
                building=image.groupby(level='building').mean()
                x=column_stats(image[cols]);xa=column_stats(image[abscols]);xb=column_stats(building[cols]);xab=column_stats(building[abscols])
                lo=g[mincols].min().to_numpy();hi=g[maxcols].max().to_numpy();vp=g[cols].notna().sum().to_numpy()
                reg_pools=g.pool_id.nunique();reg_images=g.image.nunique();arows=int(g.panel_rows.sum())
                for i,col in enumerate(cols):
                    metric=col[:-11]
                    r=dict(base,metric=metric,registered_pools=reg_pools,valid_pools=int(vp[i]),
                        registered_images=reg_images,valid_images=int(x['count'][i]),valid_buildings=int(xb['count'][i]),analysis_rows=arows,
                        image_mean=float(x['mean'][i]),image_mean_absolute_of_image_mean=float(x['absolute'][i]),
                        image_balanced_mean_absolute_within_pool=float(xa['mean'][i]),
                        building_balanced_mean_absolute_within_pool=float(xab['mean'][i]),
                        image_median=float(x['median'][i]),image_p10=float(x['p10'][i]),
                        image_min=float(x['low'][i]),image_max=float(x['high'][i]),
                        observed_analysis_row_min=float(lo[i]),observed_analysis_row_max=float(hi[i]),
                        positive_images=int(x['positive'][i]),negative_images=int(x['negative'][i]),zero_images=int(x['zero'][i]),
                        positive_image_fraction=float(x['fraction'][i]),building_balanced_mean=float(xb['mean'][i]))
                    writer.writerow({k:'' if pd.isna(v) else v for k,v in r.items()});count+=1
    tmp.replace(dest)
    expected=json.loads((out/'SENSITIVITY_RECEIPT.json').read_text())['image_balanced_summary_rows'];assert count==expected
    actual=0;maximum_signed_summary_difference=0.
    old=out/'SENSITIVITY_IMAGE_BALANCED_SUMMARY.csv.gz'
    key_fields=FIELDS[:18]
    scalar_fields=['registered_pools','valid_pools','registered_images','valid_images','valid_buildings',
        'image_mean','image_median','image_p10','image_min','image_max','positive_images','negative_images',
        'zero_images','positive_image_fraction','building_balanced_mean']
    with gzip.open(old,'rt',encoding='utf-8-sig',newline='') as oldstream,gzip.open(dest,'rt',encoding='utf-8-sig',newline='') as newstream:
        before,after=csv.DictReader(oldstream),csv.DictReader(newstream)
        for r0,r1 in itertools.zip_longest(before,after):
            assert r0 is not None and r1 is not None
            assert None not in r0 and None not in r1 and all(v is not None for v in r1.values())
            for key in key_fields:
                if r0.get(key,'')!=r1.get(key,''):
                    assert key in ['n','m','n_from','n_to','m_from','m_to'] and float(r0[key])==float(r1[key]),(actual,key,r0.get(key),r1.get(key))
            for field in scalar_fields:
                av,bv=r0[field],r1[field]
                if not av or not bv:assert av==bv,(actual,field,av,bv)
                else:
                    aa,bb=float(av),float(bv)
                    assert math.isclose(aa,bb,abs_tol=1e-10,rel_tol=1e-10),(actual,field,aa,bb)
                    maximum_signed_summary_difference=max(maximum_signed_summary_difference,abs(aa-bb))
            if r0['image_mean_abs']:
                assert math.isclose(float(r0['image_mean_abs']),float(r1['image_mean_absolute_of_image_mean']),abs_tol=1e-10,rel_tol=1e-10)
            else:assert not r1['image_mean_absolute_of_image_mean']
            actual+=1
    assert actual==count
    receipt={'rows':count,'same_conditions_and_signed_effects_as_v1':True,
        'maximum_signed_summary_difference':maximum_signed_summary_difference,'full_gzip_eof':True,'csv_widths_valid':True,
        'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'sources':sources,
        'interpretation':'image_mean_absolute_of_image_mean can cancel within images; image_balanced_mean_absolute_within_pool retains absolute amplitude at the saved analysis-row level before image balancing',
        'new_fusions':0,'new_scores':0,'new_events':0}
    (out/'AMPLITUDE_ENRICHMENT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
