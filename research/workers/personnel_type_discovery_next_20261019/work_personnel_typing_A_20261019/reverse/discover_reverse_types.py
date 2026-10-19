#!/usr/bin/env python3
"""Building-excluded reverse personnel partition discovery, Part A r1.

The archived local partitions are a historical training measurement, never a
personnel type on the test building. Every outer/inner fit recomputes historical
pair relations using exactly the listed training buildings. No connected-component
closure is used. See REGISTRATION.json and selection_common.py for frozen choices.
"""
from __future__ import annotations
import argparse, gzip, hashlib, itertools, json, math, os, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score
from selection_common import (attach_relation, building_brier, fit_calibrator,
                              predict_calibrator, one_se_choice)

HERE = Path(__file__).resolve().parent
DIFFICULTIES = ['easy', 'medium', 'hard']
DIFFICULTY_MAP = {'简单':'easy','中等':'medium','困难':'hard'}
K_VALUES = [4, 6, 8, 10]
RELATION_SOURCES = ['geometry9', 'geometry12', 'geometry9_swap_equal', 'swap_joint']
LINKAGES = ['average', 'complete']
PRIOR_BUILDINGS = 2.0
MIN_IMAGES, MIN_BUILDINGS = 6, 3
PAIR_MIN_IMAGES, PAIR_MIN_BUILDINGS = 3, 2


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    def default(x):
        if isinstance(x, (np.integer,np.floating)): return x.item()
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,Path):return str(x)
        raise TypeError(type(x).__name__)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=default)+'\n')
    os.replace(tmp,path)


def training_key(buildings):
    return hashlib.sha256('|'.join(sorted(map(str,buildings))).encode()).hexdigest()[:16]


def read_geometry_inputs(assignments, records):
    a=pd.read_csv(assignments)
    r=pd.read_csv(records)
    r=r[r.layer.eq('ordinary_manual')].copy()
    r=r.rename(columns={'building_id':'building'})
    r['difficulty_raw']=r.difficulty
    r['difficulty']=r.difficulty.replace(DIFFICULTY_MAP)
    assert len(r)==5719 and r.image_id.nunique()==177 and r.building.nunique()==22
    assert not r.duplicated(['pool_id','worker_id']).any()
    a=a[a.layer.eq('ordinary_manual') & a.method.eq('affinity')].copy()
    a=a[a.threshold_deg.isin([9,12])]
    p=a.pivot(index=['pool_id','worker_id'],columns='threshold_deg',values='cluster_id').reset_index().rename(columns={9.0:'local9',12.0:'local12'})
    r=r.merge(p,on=['pool_id','worker_id'],validate='one_to_one')
    pairs=[]
    for pool,g in r.groupby('pool_id',sort=True):
        g=g.sort_values('worker_id');meta=g.iloc[0]
        for aa,bb in itertools.combinations(g.to_dict('records'),2):
            pairs.append({'pool_id':pool,'image_id':meta.image_id,'building':meta.building,'difficulty':meta.difficulty,
                          'worker_a':aa['worker_id'],'worker_b':bb['worker_id'],
                          'same9':int(aa['local9']==bb['local9']), 'same12':int(aa['local12']==bb['local12']),
                          'same_point_count':int(aa['pair_count']==bb['pair_count']),
                          'abs_point_count_difference':abs(aa['pair_count']-bb['pair_count'])})
    p=pd.DataFrame(pairs)
    assert not p.duplicated(['pool_id','worker_a','worker_b']).any()
    return r,p


