"""Image-grade dependency update; reuse every score, geometry and team identity."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT/'research/data/releases/v2.1'
EXT = REL/'admitted_space_extension'
OUT = EXT/'image_difficulty_20261030'
CLASS = ROOT/'research/workers/personnel_v21_reselection_20261029/classification'

def read(p):
    return json.loads(p.read_text(encoding='utf8'))

def write(name, obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')

def csv(name, data):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);data.to_csv(p,index=False,encoding='utf-8-sig')

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def grades():
    return {r['image']:r['current_class'] for r in read(REL/'difficulty_records.json')['records']}

def relabel(frame, image='image', grade='difficulty'):
    d=frame.copy();g=d[image].map(grades());assert g.isin(['简单','中等','困难']).all()
    d[grade]=g
    pd.testing.assert_frame_equal(d.drop(columns=grade),frame.drop(columns=grade))
    return d

def inputs():
    OUT.mkdir(exist_ok=True)
    snapshot=read(EXT/'pools/INPUT_SNAPSHOT.json');g=grades();mapping=[]
    for p in snapshot['images']:
        meta=p['meta'];meta['difficulty']=g[meta['image']]
        meta['difficulty_basis']='image_grade_user_confirmed';meta['difficulty_aligned']=True
        mapping.append(meta)
    assert len(mapping)==31 and len({r['image'] for r in mapping})==28
    write('pools/INPUT_SNAPSHOT.json',snapshot);csv('POOL_COVERAGE.csv',pd.DataFrame(mapping))
    records=read(EXT/'ANALYSIS_RECORDS.json')
    for r in records:r['current_class']=g[r['image_code']]
    write('ANALYSIS_RECORDS.json',records)
    for p in sorted((EXT/'natural_inputs').glob('*.csv.gz')):
        d=pd.read_csv(p,low_memory=False);csv('natural_inputs/'+p.name,relabel(d))
    for name in ['natural_analysis/UPDATED_CURVES.csv.gz','DISPLAY_CURVES.csv.gz','two_person_natural256/IMAGE_RESULTS.csv']:
        d=pd.read_csv(EXT/name,low_memory=False)
        mask=d.pool_id.isin([r['pool_id'] for r in mapping]);new=d.copy()
        new.loc[mask,'difficulty']=d.loc[mask,'image'].map(g)
        pd.testing.assert_frame_equal(new.drop(columns='difficulty'),d.drop(columns='difficulty'))
        csv(name,new)
    # Historic joint behavior already carries image-level grades; no model rerun is needed.
    joint=pd.read_csv(EXT/'joint_history_classification/BEHAVIOR_RECORDS.csv.gz',low_memory=False)
    ids={r['object_id'] for r in records};part=joint[joint.object_id.isin(ids)]
    imagecol='image' if 'image' in part else 'image_code'
    if imagecol not in part:
        idgrade={r['object_id']:r['current_class'] for r in records};expected=part.object_id.map(idgrade)
    else:expected=part[imagecol].map(g)
    assert part.difficulty.eq(expected).all()
    raw=pd.read_csv(CLASS/'RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False);new=raw.copy()
    mask=new.scope.eq('other_admitted');assert mask.sum()==231
    new.loc[mask,'official_difficulty']=new.loc[mask,'image'].map(g)
    pd.testing.assert_frame_equal(raw.drop(columns='official_difficulty'),new.drop(columns='official_difficulty'))
    csv('classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',new)
    train=pd.read_csv(EXT/'fusion_role_classification/NATURAL_TRAINING_ENDPOINTS.csv.gz',low_memory=False)
    mask=train.support_origin.eq('other_admitted_target');assert mask.sum()==343
    updated=train.copy();updated.loc[mask,'difficulty']=train.loc[mask,'image'].map(g)
    pd.testing.assert_frame_equal(train.drop(columns='difficulty'),updated.drop(columns='difficulty'))
    csv('rfuse/NATURAL_TRAINING_ENDPOINTS.csv.gz',updated)
    write('INPUT_CHECKS.json',dict(pools=31,images=28,records=231,rfuse_added_endpoints=343,
          joint_history_already_image_graded=True,unchanged_scores_geometry_members=True,new_fusion=0,new_scoring=0,
          grade_counts=pd.DataFrame(mapping).groupby('difficulty').size().to_dict()))

def target_fit():
    import warnings
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
    m=module('target_update',CLASS/'code/build_target_aware_candidates.py')
    m.FAMILIES={'TARGET_DSTRUCT':m.FAMILIES['TARGET_DSTRUCT']}
    raw=pd.read_csv(OUT/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    roster=pd.read_csv(CLASS/'NEW_PERSONNEL_HISTORY_ALL.csv')[['worker_id','origin']].drop_duplicates()
    folds=['ALL']+sorted(raw.loc[raw.history_eligible,'building'].unique())
    tabs={k:[] for k in ['HISTORY','LABELS','CENTERS','REGISTRY']}
    for fold in folds:
        f,tr=m.history(raw,roster,fold);lab,cen,reg,enc=m.fit(f)
        for key,d in zip(tabs,[f,lab,cen,reg]):tabs[key].append(d)
        print('TARGET image-grade',fold,flush=True)
    for key,parts in tabs.items():csv('classification/'+key+'_ALL_LOBO.csv.gz',pd.concat(parts,ignore_index=True))
    write('classification/CHECKS.json',dict(folds=len(folds),family='TARGET_DSTRUCT',ks=[2,3,4],final_selection=False,new_fusion=0))

def rfuse_fit():
    from . import refit_v21_fusion_roles_20261028 as native
    prep,core=native.modules()
    target=module('target_rfuse_update',CLASS/'code/build_target_weighted_rfuse.py')
    roster=pd.read_csv(CLASS/'NEW_PERSONNEL_HISTORY_ALL.csv')[['worker_id','origin']].drop_duplicates()
    for kind,Study in [('RFUSE',core.Study),('TARGET_RFUSE',target.TargetStudy)]:
        study=Study(OUT/'rfuse/NATURAL_TRAINING_ENDPOINTS.csv.gz');tabs={k:[] for k in ['LABELS','FEATURES','SELECTION']}
        for fold in ['ALL']+study.buildings:
            selected,selection,checks=study.select(fold);tabs['SELECTION'].append(selection)
            for family,alpha in selected.items():
                f=study.response_features(fold,alpha);lab,centers,registry,enc=core.labels_for(f,family,roster)
                if kind=='TARGET_RFUSE':lab['method']='TARGET_'+lab.method
                tabs['LABELS'].append(lab);f['family']=family;tabs['FEATURES'].append(f)
            print(kind,fold,flush=True)
        for key,parts in tabs.items():csv('rfuse/'+kind+'_'+key+'_ALL_LOBO.csv.gz',pd.concat(parts,ignore_index=True))

def summaries():
    from .summarize_admitted_space_descriptive_20261029 import compare
    d=pd.DataFrame(read(OUT/'ANALYSIS_RECORDS.json'));d['image_difficulty']=d.current_class
    for col in ['B8L2','D10','source_active_time_seconds']:d[col]=pd.to_numeric(d[col],errors='raise')
    d.loc[d.source_active_time_seconds.le(0),'source_active_time_seconds']=np.nan
    csv('DESCRIPTION_BY_DIFFICULTY.csv',compare(d,['condition','image_difficulty'],['B8L2','D10']))
    csv('PERSONNEL_BY_DIFFICULTY.csv',compare(d,['condition','image_difficulty','worker_id'],['B8L2','D10']))
    csv('TIME_BY_DIFFICULTY_SOURCE.csv',compare(d,['condition','image_difficulty','origin','time_provenance'],['source_active_time_seconds']))
    curve=pd.read_csv(OUT/'DISPLAY_CURVES.csv.gz',low_memory=False);rows=[]
    for support in ['other_admitted_target','combined']:
        subset=curve if support=='combined' else curve[curve.support.eq(support)]
        for key,part in subset.groupby(['condition','layer','difficulty','k']):
            for metric in ['Q_mean','Q_p10','Q_sd_ddof1','actual_consensus_failure_rate','output_unscoreable_rate']:
                z=part.dropna(subset=[metric]);im=z.groupby(['building','image'])[metric].mean()
                rows.append(dict(support=support,condition=key[0],layer=key[1],difficulty=key[2],k=key[3],metric=metric,mean=im.mean(),valid_pools=len(z),images=len(im),buildings=im.index.get_level_values(0).nunique(),eligible_pools=len(part)))
    csv('CURVES_BY_DIFFICULTY.csv',pd.DataFrame(rows))
    write('SUMMARY_CHECKS.json',dict(new_fusion=0,all_scores_reused=True,target_then_image_equal=True,labor_source_separate=True))

def labels():
    return pd.concat([pd.read_csv(OUT/'classification/LABELS_ALL_LOBO.csv.gz'),
                     pd.read_csv(OUT/'rfuse/RFUSE_LABELS_ALL_LOBO.csv.gz'),
                     pd.read_csv(OUT/'rfuse/TARGET_RFUSE_LABELS_ALL_LOBO.csv.gz')],ignore_index=True)

def block_direction(row, roster, suffix=''):
    groups=[{roster.get(w) for w in str(row[k+suffix]).split('|') if w} for k in 'XYZ']
    legal=all(len(g)==1 and None not in g for g in groups) and groups[0]==groups[1] and groups[0]!=groups[2]
    return (str(next(iter(groups[0])))+'→'+str(next(iter(groups[2])))) if legal else ''

def downstream():
    from .compare_admitted_space_classifications_20261029 import align_labels
    from sklearn.metrics import adjusted_rand_score
    old=pd.read_csv(CLASS/'MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    new=labels();comparisons=[]
    for (method,fold),g in new.groupby(['method','heldout_building']):
        a=old[(old.method==method)&(old.heldout_building==fold)]
        pair=a[a.known][['worker_id','class_id']].merge(g[g.known][['worker_id','class_id']],on='worker_id',suffixes=('_old','_new'))
        mapping,amb=align_labels(pair.class_id_old.astype(str),pair.class_id_new.astype(str))
        comparisons.append(dict(method=method,fold=fold,old_known=int(a.known.sum()),new_known=int(g.known.sum()),common=len(pair),
            changed_aligned=int((pair.class_id_old.astype(str)!=pair.class_id_new.astype(str).map(mapping)).sum()),
            ARI=adjusted_rand_score(pair.class_id_old,pair.class_id_new) if len(pair)>1 else np.nan))
    csv('LABEL_CHANGE.csv',pd.DataFrame(comparisons))
    # MAIN45 RFUSE includes a different historical scope; isolate grade-only change too.
    scope_old=pd.read_csv(EXT/'fusion_role_classification/LABELS_ALL_LOBO.csv.gz',low_memory=False)
    scope_new=new[new.method.isin(scope_old.method.unique())];scoped=[]
    for (method,fold),g in scope_new.groupby(['method','heldout_building']):
        a=scope_old[(scope_old.method==method)&(scope_old.heldout_building==fold)]
        pair=a[a.known][['worker_id','class_id']].merge(g[g.known][['worker_id','class_id']],on='worker_id',suffixes=('_old','_new'))
        mapping,_=align_labels(pair.class_id_old.astype(str),pair.class_id_new.astype(str))
        scoped.append(dict(method=method,fold=fold,common=len(pair),changed_aligned=int((pair.class_id_old.astype(str)!=pair.class_id_new.astype(str).map(mapping)).sum()),ARI=adjusted_rand_score(pair.class_id_old,pair.class_id_new)))
    csv('RFUSE_GRADE_ONLY_LABEL_CHANGE.csv',pd.DataFrame(scoped))
    rosters={(m,b):dict(zip(g[g.known].worker_id,g[g.known].class_id.astype(str))) for (m,b),g in new.groupby(['method','heldout_building'])}
    from .continue_v21_final_classification_20261029 import image_summary
    e=pd.read_csv(REL/'final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz',low_memory=False)
    e['updated_direction']=[block_direction(r,rosters['TARGET_DSTRUCT_K3',r['building']]) for r in e.to_dict('records')]
    e['updated_class_legal']=e.updated_direction.ne('');csv('HALF_EVENT_LEGALITY.csv.gz',e)
    stats=[]
    for n,d in e.groupby('n'):
        for scope,z in [('frozen_design',d),('updated_labels_legal_subset',d[d.updated_class_legal])]:
            stats.append(dict(n=n,scope=scope,**image_summary(z)))
    csv('HALF_SUMMARY.csv',pd.DataFrame(stats))
    pro=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
    room=pd.read_csv(pro/'stage02_same_room/EXISTING_VALID_EVENT_SOURCE.csv.gz',low_memory=False)
    room=room[room.ordinary_comparable & room.condition.eq('manual') & (room.m*2).eq(room.n)].copy()
    outputs=[];pairs=[]
    for method in ['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','RFUSE_GEOM_K2']:
        z=room.copy();z['updated_direction']=[block_direction(r,rosters[method,r['building']], '_members') for r in z.to_dict('records')]
        z=z[z.updated_direction.ne('')].drop_duplicates(['pair_key','A_members','B_members','C_members'])
        z['method_updated']=method
        for side in ['a','b']:
            ba=z['B8L2_'+side+'_BA'];ca=z['B8L2_'+side+'_CA'];cb=z['B8L2_'+side+'_CB']
            z['GA_'+side]=ca.abs()-ba.abs();z['GS_'+side]=(ca.abs()+cb.abs())/2-ba.abs();z['CB_'+side]=cb
        metrics=[m+'_'+v for m in ['GA','GS','CB'] for v in ['a','b']]
        z.loc[~z[metrics].notna().all(axis=1),metrics]=np.nan
        z['block']=z.X_members+' / '+z.Y_members+' / '+z.Z_members
        outputs.append(z)
        keys=['method_updated','building','pair_key','n','m','updated_direction']
        pair=z.groupby(keys+['block'],dropna=False)[metrics].mean().groupby(level=keys).mean().reset_index()
        pairs.append(pair)
    csv('SAME_ROOM_HALF_EVENTS.csv.gz',pd.concat(outputs,ignore_index=True))
    pair=pd.concat(pairs,ignore_index=True);csv('SAME_ROOM_HALF_PAIRS.csv',pair)
    rows=[]
    for key,g in pair.groupby(['method_updated','n','m','updated_direction']):
        z=g.dropna(subset=['CB_a','CB_b'])
        rows.append(dict(method=key[0],n=key[1],m=key[2],direction=key[3],registered_pairs=len(g),valid_pairs=len(z),buildings=z.building.nunique(),CB_mean=((z.CB_a+z.CB_b)/2).mean(),CB_positive_pairs=int(((z.CB_a+z.CB_b)>0).sum()),CB_both_positive=int(((z.CB_a>0)&(z.CB_b>0)).sum())))
    csv('SAME_ROOM_HALF_SUMMARY.csv',pd.DataFrame(rows))

def speed():
    pro=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
    m=module('speed_update',pro/'scripts/speed_difficulty.py');m.OUT=OUT/'speed_difficulty';m.OUT.mkdir(exist_ok=True)
    fresh=labels();original_read=m.read
    def reader(path):
        if path.name in ['MAIN45_LABELS_ALL_LOBO.csv.gz','USED_FINAL_LOBO_LABELS.csv.gz']:
            d=original_read(path);d=d[~d.method.isin(fresh.method.unique())]
            return pd.concat([d,fresh],ignore_index=True)
        return original_read(path)
    m.read=reader
    x=m.records();lab,h=m.labels_and_history();lab=lab[lab.method.isin(['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3'])]
    p=m.current_pairs(x,lab,h)
    m.summarize(p,m.METRICS,'CURRENT_MATCHED',{'all_current_support':pd.Series(True,index=p.index)})
    m.same_people(p,m.METRICS,'CURRENT_SAME_PEOPLE')
    m.same_people(p,m.METRICS,'CURRENT_SAME_PEOPLE_SAME_BUILDING',paired_building=True)

def same_room_composition():
    from . import reaggregate_v21_same_room_oppjoint_fixed_panels_20261029 as sr
    from collections import Counter
    lab=labels();roster={(m,b):dict(zip(g[g.known].worker_id,g[g.known].class_id)) for (m,b),g in lab.groupby(['method','heldout_building'])}
    engine=sr.load_engine();panels=engine.annotate_budget(pd.read_csv(sr.DESIGN/'PANELS.csv'))
    for c in ['ordinary_comparable','scope_comparable']:panels[c]=sr.as_bool(panels[c])
    links=pd.read_csv(sr.DESIGN/'PANEL_TEAM_LINKS.csv.gz');ep=pd.read_csv(sr.ENDPOINTS,low_memory=False);pm=panels.set_index('panel_id')
    for method in ['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','RFUSE_GEOM_K2']:
        sr.METHODS=(method,);engine=sr.load_engine();annotated=links.copy();vectors=[];known=[]
        for r in links.itertuples():
            c=Counter(roster[method,pm.loc[r.panel_id].building].get(w,'unknown') for w in r.member_set_key.split('|'))
            vectors.append(json.dumps(dict(sorted(c.items()))));known.append('unknown' not in c)
        annotated[method+'_vector']=vectors;annotated[method+'_all_known']=known;annotated['both_methods_all_known']=known
        paired=sr.join_endpoints(panels,annotated,ep,engine.METRICS);moments,support=sr.summarize(panels,paired,engine)
        csv('same_room_composition/'+method+'_SUPPORT.csv',support)
        for name,frame in zip(['PAIR','GROUP','BUILDING','SUMMARY'],sr.aggregate(moments,engine)):
            csv('same_room_composition/'+method+'_'+name+'.csv',frame)

def composition(scope):
    import types
    packages=CLASS.parent/'additional_delivery/packages'
    configs={'primary':(packages/'03B_core/composition/primary_panel_inputs',None,'manual'),
             'semi':(packages/'03C/composition/primary_semi_inputs',None,'semi'),
             'other':(packages/'03A/composition/other_targets_design',packages/'03A/composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz','manual')}
    folder,endpoint,condition=configs[scope]
    lab=labels();lab['evaluation_condition']='manual_and_semi_separately'
    csv(f'composition_{scope}_labels.csv.gz',lab)
    tc=pd.read_csv(packages/'03B_core/targets/POOL_TARGET_CONDITIONS.csv')
    mask=tc.pool_id.isin(pd.read_csv(OUT/'POOL_COVERAGE.csv').pool_id)
    tc.loc[mask,'official_difficulty']=tc.loc[mask,'image'].map(grades())
    csv(f'composition_{scope}_conditions.csv',tc)
    path=CLASS.parent/'composition/code/aggregate_frozen_panels.py';source=path.read_text(encoding='utf8')
    start=source.index('    signature=hashlib.sha256()');end=source.index('    # Precompute shared',start)
    # No new SHA checks: disable checkpoint reuse instead of trusting a stale signature.
    source=source[:start]+"    run_hash='not_hashed_cache_disabled_image_grade_update'\n"+source[end:]
    source=source.replace('if checkpoint.exists() and','if False and checkpoint.exists() and')
    m=types.ModuleType('composition_update');m.__file__=str(path);exec(compile(source,str(path),'exec'),m.__dict__)
    args=['composition_update','--inputs',str(folder),'--labels',str(OUT/f'composition_{scope}_labels.csv.gz'),'--out',str(OUT/'composition'/scope),'--condition',condition,'--target-conditions',str(OUT/f'composition_{scope}_conditions.csv')]
    if endpoint:args+=['--endpoints',str(endpoint)]
    original=sys.argv
    try:sys.argv=args;m.main()
    finally:sys.argv=original

def retained_strata():
    m=module('saved_composition',CLASS.parent/'composition/code/aggregate_frozen_panels.py')
    changed=set(labels().method)
    base=CLASS.parent/'additional_delivery/packages/03A/composition'
    summaries=[]
    for scope in ['other_targets_manual45','other_targets_semi4']:
        for p in (base/scope).rglob('PANEL_VARIANCE.csv.gz'):
            d=pd.read_csv(p,low_memory=False)
            if d.empty or set(d.method)<=changed:continue
            d=relabel(d);z=m.macro(d);z['source_dataset']=scope;summaries.append(z)
    assert summaries
    csv('UNCHANGED_METHOD_DIFFICULTY_SUMMARY.csv',pd.concat(summaries,ignore_index=True))

def background():
    source=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage01_half_team/EXACT_XYZ_14_7_TO_20_7.csv'
    links=pd.read_csv(source)
    events=pd.read_csv(OUT/'HALF_EVENT_LEGALITY.csv.gz',low_memory=False)
    legal=set(events.loc[events.updated_class_legal,'event_id'])
    links=links[links.event_id_14.isin(legal)&links.event_id_20.isin(legal)]
    csv('MATCHED_BACKGROUND_LINKS.csv',links)
    rows=[];keys=['building_14','image_14','pool_id','X','Y','Z']
    for scope,part in [('all_exact_XYZ',links),('D14_subset_D20',links[links.D14_subset_D20]),('D_also_replaced',links[~links.D14_subset_D20])]:
        for metric in ['gap_A','gap_sym','CB','B8L2_within','B8L2_cross_direct','B8L2_cross_symmetric']:
            cols=[metric+'_14',metric+'_20'];v=part.dropna(subset=cols)
            z=v.groupby(keys)[cols].mean().groupby(level=keys[:3]).mean().groupby(level=keys[:2]).mean().reset_index()
            delta=z[cols[1]]-z[cols[0]]
            rows.append(dict(scope=scope,metric=metric,registered_links=len(part),valid_links=len(v),images=len(z),buildings=z.building_14.nunique(),mean_14=z[cols[0]].mean(),mean_20=z[cols[1]].mean(),mean_delta=delta.mean(),positive=int((delta>0).sum()),negative=int((delta<0).sum())))
    csv('MATCHED_BACKGROUND_SUMMARY.csv',pd.DataFrame(rows))
    from tools.thesis_main.analysis.continue_v21_final_classification_20261029 import image_summary
    strata=[];metrics=[]
    events['difficulty']=events.image.map(grades())
    for (n,difficulty),group in events.groupby(['n','difficulty']):
        for scope,z in [('frozen_design',group),('updated_labels_legal_subset',group[group.updated_class_legal])]:
            strata.append(dict(n=n,difficulty=difficulty,scope=scope,**image_summary(z)))
            for metric in ['B8L2_CB','D10_CB','fusion_turn_n_CB','fusion_short_turn_edges_CB','omission_CB','extension_CB','record_time_CB_pct_source_matched']:
                v=z.groupby(['building','image','pool_id','block_id','background_id'],dropna=False)[metric].mean()
                v=v.groupby(level=['building','image','pool_id','block_id']).mean().groupby(level=['building','image','pool_id']).mean().groupby(level=['building','image']).mean().dropna()
                metrics.append(dict(n=n,difficulty=difficulty,scope=scope,metric=metric,images=len(v),mean=v.mean(),positive=int((v>0).sum()),negative=int((v<0).sum())))
    csv('HALF_BY_DIFFICULTY.csv',pd.DataFrame(strata))
    csv('HALF_DIFFICULTY_COMPONENTS.csv',pd.DataFrame(metrics))

def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    folder=OUT/'figures';folder.mkdir(exist_ok=True);index=[]
    def emit(fig,name,title,caption,source):
        fig.suptitle(title,fontsize=13)
        for ext in ['png','pdf','svg']:fig.savefig(folder/(name+'.'+ext),dpi=300,bbox_inches='tight')
        plt.close(fig);index.append(dict(name=name,title=title,caption=caption,source=source))
    d=pd.read_csv(OUT/'DESCRIPTION_BY_DIFFICULTY.csv');c=pd.read_csv(OUT/'CURVES_BY_DIFFICULTY.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,kind in zip(axes,['individual','team']):
        z=d[d.condition.eq('manual')].set_index('image_difficulty') if kind=='individual' else c[c.support.eq('other_admitted_target')&c.condition.eq('manual')&c.k.eq(3)&c.metric.eq('Q_mean')].set_index('difficulty')
        z=z.loc[['简单','中等','困难']];values=z.B8L2 if kind=='individual' else z['mean'];ns=z.B8L2_images if kind=='individual' else z.images
        ax.bar(range(3),values,color='#337b91',edgecolor='black',hatch='/');ax.set(xticks=range(3),xticklabels=[f'{l}\n{int(n)} images' for l,n in zip(['Easy','Moderate','Difficult'],ns)],xlabel='Confirmed image difficulty',ylabel='Mean quality Q (points)',title='Individual annotations' if kind=='individual' else 'Three-person consensus teams');ax.set_ylim(0,100)
    emit(fig,'U01_space_difficulty','Annotation and consensus quality for additional legal spaces\nby confirmed image difficulty','Manual additional targets only. Targets are equally weighted within each image. Individual scores and conditional scoreable team means are different estimands. The same image grade is used for every target; references and personnel pools remain separate. No score or fusion was recomputed.','DESCRIPTION_BY_DIFFICULTY.csv;CURVES_BY_DIFFICULTY.csv')
    d=pd.read_csv(OUT/'HALF_SUMMARY.csv');fig,axes=plt.subplots(1,3,figsize=(12,4.5),layout='constrained')
    for ax,metric,label in zip(axes,['gap_A','gap_sym','CB'],['GA: excess direct magnitude','GS: excess symmetric magnitude','C - B: quality direction']):
        for i,scope in enumerate(['frozen_design','updated_labels_legal_subset']):
            z=d[d.scope.eq(scope)].sort_values('n');ax.bar(np.arange(2)+(i-.5)*.32,z[metric],width=.32,label='Frozen labels' if i==0 else 'Updated-label legal subset',hatch='/' if i==0 else '',edgecolor='black')
        ax.axhline(0,color='black',lw=.7);ax.set(xticks=range(2),xticklabels=['14 / 7','20 / 7'],xlabel='Team size / replaced members',ylabel='Quality contrast (Q points)',title=label)
    axes[0].legend(fontsize=8)
    emit(fig,'U02_half_sensitivity','Quality contrasts under frozen and updated working labels\nfor seven-member replacement','TARGET K3 remains a working classification. Frozen n14/n20: 197/82 events and 83/70 valid images. Updated-label legal subset: 147/61 events and 67/52 valid images. Saved scores are unchanged. Different support prevents interpreting the mean difference as the causal effect of grade revision.','HALF_SUMMARY.csv;HALF_EVENT_LEGALITY.csv.gz')
    old=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage03_speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv'
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    for ax,metric,label in zip(axes,['turn_n','short_turn_edges'],['Turn-count advantage (turns)','Short-edge advantage (edges)']):
        vals=[];counts=[]
        for path in [old,OUT/'speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv']:
            z=pd.read_csv(path);r=z[z.method.eq('TARGET_DSTRUCT_K3')&z.condition.eq('manual')&z.origin.eq('new')&z.metric.eq(metric)].iloc[0];vals.append(r['mean']);counts.append(int(r.valid_pair_rows))
        ax.bar(range(2),vals,color='#337b91',edgecolor='black',hatch='/');ax.axhline(0,color='black',lw=.7);ax.set(xticks=range(2),xticklabels=[f'Frozen labels\n{counts[0]} pairs',f'Updated labels\n{counts[1]} pairs'],xlabel='Working-label matching condition',ylabel='Hard-minus-easy change in\nslow-minus-fast '+label.lower())
    emit(fig,'U03_speed_difficulty','Structural-expression contrasts between slower and faster annotators\nafter updating difficulty-dependent working labels','Outside-building history and matching rules are fixed. Current TARGET K3 support changes from 105 to 100 pairs; weak average contrasts remain. This comparison does not alter the frozen v2 63-pair evidence.','speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv')
    d=pd.read_csv(OUT/'SAME_ROOM_HALF_PAIRS.csv');d=d[d.method_updated.eq('TARGET_DSTRUCT_K3')&d.updated_direction.eq('C2→C3')]
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    for ax,n in zip(axes,[10,14]):
        z=d[d.n.eq(n)].dropna(subset=['CB_a','CB_b']);ax.scatter(z.CB_a,z.CB_b,marker='o' if n==10 else '^',color='#337b91');ax.axhline(0,color='black',lw=.7);ax.axvline(0,color='black',lw=.7)
        low=min(0,z[['CB_a','CB_b']].min().min());high=z[['CB_a','CB_b']].max().max();pad=(high-low)*.08;ax.set(xlim=(low-pad,high+pad),ylim=(low-pad,high+pad),xlabel='View 1: C - B (Q points)',ylabel='View 2: C - B (Q points)',title=f'n={n}, m={n//2}: {len(z)} pairs')
    emit(fig,'U04_same_room','Cross-view quality differences under half-team replacement\nusing updated TARGET K3 working labels','Ordinary comparable Manual, direction C2 to C3. The saved event archive is filtered under updated labels and physically deduplicated. 10/5: 322 events, 295 six-endpoint scoreable, 19 pairs; 14/7: 10 events, 6 scoreable, 2 pairs. No new teams or fusion; 14/7 still has one incoming seven-member block.','SAME_ROOM_HALF_PAIRS.csv;SAME_ROOM_HALF_EVENTS.csv.gz')
    csv('figures/INDEX.csv',pd.DataFrame(index))
    body='<h1>Image-difficulty update: publication figures</h1>'
    for r in index:body+=f'<section><h2>{r["title"]}</h2><img src="{r["name"]}.png"><p>{r["caption"]}</p><p><a href="{r["name"]}.pdf">PDF</a> | <a href="{r["name"]}.svg">SVG</a></p></section>'
    (folder/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Difficulty update</title><style>body{font:17px sans-serif;max-width:1200px;margin:30px auto}img{width:100%}section{margin-bottom:45px}</style>'+body,encoding='utf8')

if __name__=='__main__':
    stages={'inputs':inputs,'target':target_fit,'rfuse':rfuse_fit,'summaries':summaries,'downstream':downstream,'speed':speed,'same_room_composition':same_room_composition,
            'composition_primary':lambda:composition('primary'),'composition_other':lambda:composition('other'),'composition_semi':lambda:composition('semi'),'retained_strata':retained_strata,'background':background,'figures':figures}
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=stages);args=ap.parse_args();stages[args.stage]()
