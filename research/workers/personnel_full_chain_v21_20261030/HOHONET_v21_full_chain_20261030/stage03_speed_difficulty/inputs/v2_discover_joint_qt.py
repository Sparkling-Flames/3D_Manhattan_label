#!/usr/bin/env python3
"""Actual joint formation from structure/scale and Q/T, nested by building.

This is an additional candidate with a distinct use objective. Q/T are actual
clustering inputs. They are not labels appended to geometric classes after fit.
It never uses team endpoints. Times remain relative within source conventions.
"""
import os
for v in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[v]='1'
import json,time
from functools import lru_cache
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.metrics import adjusted_rand_score
import discover_behavior_classes as base

HERE=base.HERE
OUTCOMES=['turn_history','short_history','area_history','height_history','q_history','t_history']
RECORD_COLS=['turn_history','short_history','area_history','height_history','B8L2_peer_delta','log_time_peer_delta']
WEIGHTS=np.array([.125,.125,.125,.125,.25,.25])
DOMAIN={'E':['turn_history','short_history'],'G':['area_history','height_history'],
        'Q':['q_history','q_downside'],'T':['t_history'],'C':base.CONTEXT}
FAMILIES={'EQT':['E','Q','T'],'GEQT':['E','G','Q','T'],'CQT':['C','Q','T']}

