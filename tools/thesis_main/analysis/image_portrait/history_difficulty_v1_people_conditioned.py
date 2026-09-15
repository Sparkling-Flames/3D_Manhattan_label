"""Condition-specific E analysis; pooled task-adjusted axes are archival only.

The main comparison trains Q/T within the same Manual or Semi condition and
outside the complete target building. No worker is typed from a target answer.
"""
import collections,itertools,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people import boundaries_and_audit,replay


def run():
    raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz');raw=raw[raw.main_worker_included&raw.raw_condition.isin(['manual','semi'])].copy()
    bd=boundaries_and_audit(raw);raw['log_time']=np.log(raw.active_seconds.where(raw.active_seconds>0));pr=[]
    for arm,g in raw.groupby('raw_condition'):
        for building in sorted(g.building.unique()):
            train=g[g.building!=building]
            for axis,col in [('Q','quality'),('T','log_time')]:
                x=train.dropna(subset=[col]).copy();x['residual']=x[col]-x.groupby('image_id')[col].transform('median')
                for w,z in x.groupby('worker_id'):
                    ok=len(z)>=6 and z.building.nunique()>=3
                    pr.append(dict(condition=arm,target_building=building,worker_id=w,axis=axis,qualified=ok,training_responses=len(z),training_buildings=z.building.nunique(),score=z.residual.mean() if ok else np.nan,source_condition=arm))
    profiles=csv('E_conditioned/outside_building_person_scores.csv',pr)
    meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id');target=pd.read_csv(OUT/'targets/primary_per_image.csv').set_index(['image_id','condition'])
    cache={};rows=[];caps=[]
    def calculate(g):
        key=(g.image_id.iloc[0],g.raw_condition.iloc[0],tuple(sorted(g.worker_id)))
        if key not in cache:cache[key]=replay(g,bd,orders=30)
        return cache[key]
    for (i,arm),g in raw.groupby(['image_id','raw_condition']):
        building=i.split('_')[0]
        for axis in ['Q','T']:
            p=profiles[profiles.condition.eq(arm)&profiles.target_building.eq(building)&profiles.axis.eq(axis)&profiles.qualified].set_index('worker_id').score
            pool=g[g.worker_id.isin(p.index)];rank=sorted(pool.worker_id,key=lambda w:(p[w],w))
            caps.append(dict(image_id=i,condition=arm,axis=axis,observed_people=len(g),training_qualified_target_people=len(pool),unclassified_people=len(g)-len(pool)))
            for n in (4,6,8,10,12):
                if len(pool)<2*n:continue
                low=rank[:n];high=rank[-n:];mix=rank[:(n+1)//2]+rank[-n//2:]
                configurations=[('lower_axis',low),('higher_axis',high),('mixed_axis',mix)]
                rng=np.random.default_rng(seed(i,arm,axis,n,'conditioned'));seen=set()
                for repeat in range(12):
                    ws=tuple(sorted(rng.choice(rank,n,replace=False)))
                    if ws not in seen:seen.add(ws);configurations.append(('random_same_panel',list(ws)))
                for label,ws in configurations:
                    subgroup=pool[pool.worker_id.isin(ws)]
                    assert subgroup.worker_id.nunique()==n
                    rows.append(dict(image_id=i,building=building,condition=arm,axis=axis,n_people=n,composition=label,workers=';'.join(sorted(ws)),scene=meta.loc[i,'scene_category'],main_function=meta.loc[i,'main_function_primary'],full_grade=target.loc[(i,arm),'grade'],**calculate(subgroup)))
        if len(rows)%1000<40:print('CONDITIONED',i,arm,'rows',len(rows),flush=True)
    d=csv('E_conditioned/real_equal_count_compositions.csv.gz',rows);csv('E_conditioned/person_support_capacity.csv',caps)
    measures=['point_count_disagreement','singleton_mass','within_mode_median','mode_entropy','n_supported_modes','p_early7','p_by19','p_tail','late_new']
    contrasts=[]
    if len(d):
        csv('E_conditioned/composition_summary.csv',d.groupby(['condition','axis','n_people','composition'])[measures].mean().reset_index())
        for (arm,axis,n),z in d.groupby(['condition','axis','n_people']):
            avg=z.groupby(['image_id','building','composition'])[measures].mean().reset_index()
            for a,b in [('lower_axis','higher_axis'),('mixed_axis','lower_axis'),('mixed_axis','random_same_panel')]:
                joined=avg[avg.composition==a].merge(avg[avg.composition==b],on=['image_id','building'],suffixes=('_a','_b'))
                for measure in measures:
                    joined['delta']=joined[measure+'_a']-joined[measure+'_b'];contrasts.append(dict(condition=arm,axis=axis,n_people=n,composition_a=a,composition_b=b,measure=measure,**paired_ci(joined,'delta')))
        csv('E_conditioned/paired_composition_effects.csv',contrasts)
        csv('E_conditioned/within_image_subset_variation.csv',d[d.composition=='random_same_panel'].groupby(['image_id','building','condition','axis','n_people']).agg(grade_variants=('grade',lambda a:a.fillna('').nunique()),p_early_min=('p_early7','min'),p_early_max=('p_early7','max'),singleton_min=('singleton_mass','min'),singleton_max=('singleton_mass','max'),modes_min=('n_supported_modes','min'),modes_max=('n_supported_modes','max'),distinct_real_subsets=('workers','nunique')).reset_index())
    js('E_conditioned/executed_summary.json',dict(status='executed',real_subset_rows=len(rows),target_images=d.image_id.nunique() if len(d) else 0,profiles_source_condition_separated=True,outside_target_building=True,qualified_condition_worker_scores=int(profiles.qualified.sum()),orders_per_subset=30,unknown_is_not_type=True,main_use='condition-specific scores and contrasts here; E/ pooled Q/T scores are superseded for primary reporting',valid_main_E_common_people_file='E/same_room_exact_common_people.csv',limits=['Observed panel, not independently randomized worker assignment.','Time never interpreted as care.','Reference-alignment scores do not adjudicate semantic legitimacy.','Subset observations are not independent samples; intervals resample buildings.']))
    print('CONDITIONED SUMMARY',read(OUT/'E_conditioned/executed_summary.json'),flush=True)

if __name__=='__main__':run()
