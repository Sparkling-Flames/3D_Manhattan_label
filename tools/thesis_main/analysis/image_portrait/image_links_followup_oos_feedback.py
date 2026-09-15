"""Read inherited numeric exports for nine omitted OOS images, never pixels.

These are explicitly pinned e086 model outputs, not claimed to be new DINO.
They supplement the 205-image current-kernel comparison without changing it.
Original transported files are copied and hashed; the small regression is a
fixed-alpha descriptive leave-building supplement, no layer winner selection.
"""
from __future__ import annotations
import io,itertools,zipfile,argparse
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_models import dense_corners,distance,extract_one,normalize_rows
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict import center_scale
from scipy.linalg import solve

def export_source(archive_root):
 ids={i for i,c in groups()if c=='oos_geometry'};dest=OUT/'inputs/oos_inherited_model_arrays';dest.mkdir(parents=True,exist_ok=True);manifest=[]
 for num in range(6):
  p=Path(archive_root)/f'portrait_numeric_{num}_artifact.zip'
  with zipfile.ZipFile(p)as z,zipfile.ZipFile(io.BytesIO(z.read(z.namelist()[0])))as inner:
   m=json.loads(inner.read('NUMERIC_TRANSPORT_MANIFEST.json'));assert m['input_commit']=='e086b2b94d60b8a858a71f0326f12930538fe4fe'
   for name in inner.namelist():
    if not name.endswith('.npz')or Path(name).stem not in ids:continue
    data=inner.read(name);q=dest/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data);manifest.append(dict(path=str(q.relative_to(OUT)),source_artifact=p.name,transported_member=name,input_commit=m['input_commit'],sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),actual_read=True))
 csv('audit/oos_inherited_model_sources.csv',manifest);return dest

def feedback(dest,ids):
 out=[];fails=[]
 for i in ids:
  row=dict(image_id=i);bounds={}
  for model in ['hohonet','bilayout','ulayout']:
   p=dest/'predictions'/model/(i+'.npz')
   try:
    with np.load(p,allow_pickle=False)as z:
     if model=='hohonet':
      counts=[len(z[f'yaw{y}__post__cor_id'])for y in [0,90,180,270]];row['count_hohonet']=np.median(counts);row['count_yaw_range_hohonet']=np.ptp(counts);bounds['hohonet']=[np.clip(np.rint((z[f'yaw{y}__raw__bon']/np.pi+.5)*512),0,511)for y in [0,90,180,270]]
     elif model=='bilayout':
      for head in ['enclosed','extended']:
       cs=[z[f'yaw{y}__post__corners_{head}']for y in [0,90,180,270]];row['count_bi_'+head]=np.median([len(c)for c in cs]);row['count_yaw_range_bi_'+head]=np.ptp([len(c)for c in cs]);bounds['bi_'+head]=[dense_corners(c)for c in cs]
      row['bi_head_geometry_gap']=np.mean([distance(a,b)for a,b in zip(bounds['bi_enclosed'],bounds['bi_extended'])]);row['bi_height_head_gap']=np.mean([abs(z[f'yaw{y}__raw__height_enclosed']-z[f'yaw{y}__raw__height_extended']).mean()for y in [0,90,180,270]])
     else:bounds['ulayout']=[np.clip(np.rint(z[f'yaw{y}_boundary_pixels_float']),0,511)for y in [0,90,180,270]]
   except Exception as e:fails.append(dict(image_id=i,model=model,error=repr(e)))
  for name,bb in bounds.items():row['rotation_'+name]=np.mean([distance(a,b)for a,b in itertools.combinations(bb,2)])
  for a,b in itertools.combinations(bounds,2):row['gap_'+a+'_'+b]=np.mean([distance(x,y)for x,y in zip(bounds[a],bounds[b])])
  out.append(row)
 csv('oos/model_feedback_failures.csv',fails);return csv('oos/model_feedback_inherited.csv',out)

