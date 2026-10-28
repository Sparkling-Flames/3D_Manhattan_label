"""Frozen K3 definition sensitivity and cached-team relabeling; no fusion or scoring."""
from pathlib import Path
import importlib.util
import json
from collections import Counter
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/difficulty/difficulty_computable_comparison_20261028/structure_sensitivity_v1'
AUD=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked'
COMP=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
ST=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9']
METHODS=['published','original_common','overall_common','geometry_common']


def save(name,d):d.to_csv(OUT/name,index=False,encoding='utf-8')


def history_metrics(d,mask,prefix,workers):
    z=d[mask];cols=[x+'_peer' for x in ST]
    values=z.groupby(['worker_id','building'])[cols].mean().groupby('worker_id').mean()
    values.columns=[prefix+'_'+x for x in ST]
    counts=z.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building','nunique'))
    counts.columns=[prefix+'_'+x for x in counts]
    out=pd.DataFrame(index=workers).join(values).join(counts)
    out[[prefix+'_images',prefix+'_buildings']]=out[[prefix+'_images',prefix+'_buildings']].fillna(0)
    return out


def align_labels(labels,reference):
    cats=sorted(set(labels));refs=sorted(set(reference))
    table=np.array([[sum((labels==c)&(reference==r)) for r in refs] for c in cats])
    i,j=linear_sum_assignment(-table)
    mapping={cats[a]:refs[b] for a,b in zip(i,j)}
    return np.array([mapping[x] for x in labels]),mapping


def fit_classes(frame,domains,sort_cols,core):
    x,transform=core.domain_matrix(frame,domains)
    lab=cut_tree(linkage(x,method='ward',optimal_ordering=True),n_clusters=3).ravel()
    order=sorted(set(lab),key=lambda j:tuple(frame.loc[lab==j,sort_cols].mean()))
    return np.array(['C'+str(order.index(j)+1) for j in lab]),transform


