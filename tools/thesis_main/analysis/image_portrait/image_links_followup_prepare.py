"""Audit all 239 image-condition pools, recover OOS geometry, keep both old grades."""
from __future__ import annotations
import itertools,time
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import cluster_static,one_replay,normalize_geometry,dense,dmask

def run():
 OUT.mkdir(parents=True,exist_ok=True)
 from tools.thesis_main.analysis.image_portrait.build_bundle import verify_bundle
 checked=verify_bundle(B);raw=readj(B/'human/responses.jsonl.gz');assert len(raw)==2501
 data=(B/'human/responses.jsonl.gz').read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob=='6261c30d1abf2d7ad0e71702348fc81819e783ad'
 previous=pd.read_csv(V2/'audit/response_inclusion.csv.gz').set_index('canonical_annotation_id');rows=[];bounds={};pts={}
 for r in raw:
  cid=r['canonical_annotation_id'];arm=r['raw_condition'];w=r['worker_id'];q={k:r.get(k)for k in ['canonical_annotation_id','image_id','worker_id','raw_condition','assistance_exposure','unassisted_manual_included','calculation_included','processing_status','raw_point_count','effective_point_count','imputed_point','confirmation_source']}
  q['condition']='oos_geometry'if arm=='oos'else arm;q['main_worker']=w not in EXCLUDE;q['raw_odd']=bool(r['raw_point_count']%2);q['reviewed_repair']=r['processing_status']in ('confirmed_point_removed','confirmed_point_added')and bool(r['confirmation_source']);p=r.get('effective_points_1024x512')
  if w in EXCLUDE:reason='excluded_worker'
  elif arm not in ['manual','semi','oos']:reason='unknown_condition'
  elif q['raw_odd']and not q['reviewed_repair']:reason='unconfirmed_odd_or_ambiguous'
  elif not r.get('calculation_included',True):reason='explicit_review_excluded'
  elif p is None:reason='missing_effective_geometry'
  else:
   n=normalize_geometry(p);reason=''if n['valid']else 'geometry_'+n['reason']
   if not reason:bounds[cid]=dense(n['pairs']);pts[cid]=p
  q['valid']=not reason;q['reason']=reason;ev=r.get('evidence')or{};q['historical_scope_status']=ev.get('scope_status','');q['reference_scope_status']=ev.get('reference_scope_status','')
  vals=[str(v).lower()for a in r.get('choices',[])if str(a.get('from_name','')).lower()=='scope'for v in a.get('choices',[])]
  q['scope_choice']='oos'if any(v.startswith(('oos','out_of_scope'))for v in vals)else 'in_scope'if any(v in ['normal','in_scope','in-scope']for v in vals)else 'unknown';rows.append(q)
  if arm in ['manual','semi']:assert bool(previous.loc[cid].analysis_valid)==q['valid'],cid
 d=csv('inputs/response_audit.csv.gz',rows);oldindex=readj(V2/'cache/group_index.json');oldz=np.load(V2/'cache/pairwise_geometry.npz',allow_pickle=False);index=[];arrays={};parity=[]
 for j,((i,arm),g)in enumerate(d[d.main_worker].groupby(['image_id','condition'])):
  v=g[g.valid].sort_values('worker_id');ids=v.canonical_annotation_id.to_numpy(str);pc=np.array([len(pts[c])for c in ids],int);n=len(v);dm=np.zeros((n,n))
  for a,bb in itertools.combinations(range(n),2):dm[a,bb]=dm[bb,a]=dmask(bounds[ids[a]],bounds[ids[bb]])if pc[a]==pc[bb]else 2.
  key=f'u{j:03d}';index.append(dict(key=key,image_id=i,condition=arm,n_observed=len(g),n_valid=n,n_excluded=len(g)-n));arrays.update({key+'_dm':dm,key+'_pcs':pc,key+'_workers':v.worker_id.to_numpy(str),key+'_ids':ids})
  if arm!='oos_geometry':
   old=next(r for r in oldindex if r['image_id']==i and r['condition']==arm);oid=oldz[old['key']+'_ids'].tolist();ix=[oid.index(c)for c in ids];delta=float(np.abs(dm-oldz[old['key']+'_dm'][np.ix_(ix,ix)]).max())if n else 0.;assert delta<1e-8;parity.append(dict(image_id=i,condition=arm,n_valid=n,max_distance_delta=delta))
 js('inputs/group_index.json',index);np.savez_compressed(OUT/'inputs/pairwise_geometry.npz',**arrays);js('inputs/effective_points.json',pts);csv('audit/old_pairwise_parity.csv',parity)
 o=d[d.main_worker&d.condition.eq('oos_geometry')];assert len(o)==216 and o.image_id.nunique()==9 and o.unassisted_manual_included.all()and o.assistance_exposure.eq('none').all();csv('oos/response_audit.csv',o)
 hist=d[d.main_worker];cov=[]
 for a,g in hist.groupby('condition'):cov.append(dict(condition=a,responses=len(g),images=g.image_id.nunique(),workers=g.worker_id.nunique(),valid_responses=int(g.valid.sum()),valid_images=g[g.valid].image_id.nunique(),explicit_unassisted_included=int(g.unassisted_manual_included.sum()),invalid_or_excluded_geometry=int((~g.valid).sum())))
 csv('audit/coverage.csv',cov);ost=[];ocs=[];oms=[];ors=[];ocu=[]
 for (i,a),(r,dm,pc,workers,ids)in groups().items():
  if a!='oos_geometry':continue
  for cut in [.075,.1,.125]:
   st,cs,ps,lab=cluster_static(dm,pc,cut);ident=dict(image_id=i,condition=a,building=i.split('_')[0],cut=cut,**{k:r[k]for k in ['n_observed','n_valid','n_excluded']});ost.append(dict(ident,**st))
   for h in cs:ocs.append(dict(ident,**h,medoid_worker=workers[h['medoid_index']],medoid_canonical_id=ids[h['medoid_index']]))
   if cut==.1:
    for h,cid in enumerate(ids):oms.append(dict(image_id=i,condition=a,worker_id=workers[h],canonical_annotation_id=cid,point_count=pc[h],cluster=lab[h],cluster_people=int(np.sum(lab==lab[h]))))
    ss,cc,_=one_replay(dm,pc,cut,200,i,a,False);ors+=ss;ocu+=cc
  print('OOS',i,len(pc),flush=True)
 csv('oos/static_all_cuts.csv',ost);csv('oos/cluster_evidence.csv',ocs);csv('oos/mode_memberships.csv',oms);csv('oos/per_order_onsets.csv.gz',ors);csv('oos/prefix_curves.csv',ocu)
 meta=pd.read_csv(V1/'inputs/image_metadata_whitelist.csv',keep_default_na=False);csv('inputs/image_metadata_whitelist.csv',meta)
 v2=pd.read_csv(V2/'proposal/final_review_draft_per_image.csv');v1=pd.read_csv(V1/'targets/primary_with_robustness.csv');assert v2.user_final_grade.isna().all()
 first=v1[['image_id','condition','grade','status_x']].rename(columns={'grade':'grade_v1','status_x':'status_v1'})
 keep=['image_id','condition','building','n_observed','n_valid','n_excluded','total_clusters','supported_clusters','singletons','singleton_share','supported_share','largest_share','point_count_disagreement','within_cluster_median','sizes_descending','min_supported_loo_jaccard','max_cross_compatible_share','weakly_separated_supported_pair','min_sub80_jaccard','review_draft_grade','review_draft_reason','full_p_by_8','core10_p_by_19','full_tail_no_gate','core_tail_10','late_quarter_new','late_half_new','late_quarter_structure','late_quarter_repartition','half_tv_all','half_tv_core']
 targets=v2[keep].merge(first,on=['image_id','condition'],how='left');od=pd.DataFrame(ost);od=od[od.cut.eq(.1)].copy();rr=pd.DataFrame(ors);stats=[]
 for (i,a),g in rr.groupby(['image_id','condition']):stats.append(dict(image_id=i,condition=a,full_p_by_8=np.mean(g.full_onset_no_gate<=8),core10_p_by_19=np.mean(g.core_onset_10<=19),full_tail_no_gate=g.full_tail_no_gate.mean(),core_tail_10=g.core_tail_10.mean(),**{c:g[c].mean()for c in ['late_quarter_new','late_half_new','late_quarter_structure','late_quarter_repartition','half_tv_all','half_tv_core']}))
 od=od.merge(pd.DataFrame(stats),on=['image_id','condition']);od['review_draft_grade']='not_assigned_scope_separate';od['review_draft_reason']='OOS geometry separate; no in-scope relabeling';od['grade_v1']='';od['status_v1']='previously_not_geometrically_analysed'
 targets=pd.concat([targets,od],ignore_index=True).merge(meta.drop(columns='building'),on='image_id',how='left');targets['review_status']='not_provided';targets['reviewed_grade']='';targets['full_requested8_exceeds_n']=targets.n_valid<8;targets['core_requested19_exceeds_n']=targets.n_valid<19;csv('targets/per_image_versions_and_process.csv',targets)
 tags=pd.read_csv(V1/'expert/independent_tags106.csv');csv('expert/contrasts_unchanged_user_tags.csv',targets.merge(tags,on='image_id',how='inner'));ids=set(hist.image_id);ex=set(tags.image_id)
 js('audit/manifest.json',dict(latest_branch_commit=INPUT_COMMIT,raw_git_blob=blob,raw_matches_latest=True,bundle_check=checked,restored_previous_pairwise_units=len(parity),new_oos_geometry_units=9,historical_unique_images=len(ids),expert_images=len(ex),intersection=len(ids&ex),union=len(ids|ex),old_historical_unique=205,new_unique_images_vs_old205=9,old_experiment_difficulty_used=False,new_user_review_json_provided=False,new_visual_review_notes_provided=False,AGENTS_root='404 at latest commit',no_new_cloud_tasks=True,no_new_visual_inference=True,exploratory_not_new_independent_confirmation=True))
 csv('targets/candidate_version_counts.csv',targets.groupby(['condition','grade_v1','review_draft_grade'],dropna=False).size().reset_index(name='units'));print('READY',cov,len(targets),flush=True)
if __name__=='__main__':run()