def normalize_events(path):
    needed={'event_id','panel_id','image_id','building','building_id','difficulty','k','worker_a','worker_b',
            'stable_main','joint_stable_main','joint_main','condition','layer',
            'worker_out','worker_in','removed_worker','added_worker'}
    e=pd.read_csv(path,low_memory=False,usecols=lambda c:c in needed)
    aliases={'building_id':'building','joint_stable_main':'stable_main','joint_main':'stable_main',
             'worker_out':'worker_a','worker_in':'worker_b','removed_worker':'worker_a','added_worker':'worker_b'}
    for a,b in aliases.items():
        if b not in e and a in e:e=e.rename(columns={a:b})
    if 'layer' in e:e=e[e.layer.eq('ordinary_manual')].copy()
    if 'condition' in e and not 'layer' in e:e=e[e.condition.isin(['manual','Manual'])].copy()
    req=['event_id','image_id','building','difficulty','k','worker_a','worker_b','stable_main']
    missing=[c for c in req if c not in e]
    if missing:raise ValueError(f'Event schema missing {missing}')
    if e.stable_main.dtype==object:
        mp={'True':1.,'False':0.,'true':1.,'false':0.,'1':1.,'0':0.}
        e['stable_main']=e.stable_main.astype(str).map(mp)
    else:e['stable_main']=pd.to_numeric(e.stable_main,errors='coerce')
    assert e.event_id.is_unique
    assert set(e.stable_main.dropna().unique()).issubset({0.,1.})
    # Numeric failures must already be coded unstable by the common outcome contract.
    # Missing outcome remains missing; no silent conversion of missing to zero.
    a=np.minimum(e.worker_a.astype(str).values,e.worker_b.astype(str).values)
    b=np.maximum(e.worker_a.astype(str).values,e.worker_b.astype(str).values)
    e['pair_a']=a;e['pair_b']=b
    e['k']=e.k.astype(int)
    return e.reset_index(drop=True)