def fit_labels():
    spec=importlib.util.spec_from_file_location('frozen_dstruct',AUD/'03/classifications/code/build_condition_response_classes.py')
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    raw=pd.read_csv(AUD/'01/features/RAW_CONDITION_RESPONSE_RECORDS.csv.gz',low_memory=False)
    raw=raw[raw.history_eligible & raw.condition.eq('manual') & raw.difficulty_coarse.isin(['简单','中等','困难'])].copy()
    assert len(raw)==5785 and raw.image_id.nunique()==179 and raw.object_id.is_unique
    assert raw[['ref_turn5','ref_H','ref_short_edges']].notna().all().all()
    raw['challenge']=raw.ref_turn5.gt(6)|raw.ref_H.gt(0)|raw.ref_short_edges.gt(0)
    save('TRAINING_RECORD_CONDITIONS.csv.gz',raw[['object_id','worker_id','image_id','building','difficulty_coarse','ref_turn5','ref_H','ref_short_edges','challenge']])
    saved=pd.read_csv(AUD/'01/features/HISTORY_FEATURES_ALL_LOBO.csv.gz')
    published=pd.read_csv(AUD/'01/classifications/NEW_METHOD_LABELS_ALL_LOBO.csv.gz')
    published=published[published.method.eq('DSTRUCT_K3')]
    core.DOMAINS['GEOM_RESPONSE']=['c_'+x for x in ST]+['c_minus_p_'+x for x in ST]
    labels=[];support=[];changes=[];centers=[];features=[];transforms={};maxerr=0
    for fold,old in saved.groupby('heldout_building',sort=False):
        old=old.sort_values('worker_id').reset_index(drop=True);workers=old.worker_id.tolist()
        d=raw if fold=='ALL' else raw[raw.building.ne(fold)]
        f=old.set_index('worker_id').copy()
        for mask,prefix in [(np.ones(len(d),bool),'a'),(d.challenge,'c'),(~d.challenge,'p')]:
            f=f.join(history_metrics(d,mask,prefix,workers))
        for metric in ST:
            f['c_minus_p_'+metric]=f['c_'+metric]-f['p_'+metric]
            np.testing.assert_allclose(f['a_'+metric],f['m_all_'+metric],equal_nan=True,atol=1e-10)
            er=(f['a_'+metric]-f['m_all_'+metric]).abs().max();maxerr=max(maxerr,float(er))
        f=f.reset_index();f['heldout_building']=fold
        needs=core.DOMAINS['M_STRUCTURE_LEVEL']+core.DOMAINS['M_STRUCTURE_HARD']
        orig=f.manual_geometry & f[needs].notna().all(axis=1)
        overall=f.a_images.ge(12)&f.a_buildings.ge(3)&f[['a_'+x for x in ST]].notna().all(axis=1)
        geo=overall&f.p_images.ge(5)&f.p_buildings.ge(2)&f.c_images.ge(4)&f.c_buildings.ge(2)&f[core.DOMAINS['GEOM_RESPONSE']].notna().all(axis=1)
        common=orig&overall&geo
        for i,r in f.iterrows():support.append(dict(heldout_building=fold,worker_id=r.worker_id,original=bool(orig.iloc[i]),overall_native=bool(overall.iloc[i]),geometry_native=bool(geo.iloc[i]),common=bool(common.iloc[i]),plain_images=r.p_images,plain_buildings=r.p_buildings,challenge_images=r.c_images,challenge_buildings=r.c_buildings,all_images=r.a_images,all_buildings=r.a_buildings))
        pub=published[published.heldout_building.eq(fold)].set_index('worker_id').class_id
        # Original all-eligible fit must reproduce the published partition before contrasts.
        original=f[orig].copy().reset_index(drop=True)
        rec,_=fit_classes(original,['M_STRUCTURE_LEVEL','M_STRUCTURE_HARD'],core.FAMILIES['DSTRUCT']['sort'],core)
        assert np.array_equal(rec,original.worker_id.map(pub).to_numpy()),fold
        for method,mask,domains,sortcols in [
            ('original_common',common,['M_STRUCTURE_LEVEL','M_STRUCTURE_HARD'],core.FAMILIES['DSTRUCT']['sort']),
            ('overall_common',common,['M_STRUCTURE_LEVEL'],['m_all_turn_n','m_all_short_turn_edges']),
            ('geometry_common',common,['M_STRUCTURE_LEVEL','GEOM_RESPONSE'],['c_turn_n','c_short_turn_edges','m_all_turn_n'])]:
            fit=f[mask].copy().reset_index(drop=True);assert len(fit)>=3
            lab,tr=fit_classes(fit,domains,sortcols,core)
            ref=fit.worker_id.map(pub).to_numpy();aligned,mapping=align_labels(lab,ref)
            lookup=dict(zip(fit.worker_id,aligned));rawlookup=dict(zip(fit.worker_id,lab))
            transforms[fold+'/'+method]=dict(transform=tr,alignment=mapping)
            for wid in workers:labels.append(dict(heldout_building=fold,method=method,worker_id=wid,class_id=lookup.get(wid,'unknown'),raw_class_id=rawlookup.get(wid,'unknown'),published_class=pub.get(wid,'unknown')))
            changes.append(dict(heldout_building=fold,method=method,people=len(fit),changed=int((aligned!=ref).sum()),ARI=adjusted_rand_score(ref,aligned),original_native=int(orig.sum()),overall_native=int(overall.sum()),geometry_native=int(geo.sum())))
            fit['class_id']=aligned
            for cls,g in fit.groupby('class_id'):
                row=dict(heldout_building=fold,method=method,class_id=cls,people=len(g),members='|'.join(g.worker_id))
                row.update(g[['m_all_'+x for x in ST]+['m_hard_'+x for x in ST]+['c_'+x for x in ST]+['c_minus_p_'+x for x in ST]].mean().to_dict());centers.append(row)
        for wid in workers:labels.append(dict(heldout_building=fold,method='published',worker_id=wid,class_id=pub.get(wid,'unknown'),raw_class_id=pub.get(wid,'unknown'),published_class=pub.get(wid,'unknown')))
        features.append(f)
    save('LABELS_ALL_LOBO.csv',pd.DataFrame(labels));save('ELIGIBILITY.csv',pd.DataFrame(support));save('LABEL_CHANGES.csv',pd.DataFrame(changes));save('CLASS_CENTERS.csv',pd.DataFrame(centers));save('HISTORY_FEATURES.csv.gz',pd.concat(features,ignore_index=True))
    save('LABEL_CROSSTAB.csv',pd.DataFrame(labels).groupby(['heldout_building','method','published_class','class_id']).size().rename('people').reset_index())
    (OUT/'TRANSFORMS.json').write_text(json.dumps(transforms,ensure_ascii=False,indent=2),encoding='utf-8')
    return pd.DataFrame(labels),dict(training_records=len(raw),training_images=raw.image_id.nunique(),original_partition_reproduced_folds=saved.heldout_building.nunique(),history_max_error=maxerr)


