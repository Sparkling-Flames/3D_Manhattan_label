"""Train-only kernel centering/PCA and nested fixed-building prediction.

Primary comparison: exact L2 feature kernels, normalized by TRAIN centered total
variance. Numerical ridge and kNN grids retain the work-package candidate values.
The kernel method is a declared new follow-up, not a claim to reproduce old z-PCA.
"""
from __future__ import annotations
import argparse,collections,itertools,time,warnings
import numpy as np,pandas as pd
from scipy.linalg import eigh
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
CONFIGS=[dict(algorithm=alg,pca=pc,parameter=p) for alg in ('ridge','knn') for pc in (None,16,32) for p in ((100.,10.,1.,.1) if alg=='ridge' else (1,3,5))]
CONT=['cdf_early7','cdf_observed_by19','late_new_geometry','half_tv','singleton_mass','within_mode_median']


def center_scale(K,tr):
    m=K[:,tr].mean(1);grand=float(K[np.ix_(tr,tr)].mean());C=K-m[:,None]-m[None,:]+grand
    var=float(np.mean(np.diag(C)[tr]));return C/max(var,1e-12)


def clipped(pred,ordinal):
    a=np.clip(pred,0,1)
    if ordinal:
        # Projection onto the two-threshold monotonic cone, rather than relabeling observations.
        bad=a[...,0]<a[...,1];avg=a.mean(-1);a[...,0]=np.where(bad,avg,a[...,0]);a[...,1]=np.where(bad,avg,a[...,1])
    return a


def grid(K,Y,tr,te,ordinal=False):
    tr=np.asarray(tr,int);te=np.asarray(te,int);n=len(tr);d=Y.shape[1]
    if not n:return np.full((len(CONFIGS),len(te),d),np.nan)
    ym=Y[tr].mean(0);yc=Y[tr]-ym
    if n<2:return np.broadcast_to(ym,(len(CONFIGS),len(te),d)).copy()
    # K was centered and scaled from tr only. Recenter removes harmless roundoff.
    A=K[np.ix_(tr,tr)];Bv=K[np.ix_(te,tr)];m=A.mean(0);grand=A.mean()
    A=A-m[None,:]-m[:,None]+grand;Bv=Bv-m[None,:]-Bv.mean(1)[:,None]+grand
    ev,U=eigh((A+A.T)/2,check_finite=False,driver='evr');jj=np.argsort(ev)[::-1];ev=np.maximum(ev[jj],0);U=U[:,jj]
    ss=np.sqrt(ev);Zt=U*ss;Zv=np.divide(Bv@U,ss[None,:],out=np.zeros((len(te),n)),where=ss[None,:]>1e-8)
    proj=U.T@yc;out=[]
    for cfg in CONFIGS:
        p=n-1 if cfg['pca'] is None else min(n-1,cfg['pca'])
        if cfg['algorithm']=='ridge':
            beta=(ss[:p,None]*proj[:p])/(ev[:p,None]+cfg['parameter']);pred=Zv[:,:p]@beta+ym
        else:
            if cfg['pca'] is None:dist=np.diag(K)[te,None]+np.diag(K)[tr][None,:]-2*K[np.ix_(te,tr)]
            else:
                x=Zv[:,:p];z=Zt[:,:p];dist=(x*x).sum(1)[:,None]+(z*z).sum(1)[None,:]-2*x@z.T
            ix=np.argsort(dist,axis=1,kind='stable')[:,:min(int(cfg['parameter']),n)];pred=Y[tr[ix]].mean(1)
        out.append(pred)
    return clipped(np.stack(out),ordinal)