class RelationStore:
    def __init__(self, records, geom_pairs, events=None):
        self.records=records;self.pairs=geom_pairs;self.events=events
        self.workers=sorted(records.worker_id.unique())
        self.cache={}

    def _relations(self, geo, ev, workers, domain):
        if domain!='global':
            geo=geo[geo.difficulty.eq(domain)]
            if ev is not None:ev=ev[ev.difficulty.eq(domain)]
        # Geometry: repeated images cannot become extra independent pair occasions.
        g=geo.groupby(['worker_a','worker_b','building','image_id'],sort=False).agg(
            same9=('same9','mean'),same12=('same12','mean'),same_point_count=('same_point_count','mean'),
            abs_point_count_difference=('abs_point_count_difference','mean')).reset_index()
        gb=g.groupby(['worker_a','worker_b','building'],sort=False)[['same9','same12','same_point_count','abs_point_count_difference']].mean().reset_index()
        prior=(g.groupby(['building','image_id'])[['same9','same12','same_point_count','abs_point_count_difference']].mean()
               .groupby('building').mean().mean()).to_dict() if len(g) else {'same9':.5,'same12':.5,'same_point_count':.5,'abs_point_count_difference':0.}
        pair_support=g.groupby(['worker_a','worker_b']).agg(n_images=('image_id','nunique'),n_buildings=('building','nunique'))
        pair_means=gb.groupby(['worker_a','worker_b'])[['same9','same12','same_point_count','abs_point_count_difference']].mean()
        ep={}; swap_prior=.5
        if ev is not None and len(ev):
            # Within image, k nodes receive equal weight; within k all registered
            # backgrounds receive equal weight. Then pair building means.
            ek=ev.groupby(['pair_a','pair_b','building','image_id','k'],sort=False).stable_main.mean().reset_index()
            ei=ek.groupby(['pair_a','pair_b','building','image_id'],sort=False).stable_main.mean().reset_index()
            eb=ei.groupby(['pair_a','pair_b','building'],sort=False).stable_main.mean().reset_index()
            es=ei.groupby(['pair_a','pair_b']).agg(n_images=('image_id','nunique'),n_buildings=('building','nunique'))
            em=eb.groupby(['pair_a','pair_b']).stable_main.mean()
            z=(ev.groupby(['building','image_id','k']).stable_main.mean().groupby(['building','image_id']).mean().groupby('building').mean())
            swap_prior=float(z.mean()) if len(z) else .5
            for key,v in em.items():
                ep[key]=(float(v),int(es.loc[key,'n_images']),int(es.loc[key,'n_buildings']))
        rows=[]
        matrices={name:np.ones((len(workers),len(workers))) for name in RELATION_SOURCES}
        for i,a in enumerate(workers):
            for j in range(i+1,len(workers)):
                b=workers[j];key=(a,b)
                if key in pair_support.index:
                    ni=int(pair_support.loc[key,'n_images']);nb=int(pair_support.loc[key,'n_buildings']);m=pair_means.loc[key]
                else:ni=nb=0;m=None
                row={'worker_a':a,'worker_b':b,'domain':domain,'n_images':ni,'n_buildings':nb,'geometry_pair_supported':ni>=PAIR_MIN_IMAGES and nb>=PAIR_MIN_BUILDINGS}
                for metric in ['same9','same12','same_point_count','abs_point_count_difference']:
                    val=float(m[metric]) if m is not None else float('nan')
                    posterior=(nb*val+PRIOR_BUILDINGS*prior[metric])/(nb+PRIOR_BUILDINGS) if nb else prior[metric]
                    row[f'{metric}_observed']=val;row[f'{metric}_posterior']=posterior;row[f'{metric}_training_prior']=prior[metric]
                v,eni,enb=ep.get(key,(float('nan'),0,0))
                post=(enb*v+PRIOR_BUILDINGS*swap_prior)/(enb+PRIOR_BUILDINGS) if enb and np.isfinite(v) else swap_prior
                row.update(swap_stability_observed=v,swap_stability_posterior=post,swap_training_prior=swap_prior,
                           n_swap_images=eni,n_swap_buildings=enb,swap_pair_supported=eni>=PAIR_MIN_IMAGES and enb>=PAIR_MIN_BUILDINGS)
                vals={'geometry9':1-row['same9_posterior'],'geometry12':1-row['same12_posterior'],
                      'swap_joint':1-post,'geometry9_swap_equal':.5*(2-row['same9_posterior']-post)}
                for src,val in vals.items():matrices[src][i,j]=matrices[src][j,i]=val
                rows.append(row)
        for d in matrices.values():np.fill_diagonal(d,0)
        return pd.DataFrame(rows),matrices

    def fit(self, train_buildings):
        train_buildings=tuple(sorted(train_buildings));key=training_key(train_buildings)
        if key in self.cache:return self.cache[key]
        rec=self.records[self.records.building.isin(train_buildings)]
        geo=self.pairs[self.pairs.building.isin(train_buildings)]
        ev=None if self.events is None else self.events[self.events.building.isin(train_buildings)]
        supports={};relations={};matrices={}
        for dom in ['global']+DIFFICULTIES:
            rr=rec if dom=='global' else rec[rec.difficulty.eq(dom)]
            ss=rr.groupby('worker_id').agg(n_images=('image_id','nunique'),n_buildings=('building','nunique'),n_records=('object_id','nunique')).reindex(self.workers).fillna(0).astype(int)
            ss['supported']=(ss.n_images>=MIN_IMAGES)&(ss.n_buildings>=MIN_BUILDINGS)
            supports[dom]=ss
            relations[dom],matrices[dom]=self._relations(geo,ev,self.workers,dom)
        out={'training_key':key,'train_buildings':list(train_buildings),'workers':self.workers,'supports':supports,'relations':relations,'matrices':matrices}
        self.cache[key]=out
        return out


def canonical_classes(workers, values, prefix='C'):
    groups={}
    for w,v in zip(workers,values):groups.setdefault(int(v),[]).append(w)
    ordered=sorted(groups.values(),key=lambda x:min(x))
    return {w:f'{prefix}{j+1:02d}' for j,grp in enumerate(ordered) for w in grp}