def members(value):return set(str(value).split('|')) if pd.notna(value) and value!='' else set()


def strict_relation(row,lookup):
    d,x,y,z=(members(row[k]) for k in ['D','X','Y','Z'])
    assert len(x)==len(y)==len(z)==row['m']
    assert all(not a&b for i,a in enumerate([d,x,y,z]) for b in [d,x,y,z][i+1:])
    assert members(row['A_members'])==d|x and members(row['B_members'])==d|y and members(row['C_members'])==d|z
    groups=[{lookup.get(w,'unknown') for w in block} for block in [x,y,z]]
    if any('unknown' in g for g in groups):return False,'unknown_block_member'
    if any(len(g)!=1 for g in groups):return False,'mixed_block'
    if groups[0]!=groups[1]:return False,'XY_different_class'
    if groups[0]==groups[2]:return False,'Z_same_class'
    return True,'strict_ABC'


def label_maps(labels):
    return {(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labels.groupby(['method','heldout_building'])}


def balanced_images(z,keys):
    metrics=['within','cross','gap','CB']
    levels=z.groupby(keys+['building','image','block_id','background_target_n'])[metrics].mean()
    blocks=levels.groupby(level=keys+['building','image','block_id']).mean()
    im=blocks.groupby(level=keys+['building','image']).mean().reset_index()
    counts=z.groupby(keys+['building','image']).size().rename('events').reset_index()
    return im.merge(counts,on=keys+['building','image'],validate='one_to_one')


def abc(labels):
    maps=label_maps(labels);events=[]
    base=['event_id','pool_id','building','image','phase','source_class','target_class','block_id','background_target_n','n','m','method','design','D','X','Y','Z','A_members','B_members','C_members','A_team_key','B_team_key','C_team_key','A_B8L2','B_B8L2','C_B8L2','ABC_scored','A_failed','B_failed','C_failed']
    for stage,path in [('screen','02A/results/screen'),('confirm','04A1/results/confirm'),('size_paths','05/results/size_paths')]:
        e=pd.read_csv(AUD/path/'EVENT_METRICS.csv.gz',usecols=base,low_memory=False)
        e=e[e.method.eq('DSTRUCT_K3')&e.design.eq('strict_disjoint_ABC')].copy();e['stage']=stage;events.append(e)
    e=pd.concat(events,ignore_index=True);assert not e.duplicated(['stage','event_id']).any()
    centers=pd.read_csv(OUT/'CLASS_CENTERS.csv');centers=centers[centers.method.eq('original_common')]
    role={}
    for fold,g in centers.groupby('heldout_building'):
        role[fold]=(set(g.loc[g.people.eq(g.people.max()),'class_id']),set(g.loc[g.m_hard_turn_n.eq(g.m_hard_turn_n.max()),'class_id']))
    e['frozen_primary_role']=[r.source_class in role[r.building][0] and r.target_class in role[r.building][1] and r.source_class not in role[r.building][1] for r in e.itertuples()]
    save('ABC_CACHED_SOURCE.csv.gz',e)
    rows=[]
    for r in e.to_dict('records'):
        for method in METHODS:
            lookup=maps[(method,r['building'])];legal,reason=strict_relation(r,lookup)
            scored=bool(r['ABC_scored']) and all(np.isfinite(r[k+'_B8L2']) for k in ['A','B','C'])
            a,b,c=(r[k+'_B8L2'] for k in ['A','B','C'])
            rows.append(dict(stage=r['stage'],event_id=r['event_id'],method=method,pool_id=r['pool_id'],image=r['image'],building=r['building'],phase=r['phase'],source_class=r['source_class'],target_class=r['target_class'],n=r['n'],m=r['m'],legal=legal,reason=reason,unknown_D=sum(lookup.get(w,'unknown')=='unknown' for w in members(r['D'])),scored=scored,within=abs(b-a) if scored else np.nan,cross=(abs(c-a)+abs(c-b))/2 if scored else np.nan,CB=c-b if scored else np.nan,A_failed=r['A_failed'],B_failed=r['B_failed'],C_failed=r['C_failed']))
    a=pd.DataFrame(rows);a['gap']=a.cross-a.within
    a=a.merge(e[['stage','event_id','block_id','background_target_n','frozen_primary_role']],on=['stage','event_id'],validate='many_to_one')
    common=a.groupby(['stage','event_id']).legal.all().rename('common_legal').reset_index();a=a.merge(common,on=['stage','event_id'],validate='many_to_one')
    assert a[a.method.eq('published')].legal.all()
    save('ABC_RELABELED.csv.gz',a)
    keys=['stage','phase','source_class','target_class','n','m','method'];save('ABC_SUPPORT.csv',a.groupby(keys+['reason']).agg(events=('event_id','size'),images=('image','nunique'),buildings=('building','nunique'),scored_events=('scored','sum')).reset_index())
    ims=[]
    for support,mask in [('own_legal',a.legal),('common_legal',a.common_legal)]:
        z=a[mask & a.scored];im=balanced_images(z,keys);im['support']=support;ims.append(im)
    im=pd.concat(ims,ignore_index=True);save('ABC_IMAGE_RESULTS.csv',im)
    keys=['support',*keys];b=im.groupby(keys+['building'])[['within','cross','gap','CB']].mean().reset_index();save('ABC_BUILDING_RESULTS.csv',b)
    sm=im.groupby(keys).agg(images=('image','nunique'),buildings=('building','nunique'),positive_gap_images=('gap',lambda s:int((s>0).sum())),positive_CB_images=('CB',lambda s:int((s>0).sum())),events=('events','sum'))
    save('ABC_SUMMARY.csv',sm.join(b.groupby(keys)[['within','cross','gap','CB']].mean().add_suffix('_building_equal')).join(im.groupby(keys)[['within','cross','gap','CB']].mean().add_suffix('_image_equal')).reset_index())
    # Preserve the old largest-to-highest-turn direction; do not select a new winner.
    focus=a[a.frozen_primary_role & a.n.eq(18) & a.m.eq(7) & a.stage.eq('confirm')]
    save('ABC_FOCUS_EVENTS.csv.gz',focus)
    key=['phase','method'];parts=[]
    for support,mask in [('own_legal',focus.legal),('common_legal',focus.common_legal)]:
        im=balanced_images(focus[mask & focus.scored],key);im['support']=support;parts.append(im)
    im=pd.concat(parts,ignore_index=True);save('ABC_FOCUS_IMAGE.csv',im)
    key=['support','phase','method'];b=im.groupby(key+['building'])[['within','cross','gap','CB']].mean().reset_index();save('ABC_FOCUS_BUILDING.csv',b)
    count=im.groupby(key).agg(images=('image','nunique'),buildings=('building','nunique'),events=('events','sum'),positive_gap_images=('gap',lambda s:int((s>0).sum())))
    save('ABC_FOCUS_SUMMARY.csv',count.join(b.groupby(key)[['within','cross','gap','CB']].mean().add_suffix('_building_equal')).join(im.groupby(key)[['within','cross','gap','CB']].mean().add_suffix('_image_equal')).reset_index())
    return dict(cached_strict_events=len(e),new_teams_selected=0,new_fusion=0,common_legal_events=int(common.common_legal.sum()))


def decompose(values,groups):
    f=pd.DataFrame({'y':values,'g':groups}).dropna(subset=['y'])
    if f.empty:return dict(valid=0,total=np.nan,between=np.nan,within=np.nan)
    avg=f.groupby('g').y.transform('mean');mu=f.y.mean()
    return dict(valid=len(f),total=float(((f.y-mu)**2).mean()),between=float(((avg-mu)**2).mean()),within=float(((f.y-avg)**2).mean()))


def composition(labels):
    maps=label_maps(labels);p=pd.read_csv(COMP/'PANELS_USED.csv');p=p[p.condition.eq('manual')]
    links=pd.read_csv(COMP/'PANEL_TEAMS.csv.gz');links=links[links.panel_id.isin(p.panel_id)]
    tm=pd.read_csv(COMP/'TEAM_MEMBERS.csv.gz');tm=tm[tm.condition.eq('manual')].set_index('team_key')
    ep=pd.read_csv(COMP/'ENDPOINT_OUTCOMES_manual.csv.gz').set_index('team_key')
    assert tm.index.is_unique and ep.index.is_unique and len(p)==231 and len(links)==213444
    coverage=[];results=[];vectors=[]
    for row in p.to_dict('records'):
        keys=links.loc[links.panel_id.eq(row['panel_id']),'team_key'].tolist();assert len(keys)==924
        assert set(keys)<=set(ep.index) and set(keys)<=set(tm.index)
        workers=members(row['background_workers'])|members(row['variable_workers'])
        unknown={m:sorted(w for w in workers if maps[(m,row['building'])].get(w,'unknown')=='unknown') for m in METHODS}
        common=not any(unknown.values())
        for m in METHODS:coverage.append(dict(panel_id=row['panel_id'],image=row['image'],building=row['building'],method=m,common_panel=common,unknown_workers='|'.join(unknown[m]),teams=924))
        if not common:continue
        for method in METHODS:
            lookup=maps[(method,row['building'])];group=[]
            for key in keys:
                counts=Counter(lookup[w] for w in members(tm.loc[key,'member_workers']))
                vec='|'.join(str(counts.get(c,0)) for c in ['C1','C2','C3']);group.append(vec)
                vectors.append(dict(panel_id=row['panel_id'],team_key=key,method=method,configuration=vec))
            for metric in ['B8L2','fusion_turn_n']:
                stat=decompose(ep.loc[keys,metric].to_numpy(),group)
                results.append(dict(panel_id=row['panel_id'],image=row['image'],building=row['building'],n=row['n'],method=method,metric=metric,**stat))
    r=pd.DataFrame(results);save('COMPOSITION_PANEL_SUPPORT.csv',pd.DataFrame(coverage));save('COMPOSITION_TEAM_LABELS.csv.gz',pd.DataFrame(vectors));save('COMPOSITION_PANEL_RESULTS.csv',r)
    im=r.groupby(['method','metric','building','image'])[['total','between','within']].mean().reset_index();save('COMPOSITION_IMAGE_RESULTS.csv',im)
    b=im.groupby(['method','metric','building'])[['total','between','within']].mean().reset_index();save('COMPOSITION_BUILDING_RESULTS.csv',b)
    s=b.groupby(['method','metric'])[['total','between','within']].mean();s['between_share']=s.between/s.total
    save('COMPOSITION_SUMMARY.csv',s.reset_index())
    assert np.allclose(r.total,r.between+r.within,atol=1e-10,equal_nan=True)
    return dict(original_panels=231,common_panels=r.panel_id.nunique(),common_images=r.image.nunique(),common_buildings=r.building.nunique(),endpoint_cache_missing=0)


def main():
    assert (OUT/'PLAN.json').exists()
    labels,checks=fit_labels();print('labels',checks,flush=True)
    checks['ABC']=abc(labels);print(checks['ABC'],flush=True)
    checks['composition']=composition(labels);print(checks['composition'],flush=True)
    (OUT/'DSTRUCT_CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')


if __name__=='__main__':main()