class Provider:
    def __init__(self,ids):
        self.ids=list(ids);self.meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id').loc[ids]
        self.feedback=pd.read_csv(OUT/'B/model_feedback.csv').set_index('image_id').reindex(ids)
        self.registry={r['feature']:r for r in read(OUT/'kernels/registry.json')};self.stored={};self.available={}
        self.feedback_fields={
            'feedback_counts':['count_hohonet','count_bi_enclosed','count_bi_extended'],
            'feedback_heads':[c for c in self.feedback if c.startswith('bi_')],
            'feedback_rotation':[c for c in self.feedback if c.startswith(('rotation_','count_yaw'))],
            'feedback_between':[c for c in self.feedback if c.startswith('gap_')],
            'feedback_all':list(self.feedback.columns)}
    def load_deep(self,name):
        if name not in self.stored:
            z=np.load(OUT/'kernels'/self.registry[name]['file'],allow_pickle=False);lookup={i:j for j,i in enumerate(z['image_ids'].tolist())};idx=[lookup.get(i,-1) for i in self.ids];ok=np.array(idx)>=0;K=np.full((len(idx),len(idx)),np.nan);ii=np.flatnonzero(ok);K[np.ix_(ii,ii)]=z['K'][np.ix_(np.array(idx)[ok],np.array(idx)[ok])];self.stored[name]=K;self.available[name]=ok
        return self.stored[name]
    def fields(self,name):
        if name=='scene':return ['scene_category']
        if name=='main_space':return ['main_function_primary']
        if name=='fine_human':return ['fine_human']
        if name=='fine_ai':return ['fine_ai']
        if name=='traits':return TRAITS+['doorway']
        if name=='positions':return [c for c in self.meta if c.startswith('position_')]
        if name=='scene_traits':return ['scene_category',*TRAITS,'doorway']
        if name=='main_traits':return ['main_function_primary',*TRAITS,'doorway']
        return []
    def valid(self,name):
        if name.startswith('counts_plus::'):return self.valid('feedback_counts')&self.valid(name.split('::',1)[1])
        if name.startswith('main_plus::'):return self.valid(name.split('::',1)[1])
        if name in self.registry:self.load_deep(name);return self.available[name]
        if name in self.feedback_fields:
            cols=self.feedback_fields[name];return np.isfinite(self.feedback[cols].to_numpy(float)).all(1) if cols else np.zeros(len(self.ids),bool)
        return np.ones(len(self.ids),bool)
    def kernel(self,name,tr):
        if name.startswith('counts_plus::'):
            return .5*self.kernel('feedback_counts',tr)+.5*self.kernel(name.split('::',1)[1],tr)
        if name.startswith('main_plus::'):
            return .5*self.kernel('main_space',tr)+.5*self.kernel(name.split('::',1)[1],tr)
        if name in self.registry:return center_scale(self.load_deep(name),tr)
        if name in self.feedback_fields:
            X=self.feedback[self.feedback_fields[name]].to_numpy(float);mu=X[tr].mean(0);sd=X[tr].std(0);keep=sd>1e-12
            Z=(X[:,keep]-mu[keep])/sd[keep] if keep.any() else np.zeros((len(X),1));return center_scale(Z@Z.T,tr)
        cols=self.fields(name);K=np.zeros((len(self.ids),len(self.ids)))
        for col in cols:
            x=self.meta[col].astype(str).to_numpy();K+=(x[:,None]==x[None,:]).astype(float)/max(1,len(cols))
        return center_scale(K,tr)


def load_tasks():
    a=pd.read_csv(OUT/'targets/continuous_targets.csv');tasks=[]
    for arm,g in a.groupby('condition'):
        base=g.sort_values('image_id').reset_index(drop=True)
        lab=base[base.grade.isin(GRADES)].copy();code=lab.grade.map(dict(zip(GRADES,range(3)))).to_numpy()
        if len(lab):tasks.append((arm,'tier_primary',lab,np.column_stack((code>=1,code>=2)).astype(float),True))
        for target in CONT:
            q=base.dropna(subset=[target]).copy()
            if len(q):tasks.append((arm,target,q,q[[target]].to_numpy(float),False))
    return tasks