def cluster_labels(fit,source,algorithm,k,conditional=False):
    workers=fit['workers'];eligible=fit['supports']['global'].query('supported').index.tolist()
    pos={w:i for i,w in enumerate(workers)}
    idx=[pos[w] for w in eligible]
    labels={w:'unknown' for w in workers}
    z=None
    if len(idx)>=2:
        d=fit['matrices']['global'][source][np.ix_(idx,idx)]
        z=linkage(squareform(d,checks=True),method=algorithm,optimal_ordering=False)
        vals=cut_tree(z,n_clusters=[min(k,len(idx))]).reshape(-1)
        labels.update(canonical_classes(eligible,vals))
    elif len(idx)==1:labels[eligible[0]]='C01'
    if not conditional:return labels,z
    out={}
    for dom in DIFFICULTIES:
        supported=set(fit['supports'][dom].query('supported').index)
        for w in workers:out[(dom,w)]='unknown'
        for base in sorted(set(labels.values())-{'unknown'}):
            members=sorted(w for w in workers if labels[w]==base and w in supported)
            if not members:continue
            local={w:base for w in members}
            if len(members)>=4:
                subidx=[pos[w] for w in members]
                d=fit['matrices'][dom][source][np.ix_(subidx,subidx)]
                zz=linkage(squareform(d,checks=True),method=algorithm,optimal_ordering=False)
                cv=cut_tree(zz,n_clusters=[2]).reshape(-1)
                sizes=np.bincount(cv)
                if len(sizes)==2 and min(sizes)>=2:
                    tmp=canonical_classes(members,cv,prefix='S')
                    local={w:base+'_'+tmp[w] for w in members}
            for w,c in local.items():out[(dom,w)]=c
    return out,z


def candidates(include_swap=True):
    out=[]
    for src in RELATION_SOURCES:
        if not include_swap and 'swap' in src:continue
        for alg in LINKAGES:
            for k in K_VALUES:
                for cond in [False,True]:
                    name=f'reverse_{src}_{alg}_K{k}'+('_difficulty' if cond else '_global')
                    out.append({'method_id':name,'source':src,'algorithm':alg,'k':k,'conditional':cond})
    return out


def class_rows(fit,cand,labels,fold_id,heldout):
    out=[];domains=DIFFICULTIES if cand['conditional'] else ['global']
    for dom in domains:
        support=fit['supports'][dom]
        for w in fit['workers']:
            c=labels.get((dom,w),'unknown') if cand['conditional'] else labels.get(w,'unknown')
            s=support.loc[w]
            out.append({'data_release':'v2','method_id':cand['method_id'],'fold_id':fold_id,'heldout_building':heldout,
                        'training_key':fit['training_key'],'worker_id':w,'condition':'ordinary_manual','domain':dom,'difficulty':dom,
                        'class_id':c,'n_images':int(s.n_images),'n_buildings':int(s.n_buildings),'n_records':int(s.n_records),
                        'unknown_reason':'' if c!='unknown' else 'fewer_than_6_training_images_or_3_buildings',
                        'information_stage':'history_before_target_building','declared_base_k':cand['k'],
                        'relation_source':cand['source'],'linkage':cand['algorithm']})
    return out


def class_diagnostics(fit,cand,labels,fold_id):
    out=[];domains=DIFFICULTIES if cand['conditional'] else ['global']
    for dom in domains:
        lab={w:labels.get((dom,w),'unknown') if cand['conditional'] else labels.get(w,'unknown') for w in fit['workers']}
        rel=fit['relations'][dom]
        for c in sorted(set(lab.values())):
            mem=sorted(w for w,t in lab.items() if t==c)
            g=rel[rel.worker_a.isin(mem)&rel.worker_b.isin(mem)]
            supported=g[g.geometry_pair_supported]
            sw=g[g.swap_pair_supported]
            replaceable=set(supported.worker_a)|set(supported.worker_b)
            out.append({'method_id':cand['method_id'],'fold_id':fold_id,'training_key':fit['training_key'],'domain':dom,'class_id':c,
                        'members':'|'.join(mem),'n_members':len(mem),'singleton':len(mem)==1,'doubleton':len(mem)==2,
                        'possible_within_pairs':len(g),'supported_geometry_pairs':len(supported),'supported_swap_pairs':len(sw),
                        'geometry_replaceable_members':len(replaceable),
                        'unsupported_pair_share':1-len(supported)/len(g) if len(g) else np.nan,
                        'same9_observed_mean':supported.same9_observed.mean(),
                        'same9_observed_p10':supported.same9_observed.quantile(.1),
                        'same9_observed_min':supported.same9_observed.min(),
                        'bad_geometry_tail_share_p_lt_point2':supported.same9_observed.lt(.2).mean() if len(supported) else np.nan,
                        'swap_stability_observed_mean':sw.swap_stability_observed.mean(),
                        'swap_stability_observed_p10':sw.swap_stability_observed.quantile(.1),
                        'swap_stability_observed_min':sw.swap_stability_observed.min()})
    return out


