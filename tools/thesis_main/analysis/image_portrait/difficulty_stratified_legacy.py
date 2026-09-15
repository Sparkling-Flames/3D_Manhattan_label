"""Exact archived HoHoNet mean on its native overlap only, versus matched current features."""
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv import *
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_results import measure,paired

def main():
 d0=pd.read_csv(O/'images/labels106.csv');p=B/'history/historical_image_features.npz'
 with np.load(p,allow_pickle=False)as z:
  idx={s:j for j,s in enumerate(z['image_ids'].tolist())};d=d0[d0.image_id.isin(idx)].reset_index(drop=True);sel=np.array([idx[s]for s in d.image_id]);Xold=z['legacy_mean_phase0'][sel].copy()
 csv('legacy/native_labels.csv',d);n=len(d);pos=d0.set_index('image_id').loc[d.image_id].index;lookup={s:j for j,s in enumerate(d0.image_id)};rows106=[lookup[s]for s in d.image_id]
 xs={'historical_exact_phase0_mean':Xold,'current_phase0_mean':np.load(O/'cache/hohonet__legacy_current.npy')[rows106],'current_shared_global':np.load(O/'cache/hohonet__shared__global.npy')[rows106],'dino12_panorama_mean':np.load(O/'cache/dinov3__block12__panorama_mean.npy')[rows106]}
 records=[];settings=[];y=d.y.to_numpy(int);bs=sorted(d.building.unique())
 for name,X in xs.items():
  np.save(O/'cache'/f'native35__{name}.npy',X)
  for b in bs:
   tr=np.flatnonzero(d.building!=b);te=np.flatnonzero(d.building==b);inner=np.full((3,len(GRID),n,3),np.nan);out=grids(X,d,tr,te)
   for b2 in bs:
    if b2==b:continue
    fit=tr[d.building.to_numpy()[tr]!=b2];ev=tr[d.building.to_numpy()[tr]==b2]
    if len(fit):inner[:,:,ev,:]=grids(X,d,fit,ev)
   for mi,mode in enumerate(MODES):
    for alg in ['ridge','knn']:
     options=[j for j,g in enumerate(GRID)if g['algorithm']==alg];scores=[np.nanmean(rps(inner[mi,j,tr],y[tr]))for j in options];j=options[int(np.argmin(scores))]
     for i,pp in zip(te,out[mi,j]):records.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=y[i],feature=name,baseline=mode,algorithm=alg,design='native35_leave_building',p0=pp[0],p1=pp[1],p2=pp[2],prediction=int(pp.argmax()),rps=rps(pp,y[i]),brier=brier(pp,y[i]),status='ok'))
     settings.append(dict(building=b,feature=name,baseline=mode,algorithm=alg,grid=j,inner_rps=min(scores)))
 for b in bs:
  tr=np.flatnonzero(d.building!=b);te=np.flatnonzero(d.building==b)
  for mode in MODES:
   for i,pp in zip(te,cat_probs(d,tr,te,mode)):records.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=y[i],feature='baseline__'+mode,baseline='none',algorithm='frequency',design='native35_leave_building',p0=pp[0],p1=pp[1],p2=pp[2],prediction=int(pp.argmax()),rps=rps(pp,y[i]),brier=brier(pp,y[i]),status='ok'))
 z=csv('legacy/native_predictions.csv',records);csv('legacy/selection.csv',settings);csv('legacy/native_scores.csv',[dict(zip(['feature','baseline','algorithm'],k),**measure(g))for k,g in z.groupby(['feature','baseline','algorithm'])])
 pr=[]
 for mi,mode in enumerate(MODES):
  for alg in ['ridge','knn']:
   a=z[(z.feature=='historical_exact_phase0_mean')&(z.baseline==mode)&(z.algorithm==alg)];bb=z[(z.feature=='current_phase0_mean')&(z.baseline==mode)&(z.algorithm==alg)];pr.append(paired(a,bb,'archived vs current '+mode+' '+alg))
 csv('legacy/native_paired.csv',pr);savej('legacy/coverage.json',dict(labelled106=106,archived_overlap=len(d),missing_archived_for_current_tagged=106-len(d),source=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),not_relabelled=True,legacy_dt_status='no traceable dt score/reference manifest; not substituted'))
 print('LEGACY',len(d),flush=True)
if __name__=='__main__':main()