def baseline(task,meta):
    arm,target,q,Y,ordinal=task;build=q.building.to_numpy();out=[]
    for b in sorted(set(build)):
        tr=np.flatnonzero(build!=b);te=np.flatnonzero(build==b)
        for mode,col in [('constant',None),('scene_frequency','scene_category'),('main_frequency','main_function_primary'),('fine_frequency','fine_ai')]:
            for j in te:
                use=tr if col is None else tr[meta.iloc[tr][col].to_numpy()==meta.iloc[j][col]]
                fallback=not len(use)
                if not len(use):use=tr
                pred=Y[use].mean(0) if ordinal and len(use) else np.median(Y[use],axis=0) if len(use) else np.full(Y.shape[1],np.nan)
                out.append(prediction_row(arm,target,mode,'baseline',q,j,Y[j],pred,ordinal,n_train=len(use),inner_loss=np.nan,pca='None',parameter=np.nan,unseen_stratum=fallback))
    return out


def prediction_row(arm,target,feature,algorithm,q,j,truth,pred,ordinal,**extra):
    truth=np.asarray(truth,float);pred=np.asarray(pred,float);ok=np.isfinite(pred).all()
    row=dict(image_id=q.image_id.iloc[j],building=q.building.iloc[j],condition=arm,target=target,feature=feature,algorithm=algorithm,design='leave_building',prediction_status='ok' if ok else 'no_training_or_predictor',loss=float(np.mean((pred-truth)**2)) if ordinal and ok else float(np.mean(np.abs(pred-truth))) if ok else np.nan,truth=float(truth.sum()) if ordinal else float(truth[0]),prediction=float(pred.sum()) if ordinal and ok else float(pred[0]) if ok else np.nan)
    if ordinal:
        probs=np.array([1-pred[0],pred[0]-pred[1],pred[1]]) if ok else np.full(3,np.nan)
        row.update(p_simple=probs[0],p_medium=probs[1],p_difficult_candidate=probs[2],predicted_class=int(np.argmax(probs)) if ok else np.nan,correct=float(np.argmax(probs)==truth.sum()) if ok else np.nan)
    row.update(extra);return row


def evaluate(name,task):
    start=time.monotonic();arm,target,q,Y,ordinal=task;q=q.reset_index(drop=True)
    provider=Provider(q.image_id.tolist());good=provider.valid(name);build=q.building.to_numpy();bset=sorted(set(build));cache={};predrows=[];innerrows=[]
    def fit(excluded):
        key=tuple(sorted(excluded))
        if key not in cache:
            tr=np.flatnonzero(~np.isin(build,key)&good);te=np.flatnonzero(np.isin(build,key)&good)
            if len(tr):K=provider.kernel(name,tr);pr=grid(K,Y,tr,te,ordinal)
            else:pr=np.full((len(CONFIGS),len(te),Y.shape[1]),np.nan)
            cache[key]=(te,pr,len(tr))
        return cache[key]
    for b in bset:
        te,po,nt=fit([b]);score=np.zeros(len(CONFIGS));den=0
        for inner in bset:
            if inner==b:continue
            ix,pp,ntr=fit([b,inner]);valid=build[ix]==inner
            if not ntr:continue
            valid &= np.isfinite(pp).all(axis=(0,2))
            err=np.mean((pp[:,valid]-Y[ix[valid]][None])**2,axis=2) if ordinal else np.mean(np.abs(pp[:,valid]-Y[ix[valid]][None]),axis=2)
            score+=err.sum(1);den+=int(valid.sum())
        score=score/den if den else np.full(len(CONFIGS),np.nan)
        for alg in ('ridge','knn'):
            cand=[c for c,cf in enumerate(CONFIGS) if cf['algorithm']==alg]
            sel=min(cand,key=lambda c:(score[c],c)) if den else next(c for c in cand if CONFIGS[c]['pca'] is None and CONFIGS[c]['parameter']==(10 if alg=='ridge' else 1))
            cfg=CONFIGS[sel]
            for pos,j in enumerate(te):predrows.append(prediction_row(arm,target,name,alg,q,j,Y[j],po[sel,pos],ordinal,n_train=nt,inner_loss=score[sel],inner_n=den,pca='None' if cfg['pca'] is None else cfg['pca'],parameter=cfg['parameter'],training_classes=int(np.unique(Y[build!=b].sum(1)).size) if ordinal else np.nan))
            for j in np.flatnonzero((build==b)&~good):predrows.append(prediction_row(arm,target,name,alg,q,j,Y[j],np.full(Y.shape[1],np.nan),ordinal,n_train=nt,inner_loss=np.nan,inner_n=den,pca='None',parameter=np.nan))
        for j,cf in enumerate(CONFIGS):innerrows.append(dict(feature=name,condition=arm,target=target,outer_building=b,algorithm=cf['algorithm'],pca='None' if cf['pca'] is None else cf['pca'],parameter=cf['parameter'],inner_loss=score[j],inner_n=den))
    return predrows,innerrows