def geometry_only(args):
    start=time.time();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    rec,pairs=read_geometry_inputs(args.assignments,args.records)
    rec.to_csv(out/'ordinary_records.csv.gz',index=False)
    pairs.to_csv(out/'historical_geometry_pair_observations.csv.gz',index=False)
    store=RelationStore(rec,pairs)
    splits=json.loads(Path(args.splits).read_text())['folds']
    classes=[];diags=[];fits=[];rels=[]
    for fold,sp in splits.items():
        fit=store.fit(sp['train_buildings']);fits.append({'fold_id':fold,'training_key':fit['training_key'],'train_buildings':fit['train_buildings']})
        for dom,rr in fit['relations'].items():
            rr=rr.copy();rr['fold_id']=fold;rr['training_key']=fit['training_key'];rels.append(rr)
        for c in candidates(include_swap=False):
            lab,_=cluster_labels(fit,c['source'],c['algorithm'],c['k'],c['conditional'])
            classes+=class_rows(fit,c,lab,fold,'' if fold=='FULL' else fold)
            diags+=class_diagnostics(fit,c,lab,fold)
        print(f'geometry {fold} train={len(fit["train_buildings"])}',flush=True)
    pd.DataFrame(classes).to_csv(out/'geometry_candidate_classes.csv.gz',index=False)
    pd.DataFrame(diags).to_csv(out/'geometry_candidate_class_diagnostics.csv.gz',index=False)
    pd.concat(rels,ignore_index=True).to_csv(out/'geometry_person_pair_relations.csv.gz',index=False)
    write_json(out/'GEOMETRY_STAGE_RECEIPT.json',{'new_computation':True,'source_local_partition_cache':'archived assignments reused byte-for-byte; personnel relationships and partitions newly computed',
      'input_sha256':{str(args.assignments):sha256(args.assignments),str(args.records):sha256(args.records),str(args.splits):sha256(args.splits)},
      'n_records':len(rec),'n_images':rec.image_id.nunique(),'n_buildings':rec.building.nunique(),'n_workers':rec.worker_id.nunique(),
      'pair_observations':len(pairs),'n_candidate_methods':len(candidates(False)),'class_rows':len(classes),'fits':fits,'seconds':time.time()-start})


def complexity(labels,cond):
    if not cond:return len(set(labels.values())-{'unknown'})
    return float(np.mean([len(set(v for (d,w),v in labels.items() if d==dom)-{'unknown'}) for dom in DIFFICULTIES]))


