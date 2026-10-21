#!/usr/bin/env python3
"""Open-K, nested-building selection of interpretable behavioral classes.

All geometry/qualification descriptors are reused unchanged. Classes are selected
only by training-building raw expression reconstruction, never team endpoints.
Every finished output is atomically replaced after row/key checks.
"""
from __future__ import annotations
import os
for _v in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[_v] = '1'
import argparse, hashlib, itertools, json, time
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.metrics import adjusted_rand_score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXPRESSION = REPO/'research/workers/personnel_marking_patterns_20261020/record_expression.csv'
PROFILE = REPO/'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz'
RAW = ['turn_n', 'short_turn_edges', 'near_straight_nodes_5deg', 'log_area', 'log_height']
HIST = ['turn_history', 'short_history', 'redundancy_history', 'area_history', 'height_history']
CONTEXT = ['simple_turn_history','complex_turn_history','complex_short_history']
DOMAINS = {
    'E': ['turn_history','short_history'],
    'R': ['redundancy_history'],
    'G': ['area_history','height_history'],
    'C': CONTEXT,
}
FAMILIES = {'TURN':['E'], 'STRUCTURE':['E','R'], 'SCALE':['G'],
            'JOINT':['E','R','G'], 'CONTEXT':['C','R','G']}
# No fixed class-count cap. A multi-member class needs three people, so the
# entire inventory supplies a mathematical upper bound; every fitted population
# is also checked at each Ward cut. Once a singleton/small branch appears, later
# cuts cannot recover capacity.
KS = list(range(2, pd.read_csv(EXPRESSION,usecols=['worker_id']).worker_id.nunique()//3+1))
WEIGHT = np.array([1/6,1/6,1/3,1/6,1/6])
KEY=['condition','layer','image_id','reference_id']

def save(d,name):
    p=HERE/name; p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.partial')
    compression={'method':'gzip','mtime':0} if p.name.endswith('.gz') else None
    d.to_csv(tmp,index=False,encoding='utf-8-sig',compression=compression)
    check=pd.read_csv(tmp,compression='gzip' if compression else None)
    assert check.shape==d.shape, (name,check.shape,d.shape)
    os.replace(tmp,p)

def js(name,x):
    p=HERE/name; tmp=p.with_name(p.name+'.partial')
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    os.replace(tmp,p)

def load():
    x=pd.read_csv(EXPRESSION)
    x['source_layer']=x.layer
    x.loc[x.quality_use.eq('special_conditional_only'),'layer']='special_conditional'
    x['turn_n']=x.pair_n-x.near_straight_nodes_5deg
    x['behavior_usable']=x.personal_comparison & x.peer_n.ge(3)
    usable=x.loc[x.behavior_usable]
    for r,h in zip(RAW,HIST):
        x[h]=x[r]-usable.groupby(KEY,dropna=False)[r].transform('median')
    x['panel_turn_median']=usable.groupby(KEY,dropna=False).turn_n.transform('median')
    x['complex_opportunity']=x.panel_turn_median.ge(6)
    x['simple_turn_history']=x.turn_history.where(~x.complex_opportunity)
    x['complex_turn_history']=x.turn_history.where(x.complex_opportunity)
    x['complex_short_history']=x.short_history.where(x.complex_opportunity)
    idx=pd.read_csv(PROFILE)
    cols=['object_id','B8L2','D10','source_active_time_seconds','time_source_kind']
    x=x.merge(idx[cols],on='object_id',validate='one_to_one')
    qok=x.quality_usable & ((~x.layer.eq('ordinary'))|x.quality_use.eq('ordinary_primary'))
    for q in ['B8L2','D10']:
        x.loc[~qok,q]=np.nan
        x[q+'_peer_delta']=x[q]-x.loc[qok].groupby(KEY,dropna=False)[q].transform('mean')
    tok=x.primary_expression & x.source_active_time_seconds.gt(0)
    x['log_seconds']=np.log(x.source_active_time_seconds.where(tok))
    x['log_time_peer_delta']=x.log_seconds-x.loc[tok].groupby(KEY+['origin','time_source_kind'],dropna=False).log_seconds.transform('mean')
    return x

class Study:
    def __init__(self,x):
        self.x=x
        self.fit=x[x.behavior_usable & x.layer.eq('ordinary')].copy()
        self.buildings=sorted(x.building_id.unique())
        self.roster=sorted(x.worker_id.unique())
        self.bb={c:sorted(g.building_id.unique()) for c,g in self.fit.groupby('condition')}
        self.fit_by={c:g.copy() for c,g in self.fit.groupby('condition')}
        self.by_image={}
        for (c,b),g in self.fit.groupby(['condition','building_id']):
            self.by_image[c,b]=g.copy()

    @lru_cache(maxsize=None)
    def features(self,c,excluded):
        d=self.fit_by[c]
        d=d[~d.building_id.isin(excluded)]
        f=d.groupby(['worker_id','building_id'])[HIST+CONTEXT].mean().groupby('worker_id').mean()
        sup=d.groupby('worker_id').agg(n_records=('object_id','size'),n_images=('image_id','nunique'),
            n_buildings=('building_id','nunique'),origin=('origin',lambda a:'|'.join(sorted(a.unique()))),
            n_quality_usable=('quality_usable','sum'),n_independent_vote_eligible=('independent_vote_eligible','sum'))
        f=f.join(sup).reindex(self.roster).rename_axis('worker_id').reset_index()
        for flag in [False,True]:
            z=d[d.complex_opportunity.eq(flag)]
            s=z.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building_id','nunique'))
            prefix='complex' if flag else 'simple'
            for col in ['images','buildings']:
                f[prefix+'_'+col]=f.worker_id.map(s[col]).fillna(0).astype(int)
        counts=['n_records','n_images','n_buildings','n_quality_usable','n_independent_vote_eligible']
        f[counts]=f[counts].fillna(0).astype(int)
        f['base_supported']=f.n_images.ge(12)&f.n_buildings.ge(4)&f[HIST].notna().all(axis=1)
        f['context_supported']=f.base_supported & f.simple_images.ge(3)&f.simple_buildings.ge(2)&f.complex_images.ge(3)&f.complex_buildings.ge(2)
        f['condition']=c
        return f

    @lru_cache(maxsize=None)
    def fitted(self,c,excluded,family):
        f=self.features(c,excluded)
        mask=f.context_supported if family=='CONTEXT' else f.base_supported
        g=f[mask].copy().reset_index(drop=True)
        if len(g)<6:return {}
        arr=[];params={}
        for domain in FAMILIES[family]:
            cols=DOMAINS[domain];a=g[cols].to_numpy(float)
            median=np.median(a,axis=0);sd=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
            sd=np.where(sd>1e-8,sd,np.std(a,axis=0));sd=np.where(sd>1e-8,sd,1.)
            arr.append(np.clip((a-median)/sd,-3,3)/np.sqrt(len(cols)*len(FAMILIES[family])))
            params[domain]={'fields':cols,'median':median.tolist(),'scale':sd.tolist(),'clip':3}
        a=np.column_stack(arr);tree=linkage(a,method='ward')
        out={}
        for k in KS:
            if k>=len(g):continue
            raw=cut_tree(tree,n_clusters=k).ravel()
            order_cols=['height_history','area_history','turn_history'] if family=='SCALE' else ['turn_history','height_history','area_history']
            order=sorted(set(raw),key=lambda j:tuple(g.loc[raw==j,order_cols].mean().tolist()))
            labels=np.array([order.index(j) for j in raw])
            sizes=np.bincount(labels,minlength=k)
            centers=g.groupby(pd.Series(labels,name='cluster'))[HIST].mean().to_numpy()
            out[k]={'workers':g.worker_id.to_numpy(),'labels':labels,'sizes':sizes,'centers':centers,
                    'eligible':bool(sizes.min()>=3),'scale':params,'features':g}
        return out

    def evaluate(self,c,excluded,target,family,k):
        fits=self.fitted(c,excluded,family)
        if k not in fits:return None
        model=fits[k];g=self.by_image.get((c,target))
        if g is None:return None
        lab=dict(zip(model['workers'],model['labels']))
        d=g[g.worker_id.isin(lab)].copy()
        if len(d)<6:return None
        tr=self.fit_by[c];tr=tr[~tr.building_id.isin(excluded)]
        # Outcome scaling is fit without either inner or outer target.
        scale=tr[HIST].std().to_numpy(float);scale=np.where(scale>1e-8,scale,1.)
        a=d[HIST].to_numpy(float);p=model['centers'][d.worker_id.map(lab).to_numpy(int)]
        e=(a-p)**2; en=e/(scale**2)
        # Same reference opportunities within image equally; then equal images.
        by=d[['image_id','reference_id']].copy()
        losses=[]
        for j,col in enumerate(HIST):
            by[col]=en[:,j]
        av=by.groupby(['image_id','reference_id'],dropna=False)[HIST].mean().groupby('image_id').mean().mean()
        return dict(condition=c,target_building=target,family=family,k=k,eligible=model['eligible'],
            min_class=int(model['sizes'].min()),workers=len(lab),records=len(d),images=d.image_id.nunique(),
            loss=float(av.to_numpy()@WEIGHT),**{col+'_nmse':float(av[col]) for col in HIST})

    def inner(self,c,outer):
        rows=[]
        inners=[b for b in self.bb[c] if b!=outer]
        for inner in inners:
            exc=tuple(sorted(set([inner]+([] if outer=='ALL' else [outer]))))
            for family in FAMILIES:
                for k in KS:
                    r=self.evaluate(c,exc,inner,family,k)
                    if r is not None:rows.append(dict(heldout_building=outer,**r))
        return rows

    def choose(self,c,outer,rows):
        d=pd.DataFrame(rows);cand=[]
        ninner=len([b for b in self.bb[c] if b!=outer])
        f0=self.features(c,() if outer=='ALL' else (outer,))
        nbase=int(f0.base_supported.sum())
        for family in FAMILIES:
            # Candidate family must cover at least 90% of base workers. Sparse
            # conditional opportunities do not win by dropping difficult people.
            outside=self.fitted(c,() if outer=='ALL' else (outer,),family)
            for k in KS:
                dd=d[(d.family==family)&(d.k==k)]
                viable=k in outside and outside[k]['eligible'] and len(outside[k]['workers'])>=.9*nbase
                passed=int(dd.eligible.sum()) if len(dd) else 0
                # Every inner target contributes if this cut forms valid classes.
                # Requiring 80% counts preserves failures explicitly in the ledger.
                ok=viable and passed>=max(5,int(np.ceil(.8*ninner)))
                # Class capacity is a selection gate; it is never a way to drop
                # an unfavorable validation building from the loss average.
                e=dd
                cand.append(dict(condition=c,heldout_building=outer,family=family,k=k,eligible_selection=ok,
                    inner_buildings=ninner,valid_inner_buildings=passed,outer_min_class=int(outside[k]['sizes'].min()) if k in outside else 0,
                    outer_workers=len(outside[k]['workers']) if k in outside else 0,
                    score=float(e.loss.mean()) if len(e) else np.nan,
                    score_se=float(e.loss.std(ddof=1)/np.sqrt(len(e))) if len(e)>1 else np.nan))
        cs=pd.DataFrame(cand);v=cs[cs.eligible_selection].copy()
        if not len(v):raise RuntimeError(('No supported candidate',c,outer,cs.to_dict('records')))
        best=v.sort_values(['score','k','family']).iloc[0]
        family=str(best.family);fine=int(best.k)
        z=d[d.family==family]
        best_scores=z[z.k.eq(fine)].set_index('target_building').loss
        coarse=fine;decisions=[]
        for k in sorted(v[(v.family==family)&v.k.le(fine)].k):
            ss=z[z.k.eq(k)].set_index('target_building').loss
            a=pd.concat([ss.rename('candidate'),best_scores.rename('fine')],axis=1).dropna()
            delta=a.candidate-a.fine
            se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else 0.
            within=bool(delta.mean()<=se+1e-12)
            decisions.append(dict(k=int(k),paired_inner_buildings=len(a),loss_delta=float(delta.mean()),paired_se=se,within_one_se=within))
            if within:coarse=min(coarse,int(k))
        return dict(condition=c,heldout_building=outer,family=family,coarse_k=coarse,fine_k=fine,
            selected_inner_loss=float(best.score),coarse_choice=decisions),cs

    def labels(self,choice):
        c,b,fam=choice['condition'],choice['heldout_building'],choice['family']
        exc=() if b=='ALL' else (b,)
        f=self.features(c,exc).copy();fit=self.fitted(c,exc,fam)
        coarse,fine=fit[choice['coarse_k']],fit[choice['fine_k']]
        mapping_c=dict(zip(coarse['workers'],coarse['labels']))
        mapping_f=dict(zip(fine['workers'],fine['labels']))
        prefix='M' if c=='manual' else 'S'
        canonical={}
        for q in sorted(set(coarse['labels'])):
            children=sorted(set(mapping_f[w] for w in mapping_c if mapping_c[w]==q))
            for j,t in enumerate(children):canonical[t]=f'{prefix}{q+1}.{j+1}'
        f['method']='V3_BEHAVIOR';f['heldout_building']=b;f['selected_family']=fam
        f['coarse_label']=f.worker_id.map({w:f'{prefix}{j+1}' for w,j in mapping_c.items()}).fillna('unknown')
        f['fine_label']=f.worker_id.map({w:canonical[j] for w,j in mapping_f.items()}).fillna('unknown')
        f['known']=f.coarse_label.ne('unknown');f['missing_reason']=''
        f.loc[~f.base_supported,'missing_reason']='fewer_than_12_images_or_4_buildings_or_invalid_geometry_features'
        if fam=='CONTEXT':f.loc[f.base_supported & ~f.context_supported,'missing_reason']='insufficient_simple_or_complex_opportunity'
        f['coarse_k']=choice['coarse_k'];f['fine_k']=choice['fine_k']
        f['label_stage']='all_data_descriptive' if b=='ALL' else 'outer_building_excluded_inner_selected'
        return f

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--features-only',action='store_true');args=ap.parse_args()
    started=time.time();x=load();study=Study(x)
    inv=x[['object_id','worker_id','condition','origin','layer','source_layer','image_id','image_code','building_id','reference_id','behavior_usable','quality_usable','quality_use','independent_vote_eligible','cleaning_disposition','complex_opportunity','pair_n']+RAW+HIST+CONTEXT+['B8L2','D10','B8L2_peer_delta','D10_peer_delta','source_active_time_seconds','time_source_kind','log_time_peer_delta']]
    save(inv,'BEHAVIOR_RECORDS.csv.gz')
    frows=[]
    for c in ['manual','semi']:
        for b in ['ALL']+study.buildings:
            f=study.features(c,() if b=='ALL' else (b,)).copy();f['heldout_building']=b;frows.append(f)
    features=pd.concat(frows,ignore_index=True)
    save(features,'CONTINUOUS_FEATURES_LOBO.csv.gz')
    save(features[features.heldout_building.eq('ALL')],'CONTINUOUS_FEATURES_ALL.csv')
    if args.features_only:return
    allinner=[];allcand=[];choices=[];labels=[]
    for c in ['manual','semi']:
        for b in ['ALL']+study.buildings:
            rows=study.inner(c,b);choice,cands=study.choose(c,b,rows)
            allinner.extend(rows);allcand.append(cands);choices.append(choice);labels.append(study.labels(choice))
            print(json.dumps({k:v for k,v in choice.items() if k!='coarse_choice'},ensure_ascii=False),flush=True)
        save(pd.concat([z for z in labels if z.condition.iloc[0]==c],ignore_index=True),f'{c.upper()}_LABELS_CHECKPOINT.csv.gz')
        save(pd.concat([z for z in allcand if z.condition.iloc[0]==c],ignore_index=True),f'{c.upper()}_CANDIDATE_SELECTION_CHECKPOINT.csv')
        # Fitted raw data are small; condition checkpoints are complete independent deliverables.
        js(f'{c.upper()}_SELECTION_CHECKPOINT.json',[z for z in choices if z['condition']==c])
    labs=pd.concat(labels,ignore_index=True);cands=pd.concat(allcand,ignore_index=True)
    save(labs[labs.heldout_building.ne('ALL')],'LABELS_LOBO.csv.gz')
    save(labs[labs.heldout_building.eq('ALL')],'LABELS_ALL_DATA.csv')
    save(cands,'CANDIDATE_SELECTION_ALL.csv')
    save(pd.DataFrame(allinner),'INNER_BUILDING_CANDIDATE_LOSSES.csv.gz')
    js('SELECTED_MODELS.json',choices)
    members=[]
    for (c,coarse,fine),g in labs[labs.heldout_building.eq('ALL')].groupby(['condition','coarse_label','fine_label']):
        members.append(dict(condition=c,coarse_label=coarse,fine_label=fine,known=bool(g.known.all()),
            n_members=len(g),members='|'.join(g.worker_id),selected_family=g.selected_family.iloc[0],
            records=int(g.n_records.sum()),member_buildings_min=int(g.n_buildings.min()),member_buildings_max=int(g.n_buildings.max()),
            old_members=int(g.origin.eq('v1').sum()),new_members=int(g.origin.eq('new').sum()),
            **{col:float(g[col].mean()) for col in HIST+CONTEXT}))
    save(pd.DataFrame(members),'CLASS_MEMBERS_AND_FEATURES.csv')
    stab=[]
    for c,g in labs.groupby('condition'):
        full=g[g.heldout_building.eq('ALL')]
        for b,zz in g[g.heldout_building.ne('ALL')].groupby('heldout_building'):
            j=zz.merge(full,on='worker_id',suffixes=('_fold','_full'))
            j=j[j.known_fold & j.known_full]
            stab.append(dict(condition=c,heldout_building=b,workers=len(j),coarse_ari=float(adjusted_rand_score(j.coarse_label_fold,j.coarse_label_full)),
                fine_ari=float(adjusted_rand_score(j.fine_label_fold,j.fine_label_full)),fold_coarse_k=int(zz.coarse_k.iloc[0]),fold_fine_k=int(zz.fine_k.iloc[0]),
                fold_family=zz.selected_family.iloc[0],condition_has_target=bool((x.condition.eq(c)&x.building_id.eq(b)).any())))
    save(pd.DataFrame(stab),'OUTER_LABEL_STABILITY.csv')
    js('DISCOVERY_RECEIPT.json',dict(seconds=time.time()-started,behavior_records=len(x),fit_records=len(study.fit),
        labels=len(labs),candidate_instances=len(cands),inner_validation_rows=len(allinner),
        input_sha256={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [EXPRESSION,PROFILE]},
        source_revision='324dba44d0a82d9d64a62965f2e549ee05165417',team_outcomes_seen=False,
        decisions='No imposed class-count cap. K is explored to inventory_size//3 and screened by actual class capacity >=3; nested held-building selection; unknown opportunity never filled with zero.'))
    print('Finished',time.time()-started,flush=True)

if __name__=='__main__': main()