def run():
    (OUT/'prediction').mkdir(exist_ok=True);tasks=load_tasks();registry=read(OUT/'kernels/registry.json')
    simple=['scene','main_space','fine_human','fine_ai','traits','positions','scene_traits','main_traits','feedback_counts','feedback_heads','feedback_rotation','feedback_between','feedback_all']
    deep=[r['feature'] for r in registry]
    # All candidates separately; adding simple counts permits a genuine incremental comparison.
    candidates=simple+deep+['counts_plus::'+x for x in deep]
    candidates+=['main_plus::feedback_counts','main_plus::feedback_all']
    for name in deep:
        if ('global' in name or name=='dinov3__cls__panorama') and 'concat' not in name:candidates.append('main_plus::'+name)
    base=[]
    metadata=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id')
    for task in tasks:base.extend(baseline(task,metadata.loc[task[2].image_id].reset_index()))
    csv('prediction/baselines.csv.gz',base)
    completed=[];failed=[]
    for counter,name in enumerate(candidates):
        stem=name.replace('::','___');dest=OUT/'prediction'/(stem+'.csv.gz')
        if dest.exists():completed.append(name);continue
        rows=[];inner=[];t0=time.monotonic()
        try:
            for task in tasks:
                a,b=evaluate(name,task);rows+=a;inner+=b
            csv('prediction/'+stem+'.csv.gz',rows);csv('prediction/'+stem+'.inner.csv.gz',inner);completed.append(name)
        except Exception as e:failed.append(dict(feature=name,error=repr(e)))
        print('PREDICT',counter+1,len(candidates),name,'seconds',round(time.monotonic()-t0,2),'rows',len(rows),flush=True)
    js('prediction/execution.json',dict(completed=completed,failed=failed,candidate_count=len(candidates),model_selection='outer leave-building, inner leave-building; layer selection from saved inner losses only',normalization='per-image L2 then training-centered total-variance scaling; feedback per-column z-scaling training-side; additive blocks equal weight',configurations=CONFIGS,exploratory_reuse='same historical images already examined in previous rounds; not new independent validation'))
    summarize()