def run_discovery(args):
    start=time.time();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    rec,pairs=read_geometry_inputs(args.assignments,args.records)
    ev=normalize_events(args.events)
    if args.panel_id:ev=ev[ev.panel_id.eq(args.panel_id)].copy()
    if 'panel_id' not in ev:raise ValueError('panel_id required to exclude evaluation-only backgrounds from training')
    training_ev=ev[ev.panel_id.eq(args.training_panel)].copy()
    if len(training_ev)!=270370:raise ValueError(f'Incomplete registered training panel: {len(training_ev)} rather than 270370')
    if not set(ev.building).issubset(set(rec.building)):raise ValueError('Unknown event building')
    ev['difficulty']=ev.difficulty.replace(DIFFICULTY_MAP)
    training_ev['difficulty']=training_ev.difficulty.replace(DIFFICULTY_MAP)
    store=RelationStore(rec,pairs,training_ev)
    splits=json.loads(Path(args.splits).read_text())['folds']
    candlist=candidates(True)
    if args.folds: splits={f:s for f,s in splits.items() if f in args.folds.split(',')}
    for fold,sp in splits.items():
        foldpath=out/'folds'/fold;foldpath.mkdir(parents=True,exist_ok=True)
        if (foldpath/'COMPLETE.json').exists() and not args.force:
            print(f'reuse_complete_discovery {fold}',flush=True);continue
        t0=time.time();fit=store.fit(sp['train_buildings']);train=training_ev[training_ev.building.isin(sp['train_buildings'])]
        test=ev[ev.building.eq(fold)] if fold!='FULL' else ev.iloc[:0]
        allclasses=[];diags=[];inner_scores=[];inner_meta=[];inner_classes=[];calibration_rows=[];preds=[];complexrows=[]
        labs={}
        for ci,c in enumerate(candlist):
            lab,_=cluster_labels(fit,c['source'],c['algorithm'],c['k'],c['conditional']);labs[c['method_id']]=lab
            allclasses+=class_rows(fit,c,lab,fold,'' if fold=='FULL' else fold)
            diags+=class_diagnostics(fit,c,lab,fold)
            complexrows.append({'method_id':c['method_id'],'complexity_order':complexity(lab,c['conditional']),
                                'tie_order':(1000 if c['conditional'] else 0)+RELATION_SOURCES.index(c['source'])*100+LINKAGES.index(c['algorithm'])*10+c['k']})
            trrel=attach_relation(train,lab,'difficulty' if c['conditional'] else 'global')
            cal=fit_calibrator(train,trrel)
            if len(test):
                terel=attach_relation(test,lab,'difficulty' if c['conditional'] else 'global')
                p=predict_calibrator(cal,test,terel)
                preds.append(pd.DataFrame({'event_id':test.event_id,'method_id':c['method_id'],'fold_id':fold,
                                           'relation':terel,'predicted_stability':p,'probability':p,'training_key':fit['training_key']}))
            for (k,d),p in cal['cells'].items():calibration_rows.append({'method_id':c['method_id'],'fold_id':fold,'k':k,'difficulty':d,'relation':'unknown','probability':p,'n_buildings':None})
            for (k,d,r),p in cal['rates'].items():calibration_rows.append({'method_id':c['method_id'],'fold_id':fold,'k':k,'difficulty':d,'relation':r,'probability':p,'n_buildings':cal['support'][(k,d,r)]})
        for inner,held in sp['inner_validation_groups'].items():
            itr=[b for b in sp['train_buildings'] if b not in held]
            infit=store.fit(itr)
            itrain=train[train.building.isin(itr)];ival=train[train.building.isin(held)]
            if not len(ival):continue
            for c in candlist:
                lab,_=cluster_labels(infit,c['source'],c['algorithm'],c['k'],c['conditional'])
                inner_classes+=class_rows(infit,c,lab,f'{fold}__inner{inner}','|'.join(held))
                trrel=attach_relation(itrain,lab,'difficulty' if c['conditional'] else 'global')
                cal=fit_calibrator(itrain,trrel)
                valrel=attach_relation(ival,lab,'difficulty' if c['conditional'] else 'global')
                p=predict_calibrator(cal,ival,valrel)
                score=building_brier(ival,p);score['method_id']=c['method_id'];score['inner_group']=inner
                score['outer_fold']=fold;score['training_key']=infit['training_key'];inner_scores.append(score)
            inner_meta.append({'inner_group':inner,'train_buildings':itr,'validation_buildings':held,'training_key':infit['training_key'],'n_train_events':len(itrain),'n_validation_events':len(ival)})
            print(f'reverse inner {fold}/{inner} train_b={len(itr)} events={len(itrain)}',flush=True)
        bs=pd.concat(inner_scores,ignore_index=True)
        comp=pd.DataFrame(complexrows)
        chosen,selection=one_se_choice(bs,comp)
        # A selected-global and selected-condition candidate are separate, frozen
        # outputs, as are geometry-only and swap-only ablations. Same inner data.
        selectors={'reverse_selected':candlist,
                   'reverse_selected_global':[c for c in candlist if not c['conditional']],
                   'reverse_selected_difficulty':[c for c in candlist if c['conditional']],
                   'reverse_selected_geometry':[c for c in candlist if c['source'] in ['geometry9','geometry12']],
                   'reverse_selected_swap':[c for c in candlist if c['source']=='swap_joint']}
        selectedmap={}
        for alias,cc in selectors.items():
            ids={c['method_id'] for c in cc};sel,ss=one_se_choice(bs[bs.method_id.isin(ids)],comp[comp.method_id.isin(ids)])
            selectedmap[alias]=sel
        ac=pd.DataFrame(allclasses);cd=pd.DataFrame(diags)
        aliases=[]
        for alias,mid in selectedmap.items():
            z=ac[ac.method_id.eq(mid)].copy();z['source_candidate_id']=z.method_id;z['method_id']=alias;aliases.append(z)
        ac=pd.concat([ac]+aliases,ignore_index=True)
        ac.to_csv(foldpath/'classes.csv.gz',index=False)
        cd.to_csv(foldpath/'class_diagnostics.csv.gz',index=False)
        selection.to_csv(foldpath/'candidate_selection.csv',index=False)
        bs.to_csv(foldpath/'inner_building_scores.csv.gz',index=False)
        pd.DataFrame(inner_classes).to_csv(foldpath/'inner_classes.csv.gz',index=False)
        pd.DataFrame(calibration_rows).to_csv(foldpath/'calibration.csv.gz',index=False)
        relations=[]
        for dom,rr in fit['relations'].items():
            z=rr.copy();z['fold_id']=fold;z['training_key']=fit['training_key'];relations.append(z)
        pd.concat(relations,ignore_index=True).to_csv(foldpath/'pair_relations.csv.gz',index=False)
        if preds:
            pp=pd.concat(preds,ignore_index=True);app=[]
            for alias,mid in selectedmap.items():
                z=pp[pp.method_id.eq(mid)].copy();z['source_candidate_id']=mid;z['method_id']=alias;app.append(z)
            pd.concat([pp]+app,ignore_index=True).to_csv(foldpath/'predictions.csv.gz',index=False)
        write_json(foldpath/'COMPLETE.json',{'fold_id':fold,'training_key':fit['training_key'],'train_buildings':sp['train_buildings'],
            'heldout_building':None if fold=='FULL' else fold,'n_train_events':len(train),'n_test_events':len(test),
            'inner':inner_meta,'selected_candidates':selectedmap,'candidate_count':len(candlist),'seconds':time.time()-t0,
            'training_panel':args.training_panel,'evaluation_only_panels':sorted(set(ev.panel_id)-{args.training_panel}),
            'event_sha256':sha256(args.events),'code_sha256':sha256(__file__),'selection_code_sha256':sha256(HERE/'selection_common.py')})
        # Cache uses exact training-building tuple but can be large; no cache from
        # another fold is scientifically required. Clear to bound memory.
        store.cache.clear()
        print(f'reverse complete {fold} selected={chosen} sec={time.time()-t0:.1f}',flush=True)
    batch_id=hashlib.sha256('|'.join(sorted(splits)).encode()).hexdigest()[:12]
    write_json(out/f'DISCOVERY_RUN_RECEIPT_{batch_id}.json',{'seconds':time.time()-start,'events_sha256':sha256(args.events),'n_events':len(ev),
             'source_sha256':{str(args.assignments):sha256(args.assignments),str(args.records):sha256(args.records)},
             'candidate_count':len(candlist),'folds_requested':list(splits),'new_fusion_calls':0,
             'historical_local_partitions':'reused archived measurement','pair_relationships_and_personnel_partitions':'new fits excluding outer and inner validation buildings'})


