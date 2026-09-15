"""A/B and independent expert contrasts, with explicit observational controls.

These are descriptive follow-up associations, not causal attribution. Diagnostic
adjustments may use actual n, but no adjusted n enters a pure-image predictor.
"""
from __future__ import annotations
import itertools,warnings
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
ENDPOINTS=['cdf_early7','cdf_observed_by19','late_new_geometry','half_tv','singleton_mass','within_mode_median','point_count_disagreement']


def residual(v,C):
    return v-C@np.linalg.lstsq(C,v,rcond=None)[0]


def rho(a,b):
    return float(spearmanr(a,b).statistic) if len(a)>2 and np.ptp(a)>1e-12 and np.ptp(b)>1e-12 else np.nan


def contrast_fit(z,xname,target,controls):
    d=z.dropna(subset=[xname,target,'n_valid']).copy()
    if len(d)<8 or d[xname].nunique()<2:return dict(n=len(d),status='insufficient_predictor_variation')
    X=[np.ones(len(d))]
    if 'n' in controls:X.append(np.log1p(d.n_valid.to_numpy(float)))
    if 'building' in controls:X.extend(pd.get_dummies(d.building,drop_first=True,dtype=float).to_numpy().T)
    if 'scene' in controls:X.extend(pd.get_dummies(d.scene_category,drop_first=True,dtype=float).to_numpy().T)
    C=np.asarray(X,float).T;x=d[xname].to_numpy(float);y=d[target].to_numpy(float)
    xr=residual(x,C);yr=residual(y,C)
    if float(xr@xr)<1e-9:return dict(n=len(d),status='no_within_control_variation')
    slope=float(xr@yr/(xr@xr));error=yr-slope*xr
    # Building-cluster sandwich for the partialled scalar, explicitly descriptive.
    score=pd.DataFrame({'building':d.building.to_numpy(),'s':xr*error}).groupby('building').s.sum()
    groups=len(score);se=float(np.sqrt((score@score)/(xr@xr)**2*groups/(groups-1))) if groups>1 else np.nan
    return dict(n=len(d),buildings=groups,slope=slope,cluster_se=se,lo=slope-1.96*se,hi=slope+1.96*se,partial_rho=rho(xr,yr),status='descriptive_cluster_adjusted_not_causal',residual_predictor_variance=float(np.var(xr)))