def run(archive_root=None):
 dest=export_source(archive_root)if archive_root else OUT/'inputs/oos_inherited_model_arrays';ids=sorted(i for i,c in groups()if c=='oos_geometry');fb=feedback(dest,ids).set_index('image_id');data=pd.read_csv(OUT/'targets/per_image_versions_and_process.csv');data=data[data.condition.eq('oos_geometry')].set_index('image_id').loc[ids];registry=[];matrices={}
 for model in ['hohonet','bilayout','ulayout','da3']:
  rows=collections.defaultdict(list)
  for i in ids:
   with np.load(dest/'features'/model/(i+'.npz'),allow_pickle=False)as z:
    if model=='da3':features=extract_one(z,model)
    else:
     features={}
     for key in z.files:
      if key.endswith('__global')or key.endswith('__local16'):
       layer,pool=key.split('__');pool='regions'if pool=='local16'and model in ['hohonet','bilayout']else pool;features[model+'__'+layer+'__'+pool]=z[key].ravel()
     if model=='hohonet'and 'legacy_single_phase_mean'in z:features['hohonet__legacy_current']=z['legacy_single_phase_mean']
    for name,x in features.items():rows[name].append(x)
  for name,v in rows.items():
   X=np.stack(v);xn,ok=normalize_rows(X);assert ok.all();matrices[name]=xn@xn.T;registry.append(dict(feature=name,model=model,images=9,dimension=X.shape[1],source_version='inherited_e086_numerical_outputs',inference_calls=0))
 csv('C/oos_inherited_candidate_inventory.csv',registry);(OUT/'oos/kernels').mkdir(exist_ok=True)
 for name,K in matrices.items():np.savez_compressed(OUT/'oos/kernels'/(name+'.npz'),image_ids=np.array(ids),K=K)
 targets=['core10_p_by_19','core_tail_10','late_quarter_new','half_tv_all','singleton_share'];names=['constant','scene_frequency','feedback_counts',*matrices];out=[];build=data.building.to_numpy()
 for target in targets:
  y=data[target].to_numpy(float)
  for j,i in enumerate(ids):
   tr=np.flatnonzero(build!=build[j]);ym=y[tr].mean()
   for name in names:
    if name=='constant':pred=np.median(y[tr])
    elif name=='scene_frequency':
     ix=tr[data.scene_category.iloc[tr].to_numpy()==data.scene_category.iloc[j]];pred=np.median(y[ix])if len(ix)else np.median(y[tr])
    else:
     if name=='feedback_counts':
      X=fb[['count_hohonet','count_bi_enclosed','count_bi_extended']].to_numpy(float);mu=X[tr].mean(0);sd=X[tr].std(0);X=(X-mu)/np.where(sd>1e-10,sd,1);K=center_scale(X@X.T,tr)
     else:K=center_scale(matrices[name],tr)
     pred=K[j,tr]@solve(K[np.ix_(tr,tr)]+10*np.eye(len(tr)),y[tr]-ym,assume_a='pos')+ym;pred=np.clip(pred,0,1)
    out.append(dict(image_id=i,condition='oos_geometry',building=build[j],target=target,feature=name,truth=y[j],prediction=pred,loss=abs(pred-y[j]),training_images=len(tr),alpha=10,preprocessing='per-image L2 then training-side center and total variance scale',design='fixed_leave_building_oos_only',source_version='inherited_e086'))
 o=csv('oos/fixed_candidate_predictions.csv',out);csv('oos/fixed_candidate_score_summary.csv',o.groupby(['target','feature']).agg(images=('image_id','size'),buildings=('building','nunique'),mae=('loss','mean')).reset_index());csv('B/oos_feedback_process_join.csv',data.reset_index().merge(fb.reset_index(),on='image_id',suffixes=('','_model')))
 js('oos/model_supplement_method.json',dict(original_model_input='e086b2b9, inherited already transported numerical output',actually_retrieved_images=9,models=['hohonet','bilayout','ulayout','da3'],candidates=len(matrices),newer_dino_not_substituted=True,dino_missing_oos_ids=ids,fit='fixed ridge alpha10 no PCA, separately for nine OOS targets; no internal layer winner',strict_scope_separation=True,no_original_images=True,no_new_cloud_tasks=True))
 print('OOS MODEL',len(registry),'candidates',len(o),'predictions',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archives');a=p.parse_args();run(a.archives)
