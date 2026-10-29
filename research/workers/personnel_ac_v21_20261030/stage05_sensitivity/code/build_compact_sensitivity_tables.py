"""Compact full-pool, primary-Manual sensitivity tables for report review.

Reads completed per-pool derived summaries. It does not require the large
all-metric long table to have finished writing and creates no new endpoints.
"""
from pathlib import Path
import argparse,csv,gzip,json,hashlib
import numpy as np
import pandas as pd
from analyze_population_sensitivity import summary_spec,save
from enrich_sensitivity_amplitudes import column_stats

CORE=['B8L2_CA','D10_CA','fusion_turn_n_CA','nodes_CA','ref_node_recall_5_CA','ref_edge_recall_5_CA',
      'geometry_bev_distance_AC','geometry_centroid_distance_AC','geometry_area_h2_pct_CA','height_mean_h_pct_CA',
      'record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched','Q_missing_risk_change_CA',
      'fusion_failure_observed_risk_change_CA','output_not_complete_risk_change_CA']
FAMILIES=['MEMBER_PANELS','BACKGROUND_CHANGES','FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS',
          'UNEQUAL_DECOMPOSITION','COMPLETE_COALITIONS','SAMPLING_BATCHES']
META=['scope','condition','layer','method','panel_kind','role_direction','n','m','comparison','background_profile',
      'n_from','n_to','m_from','m_to','number_condition','unknown_background_included','pool_id','image','building','panel_rows']


def wanted(name):
    if name=='MEMBER_PANELS':
        return [m+'__'+s for m in CORE for s in ['mean','sd','span','sign_flip']]+['A_B8L2__span','C_B8L2__span']
    if name=='BACKGROUND_CHANGES':
        return [m+'__effect_difference' for m in CORE]+[m+'__effect_difference_four_team_source_matched' for m in CORE if m.startswith('record_time')]
    if name in ['FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS']:return [m+'__step_difference' for m in CORE]
    if name=='UNEQUAL_DECOMPOSITION':return [m+'__'+s for m in CORE for s in ['total','equal','addition','parts_opposite_sign']]
    if name=='COMPLETE_COALITIONS':return CORE+['n_A','n_C','delta_n','D_n']
    if name=='SAMPLING_BATCHES':return [m+'__'+s for m in CORE for s in ['mean_difference','direction_agreement']]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    source=Path(a.results);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    completed=sorted((source/'pool_shards').glob('*/COMPLETE.json'));assert len(completed)==258,len(completed)
    receipts=[];all_rows=[]
    for name in FAMILIES:
        metrics=wanted(name);use=set(META+[m+s for m in metrics for s in ['__pool_mean','__pool_mean_abs','__valid','__pool_min','__pool_max']])
        files=sorted((source/'pool_summaries').glob('*/'+name+'.csv.gz'))
        parts=[pd.read_csv(p,usecols=lambda c:c in use,low_memory=False) for p in files]
        d=pd.concat(parts,ignore_index=True);d=d[d.scope.eq('primary')&d.condition.eq('manual')]
        keys,_=summary_spec(name,d);cols=[m+'__pool_mean' for m in metrics if m+'__pool_mean' in d]
        abscols=[c[:-11]+'__pool_mean_abs' for c in cols];rows=[]
        for key,g in d.groupby(keys,dropna=False,sort=False):
            base=dict(zip(keys,key));base['analysis_table']=name
            im=g.groupby(['image','building'],dropna=False)[cols+abscols].mean();bu=im.groupby(level='building').mean()
            x=column_stats(im[cols]);xa=column_stats(im[abscols]);xb=column_stats(bu[cols]);xab=column_stats(bu[abscols])
            common=dict(registered_pools=g.pool_id.nunique(),registered_images=g.image.nunique(),analysis_rows=int(g.panel_rows.sum()))
            valid=g[cols].notna().sum().to_numpy()
            for i,col in enumerate(cols):
                metric=col[:-11];r=dict(base,**common,metric=metric,valid_pools=int(valid[i]),
                    valid_images=int(x['count'][i]),valid_buildings=int(xb['count'][i]),
                    image_mean=float(x['mean'][i]),image_mean_absolute_of_image_mean=float(x['absolute'][i]),
                    image_balanced_mean_absolute_within_pool=float(xa['mean'][i]),building_balanced_mean=float(xb['mean'][i]),
                    building_balanced_mean_absolute_within_pool=float(xab['mean'][i]),
                    image_median=float(x['median'][i]),image_p10=float(x['p10'][i]),image_min=float(x['low'][i]),image_max=float(x['high'][i]),
                    positive_images=int(x['positive'][i]),negative_images=int(x['negative'][i]),zero_images=int(x['zero'][i]),
                    positive_image_fraction=float(x['fraction'][i]))
                rows.append(r)
        frame=pd.DataFrame(rows);save(frame,out/(name+'_COMPACT_PRIMARY_MANUAL.csv.gz'));all_rows.extend(rows)
        receipts.append({'analysis_table':name,'source_pool_summaries':len(files),'rows':len(frame),'source_pool_rows':len(d),
            'source_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
        print(json.dumps({k:v for k,v in receipts[-1].items() if k!='source_sha256'}),flush=True)
    save(pd.DataFrame(all_rows),out/'ALL_COMPACT_PRIMARY_MANUAL.csv.gz')
    validation=[]
    for p in out.glob('*.csv.gz'):
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);h=next(reader);n=0
            for row in reader:assert len(row)==len(h);n+=1
        validation.append({'file':p.name,'rows':n,'full_gzip_eof':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    receipt={'completed_pool_checkpoints':len(completed),'scope':'all primary ordinary Manual derived summaries; other targets/Semi remain in the full result',
        'tables':receipts,'validation':validation,'selection':'no outcome filtering; metrics selected for report relevance',
        'new_teams':0,'new_scores':0,'new_fusions':0}
    (out/'COMPACT_FULL_POOL_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'complete':True,'rows':len(all_rows),'all_258_pools_processed':True}))


if __name__=='__main__':main()