class Joint(base.Study):
    @lru_cache(maxsize=None)
    def features(self,c,excluded):
        f=super().features(c,excluded).copy()
        d=self.fit_by[c];d=d[~d.building_id.isin(excluded)]
        for mode,field in [('q','B8L2_peer_delta'),('t','log_time_peer_delta')]:
            z=d[d[field].notna()]
            b=z.groupby(['worker_id','building_id'])[field].mean().groupby('worker_id').mean()
            f[mode+'_history']=f.worker_id.map(b)
            s=z.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building_id','nunique'))
            for suffix in ['images','buildings']:f[mode+'_'+suffix]=f.worker_id.map(s[suffix]).fillna(0).astype(int)
            if mode=='q':
                tail=z.groupby(['worker_id','building_id'])[field].quantile(.1).groupby('worker_id').mean()
                f['q_downside']=f.q_history-f.worker_id.map(tail)
        f['qt_supported']=f.base_supported & f.q_images.ge(8 if c=='manual' else 4) & f.q_buildings.ge(3)&f.t_images.ge(6)&f.t_buildings.ge(3)
        return f

    @lru_cache(maxsize=None)
    def fitted(self,c,excluded,family):
        f=self.features(c,excluded)
        m=f.qt_supported & (f.context_supported if family=='CQT' else True)
        g=f[m].copy().reset_index(drop=True)
        if len(g)<6:return {}
        xs=[];scales={}
        for domain in FAMILIES[family]:
            cols=DOMAIN[domain];a=g[cols].to_numpy(float)
            med=np.median(a,axis=0);s=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
            s=np.where(s>1e-8,s,np.std(a,axis=0));s=np.where(s>1e-8,s,1.)
            xs.append(np.clip((a-med)/s,-3,3)/np.sqrt(len(cols)*len(FAMILIES[family])))
            scales[domain]={'fields':cols,'median':med.tolist(),'scale':s.tolist()}
        tree=linkage(np.column_stack(xs),method='ward');out={}
        for k in base.KS:
            if k>=len(g):continue
            raw=cut_tree(tree,n_clusters=k).ravel()
            order=sorted(set(raw),key=lambda j:tuple(g.loc[raw==j,['q_history','t_history','turn_history']].mean()))
            lab=np.array([order.index(j) for j in raw]);sizes=np.bincount(lab,minlength=k)
            centers=g.groupby(pd.Series(lab,name='cluster'))[OUTCOMES].mean().to_numpy()
            out[k]={'workers':g.worker_id.to_numpy(),'labels':lab,'sizes':sizes,'centers':centers,
                    'eligible':bool(sizes.min()>=3),'scale':scales,'features':g}
        return out

    def evaluate(self,c,excluded,target,family,k):
        fit=self.fitted(c,excluded,family)
        if k not in fit:return None
        model=fit[k];g=self.by_image.get((c,target))
        if g is None:return None
        lab=dict(zip(model['workers'],model['labels']));d=g[g.worker_id.isin(lab)].copy()
        if len(d)<6:return None
        train=self.fit_by[c];train=train[~train.building_id.isin(excluded)]
        s=train[RECORD_COLS].std().to_numpy(float);s=np.where(s>1e-8,s,1.)
        pred=model['centers'][d.worker_id.map(lab).to_numpy(int)]
        e=(d[RECORD_COLS].to_numpy(float)-pred)**2/(s*s)
        keys=d[['image_id','reference_id']].copy()
        for i,col in enumerate(OUTCOMES):keys[col]=e[:,i]
        av=keys.groupby(['image_id','reference_id'],dropna=False)[OUTCOMES].mean().groupby('image_id').mean().mean()
        v=av.to_numpy();finite=np.isfinite(v)
        return dict(condition=c,target_building=target,family=family,k=k,eligible=model['eligible'],
            min_class=int(model['sizes'].min()),workers=len(lab),records=len(d),images=d.image_id.nunique(),
            loss=float((v[finite]*WEIGHTS[finite]).sum()/WEIGHTS[finite].sum()),
            **{col+'_nmse':float(av[col]) for col in OUTCOMES})

    def inner(self,c,outer):
        rows=[]
        for inner in [b for b in self.bb[c] if b!=outer]:
            excluded=tuple(sorted(set([inner]+([] if outer=='ALL' else [outer]))))
            for fam in FAMILIES:
                for k in base.KS:
                    r=self.evaluate(c,excluded,inner,fam,k)
                    if r is not None:rows.append(dict(heldout_building=outer,**r))
        return rows

    def choose(self,c,outer,rows):
        # Reuse the same capacity and paired-one-SE logic with QT-supported
        # population as the family coverage denominator.
        d=pd.DataFrame(rows);candidates=[]
        ninner=len([b for b in self.bb[c] if b!=outer]);exc=() if outer=='ALL' else (outer,)
        nbase=int(self.features(c,exc).qt_supported.sum())
        for fam in FAMILIES:
            fits=self.fitted(c,exc,fam)
            for k in base.KS:
                dd=d[(d.family==fam)&d.k.eq(k)];good=dd[dd.eligible]
                viable=k in fits and fits[k]['eligible'] and len(fits[k]['workers'])>=.9*nbase
                eligible=viable and len(good)>=max(5,int(np.ceil(.8*ninner)))
                candidates.append(dict(condition=c,heldout_building=outer,family=fam,k=k,
                    eligible_selection=eligible,inner_buildings=ninner,valid_inner_buildings=len(good),
                    outer_min_class=int(fits[k]['sizes'].min()) if k in fits else 0,
                    outer_workers=len(fits[k]['workers']) if k in fits else 0,
                    score=dd.loss.mean(),score_se=dd.loss.std(ddof=1)/np.sqrt(max(len(dd),1))))
        cs=pd.DataFrame(candidates);valid=cs[cs.eligible_selection]
        if not len(valid):raise RuntimeError(('No valid joint taxonomy',c,outer,cs.to_dict('records')))
        best=valid.sort_values(['score','k','family']).iloc[0];fam=str(best.family);fine=int(best.k);coarse=fine;details=[]
        z=d[d.family==fam];bestscore=z[z.k.eq(fine)].set_index('target_building').loss
        for k in sorted(valid[(valid.family==fam)&valid.k.le(fine)].k):
            ss=z[z.k.eq(k)].set_index('target_building').loss
            a=pd.concat([ss.rename('candidate'),bestscore.rename('fine')],axis=1).dropna();delta=a.candidate-a.fine
            se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else 0.
            within=bool(delta.mean()<=se+1e-12)
            details.append(dict(k=int(k),paired_inner_buildings=len(a),loss_delta=float(delta.mean()),paired_se=se,within_one_se=within))
            if within:coarse=min(coarse,int(k))
        return dict(condition=c,heldout_building=outer,family=fam,coarse_k=coarse,fine_k=fine,
            selected_inner_loss=float(best.score),coarse_choice=details),cs

    def labels(self,choice):
        c,b,fam=choice['condition'],choice['heldout_building'],choice['family'];exc=() if b=='ALL' else (b,)
        f=self.features(c,exc).copy();fits=self.fitted(c,exc,fam);co,fi=fits[choice['coarse_k']],fits[choice['fine_k']]
        lc=dict(zip(co['workers'],co['labels']));lf=dict(zip(fi['workers'],fi['labels']))
        prefix='J' if c=='manual' else 'K';canonical={}
        for parent in sorted(set(lc.values())):
            child=sorted(set(lf[w] for w in lc if lc[w]==parent))
            for j,k in enumerate(child):canonical[k]=f'{prefix}{parent+1}.{j+1}'
        f['method']='V3_JOINT_QT';f['heldout_building']=b;f['selected_family']=fam
        f['coarse_label']=f.worker_id.map({w:f'{prefix}{j+1}' for w,j in lc.items()}).fillna('unknown')
        f['fine_label']=f.worker_id.map({w:canonical[j] for w,j in lf.items()}).fillna('unknown')
        f['known']=f.coarse_label.ne('unknown');f['missing_reason']=''
        f.loc[~f.base_supported,'missing_reason']='insufficient_geometry_history'
        f.loc[f.base_supported & ~f.qt_supported,'missing_reason']='insufficient_own_condition_Q_or_source_compatible_T_opportunity'
        if fam=='CQT':f.loc[f.qt_supported & ~f.context_supported,'missing_reason']='insufficient_simple_or_complex_opportunity'
        f['coarse_k']=choice['coarse_k'];f['fine_k']=choice['fine_k'];f['label_stage']='all_data_descriptive' if b=='ALL' else 'outer_building_excluded_inner_selected'
        return f

