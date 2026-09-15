"""Descriptive and adjusted picture links; covariates are not causal identification."""
from __future__ import annotations
import itertools,warnings
import statsmodels.api as sm
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
MEAS=['full_p_by_8','core10_p_by_19','core_tail_10','late_quarter_new','half_tv_all','within_cluster_median','singleton_share','point_count_disagreement']

def fit_contrast(d,target,trait,positive,negative,adjustment):
 q=d[d[trait].isin([positive,negative])].dropna(subset=[target]).copy()
 r=dict(target=target,trait=trait,positive=positive,negative=negative,adjustment=adjustment,images=len(q),buildings=q.building.nunique(),positive_images=int(q[trait].eq(positive).sum()),negative_images=int(q[trait].eq(negative).sum()),coefficient=np.nan,lo=np.nan,hi=np.nan,status='insufficient')
 if len(q)<10 or min(r['positive_images'],r['negative_images'])<3:return r
 x=q[trait].eq(positive).astype(float).to_numpy();Z=pd.DataFrame({'const':np.ones(len(q))},index=q.index)
 if adjustment!='unadjusted':Z['log_n_valid']=np.log(q.n_valid.to_numpy())
 if 'scene' in adjustment:Z=pd.concat([Z,pd.get_dummies(q.scene_category,prefix='scene',drop_first=True,dtype=float)],axis=1)
 if 'building' in adjustment:Z=pd.concat([Z,pd.get_dummies(q.building,prefix='b',drop_first=True,dtype=float)],axis=1)
 A=Z.to_numpy(float);res=x-A@np.linalg.lstsq(A,x,rcond=None)[0]
 if np.linalg.norm(res)<1e-7:r['status']='not_identifiable_after_controls';return r
 X=np.column_stack([x,A]);groups=q.building.to_numpy()
 if len(q)<=np.linalg.matrix_rank(X)+2 or len(set(groups))<3:r['status']='insufficient_residual_degrees';return r
 with warnings.catch_warnings():
  warnings.simplefilter('ignore');m=sm.OLS(q[target].to_numpy(float),X).fit(cov_type='cluster',cov_kwds={'groups':groups,'use_correction':True});ci=m.conf_int()[0]
 r.update(coefficient=float(m.params[0]),lo=float(ci[0]),hi=float(ci[1]),pvalue=float(m.pvalues[0]),status='descriptive_adjusted_association',residual_df=m.df_resid)
 # Largest-building removal checks concentration, not a second independent test.
 biggest=q.building.value_counts().index[0];r['largest_building']=biggest
 if adjustment=='n_scene_building':
  qq=q[q.building.ne(biggest)];rr=fit_contrast(qq,target,trait,positive,negative,'n_scene_building_nojack');r['coefficient_without_largest_building']=rr['coefficient'];r['without_largest_status']=rr['status']
 return r

