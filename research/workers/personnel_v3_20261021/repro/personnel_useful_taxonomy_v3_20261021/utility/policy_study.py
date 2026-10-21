"""Actual team selection on the new exhaustive conditional member panels.

Outer-building histories, classes, fitting and evaluation remain separate.
Class ties are integrated over all tied actual teams. No target outcome is used
for selection, tuning or candidate filtering. Missing scores stay missing.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse, gc, hashlib, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
from prepare_training import HERE,OLD,CONT,METRICS as TRAIN_METRICS,atomic_csv,atomic_json,sha

METRICS=TRAIN_METRICS+['height_min_h','height_max_h','centroid_x_h','centroid_z_h',
    'bounds_min_x_h','bounds_max_x_h','bounds_min_z_h','bounds_max_z_h',
    'ref_node_recall_5','ref_edge_recall_5','diag_corner_recall_05','diag_wall_coverage_05']

NEW=HERE.parent
COMP=NEW/'composition'
TAX=NEW/'taxonomy'
QT=['q_effect','q_downside','t_effect','t_tail']
STRUCT=['turn_history','short_history','redundancy_history','area_history','height_history']
RIDGE=.1
TIE_EPS=1e-9
SEED=2026102191
POLICY_VERSION='v3_exact_field_mapping_20261021'
FAMILY_IDS=['old_structure','new_behavior','new_joint','old_multivariate']

def labels_for(family,condition):
    if family in ('new_behavior','new_joint'):
        p=TAX/('LABELS_LOBO.csv.gz' if family=='new_behavior' else 'JOINT_LABELS_LOBO.csv.gz')
        d=pd.read_csv(p,low_memory=False)
        d=d[d.condition.eq(condition)&d.known.astype(bool)].copy()
        return d,p
    method=({'manual':'M_structure','semi':'SP_scale'} if family=='old_structure' else
            {'manual':'MV_QTD_manual_new','semi':'MV_QTScopeSemi_semi_new'})[condition]
    p=OLD/'composition/FROZEN_LABELS.csv'
    d=pd.read_csv(p,low_memory=False)
    d=d[d.condition.eq(condition)&d.method_id.eq(method)]
    d=d.pivot(index=['heldout_building','worker_id'],columns='tier',values='class_id').reset_index()
    return d.rename(columns={'coarse':'coarse_label','fine':'fine_label'}),p

def load_features(condition):
    q=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz',low_memory=False)
    q=q[q.condition.eq(condition)&q.metric.eq('B8L2')]
    s=pd.read_csv(TAX/'CONTINUOUS_FEATURES_LOBO.csv.gz',low_memory=False)
    s=s[s.condition.eq(condition)]
    f=q.merge(s[['heldout_building','worker_id','base_supported']+STRUCT],
              on=['heldout_building','worker_id'],how='left',validate='one_to_one')
    return f

def load_target(condition):
    teams=pd.read_csv(COMP/'DESIGN_TEAMS.csv.gz',low_memory=False)
    teams=teams[teams.condition.eq(condition)].copy().rename(columns={'n':'k'})
    panels=pd.read_csv(COMP/'PANELS.csv',low_memory=False)
    panels=panels[panels.condition.eq(condition)].copy()
    mem=pd.read_csv(COMP/'PANEL_MEMBERSHIP.csv.gz',low_memory=False)
    mem=mem[mem.panel_id.isin(panels.panel_id)].copy()
    rows=mem[['panel_id','team_key','selected_variable_workers']].merge(teams,on='team_key',validate='many_to_one')
    rows['center_id']=rows.panel_id
    rows['image_id']=rows.image
    return rows,panels

def load_new_endpoints(need,allow_missing=False):
    files=sorted((COMP/'batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz'))
    pieces=[]
    for p in files:
        d=pd.read_csv(p,low_memory=False)
        d=d[d.team_key.isin(need)].copy()
        if len(d):pieces.append(d)
    # Any explicitly separated reused output can be supplied without recalculation.
    for p in [COMP/'REUSED_ENDPOINT_SCALARS.csv.gz',COMP/'batches/REUSED_ENDPOINT_SCALARS.csv.gz']:
        if p.exists():
            d=pd.read_csv(p,low_memory=False);d=d[d.team_key.isin(need)]
            if len(d):pieces.append(d)
    if not pieces:raise RuntimeError('No new endpoint batch available')
    d=pd.concat(pieces,ignore_index=True)
    assert not d.team_key.duplicated().any(),'Endpoint batches overlap'
    missing=set(need)-set(d.team_key)
    if missing and not allow_missing:raise RuntimeError(f'{len(missing)} endpoint teams not yet completed')
    d['failure']=(~d.complete_evaluable.astype(bool)).astype(int)
    ok=(d.source_time_known_n.eq(d.k)&d.source_time_total_seconds.gt(0)&d.time_source_kinds.fillna('').ne('')&
        ~d.time_source_kinds.fillna('').str.contains('|',regex=False))
    d['total_time_compatible']=ok;d['log_total_time']=np.log(d.source_time_total_seconds.where(ok))
    return d,files

def counts_for(frame,roster):
    lookup={w:i for i,w in enumerate(roster)}
    a=np.zeros((len(frame),len(roster)),dtype=np.uint8)
    for i,s in enumerate(frame.member_workers):
        for w in s.split('|'):a[i,lookup[w]]=1
    assert np.array_equal(a.sum(axis=1),frame.k.to_numpy())
    return a

def matrix(frame,counts,roster,features,labels,usestructure,interactions=False):
    cols=QT+(STRUCT if usestructure else [])
    f=features.set_index('worker_id').reindex(roster)
    ll=labels.set_index('worker_id').reindex(roster)
    known=f[cols].notna().all(axis=1)&f.Q_supported.fillna(False).astype(bool)&f.T_supported.fillna(False).astype(bool)
    if usestructure:known &= f.base_supported.fillna(False).astype(bool)
    known &= ll[['coarse_label','fine_label']].notna().all(axis=1)
    known &= ll.coarse_label.ne('unknown')&ll.fine_label.ne('unknown')
    valid=(counts[:,~known.to_numpy()].sum(axis=1)==0)
    cc=sorted(ll.loc[known,'coarse_label'].unique());ff=sorted(ll.loc[known,'fine_label'].unique())
    names=['source_new']+['mean_'+k for k in cols]+['second_'+k for k in cols]+['coarse_'+c for c in cc]+['fine_'+c for c in ff]
    exact=[]
    if 'selected_family' in ll and known.any():
        families=ll.loc[known,'selected_family'].unique();assert len(families)==1
        family=families[0]
        if 'q_history' in ll:
            domain={'EQT':['turn_history','short_history'],
                    'GEQT':['turn_history','short_history','area_history','height_history'],
                    'CQT':['simple_turn_history','complex_turn_history','complex_short_history']}[family]
            exact=domain+['q_history','q_downside','t_history']
        else:
            exact={'TURN':['turn_history','short_history'],
                   'STRUCTURE':['turn_history','short_history','redundancy_history'],
                   'SCALE':['area_history','height_history'],
                   'JOINT':STRUCT,
                   'CONTEXT':['simple_turn_history','complex_turn_history','complex_short_history','redundancy_history','area_history','height_history']}[family]
        assert ll.loc[known,exact].notna().all().all(),'Known class has missing exact continuous inputs'
    exact_offset=len(names)
    names += ['exact_mean_'+k for k in exact]+['exact_second_'+k for k in exact]
    phi=np.zeros((len(roster),len(names)))
    for j,w in enumerate(roster):
        if not known.iloc[j]:continue
        v=f.loc[w,cols].to_numpy(float)
        phi[j,0]=float(f.loc[w,'origin']=='new')
        phi[j,1:1+len(cols)]=v
        phi[j,1+len(cols):1+2*len(cols)]=v*v
        offset=1+2*len(cols)
        phi[j,offset+cc.index(ll.loc[w,'coarse_label'])]=1
        phi[j,offset+len(cc)+ff.index(ll.loc[w,'fine_label'])]=1
        if exact:
            v=ll.loc[w,exact].to_numpy(float)
            phi[j,exact_offset:exact_offset+len(exact)]=v
            phi[j,exact_offset+len(exact):exact_offset+2*len(exact)]=v*v
    x=(counts@phi)/frame.k.to_numpy()[:,None]
    orig=len(names)
    source=[0]
    qnames={prefix+field for field in QT for prefix in ('mean_','second_')}
    snames={prefix+field for field in STRUCT for prefix in ('mean_','second_')}
    q=[i for i,n in enumerate(names[:orig]) if n in qnames]
    s=[i for i,n in enumerate(names[:orig]) if n in snames]
    assert len(q)==2*len(QT) and (not usestructure or len(s)==2*len(STRUCT))
    c=[i for i,n in enumerate(names[:orig]) if n.startswith('coarse_')]
    fine=[i for i,n in enumerate(names[:orig]) if n.startswith('fine_')]
    indices={'source':source,'QT':source+q,'class_coarse':source+c,'class_fine':source+fine,
             'QT_class_coarse':source+q+c,'QT_class_fine':source+q+fine}
    if usestructure:indices.update(continuous_structure=source+s,QT_continuous_structure=source+q+s)
    if exact:
        ei=list(range(exact_offset,exact_offset+2*len(exact)))
        indices.update(exact_continuous=source+ei,exact_continuous_class_fine=source+ei+fine)
    if interactions:
        # Interact team means/class proportions only. Person second moments stay
        # in the base model; never square the entire already expanded matrix.
        pair_indices={};new_columns=[]
        def with_products(base,meanix):
            extra=[]
            for ii,i in enumerate(meanix):
                for j in meanix[ii:]:
                    key=(min(i,j),max(i,j))
                    if key not in pair_indices:
                        pair_indices[key]=len(names)
                        names.append('product__'+names[key[0]]+'__'+names[key[1]])
                        new_columns.append(x[:,key[0]]*x[:,key[1]])
                    extra.append(pair_indices[key])
            return sorted(set(base+extra))
        indices['class_coarse_interaction']=with_products(indices['class_coarse'],c)
        indices['class_fine_interaction']=with_products(indices['class_fine'],fine)
        qm=[i for i in q if names[i].startswith('mean_')]
        indices['QT_interaction']=with_products(indices['QT'],qm)
        if usestructure:
            sm=[i for i in s if names[i].startswith('mean_')]
            indices['QT_continuous_structure_interaction']=with_products(indices['QT_continuous_structure'],qm+sm)
        if exact:
            em=list(range(exact_offset,exact_offset+len(exact)))
            indices['exact_continuous_interaction']=with_products(indices['exact_continuous'],em)
            indices['exact_continuous_interaction_class_fine']=sorted(set(
                indices['exact_continuous_interaction']+indices['class_fine_interaction']))
        if new_columns:x=np.column_stack([x]+new_columns)
    orig=len(names)
    x=np.column_stack([x,x*20/frame.k.to_numpy()[:,None]])
    names += ['invn_'+k for k in names]
    indices={name:ix+[i+orig for i in ix] for name,ix in indices.items()}
    historyq=x[:,names.index('mean_q_effect')]
    # Arithmetic mean predicted relative time; no target record time enters selection.
    tp=np.where(known.to_numpy(),np.exp(pd.to_numeric(f.t_effect,errors='coerce').fillna(0)),0)
    historyt=(counts@tp)/frame.k.to_numpy()
    return x,names,indices,valid,historyq,historyt,known.sum(),len(cc),len(ff)

def centered_fit_inputs(frame,x,metric):
    good=frame[metric].notna().to_numpy()
    ff=frame.loc[good].copy();xx=x[good]
    sufficient=ff.groupby('center_id').center_id.transform('size').ge(2).to_numpy()
    ff=ff.loc[sufficient].reset_index(drop=True);xx=xx[sufficient]
    if len(ff)==0 or ff.building.nunique()<3:return None
    codes,levels=pd.factorize(ff.center_id,sort=False);num=np.bincount(codes)
    sums=np.zeros((len(levels),xx.shape[1]));np.add.at(sums,codes,xx)
    xx=xx-sums[codes]/num[codes,None]
    y=ff[metric].to_numpy(float);mu=np.bincount(codes,weights=y)/num;y=y-mu[codes]
    group=ff[['center_id','image','building']].drop_duplicates('center_id')
    group['groups_per_image']=group.groupby(['building','image']).center_id.transform('size')
    images=group[['building','image']].drop_duplicates().groupby('building').size()
    group['group_weight']=1/(len(images)*group.groups_per_image*group.building.map(images))
    gw=dict(zip(group.center_id,group.group_weight))
    weights=ff.center_id.map(gw).to_numpy(float)/num[codes]
    assert np.isclose(weights.sum(),1)
    return xx,y,weights,ff

def fit_predict(train,xtrain,target,xtarget,indices,names,metric):
    ready=centered_fit_inputs(train,xtrain,metric)
    if ready is None:return {},[]
    xx,y,w,ff=ready
    predictions={};fits=[]
    for model,ix in indices.items():
        a=xx[:,ix];scale=np.sqrt((a*a*w[:,None]).sum(axis=0));active=scale>1e-10
        scale=np.where(active,scale,1.);a=a/scale;a[:,~active]=0
        coef=np.linalg.solve((a*w[:,None]).T@a+RIDGE*np.eye(len(ix)),(a*w[:,None]).T@y)
        b=xtarget[:,ix]/scale;b[:,~active]=0;predictions[model]=b@coef
        fits.append(dict(model=model,outcome=metric,train_rows=len(ff),train_buildings=ff.building.nunique(),
            train_groups=ff.center_id.nunique(),train_n_min=int(ff.k.min()),train_n_max=int(ff.k.max()),
            train_n_values='|'.join(map(str,sorted(ff.k.unique()))),predictors='|'.join(names[i] for i in ix),
            active_features=int(active.sum()),ridge=RIDGE,coefficient_json=json.dumps((coef/scale).tolist()),
            target_outcomes_used=False))
    return predictions,fits

def select(condition,family,regime,use_structure=None):
    out=HERE/regime/condition/family;out.mkdir(parents=True,exist_ok=True)
    target,panels=load_target(condition)
    if regime=='historical_only':
        trainbase=pd.read_csv(HERE/'TRAINING_ENDPOINTS.csv.gz',low_memory=False)
        trainbase=trainbase[trainbase.condition.eq(condition)].copy()
        trainbase['center_id']=trainbase.pool_id+'__n'+trainbase.k.astype(str)
        inputs={'training':sha(HERE/'TRAINING_ENDPOINTS.csv.gz')}
    else:
        endpoints,files=load_new_endpoints(set(target.team_key))
        attach=endpoints[['team_key','B8L2','log_total_time']]
        trainbase=target.merge(attach,on='team_key',validate='many_to_one')
        inputs={'endpoint_batches':{str(p.relative_to(COMP)):sha(p) for p in files}}
    feat=load_features(condition);labels,labelpath=labels_for(family,condition)
    label_hash=sha(labelpath)
    if family in ('new_behavior','new_joint'):
        freeze=json.loads((TAX/'LABEL_FREEZE.json').read_text())
        assert freeze['files'][labelpath.name]==label_hash,'Taxonomy labels are not frozen'
    roster=sorted(set(w for s in pd.concat([trainbase.member_workers,target.member_workers]) for w in s.split('|')))
    shared_frames=regime!='historical_only'
    if shared_frames:
        # Cross-panel train and target refer to the same ordered finite panels;
        # target-building rows are excluded only after constructing histories.
        assert np.array_equal(trainbase[['panel_id','team_key']].to_numpy(),target[['panel_id','team_key']].to_numpy())
        allframe=trainbase;allcounts=counts_for(allframe,roster);cut=len(trainbase)
    else:
        ac=counts_for(trainbase,roster);bc=counts_for(target,roster)
        allframe=pd.concat([trainbase,target],ignore_index=True);allcounts=np.vstack([ac,bc]);cut=len(trainbase)
        del ac,bc
    usestructure=family!='old_multivariate' if use_structure is None else bool(use_structure)
    supports=[];fits=[];selections=[];candidates=[]
    for b in sorted(target.building.unique()):
        ff=feat[feat.heldout_building.eq(b)]
        lab=labels[labels.heldout_building.eq(b)]
        xx,names,ix,valid,hq,ht,workers,nco,nfi=matrix(allframe,allcounts,roster,ff,lab,usestructure,
            interactions=regime!='historical_only')
        trainx=xx if shared_frames else xx[:cut];targetx=xx if shared_frames else xx[cut:]
        trainvalid=valid if shared_frames else valid[:cut];targetvalid=valid if shared_frames else valid[cut:]
        targethq=hq if shared_frames else hq[cut:];targetht=ht if shared_frames else ht[cut:]
        tr=(trainbase.building.ne(b).to_numpy() & trainvalid)
        te=(target.building.eq(b).to_numpy() & targetvalid)
        train=trainbase.loc[tr].copy();tar=target.loc[te].copy().reset_index(drop=True)
        tx=trainx[tr];yx=targetx[te]
        qpred,qfits=fit_predict(train,tx,tar,yx,ix,names,'B8L2')
        tpred,tfits=fit_predict(train,tx,tar,yx,ix,names,'log_total_time')
        for f in qfits+tfits:fits.append(dict(condition=condition,family=family,regime=regime,heldout_building=b,**f))
        values={'history_Q':targethq[te],'history_T':-targetht[te]}
        for model,v in qpred.items():
            values[model+'__quality']=v
            if model in tpred:values[model+'__balanced']=v-10*tpred[model]
        eligiblepanels=dict(tuple(tar.groupby('panel_id',sort=False)))
        for p in panels[panels.building.eq(b)].itertuples():
            g=eligiblepanels.get(p.panel_id)
            base=dict(condition=condition,family=family,regime=regime,heldout_building=b,panel_id=p.panel_id,
                pool_id=p.pool_id,image=p.image,building=p.building,difficulty=p.difficulty,n=p.n,
                source_domain=p.source_domain,registered_teams=p.possible_member_sets,
                common_candidates=0 if g is None else len(g),supported_workers=int(workers),
                coarse_k=nco,fine_k=nfi,train_rows=len(train),train_buildings=train.building.nunique(),
                target_label_building_excluded=True,all_registered_members_common=bool(g is not None and len(g)==p.possible_member_sets))
            if g is None or len(g)<2:
                supports.append(dict(base,status='insufficient_common_candidate_teams'));continue
            if not qpred:
                supports.append(dict(base,status='insufficient_training_buildings'));continue
            supports.append(dict(base,status='evaluated'))
            for row in g.itertuples():candidates.append(dict(panel_id=p.panel_id,team_key=row.team_key,probability=1/len(g)))
            idx=g.index.to_numpy()
            for policy,v in values.items():
                z=v[idx];best=float(z.max());chosen=idx[np.abs(z-best)<=TIE_EPS]
                for i in chosen:
                    selections.append(dict(panel_id=p.panel_id,policy=policy,team_key=tar.iloc[i].team_key,
                        probability=1/len(chosen),tie_count=len(chosen),objective_max=best))
        print('SELECT',regime,condition,family,b,'eligible',len(tar),'train',len(train),flush=True)
        gc.collect()
    assert sha(labelpath)==label_hash,'Labels changed during policy selection'
    atomic_csv(pd.DataFrame(supports),out/'SUPPORT.csv')
    atomic_csv(pd.DataFrame(fits),out/'FITS.csv.gz')
    atomic_csv(pd.DataFrame(selections),out/'SELECTIONS.csv.gz')
    atomic_csv(pd.DataFrame(candidates),out/'COMMON_CANDIDATES.csv.gz')
    atomic_json(dict(condition=condition,family=family,regime=regime,inputs=inputs,policy_version=POLICY_VERSION,
        labels_path=str(labelpath),labels_sha256=label_hash,
        qt_features_sha256=sha(OLD/'multivariate/continuous_features_lobo.csv.gz'),
        features_sha256=sha(TAX/'CONTINUOUS_FEATURES_LOBO.csv.gz'),
        design_sha256=sha(COMP/'DESIGN_TEAMS.csv.gz'),panel_sha256=sha(COMP/'PANELS.csv'),
        target_outcomes_used_for_selection=False,selected_records=len(selections),candidate_records=len(candidates),
        evaluated_panels=sum(r['status']=='evaluated' for r in supports),
        tie_epsilon=TIE_EPS,ridge=RIDGE,
        quadratic_team_mean_models=regime!='historical_only',
        policy_code_sha256=sha(Path(__file__))),out/'SELECTION_RECEIPT.json')

def weighted_known(values,weights):
    a=np.asarray(values,float);good=np.isfinite(a);mass=float(weights[good].sum())
    return (float(np.dot(weights[good],a[good])/mass) if mass>0 else np.nan),mass

def inclusion_probabilities(member_strings,weights):
    result={}
    for s,w in zip(member_strings,weights):
        for person in s.split('|'):result[person]=result.get(person,0.)+float(w)
    return result

def evaluate(condition,family,regime,partial_tag=None):
    out=HERE/regime/condition/family
    selection_receipt=json.loads((out/'SELECTION_RECEIPT.json').read_text())
    assert selection_receipt.get('policy_version')==POLICY_VERSION,'Selections must be regenerated after field-map correction'
    supports=pd.read_csv(out/'SUPPORT.csv',low_memory=False)
    candidates=pd.read_csv(out/'COMMON_CANDIDATES.csv.gz',low_memory=False)
    selected=pd.read_csv(out/'SELECTIONS.csv.gz',low_memory=False)
    ep,files=load_new_endpoints(set(candidates.team_key),allow_missing=bool(partial_tag))
    total_panels=candidates.panel_id.nunique()
    if partial_tag:
        have=set(ep.team_key)
        complete=[pid for pid,g in candidates.groupby('panel_id') if set(g.team_key)<=have]
        candidates=candidates[candidates.panel_id.isin(complete)].copy()
        selected=selected[selected.panel_id.isin(complete)].copy()
        if not complete:raise RuntimeError('No entire common-candidate panel completed yet')
        out=out/('partial_'+partial_tag);out.mkdir(exist_ok=True)
    ep=ep.set_index('team_key');rows=[];opportunities=[]
    class_rows=[]
    lab,_=labels_for(family,condition)
    label_maps={b:g.set_index('worker_id')[['coarse_label','fine_label']].to_dict('index')
                for b,g in lab.groupby('heldout_building')}
    choices=dict(tuple(selected.groupby('panel_id')))
    metadata=supports.set_index('panel_id')
    for pid,cc in candidates.groupby('panel_id'):
        allteams=ep.loc[cc.team_key].copy();base=metadata.loc[pid].to_dict()
        q=np.sort(allteams.B8L2.dropna().to_numpy(float));basefail=float(allteams.failure.mean())
        alltime=bool(allteams.total_time_compatible.all())
        base_time=float(allteams.source_time_total_seconds.mean()) if alltime else np.nan
        random_members=inclusion_probabilities(allteams.member_workers,np.ones(len(allteams))/len(allteams))
        person_labels=label_maps[base['building']]
        compositions={}
        for tier in ('coarse','fine'):
            bykey={}
            for teamkey,ss in allteams.member_workers.items():
                count={}
                for worker in ss.split('|'):
                    label=person_labels[worker][tier+'_label'];count[label]=count.get(label,0)+1
                bykey[teamkey]=json.dumps(count,sort_keys=True,separators=(',',':'))
            compositions[tier]=bykey
        qmean=float(q.mean()) if len(q) else np.nan
        support_hash=hashlib.sha256('|'.join(sorted(cc.team_key)).encode()).hexdigest()
        ordinary_risk={}
        for loss in (5,10):
            p=(len(q)-np.searchsorted(q,q+loss,side='right')).mean()/len(q) if len(q) else np.nan
            ordinary_risk[loss]=(float(p),float(basefail+(len(q)/len(allteams))*p))
        opp=dict(base,panel_id=pid,successful_candidates=len(q),failed_candidates=int(allteams.failure.sum()),
            ordinary_B8L2=qmean,B8L2_min=float(q.min()) if len(q) else np.nan,
            B8L2_max=float(q.max()) if len(q) else np.nan,
            B8L2_p10=float(np.quantile(q,.1)) if len(q) else np.nan,
            B8L2_p90=float(np.quantile(q,.9)) if len(q) else np.nan,
            B8L2_std=float(np.std(q)) if len(q) else np.nan,
            oracle_quality_headroom=float(q.max()-qmean) if len(q) else np.nan,
            all_candidates_time_compatible=alltime,ordinary_time_seconds=base_time)
        if alltime and len(q):
            feasible=allteams[allteams.B8L2.ge(qmean)]
            opp['oracle_feasible_no_mean_quality_loss_teams']=len(feasible)
            opp['oracle_fastest_no_mean_quality_loss_seconds']=float(feasible.source_time_total_seconds.min())
            opp['oracle_time_saving_without_mean_quality_loss_percent']=100*(1-feasible.source_time_total_seconds.min()/base_time)
        opportunities.append(opp)
        uniform=cc[['team_key','probability']].copy();uniform['policy']='ordinary_uniform';uniform['tie_count']=len(cc)
        pol=pd.concat([uniform,choices[pid]],ignore_index=True)
        for pname,g in pol.groupby('policy'):
            got=ep.loc[g.team_key].copy();w=g.probability.to_numpy(float);assert np.isclose(w.sum(),1)
            r=dict(base,panel_id=pid,policy=pname,selected_teams=len(g),common_candidates=len(cc),
                candidate_support_sha256=support_hash,
                selected_fraction=len(g)/len(cc),policy_can_discriminate=len(g)<len(cc),
                failure_rate=float(np.dot(w,got.failure)),ordinary_failure_rate=basefail,
                failure_delta_pp=100*(np.dot(w,got.failure)-basefail),
                all_candidates_time_compatible=alltime,ordinary_time_seconds=base_time)
            r['selection_distribution_sha256']=hashlib.sha256('|'.join(sorted(g.team_key)).encode()).hexdigest()
            selected_members=inclusion_probabilities(got.member_workers,w)
            r['expected_changed_members_vs_uniform']=float(base['n']-sum(v*random_members.get(person,0.) for person,v in selected_members.items()))
            r['selected_worker_inclusion_probabilities']=json.dumps(selected_members,sort_keys=True,separators=(',',':'))
            for tier in ('coarse','fine'):
                means={};ordinary_counts={};distribution={}
                for worker,prob in selected_members.items():
                    label=person_labels[worker][tier+'_label'];means[label]=means.get(label,0.)+prob
                for worker,prob in random_members.items():
                    label=person_labels[worker][tier+'_label'];ordinary_counts[label]=ordinary_counts.get(label,0.)+prob
                for key,prob in zip(g.team_key,w):
                    count= compositions[tier][key];distribution[count]=distribution.get(count,0.)+float(prob)
                r['selected_'+tier+'_mean_counts_json']=json.dumps(means,sort_keys=True,separators=(',',':'))
                r['ordinary_'+tier+'_mean_counts_json']=json.dumps(ordinary_counts,sort_keys=True,separators=(',',':'))
                r['selected_'+tier+'_distinct_compositions']=len(distribution)
                for counts,prob in distribution.items():
                    class_rows.append(dict(condition=condition,family=family,regime=regime,panel_id=pid,
                        building=base['building'],image=base['image'],n=base['n'],policy=pname,
                        tier=tier,class_counts_json=counts,probability=prob))
            r['source_time_patterns']=';'.join(sorted(allteams.time_source_kinds.fillna('unknown').unique()))
            for field,reverse in [('below_four',False),('connection_available',True),
                                   ('location_unresolved',False),('order_tied',False),
                                   ('complete_floor_evaluable',True)]:
                if field not in got:continue
                value=pd.to_numeric(got[field],errors='coerce').to_numpy(float)
                ordinary_values=pd.to_numeric(allteams[field],errors='coerce').to_numpy(float)
                if reverse:value=1-value;ordinary_values=1-ordinary_values
                label={'connection_available':'connection_unavailable','complete_floor_evaluable':'complete_floor_failure'}.get(field,field)
                estimate,mass=weighted_known(value,w);reference=float(np.nanmean(ordinary_values))
                r[label+'_rate']=estimate;r[label+'_known_weight']=mass
                r[label+'_delta_pp']=100*(estimate-reference)
            for metric in METRICS:
                if metric not in got:continue
                value,mass=weighted_known(got[metric],w)
                ordinary=float(pd.to_numeric(allteams[metric],errors='coerce').mean())
                r[metric]=value;r[metric+'_known_weight']=mass;r['ordinary_'+metric]=ordinary
                r['delta_'+metric]=value-ordinary
            t,tmass=weighted_known(got.source_time_total_seconds.where(got.total_time_compatible),w)
            r['selected_time_known_weight']=tmass
            r['time_seconds']=t if alltime else np.nan
            r['time_percent_vs_uniform']=100*(t/base_time-1) if alltime and base_time>0 else np.nan
            r['time_seconds_delta']=t-base_time if alltime else np.nan
            gv=got.B8L2.to_numpy(float);valid=np.isfinite(gv);wm=w[valid];qm=gv[valid]
            for loss in (5,10):
                prob=(len(q)-np.searchsorted(q,qm+loss,side='right'))/len(q) if len(q) else np.full(len(qm),np.nan)
                cond=float(np.dot(wm,prob)/wm.sum()) if wm.sum()>0 and len(q) else np.nan
                combined=float(r['failure_rate']+np.dot(wm,prob)) if len(q) and np.isfinite(prob).all() else np.nan
                r[f'loss_gt{loss}_vs_random_success_probability']=cond
                r[f'failure_or_loss_gt{loss}_vs_random_success_probability']=combined
                r[f'ordinary_loss_gt{loss}_vs_random_success_probability']=ordinary_risk[loss][0]
                r[f'ordinary_failure_or_loss_gt{loss}_vs_random_success_probability']=ordinary_risk[loss][1]
                r[f'loss_gt{loss}_delta_pp']=100*(cond-ordinary_risk[loss][0])
                r[f'failure_or_loss_gt{loss}_delta_pp']=100*(combined-ordinary_risk[loss][1])
            rows.append(r)
    frame=pd.DataFrame(rows)
    assert not frame.duplicated(['panel_id','policy']).any()
    atomic_csv(frame,out/'PANEL_POLICY_RESULTS.csv.gz')
    atomic_csv(pd.DataFrame(opportunities),out/'PANEL_OBSERVED_OPPORTUNITIES.csv')
    atomic_csv(pd.DataFrame(class_rows),out/'POLICY_CLASS_COMPOSITIONS.csv.gz')
    atomic_json(dict(condition=condition,family=family,regime=regime,panels=frame.panel_id.nunique(),
        policies=sorted(frame.policy.unique()),rows=len(frame),endpoint_unique=len(ep),
        failure_retained=True,quality_failure_imputed_zero=False,
        partial=bool(partial_tag),registered_supported_panels=total_panels,
        pending_supported_panels=total_panels-frame.panel_id.nunique(),
        time_panel_gate='every common candidate has full compatible source seconds',
        sources={str(p.relative_to(COMP)):sha(p) for p in files}),out/'EVALUATION_RECEIPT.json')
    print('EVALUATED',regime,condition,family,len(frame),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['select','evaluate'])
    p.add_argument('--condition',choices=['manual','semi'],required=True)
    p.add_argument('--family',choices=FAMILY_IDS,required=True)
    p.add_argument('--regime',choices=['historical_only','cross_panel_LOBO'],required=True)
    p.add_argument('--partial-tag')
    a=p.parse_args();start=time.time()
    if a.phase=='select':
        assert not a.partial_tag,'Partial fitting would change registered training population'
        select(a.condition,a.family,a.regime)
    else:evaluate(a.condition,a.family,a.regime,a.partial_tag)
    print('DONE',a.phase,a.condition,a.family,a.regime,round(time.time()-start,2),flush=True)

if __name__=='__main__':main()