def run():
    meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False)
    target=pd.read_csv(OUT/'targets/continuous_targets.csv',keep_default_na=True)
    target['grade']=target.grade.fillna('')
    fb=pd.read_csv(OUT/'B/model_feedback.csv')
    data=target.merge(meta,on=['image_id','building'],validate='many_to_one').merge(fb,on='image_id',how='left')
    cov=[]
    for panel,d in [('all648',meta),('history205',meta[meta.image_id.isin(target.image_id)]),('assigned',meta[meta.image_id.isin(target.loc[target.grade.isin(GRADES),'image_id'])])]:
        for f in ['scene_category','fine_human','fine_ai','main_function_primary','main_space_human','main_space_source','room_status',*TRAITS,'doorway']:
            for value,g in d.groupby(f,dropna=False):cov.append(dict(panel=panel,field=f,value=value,images=len(g),buildings=g.building.nunique()))
    csv('A/coverage_and_trait_values.csv',cov)
    groups=[]
    for arm,d in data.groupby('condition'):
        for f in ['scene_category','fine_human','fine_ai','main_function_primary',*TRAITS,'doorway']+[c for c in meta if c.startswith('position_')]:
            for value,g in d.groupby(f,dropna=False):
                row=dict(condition=arm,field=f,value=value,images=len(g),buildings=g.building.nunique(),median_people=g.n_valid.median(),invalid_images=int((g.n_invalid>0).sum()),unassigned=int((~g.grade.isin(GRADES)).sum()))
                row.update({a:int(g.grade.eq(a).sum()) for a in GRADES})
                for t in ENDPOINTS:row[t+'_n']=int(g[t].notna().sum());row[t+'_mean']=g[t].mean();row[t+'_median']=g[t].median()
                groups.append(row)
    csv('A/stratified_tiers_and_process.csv',groups)
    # Co-occurrence and source provenance remain separate from outcome association.
    co=[]
    for a,b in itertools.combinations(TRAITS,2):
        for (va,vb),n in meta.groupby([a,b]).size().items():co.append(dict(field_a=a,field_b=b,value_a=va,value_b=vb,images=n))
    csv('A/trait_cooccurrence.csv',co)
    associations=[];predictor_rows=[]
    binary={}
    for field in TRAITS+['doorway']:
        for val in sorted(meta[field].astype(str).unique()):
            if val in ('','unknown','未知'):continue
            name='trait__'+field+'__'+val;binary[name]=(data[field].astype(str)==val).astype(float);predictor_rows.append(dict(feature=name,kind='sourced_trait_indicator',source_field=field,category=val))
    for col in meta:
        if col.startswith('position_'):binary[col]=pd.to_numeric(data[col],errors='coerce');predictor_rows.append(dict(feature=col,kind='first_clause_AI_position_keyword',source_field=col))
    for col in fb:
        if col!='image_id':binary[col]=data[col];predictor_rows.append(dict(feature=col,kind='numeric_model_feedback',source_field=col))
    X=pd.DataFrame(binary,index=data.index)
    for name in X:data[name]=X[name]
    for arm,d in data.groupby('condition'):
        for t in ENDPOINTS:
            for name in X:
                valid=d[[name,t]].dropna();r=rho(valid[name],valid[t]) if len(valid) else np.nan
                for controls in ('none','n','n_building_scene'):
                    result=contrast_fit(d,name,t,controls)
                    associations.append(dict(condition=arm,target=t,feature=name,controls=controls,unadjusted_rho=r,**result))
    csv('A_B/associations_with_count_building_scene_controls.csv',associations);csv('A_B/predictor_provenance.csv',predictor_rows)
    # Within-category contrasts are retained, not selected as independent replicates.
    examples=[]
    for (arm,scene),g in data.groupby(['condition','scene_category']):
        for (_,a),(_,b) in itertools.combinations(g.sort_values('image_id').iterrows(),2):
            if a.building==b.building:rel='same_building_not_necessarily_same_room'
            else:rel='same_category_different_building'
            if a.grade and b.grade and a.grade!=b.grade:
                examples.append(dict(condition=arm,scene=scene,image_a=a.image_id,image_b=b.image_id,relation=rel,grade_a=a.grade,grade_b=b.grade,n_a=a.n_valid,n_b=b.n_valid,main_a=a.main_function_primary,main_b=b.main_function_primary,singleton_a=a.singleton_mass,singleton_b=b.singleton_mass,late_new_a=a.late_new_geometry,late_new_b=b.late_new_geometry,cdf_early_a=a.p_early,cdf_early_b=b.p_early))
    csv('A/within_category_grade_contrasts.csv',examples)
    experts=pd.read_csv(OUT/'expert/independent_tags106.csv',keep_default_na=False)
    joined=data.merge(experts,on='image_id',how='inner')
    expert_code={'简单':'simple','中等':'medium','困难':'difficult_candidate'}
    joined['expert_expected_class']=joined.expert_tag.map(expert_code)
    joined['comparison_status']=np.where(~joined.grade.isin(GRADES),'historical_tier_unassigned',np.where(joined.grade==joined.expert_expected_class,'same_display_order','different_construct_or_condition'))
    themes={'occlusion':['遮挡','挡住','看不全'],'reflection':['镜','玻璃','反射'],'connected_or_scope':['连通','范围','开口','门','空间'],'multiple_interpretations':['标法','不同','多种','分歧'],'geometry_or_structure':['构造','结构','角','布局'],'limited_view':['视角','位置','局部']}
    for theme,words in themes.items():
        joined['comment_mentions_'+theme]=(joined.comment_json+' '+joined.group_comment).map(lambda s:any(w in str(s) for w in words))
    csv('expert/independent_tag_comment_process_comparison.csv',joined)
    summary=joined.groupby(['condition','expert_tag','grade','comparison_status'],dropna=False).agg(images=('image_id','nunique'),median_people=('n_valid','median')).reset_index();csv('expert/independent_comparison_summary.csv',summary)
    # Scope collapsed to one OOS direction, not a physical boundary interpretation label.
    raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz');raw=raw[raw.main_worker_included]
    sc=raw.groupby(['image_id','raw_condition']).agg(scope_known=('scope',lambda a:(a!='unknown').sum()),oos_rate=('scope',lambda a:(a[a!='unknown']=='oos').mean()),scope_unknown=('scope',lambda a:(a=='unknown').sum())).reset_index().rename(columns={'raw_condition':'condition'})
    csv('A/scope_binary_vs_geometry_process.csv',data.merge(sc,on=['image_id','condition'],how='left'))
    js('A_B/executed_summary.json',dict(historical_image_conditions=len(data),assigned_counts=data.groupby(['condition','grade']).size().to_dict(),expert_overlap_unique_images=joined.image_id.nunique(),expert_overlap_conditions=len(joined),comments_nonempty=int((experts.comment_json!='{}').sum()),group_comments_nonempty=int(experts.group_comment.ne('').sum()),association_rows=len(associations),same_category_contrast_pairs=len(examples),causal_claims=False,old_difficulty_used=False,notes=['n/building/scene controls are explanatory diagnostics, never pure prediction inputs.','AI main function is not a verified spatial-mask or camera-region truth.','Comment themes are post-hoc reading aids; original comments retained, never predictor features.']))
    print('ASSOCIATIONS',len(data),'expert overlap',joined.image_id.nunique(),'contrast pairs',len(examples),flush=True)

if __name__=='__main__':run()