def main():
    started=time.time();study=Joint(base.load());labs=[];choices=[];cands=[];inner=[]
    for c in ['manual','semi']:
        for b in ['ALL']+study.buildings:
            rows=study.inner(c,b);choice,table=study.choose(c,b,rows)
            choices.append(choice);cands.append(table);inner.extend(rows);labs.append(study.labels(choice))
            print(json.dumps({k:v for k,v in choice.items() if k!='coarse_choice'},ensure_ascii=False),flush=True)
        base.save(pd.concat([z for z in labs if z.condition.iloc[0]==c]),f'JOINT_{c.upper()}_LABELS_CHECKPOINT.csv.gz')
        base.js(f'JOINT_{c.upper()}_SELECTION_CHECKPOINT.json',[z for z in choices if z['condition']==c])
    d=pd.concat(labs,ignore_index=True)
    base.save(d[d.heldout_building.ne('ALL')],'JOINT_LABELS_LOBO.csv.gz')
    base.save(d[d.heldout_building.eq('ALL')],'JOINT_LABELS_ALL_DATA.csv')
    base.save(pd.concat(cands,ignore_index=True),'JOINT_CANDIDATE_SELECTION_ALL.csv')
    base.save(pd.DataFrame(inner),'JOINT_INNER_BUILDING_CANDIDATE_LOSSES.csv.gz')
    base.js('JOINT_SELECTED_MODELS.json',choices)
    members=[]
    for (c,co,fi),g in d[d.heldout_building.eq('ALL')].groupby(['condition','coarse_label','fine_label']):
        members.append(dict(condition=c,coarse_label=co,fine_label=fi,known=bool(g.known.all()),n_members=len(g),
            members='|'.join(g.worker_id),selected_family=g.selected_family.iloc[0],old_members=int(g.origin.eq('v1').sum()),
            new_members=int(g.origin.eq('new').sum()),**{col:float(g[col].mean()) for col in base.HIST+base.CONTEXT+['q_history','q_downside','t_history']}))
    base.save(pd.DataFrame(members),'JOINT_CLASS_MEMBERS_AND_FEATURES.csv')
    base.js('JOINT_DISCOVERY_RECEIPT.json',dict(seconds=time.time()-started,labels=len(d),input_domains=FAMILIES,
        quality='own-condition B8L2, qualified only, same-image peer mean residual, worker-building equal means; downside mean minus within-building 10th percentile',
        time='own-condition log source seconds centered within same image/origin/time_source_kind; worker-building equal means',
        geometry='same input and frozen gates as geometric candidate',objective='equal structural, scale, quality, time reconstruction domains; paired inner-building selection',
        K=base.KS,minimum_class_members=3,team_outcomes_seen=False,unknown_filled_zero=False))
    print('Joint finished',time.time()-started,flush=True)

if __name__=='__main__':main()