def consolidate(args):
    out=Path(args.output);folds=sorted((out/'folds').glob('*/COMPLETE.json'))
    for file,target in [('classes.csv.gz','all_candidate_classes.csv.gz'),('class_diagnostics.csv.gz','all_class_diagnostics.csv.gz'),
                        ('candidate_selection.csv','all_candidate_selection.csv.gz'),('inner_building_scores.csv.gz','all_inner_building_scores.csv.gz'),
                        ('calibration.csv.gz','all_calibration.csv.gz'),('pair_relations.csv.gz','all_pair_relations.csv.gz')]:
        frames=[]
        for p in folds:
            f=p.parent/file
            if f.exists():
                d=pd.read_csv(f);d['outer_fold']=p.parent.name;frames.append(d)
        if frames:pd.concat(frames,ignore_index=True).to_csv(out/target,index=False)
    # Prediction files remain per fold to avoid a giant duplicate; a manifest makes
    # joining exact event IDs explicit and portable.
    write_json(out/'PREDICTION_MANIFEST.json',{'fold_files':[{'fold_id':p.parent.name,'path':str((p.parent/'predictions.csv.gz').relative_to(out)),'sha256':sha256(p.parent/'predictions.csv.gz')} for p in folds if (p.parent/'predictions.csv.gz').exists()],
               'join_key':'event_id + method_id; events/common_events.csv.gz supplies outcomes, never used to define that heldout-building class'})
    choices=[]
    for p in folds:
        r=json.loads(p.read_text())
        for alias,c in r['selected_candidates'].items():choices.append({'fold_id':r['fold_id'],'method_id':alias,'selected_candidate':c})
    pd.DataFrame(choices).to_csv(out/'selected_candidates.csv',index=False)
    classes=pd.read_csv(out/'all_candidate_classes.csv.gz').fillna({'class_id':'unknown'})
    co=[]
    for (method,dom),g in classes[classes.fold_id.ne('FULL')].groupby(['method_id','domain']):
        pivot=g.pivot(index='worker_id',columns='fold_id',values='class_id').fillna('unknown')
        workers=list(pivot.index);values=pivot.to_numpy(dtype=object)
        valid=values!='unknown';counts=valid.astype(int)@valid.astype(int).T
        together=np.zeros_like(counts)
        for fi in range(values.shape[1]):
            together+=(values[:,fi,None]==values[None,:,fi]) & valid[:,fi,None] & valid[None,:,fi]
        for i,a in enumerate(workers):
            for j in range(i+1,len(workers)):
                b=workers[j];n=int(counts[i,j]);yes=int(together[i,j]);p=yes/n if n else np.nan
                co.append({'method_id':method,'domain':dom,'worker_a':a,'worker_b':b,'n_folds':values.shape[1],'n_supported_folds':n,
                           'n_coassigned_folds':yes,'coassignment_rate':p,
                           'coassignment_disagreement':2*p*(1-p) if n else np.nan,
                           'distinct_fold_disagreement':2*yes*(n-yes)/(n*(n-1)) if n>=2 else np.nan})
    pd.DataFrame(co).to_csv(out/'coassignment_stability.csv.gz',index=False)
    write_json(out/'CONSOLIDATION_RECEIPT.json',{'folds':len(folds),'full_fit_present':any(p.parent.name=='FULL' for p in folds),
                   'class_rows':len(classes),'coassignment_rows':len(co),'class_id_alignment':'pair coassignment, no numeric label identity assumption'})


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage',choices=['geometry','discover','consolidate'],required=True)
    p.add_argument('--assignments',default=str(HERE.parent/'recovered/work_v2_20261019/clusters/assignments.csv'))
    p.add_argument('--records',default=str(HERE.parent/'recovered/work_v2_20261019/clusters/records_geometry.csv'))
    p.add_argument('--splits',default=str(HERE/'FROZEN_BUILDING_SPLITS.json'))
    p.add_argument('--events');p.add_argument('--panel-id');p.add_argument('--training-panel',default='Pro_exact_fixed_background_v1');p.add_argument('--folds');p.add_argument('--force',action='store_true')
    p.add_argument('--output',default=str(HERE/'results'))
    args=p.parse_args()
    if args.stage=='geometry':geometry_only(args)
    elif args.stage=='discover':
        if not args.events:p.error('--events is required for discover')
        run_discovery(args)
    else:consolidate(args)
if __name__=='__main__':main()