def run():
 d=pd.read_csv(OUT/'targets/per_image_versions_and_process.csv');fb=pd.read_csv(V1/'B/model_feedback.csv');d=d.merge(fb,on='image_id',how='left');rows=[]
 for arm,g in d.groupby('condition'):
  for col in ['scene_category','fine_human','fine_ai','main_function_primary',*TRAITS]:
   for lev,z in g.groupby(col,dropna=False):
    r=dict(condition=arm,field=col,level=lev,images=len(z),buildings=z.building.nunique(),median_people=z.n_valid.median(),simple=int(z.review_draft_grade.eq('simple_candidate').sum()),medium=int(z.review_draft_grade.eq('medium_candidate').sum()),difficult=int(z.review_draft_grade.eq('difficult_candidate').sum()))
    for c in MEAS:r[c]=z[c].mean();r[c+'_n']=z[c].notna().sum()
    rows.append(r)
 csv('A/stratified_picture_process_links.csv',rows)
 comparisons=[('floor_boundary','partial','present'),('ceiling_boundary','partial','present'),('reflection_glass','present','unknown'),('doorway','确认','否'),('doorway','疑似','否')]
 ass=[]
 for arm,g in d[d.condition.ne('oos_geometry')].groupby('condition'):
  for t in MEAS:
   for trait,pos,neg in comparisons:
    for adj in ['unadjusted','n_scene','n_scene_building']:
     ass.append(dict(condition=arm,**fit_contrast(g,t,trait,pos,neg,adj)))
 csv('A/adjusted_picture_associations.csv',ass)
 coverage=[]
 meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv')
 for trait in TRAITS:
  c=meta[trait].fillna('unknown').value_counts();coverage.append(dict(trait=trait,images=len(meta),levels=len(c),largest_level_share=c.max()/len(meta),counts=json.dumps(c.to_dict(),ensure_ascii=False)))
 csv('A/trait_coverage.csv',coverage);js('A/measurement_limits.json',dict(floor_and_occlusion_identical=bool((meta.floor_boundary.eq('partial')==meta.corner_occlusion.eq('present')).all()),duplicate_trait_not_double_entered=True,reflection_present_vs_unknown_is_missingness_contrast=True,new_local_descriptions_provided=False,new_reviewed_grades_provided=False,control_variables_for_associations_only=['actual_n','scene','building'],exploratory_intervals_not_multiple_testing_corrected=True))
 cor=[]
 for arm,g in d[d.condition.ne('oos_geometry')].groupby('condition'):
  for x in fb.columns[1:]:
   for y in MEAS:
    q=g[[x,y,'n_valid','scene_category','building']].dropna();q=q[np.isfinite(q[x])]
    if len(q)<10 or q[x].nunique()<2 or q[y].nunique()<2:continue
    rho=spearmanr(q[x],q[y]).statistic
    X=np.column_stack([np.ones(len(q)),np.log(q.n_valid),pd.get_dummies(q.scene_category,drop_first=True,dtype=float).to_numpy(),pd.get_dummies(q.building,drop_first=True,dtype=float).to_numpy()]);xr=q[x].rank().to_numpy();yr=q[y].rank().to_numpy();xr-=X@np.linalg.lstsq(X,xr,rcond=None)[0];yr-=X@np.linalg.lstsq(X,yr,rcond=None)[0];adj=np.corrcoef(xr,yr)[0,1]if np.std(xr)>1e-8 and np.std(yr)>1e-8 else np.nan
    cor.append(dict(condition=arm,feature=x,target=y,images=len(q),buildings=q.building.nunique(),spearman=rho,rank_residual_association_n_scene_building=adj))
 csv('B/model_feedback_process_associations.csv',cor)
 gapcols=[c for c in fb if c.startswith('gap_')];d['model_gap']=d[gapcols].mean(1)
 quadrants=[]
 for arm,g in d[d.condition.ne('oos_geometry')].groupby('condition'):
  for target in ['point_count_disagreement','late_quarter_new','core_tail_10']:
   q=g.dropna(subset=['model_gap',target])
   for _,r in q.iterrows():
    tr=q[q.building.ne(r.building)];ml,mh=tr.model_gap.quantile([.25,.75]);hl,hh=tr[target].quantile([.25,.75]);m='low'if r.model_gap<=ml else 'high'if r.model_gap>=mh else 'middle';h='low'if r[target]<=hl else 'high'if r[target]>=hh else 'middle'
    quadrants.append(dict(image_id=r.image_id,condition=arm,building=r.building,target=target,model_gap=r.model_gap,human_value=r[target],model_bucket=m,human_bucket=h,model_training_q25=ml,model_training_q75=mh,human_training_q25=hl,human_training_q75=hh,n_valid=r.n_valid,candidate=r.review_draft_grade,supported_clusters=r.supported_clusters,max_cross_compatible=r.max_cross_compatible_share,scene_category=r.scene_category))
 csv('B/outside_building_quadrants.csv',quadrants)
 audit=pd.read_csv(OUT/'inputs/response_audit.csv.gz');oo=audit[audit.condition.eq('oos_geometry')&audit.main_worker]
 os=oo.groupby('image_id').agg(responses=('worker_id','size'),valid_geometry=('valid','sum'),oos_choices=('scope_choice',lambda x:x.eq('oos').sum()),in_scope_choices=('scope_choice',lambda x:x.eq('in_scope').sum()),reference_scope=('reference_scope_status','first')).reset_index()
 os=os.merge(d[d.condition.eq('oos_geometry')][['image_id','scene_category','main_function_primary',*MEAS,'n_valid','total_clusters','supported_clusters','singletons','sizes_descending']],on='image_id');csv('oos/geometry_scope_and_process.csv',os)
 # Same known high-support sample range, never pretend equality of workers.
 high=d[d.n_valid>=19];csv('A/actual_high_support_stratum_comparison.csv',high.groupby('condition')[MEAS+['n_valid','total_clusters','supported_clusters']].agg(['mean','median','count']).reset_index())
 print('ASSOCIATIONS',len(ass),len(cor),len(quadrants),flush=True)
if __name__=='__main__':run()
