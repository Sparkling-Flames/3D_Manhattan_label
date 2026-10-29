#!/usr/bin/env python3
"""Finite, outcome-blind v2.1 structure refits and honest held-out raw-answer audit.

Inputs are the saved ordinary-legal-target histories. No team endpoint, quality
outcome, time value, or fusion response is used to fit any new label.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse, gzip, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score

ST=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9']
RAW=ST[:3]
def cc(stratum, fields=ST): return ['m_'+stratum+'_'+x for x in fields]
FAMILIES={
 'REPRO_TARGET_DSTRUCT':dict(domains=[cc('all'),cc('hard')+cc('hard_minus_easy')],gates=['manual_all','manual_difficulty'],pca=2,weights=[1,1],sort=cc('hard')[:2]+cc('all')[:1],question='Exact original v2.1 target-aware reproduction'),
 'V21_DSTRUCT_FULL':dict(domains=[cc('all'),cc('hard')+cc('hard_minus_easy')],gates=['manual_all','manual_difficulty'],pca=None,weights=[1,1],sort=cc('hard')[:2]+cc('all')[:1],question='Does the two-PC truncation suppress meaningful structural axes?'),
 'V21_DSTRUCT_RAW3':dict(domains=[cc('all',RAW),cc('hard',RAW)+cc('hard_minus_easy',RAW)],gates=['manual_all','manual_difficulty'],pca=2,weights=[1,1],sort=cc('hard')[:2]+cc('all')[:1],question='Separate actual marking form from reference-corner localization diagnostics'),
 'V21_DSTRUCT_LEVEL':dict(domains=[cc('all')],gates=['manual_all'],pca=2,weights=[1],sort=cc('all')[:2],question='Is condition-specific history adding useful information over overall structure?'),
 'V21_DSTRUCT_COND':dict(domains=[cc('all'),cc('challenge')+cc('challenge_minus_plain')],gates=['manual_all','manual_condition'],pca=2,weights=[1,1],sort=cc('challenge')[:2]+cc('all')[:1],question='Replace legacy visual difficulty strata with actual computable target conditions'),
 'V21_DSTRUCT_HALF':dict(domains=[cc('all'),cc('hard')+cc('hard_minus_easy')],gates=['manual_all','manual_difficulty'],pca=2,weights=[1,.5],sort=cc('hard')[:2]+cc('all')[:1],question='Sensitivity to emphasis on the repeated hard and hard-minus-easy feature domain'),
}

def save_csv(frame,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=frame.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
    tmp=path.with_name(path.name+'.partial');tmp.write_bytes(b);tmp.replace(path)

def save_json(obj,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def embed(frame,spec):
    parts=[];trans=[]
    weights=np.asarray(spec['weights'],float);weights=weights/weights.sum()
    for cols,pw in zip(spec['domains'],weights):
        a=frame[cols].to_numpy(float)
        med=np.median(a,axis=0);scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
        std=np.std(a,axis=0);scale=np.where(scale>1e-9,scale,np.where(std>1e-9,std,1))
        z=np.clip((a-med)/scale,-3,3)
        record=dict(columns=cols,median=med.tolist(),scale=scale.tolist(),clip=3,weight=float(pw))
        if spec['pca'] is None:
            pc=z-z.mean(axis=0)
            record.update(encoding='all standardized dimensions; centered',pca_explained_variance_ratio=None)
        else:
            p=PCA(n_components=min(spec['pca'],len(cols),len(frame)-1),svd_solver='full')
            pc=p.fit_transform(z)
            record.update(encoding='PCA',components=p.components_.tolist(),pca_mean=p.mean_.tolist(),pca_explained_variance_ratio=p.explained_variance_ratio_.tolist())
        rms=max(float(np.sqrt(np.mean(np.sum(pc**2,axis=1)))),1e-9)
        parts.append(pc/rms*np.sqrt(pw));record['rms']=rms;trans.append(record)
    return np.column_stack(parts),trans

def fit(history,out):
    labels=[];centers=[];register=[];links=[];transforms={}
    explanation=[x for x in history if x.startswith('m_') and any(x.endswith('_'+v) for v in ST+['B8L2','B8L2_p20','log_time','log_area_ratio','log_height','matched_bottom_bias_deg','matched_top_bias_deg'])]
    for fold,f in history.groupby('heldout_building',sort=False):
        f=f.sort_values('worker_id').reset_index(drop=True).copy()
        f['manual_condition']=f.m_plain_images.ge(5)&f.m_plain_buildings.ge(2)&f.m_challenge_images.ge(4)&f.m_challenge_buildings.ge(2)
        for m in ST:f['m_challenge_minus_plain_'+m]=f['m_challenge_'+m]-f['m_plain_'+m]
        for family,spec in FAMILIES.items():
            need=list(dict.fromkeys(x for d in spec['domains'] for x in d))
            known=f[spec['gates']].all(axis=1)&f[need].notna().all(axis=1)
            g=f[known].copy();x,tr=embed(g,spec)
            tree=linkage(x,method='ward',optimal_ordering=True)
            transforms[fold+'/'+family]=tr
            parentmaps={}
            for k in (2,3,4):
                c=cut_tree(tree,n_clusters=k).ravel();g['raw_cluster']=c
                order=g.groupby('raw_cluster')[spec['sort']].mean().sort_values(spec['sort']).index.tolist()
                names={v:'C'+str(i+1) for i,v in enumerate(order)}
                assigned=pd.Series(c,index=g.index).map(names)
                method=family+'_K'+str(k)
                lab=f[['worker_id','origin','heldout_building']].copy()
                lab['method']=method;lab['family']=family;lab['k']=k;lab['class_id']=None
                lab.loc[g.index,'class_id']=assigned;lab['known']=known
                lab['missing_reason']=''
                lab.loc[~known,'missing_reason']=f.loc[~known].apply(lambda r:';'.join([gate for gate in spec['gates'] if not r[gate]]+(['missing_required_features'] if r[need].isna().any() else [])),axis=1)
                lab['input_conditions']='manual';lab['condition']='manual';lab['underlying_data_version']='v2.1'
                lab['label_stage']='all_data_descriptive' if fold=='ALL' else 'leave_target_building_out'
                lab['history_scope']='ordinary_legal_targets_only';lab['source_stage']='outcome_blind_v21_structure_audit'
                lab['uses_Q_for_fit']=False;lab['uses_T_for_fit']=False
                labels.append(lab);parentmaps[k]=dict(zip(lab.worker_id,lab.class_id))
                g['class_id']=assigned
                for cl,z in g.groupby('class_id'):
                    r=dict(method=method,family=family,k=k,heldout_building=fold,class_id=cl,workers=len(z),members='|'.join(z.worker_id))
                    r.update({v:float(z[v].mean()) for v in explanation if z[v].notna().any()})
                    centers.append(r)
                sizes=g.groupby('class_id').size()
                register.append(dict(method=method,family=family,k=k,heldout_building=fold,known_workers=int(known.sum()),unknown_workers=int((~known).sum()),class_sizes='|'.join(map(str,sizes)),min_class=int(sizes.min()),silhouette=float(silhouette_score(x,c)),selection_status='registered_without_team_outcomes',question=spec['question']))
            for child_k,parent_k in ((3,2),(4,3)):
                for child in sorted(set(v for v in parentmaps[child_k].values() if v is not None)):
                    workers=[w for w,c in parentmaps[child_k].items() if c==child]
                    parents={parentmaps[parent_k][w] for w in workers};assert len(parents)==1
                    links.append(dict(family=family,heldout_building=fold,child_k=child_k,child_class=child,parent_k=parent_k,parent_class=next(iter(parents)),workers=len(workers)))
        fold_labs=pd.concat([z for z in labels if z.heldout_building.iloc[0]==fold],ignore_index=True)
        save_csv(fold_labs,out/'folds'/('LABELS_'+fold+'.csv.gz'))
        print('saved fold',fold,flush=True)
    lab=pd.concat(labels,ignore_index=True)
    save_csv(lab,out/'NEW_LABELS_ALL_LOBO.csv.gz')
    save_csv(lab[lab.heldout_building.eq('ALL')],out/'NEW_LABELS_ALL.csv')
    save_csv(pd.DataFrame(centers),out/'CLASS_CENTERS_ALL_LOBO.csv.gz')
    save_csv(pd.DataFrame(centers).query('heldout_building == "ALL"'),out/'CLASS_CENTERS_ALL.csv')
    save_csv(pd.DataFrame(register),out/'CANDIDATE_REGISTRY.csv')
    save_csv(pd.DataFrame(links),out/'TRUE_K2_K3_K4_PARENT_LINKS.csv')
    save_json(transforms,out/'TRANSFORMS_ALL_LOBO.json')
    return lab

def check_reproduction(labels,old,out):
    z=labels[labels.family.eq('REPRO_TARGET_DSTRUCT')].copy()
    z['method']=z.method.str.replace('REPRO_TARGET','TARGET',regex=False)
    a=z.merge(old[['method','heldout_building','worker_id','class_id','known']],on=['method','heldout_building','worker_id'],suffixes=('_new','_old'),validate='one_to_one')
    a['same_known']=a.known_new==a.known_old
    a['same_label']=a.class_id_new.fillna('unknown')==a.class_id_old.fillna('unknown')
    save_csv(a,out/'EXACT_BASELINE_REPRODUCTION.csv.gz')
    assert len(a)==3*23*62 and a.same_known.all() and a.same_label.all(),a.loc[~a.same_label].to_string()
    return dict(rows=len(a),all_eligibility_identical=bool(a.same_known.all()),all_labels_identical=bool(a.same_label.all()))

def stability(labels,old,out):
    bases=['DSTRUCT_K2','DSTRUCT_K3','DSTRUCT_K4','TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','OPPSTRUCT_K2','OPPSTRUCT_K3','OPPSTRUCT_K4','OPPJOINT_K3','OPPJOINT_K4']
    combined=pd.concat([labels,old[old.method.isin(bases)]],ignore_index=True)
    rows=[]
    for method,g in combined.groupby('method'):
        all_labels=g[g.heldout_building.eq('ALL')&g.known].set_index('worker_id').class_id
        for fold,f in g[g.heldout_building.ne('ALL')&g.known].groupby('heldout_building'):
            f=f.set_index('worker_id').class_id;workers=f.index.intersection(all_labels.index)
            rows.append(dict(method=method,heldout_building=fold,workers=len(workers),ARI=adjusted_rand_score(all_labels.loc[workers],f.loc[workers])))
    save_csv(pd.DataFrame(rows),out/'LOBO_VS_ALL_STABILITY.csv')
    save_csv(pd.DataFrame(rows).groupby('method').ARI.agg(['mean','median','min','max']).reset_index(),out/'LOBO_STABILITY_SUMMARY.csv')
    changes=[]
    for (fold,k),g in labels.groupby(['heldout_building','k']):
        ref=old[old.method.eq('TARGET_DSTRUCT_K'+str(k))&old.heldout_building.eq(fold)&old.known].set_index('worker_id').class_id
        for method,z in g[g.known].groupby('method'):
            z=z.set_index('worker_id').class_id;ww=z.index.intersection(ref.index)
            changes.append(dict(method=method,heldout_building=fold,k=k,common_workers=len(ww),ARI_vs_target=adjusted_rand_score(ref.loc[ww],z.loc[ww])))
    save_csv(pd.DataFrame(changes),out/'PARTITION_CHANGES_VS_TARGET.csv')
    current=old[old.method.str.match(r'^TARGET_DSTRUCT_K[234]$')][['worker_id','heldout_building','method','class_id','known']].copy()
    current['k']=current.method.str[-1].astype(int);current=current.drop(columns='method')
    transition=labels.merge(current,on=['worker_id','heldout_building','k'],suffixes=('_new','_target'),validate='many_to_one')
    save_csv(transition,out/'ALL_WORKER_TRANSITIONS_VS_TARGET.csv.gz')
    all_members=combined[combined.heldout_building.eq('ALL')][['method','worker_id','class_id']].rename(columns={'class_id':'ALL_class'})
    fractions=combined[combined.heldout_building.ne('ALL')&combined.known].groupby(['method','worker_id','class_id']).size().rename('LOBO_folds').reset_index()
    fractions['known_folds']=fractions.groupby(['method','worker_id']).LOBO_folds.transform('sum')
    fractions['fraction']=fractions.LOBO_folds/fractions.known_folds
    fractions=fractions.merge(all_members,on=['method','worker_id'],validate='many_to_one')
    save_csv(fractions,out/'WORKER_ALL_LOBO_SEMANTIC_CLASS_FRACTIONS.csv')

def support_audit(history,raw,out):
    h=history.copy();rows=[]
    for fold,g in h.groupby('heldout_building',sort=False):
        for name,mask in [('published_all12b3',g.m_all_images.ge(12)&g.m_all_buildings.ge(3)),('all8b3',g.m_all_images.ge(8)&g.m_all_buildings.ge(3)),('all20b4',g.m_all_images.ge(20)&g.m_all_buildings.ge(4)),('all30b6',g.m_all_images.ge(30)&g.m_all_buildings.ge(6)),('difficulty_original',g.manual_all&g.manual_difficulty),('difficulty_easy8hard8b3',g.manual_all&g.m_easy_images.ge(8)&g.m_easy_buildings.ge(3)&g.m_hard_images.ge(8)&g.m_hard_buildings.ge(3)),('computable_plain5challenge4b2',g.manual_all&g.m_plain_images.ge(5)&g.m_plain_buildings.ge(2)&g.m_challenge_images.ge(4)&g.m_challenge_buildings.ge(2))]:
            for (_,r),ok in zip(g.iterrows(),mask):rows.append(dict(heldout_building=fold,worker_id=r.worker_id,gate_variant=name,eligible=bool(ok),all_images=r.m_all_images,all_buildings=r.m_all_buildings,easy_images=r.m_easy_images,hard_images=r.m_hard_images,plain_images=r.m_plain_images,challenge_images=r.m_challenge_images))
    s=pd.DataFrame(rows);save_csv(s,out/'SUPPORT_GATE_SENSITIVITY_ALL_WORKERS.csv.gz')
    save_csv(s.groupby(['heldout_building','gate_variant']).eligible.sum().rename('eligible_workers').reset_index(),out/'SUPPORT_GATE_COUNTS.csv')
    ordinary=raw[raw.layer.eq('ordinary_manual')].copy()
    valid=[]
    for metric in ST:
        v=ordinary.groupby('worker_id').agg(records=('object_id','size'),metric_valid=(metric,'count'),images=('image_id','nunique'))
        v['metric']=metric;valid.append(v.reset_index())
    save_csv(pd.concat(valid),out/'PER_METRIC_RAW_SUPPORT_ALL.csv')

def raw_pairs_audit(labels,old,raw,out):
    # Fixed common worker set across all newly registered families plus selected
    # old comparators, separately within each target pool. No label imputation.
    methods=sorted(labels.method.unique())+['TARGET_DSTRUCT_K3','DSTRUCT_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','Q_MEDIAN2']
    labs=pd.concat([labels,old[old.method.isin(methods)]],ignore_index=True)
    lookup={(m,b):dict(zip(z.loc[z.known,'worker_id'],z.loc[z.known,'class_id'])) for (m,b),z in labs.groupby(['method','heldout_building'])}
    d=raw[raw.layer.eq('ordinary_manual')].copy();records=[]
    metrics=ST+['matched_bottom_bias_deg','matched_top_bias_deg','log_area_ratio','log_height']
    for pool,g in d.groupby('pool_id'):
        building=g.building.iloc[0];image=g.image_id.iloc[0]
        common=set(g.worker_id)
        for method in methods:common&=set(lookup[(method,building)])
        for support in ('native','common'):
            for method in methods:
                mp=lookup[(method,building)];z=g[g.worker_id.isin(mp)]
                if support=='common':z=z[z.worker_id.isin(common)]
                # Raw snapshot has one answer per worker-target; assert instead
                # of treating duplicate answers as independent workers.
                assert not z.worker_id.duplicated().any()
                if len(z)<3:continue
                cls=z.worker_id.map(mp).to_numpy();ii,jj=np.triu_indices(len(z),1)
                same=cls[ii]==cls[jj]
                for metric in metrics:
                    values=z[metric].to_numpy(float);diff=np.abs(values[ii]-values[jj]);valid=np.isfinite(diff)
                    wi=diff[valid&same];cr=diff[valid&~same]
                    within_groups=[];cross_groups=[]
                    classes=sorted(set(cls))
                    for ix,a in enumerate(classes):
                        v=diff[valid&(cls[ii]==a)&(cls[jj]==a)]
                        if len(v):within_groups.append(float(v.mean()))
                        for b in classes[ix+1:]:
                            v=diff[valid&(((cls[ii]==a)&(cls[jj]==b))|((cls[ii]==b)&(cls[jj]==a)))]
                            if len(v):cross_groups.append(float(v.mean()))
                    records.append(dict(method=method,support=support,pool_id=pool,image_id=image,building=building,metric=metric,workers=len(z),same_pairs=len(wi),cross_pairs=len(cr),within=float(np.mean(within_groups)) if within_groups else np.nan,cross=float(np.mean(cross_groups)) if cross_groups else np.nan,within_pair_weighted=float(wi.mean()) if len(wi) else np.nan,cross_pair_weighted=float(cr.mean()) if len(cr) else np.nan))
    p=pd.DataFrame(records);p['gap']=p.cross-p.within
    save_csv(p,out/'HELDOUT_RAW_PAIR_DISTANCE_BY_POOL.csv.gz')
    im=p.groupby(['method','support','metric','building','image_id'])[['within','cross','gap']].mean().reset_index()
    save_csv(im,out/'HELDOUT_RAW_PAIR_DISTANCE_BY_IMAGE.csv.gz')
    bs=im.groupby(['method','support','metric','building'])[['within','cross','gap']].mean().reset_index()
    save_csv(bs,out/'HELDOUT_RAW_PAIR_DISTANCE_BY_BUILDING.csv.gz')
    summary=[]
    for key,z in im.groupby(['method','support','metric']):
        zz=z.dropna(subset=['gap'])
        row=dict(zip(['method','support','metric'],key));row.update(images=len(zz),buildings=zz.building.nunique(),positive_gap_images=int(zz.gap.gt(1e-12).sum()),negative_gap_images=int(zz.gap.lt(-1e-12).sum()),nearzero_gap_images=int(zz.gap.abs().le(1e-12).sum()),within=zz.within.mean(),cross=zz.cross.mean(),gap=zz.gap.mean(),median_gap=zz.gap.median(),gap_p10=zz.gap.quantile(.1),gap_p90=zz.gap.quantile(.9))
        summary.append(row)
    save_csv(pd.DataFrame(summary),out/'HELDOUT_RAW_PAIR_SUMMARY.csv')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    history=pd.read_csv(args.source/'classification/HISTORY_FEATURES_ALL_LOBO.csv.gz',low_memory=False)
    old=pd.read_csv(args.source/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    raw=pd.read_csv(args.source/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    config=dict(data_release='v2.1',families=FAMILIES,k=[2,3,4],formation_uses_team_outcomes=False,features_source='current saved target-aware ordinary-legal histories',interpretation='unmatched_ref_9 is reference-and-position dependent; RAW3 excludes it',prior_sensitivity='v2 original/overall/geometric comparison existed; these are current v2.1 refits, not a new conceptual invention',selection='No candidate chosen by Q; all registered variants retained')
    save_json(config,out/'CONFIG_BEFORE_NEW_TEAM_RESULTS.json')
    labels=fit(history,out)
    check=check_reproduction(labels,old,out)
    stability(labels,old,out);support_audit(history,raw,out);raw_pairs_audit(labels,old,raw,out)
    check.update(new_variants=5,new_method_k_configurations=15,baseline_reproduction_configurations=3,folds=23,raw_records=len(raw),input_files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (args.source/'classification').glob('*') if p.name in ['HISTORY_FEATURES_ALL_LOBO.csv.gz','MAIN45_LABELS_ALL_LOBO.csv.gz','RAW_TARGET_RESPONSE_RECORDS.csv.gz']})
    save_json(check,out/'FIT_AND_AUDIT_RECEIPT.json');print(json.dumps(check,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