def summarize():
    frames=[]
    for p in (OUT/'prediction').glob('*.csv.gz'):
        if p.name.endswith('.inner.csv.gz') or p.name in ['all_predictions.csv.gz','selected_predictions.csv.gz']:continue
        z=pd.read_csv(p)
        if 'loss' in z:frames.append(z)
    if not frames:return
    data=pd.concat(frames,ignore_index=True);selected=[]
    regs={r['feature']:r['family'] for r in read(OUT/'kernels/registry.json')}
    pools={
        'selected_existing_deep':[k for k,v in regs.items() if v!='dinov3'],
        'selected_dino':[k for k,v in regs.items() if v=='dinov3'],
        'selected_all_deep':list(regs),
        'selected_counts_plus_existing':['counts_plus::'+k for k,v in regs.items() if v!='dinov3'],
        'selected_counts_plus_dino':['counts_plus::'+k for k,v in regs.items() if v=='dinov3'],
        'selected_main_plus_existing':['main_plus::'+k for k,v in regs.items() if v!='dinov3'],
        'selected_main_plus_dino':['main_plus::'+k for k,v in regs.items() if v=='dinov3']}
    selection_log=[]
    for pool,names in pools.items():
        z=data[data.feature.isin(names)]
        for key,g in z.groupby(['condition','target','algorithm','building']):
            score=g.groupby('feature').agg(inner_loss=('inner_loss','first'),inner_n=('inner_n','first'))
            score=score[score.inner_n==score.inner_n.max()]
            if not len(score):continue
            best=score.inner_loss.fillna(np.inf).sort_values(kind='stable').index[0]
            q=g[g.feature==best].copy();q['selected_candidate']=best;q['feature']=pool;selected.append(q)
            selection_log.append(dict(pool=pool,condition=key[0],target=key[1],algorithm=key[2],outer_building=key[3],selected_candidate=best,inner_loss=score.loc[best,'inner_loss'],inner_n=score.loc[best,'inner_n']))
    if selected:data=pd.concat([data,*selected],ignore_index=True)
    meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False)
    data=data.merge(meta[['image_id','source_split','scene_category','main_function_primary','room_id','room_status']],on='image_id',how='left')
    csv('prediction/all_predictions.csv.gz',data);csv('C/training_only_layer_selection.csv',selection_log)
    rows=[]
    for keys,g in data.groupby(['feature','algorithm','condition','target']):
        good=g.dropna(subset=['loss'])
        r=dict(zip(['feature','algorithm','condition','target'],keys),target_images=g.image_id.nunique(),predicted_images=good.image_id.nunique(),buildings=good.building.nunique(),image_loss=good.loss.mean(),building_macro_loss=good.groupby('building').loss.mean().mean(),metric='RPS' if keys[3]=='tier_primary' else 'MAE')
        if keys[3]=='tier_primary':
            r['accuracy']=good.correct.mean()
            for c,name in enumerate(GRADES):r['recall_'+name]=good.loc[good.truth==c,'correct'].mean()
        rows.append(r)
    csv('prediction/score_summary.csv',rows)
    wanted=['constant','scene_frequency','main_frequency','feedback_counts','feedback_all','selected_existing_deep','selected_dino','selected_all_deep','selected_counts_plus_existing','selected_counts_plus_dino','selected_main_plus_existing','selected_main_plus_dino']
    paired=[]
    for (arm,t),g in data[data.feature.isin(wanted)].groupby(['condition','target']):
        gg=g[(g.algorithm=='ridge')|g.algorithm.eq('baseline')];by={n:z[['image_id','building','loss']] for n,z in gg.groupby('feature')}
        for a,b in [('feedback_counts','constant'),('feedback_all','feedback_counts'),('selected_existing_deep','feedback_counts'),('selected_dino','feedback_counts'),('selected_counts_plus_existing','feedback_counts'),('selected_counts_plus_dino','feedback_counts'),('selected_main_plus_existing','main_frequency'),('selected_main_plus_dino','main_frequency'),('selected_all_deep','selected_existing_deep')]:
            if a not in by or b not in by:continue
            z=by[a].merge(by[b],on=['image_id','building'],suffixes=('_new','_base'));z['delta']=z.loss_new-z.loss_base
            paired.append(dict(condition=arm,target=t,new=a,baseline=b,**paired_ci(z,'delta')))
    csv('prediction/paired_increment.csv',paired)
    # Conservative room folds are exactly the corresponding building-excluded predictions.
    folds=read(B/'evaluation/folds.jsonl.gz');roomrows=[]
    for f in folds:
        if f['design']=='leave_supported_room_conservative':
            q=data[data.image_id.isin(f['test'])].copy();q['room_fold']=f['fold_id'];roomrows.append(q)
    if roomrows:
        z=pd.concat(roomrows,ignore_index=True);csv('prediction/conservative_room_predictions.csv.gz',z)
        csv('prediction/conservative_room_summary.csv',z.groupby(['feature','algorithm','condition','target']).agg(images=('image_id','nunique'),image_loss=('loss','mean')).reset_index())
    print('SCORES',pd.DataFrame(rows).query("feature in @wanted and (algorithm=='ridge' or algorithm=='baseline')").to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--summarize-only',action='store_true');a=p.parse_args();summarize() if a.summarize_only else run()
