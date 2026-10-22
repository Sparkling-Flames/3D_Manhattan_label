#!/usr/bin/env python3
"""Difficulty strata for the newly unified full exchange comparison.

Input rows already average exact backgrounds within image; average images within
building, then buildings. Do not pool events or silently merge stages/directions.
"""
import numpy as np
import pandas as pd
from analyze_difficulty import HERE,ROOT,save,write_json

def main():
    path=HERE.parent/'exchanges'
    cond=pd.read_csv(path/'ALL_CONDITIONS.csv')
    img=pd.read_csv(path/'ALL_IMAGE_EFFECTS.csv.gz')
    scope=pd.read_csv(ROOT/'research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv')
    assert scope['image'].is_unique
    current=scope[['image','coarse_class','target_id','is_oos','is_doorway']].rename(columns={'coarse_class':'current_difficulty'})
    img=img.merge(current,on='image',validate='many_to_one')
    img['difficulty_agrees']=img.difficulty.eq(img.current_difficulty)
    save(img[['condition_id','image','building','difficulty','current_difficulty','difficulty_agrees',
              'target_id','is_oos','is_doorway']],'exchange_difficulty_join.csv')
    assert img.current_difficulty.notna().all()
    assert img.difficulty_agrees.all(),'Current difficulty differs; retain both and resolve interpretation before aggregation.'
    meta=['condition_id','analysis_batch','method_id','condition','tier','source_domain','study_group',
          'direction_role','n','actual_m_AB','actual_m_AC','actual_m_BC','design']
    img=img.merge(cond[meta],on='condition_id',validate='many_to_one')
    excludes={'condition_id','building','image','difficulty','current_difficulty','difficulty_agrees','target_id','is_oos','is_doorway'}|set(meta)
    metrics=[c for c in img if c not in excludes and pd.api.types.is_numeric_dtype(img[c])]
    rows=[];buildings=[];core=[]
    for (cid,dif),g in img.groupby(['condition_id','current_difficulty'],dropna=False):
        b=g.groupby('building')[metrics].mean()
        metadata=g[meta].iloc[0].to_dict()
        line=dict(metadata,current_difficulty=dif,total_images=len(g),total_buildings=len(b))
        for m in metrics:
            vv=g[m].dropna();bb=b[m].dropna()
            rows.append(dict(metadata,current_difficulty=dif,metric=m,images=len(vv),buildings=len(bb),
                image_equal_mean=vv.mean(),building_equal_mean=bb.mean(),image_median=vv.median(),
                image_p10=vv.quantile(.1),image_p90=vv.quantile(.9),
                positive_images=int(vv.gt(1e-9).sum()),negative_images=int(vv.lt(-1e-9).sum()),zero_images=int(vv.abs().le(1e-9).sum()),
                positive_buildings=int(bb.gt(1e-9).sum()),negative_buildings=int(bb.lt(-1e-9).sum()),zero_buildings=int(bb.abs().le(1e-9).sum())))
            line[m]=bb.mean()
            if m in ['net_B8L2','cross_B8L2','symmetric_B8L2','abs_advantage_B8L2','net_recorded_time_logratio','net_fusion_turn_n']:
                for u,v in [('images',len(vv)),('buildings',len(bb)),('positive_images',int(vv.gt(1e-9).sum())),
                            ('negative_images',int(vv.lt(-1e-9).sum())),('positive_buildings',int(bb.gt(1e-9).sum()))]:line[m+'_'+u]=v
        for prefix in ['same','cross','net','symmetric']:
            c=prefix+'_recorded_time_logratio';line[prefix+'_recorded_time_pct']=100*np.expm1(line[c])
        core.append(line)
        for build,row in b.iterrows():buildings.append(dict(condition_id=cid,current_difficulty=dif,building=build,**row.to_dict()))
    full=pd.DataFrame(rows);save(full,'exchange_difficulty_full.csv.gz')
    core=pd.DataFrame(core);save(core,'exchange_difficulty_core.csv')
    bs=pd.DataFrame(buildings);save(bs,'exchange_difficulty_buildings.csv.gz')
    # Same condition and same building, not disjoint building cohorts.
    paired=[]
    for (cid,b),g in bs.groupby(['condition_id','building']):
        if not {'简单','困难'}<=set(g.current_difficulty):continue
        easy=g[g.current_difficulty.eq('简单')].iloc[0];hard=g[g.current_difficulty.eq('困难')].iloc[0]
        for m in metrics:
            if pd.notna(easy[m]) and pd.notna(hard[m]):
                paired.append(dict(condition_id=cid,building=b,metric=m,easy=easy[m],hard=hard[m],hard_minus_easy=hard[m]-easy[m]))
    ps=pd.DataFrame(paired);save(ps,'exchange_same_building_easy_hard.csv.gz')
    ps=ps.groupby(['condition_id','metric']).agg(buildings=('building','nunique'),
        easy=('easy','mean'),hard=('hard','mean'),hard_minus_easy=('hard_minus_easy','mean'),
        increased_buildings=('hard_minus_easy',lambda x:int(x.gt(1e-9).sum())),
        decreased_buildings=('hard_minus_easy',lambda x:int(x.lt(-1e-9).sum()))).reset_index()
    save(ps.merge(cond[meta],on='condition_id',validate='many_to_one'),'exchange_same_building_easy_hard_summary.csv')
    write_json('STAGE_03_EXCHANGE_DIFFICULTY.json',dict(status='saved',source_conditions=len(cond),
        image_condition_rows=len(img),difficulty_conditions=len(core),metric_rows=len(full),
        difficulty_mismatches=int((~img.difficulty_agrees).sum()),
        weighting='existing background means -> image means -> equal buildings within difficulty; stages and directions remain separate',
        new_fusion=0,new_score=0,source='exchanges/ALL_IMAGE_EFFECTS.csv.gz and ALL_CONDITIONS.csv'))
    print('Saved',len(core),'difficulty conditions;',len(full),'metric rows',flush=True)

if __name__=='__main__':main()
