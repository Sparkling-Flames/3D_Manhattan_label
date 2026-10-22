"""Exact finite-member composition descriptions and outer-building response checks.
No fusion is run here; all endpoints are frozen outputs from the registered design.
"""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,csv,gzip,hashlib,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
NEW=HERE.parent;COMP=NEW/'composition';TAX=NEW/'taxonomy'
OLD=NEW.parent/'personnel_global_composition_20261021'
STRUCT=['turn_history','short_history','redundancy_history','area_history','height_history']
CONTEXT=['simple_turn_history','complex_turn_history','complex_short_history']
BEHAVIOR_FIELDS={'TURN':STRUCT[:2],'STRUCTURE':STRUCT[:3],'SCALE':STRUCT[3:],
 'JOINT':STRUCT,'CONTEXT':CONTEXT+STRUCT[2:]}
JOINT_FIELDS={'EQT':STRUCT[:2], 'GEQT':STRUCT[:2]+STRUCT[3:], 'CQT':CONTEXT}
QT=['q_effect','q_downside','t_effect','t_tail']
YCOLS=['B8L2','D10','failure','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
 'log_geometry_area','height_mean_h','top_y_mean_px','bottom_y_mean_px','iou_2d','IoU3D100',
 'S_bottom_deg','dir','Hmean','Hcenter','omission','extension','ref_node_recall_9','ref_edge_recall_9','log_source_time']
SEED=2026102199;RIDGE=.1

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def save(d,p):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.partial')
    z=p.name.endswith('.gz')
    payload=d.to_csv(index=False).encode('utf-8-sig')
    if z:payload=gzip.compress(payload,compresslevel=5,mtime=0)
    with tmp.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    check=pd.read_csv(tmp,compression='gzip' if z else None,low_memory=False)
    assert check.shape==d.shape,(p,check.shape,d.shape);os.replace(tmp,p)

def js(p,x):
    def clean(a):
        if isinstance(a,dict):return {str(k):clean(v) for k,v in a.items()}
        if isinstance(a,(list,tuple)):return [clean(v) for v in a]
        if isinstance(a,np.generic):return clean(a.item())
        if isinstance(a,float) and not np.isfinite(a):return None
        return a
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.partial')
    tmp.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)

def geometry_expression(s):
    g=json.loads(s) if s else None
    if not g:return [np.nan]*3
    p=np.asarray(g.get('footprint') or [],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():return [np.nan]*3
    edges=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(edges,axis=1)
    prev=np.roll(edges,1,axis=0);den=np.linalg.norm(prev,axis=1)*length
    if (den<=1e-12).any():return [np.nan]*3
    turn=np.degrees(np.arccos(np.clip((prev*edges).sum(axis=1)/den,-1,1)))
    redundant=int(np.sum(turn<=5));short=int(np.sum((length/length.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)))
    return [len(p)-redundant,short,redundant]

def derive_geometry():
    out=HERE/'geometry_batches';out.mkdir(exist_ok=True);manifest=[]
    for p in sorted((COMP/'batches').glob('*/ENDPOINT_GEOMETRY.csv.gz')):
        receipt=p.parent/'COMPLETION.json'
        if not receipt.exists():continue
        dst=out/(p.parent.name+'_EXPRESSION.csv.gz');inp=sha(p)
        rp=dst.with_suffix('.json')
        if dst.exists() and rp.exists() and json.loads(rp.read_text()).get('input_sha256')==inp:
            manifest.append(json.loads(rp.read_text()));continue
        d=pd.read_csv(p,usecols=['team_key','geometry_json']);cache={};rows=[]
        for r in d.itertuples(index=False):
            s=r.geometry_json if isinstance(r.geometry_json,str) else ''
            if s not in cache:cache[s]=geometry_expression(s)
            rows.append([r.team_key,*cache[s]])
        x=pd.DataFrame(rows,columns=['team_key','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n'])
        assert not x.team_key.duplicated().any();save(x,dst)
        m=dict(batch=p.parent.name,rows=len(x),unique_geometry_strings=len(cache),input_sha256=inp,output_sha256=sha(dst))
        js(rp,m);manifest.append(m);print(json.dumps(m),flush=True)
    js(HERE/'GEOMETRY_DERIVATION.json',manifest)

def load(condition):
    panels=pd.read_csv(COMP/'PANELS.csv');panels=panels[panels.condition.eq(condition)].copy()
    teams=pd.read_csv(COMP/'DESIGN_TEAMS.csv.gz',usecols=['team_key','member_workers'])
    mem=pd.read_csv(COMP/'PANEL_MEMBERSHIP.csv.gz',usecols=['panel_id','team_key'])
    frame=mem.merge(panels,on='panel_id',validate='many_to_one').merge(teams,on='team_key',validate='many_to_one')
    frame=frame[frame.condition.eq(condition)].copy()
    need=set(frame.team_key);scores=[];geos=[]
    for p in sorted((COMP/'batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz')):
        if not (p.parent/'COMPLETION.json').exists():continue
        d=pd.read_csv(p,low_memory=False);d=d[d.team_key.isin(need)]
        if len(d):scores.append(d)
    for p in sorted((HERE/'geometry_batches').glob('*_EXPRESSION.csv.gz')):
        d=pd.read_csv(p);d=d[d.team_key.isin(need)]
        if len(d):geos.append(d)
    scores=pd.concat(scores,ignore_index=True);assert not scores.team_key.duplicated().any()
    assert set(scores.team_key)==need,('unfinished',len(need-set(scores.team_key)))
    g=pd.concat(geos,ignore_index=True);assert not g.team_key.duplicated().any();assert set(g.team_key)==need
    scores['failure']=(~scores.complete_evaluable.astype(bool)).astype(float)
    scores['log_geometry_area']=np.log(scores.geometry_area_h2.where(scores.geometry_area_h2.gt(0)))
    ok=scores.source_time_known_n.eq(scores.k)&scores.source_time_total_seconds.gt(0)&scores.time_source_kinds.fillna('').ne('')&~scores.time_source_kinds.fillna('').str.contains('|',regex=False)
    scores['log_source_time']=np.log(scores.source_time_total_seconds.where(ok))
    scores=scores.merge(g,on='team_key',validate='one_to_one')
    for c in YCOLS:
        if c not in scores:scores[c]=np.nan
    frame=frame.merge(scores[['team_key']+YCOLS],on='team_key',validate='many_to_one').reset_index(drop=True)
    assert frame.groupby('panel_id').size().eq(924).all()
    roster=sorted({w for ss in frame.member_workers for w in ss.split('|')});ix={w:i for i,w in enumerate(roster)}
    count=np.zeros((len(frame),len(roster)),dtype=np.uint8)
    for i,ss in enumerate(frame.member_workers):
        for w in ss.split('|'):count[i,ix[w]]=1
    assert np.array_equal(count.sum(axis=1),frame.n)
    return frame,panels,roster,count

def inputs(condition):
    s=pd.read_csv(TAX/'CONTINUOUS_FEATURES_LOBO.csv.gz');s=s[s.condition.eq(condition)]
    q=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz');q=q[q.condition.eq(condition)&q.metric.eq('B8L2')]
    v=pd.read_csv(TAX/'LABELS_LOBO.csv.gz');v=v[v.condition.eq(condition)]
    j=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz');j=j[j.condition.eq(condition)]
    o=pd.read_csv(OLD/'composition/FROZEN_LABELS.csv');o=o[o.condition.eq(condition)]
    method='M_structure' if condition=='manual' else 'SP_scale'
    oo=o[o.method_id.eq(method)].pivot(index=['heldout_building','worker_id'],columns='tier',values='class_id').reset_index()
    return s,q,v,j,oo

def feature_matrix(roster,count,frame,build,source,domain):
    s,q,v,j,old=source
    def sub(d):return d[d.heldout_building.eq(build)].set_index('worker_id').reindex(roster)
    ss,qq,vv,jj,oo=map(sub,[s,q,v,j,old])
    behavior_family=vv.selected_family.dropna().iloc[0]
    selected_behavior_fields=BEHAVIOR_FIELDS[behavior_family]
    validw=ss.base_supported.fillna(False).astype(bool).to_numpy()&ss[STRUCT].notna().all(axis=1).to_numpy()
    for dd,cols in [(vv,['coarse_label','fine_label']),(oo,['coarse','fine'])]:
        validw &= dd[cols].notna().all(axis=1).to_numpy()&(~dd[cols].eq('unknown').any(axis=1)).to_numpy()
    validw &= vv[selected_behavior_fields].notna().all(axis=1).to_numpy()
    if domain=='qt_common':
        joint_family=jj.selected_family.dropna().iloc[0]
        selected_joint_fields=JOINT_FIELDS[joint_family]+['q_history','q_downside','t_history']
        validw &= qq[QT].notna().all(axis=1).to_numpy()&qq.Q_supported.fillna(False).astype(bool).to_numpy()&qq.T_supported.fillna(False).astype(bool).to_numpy()
        validw &= jj.known.fillna(False).astype(bool).to_numpy()&jj[['q_history','q_downside','t_history']].notna().all(axis=1).to_numpy()
        validw &= jj[selected_joint_fields].notna().all(axis=1).to_numpy()
    valid=count[:,~validw].sum(axis=1)==0
    # Set unsupported rows to zero only after excluding every team containing
    # one; no unknown worker is interpreted as having a zero feature value.
    columns=[];names=[];blocks={}
    def add(prefix,a,labels):
        start=len(names)
        for k,l in enumerate(labels):
            col=np.asarray(a[:,k],float);col[~validw]=0;columns.append(col);names.append(prefix+str(l))
        blocks[prefix]=list(range(start,len(names)))
    add('source',ss.origin.eq('new').to_numpy(float)[:,None],['_new'])
    h=ss[STRUCT].to_numpy(float);add('struct_mean_',h,STRUCT);add('struct_second_',h*h,STRUCT)
    h=vv[selected_behavior_fields].to_numpy(float)
    add('selected_behavior_mean_',h,selected_behavior_fields);add('selected_behavior_second_',h*h,selected_behavior_fields)
    for prefix,dd,col in [('old_coarse_',oo,'coarse'),('old_fine_',oo,'fine'),('new_coarse_',vv,'coarse_label'),('new_fine_',vv,'fine_label')]:
        levels=sorted(dd.loc[validw,col].unique());add(prefix,np.column_stack([dd[col].eq(k) for k in levels]) if levels else np.zeros((len(roster),0)),levels)
    if domain=='qt_common':
        a=qq[QT].to_numpy(float);add('qt_mean_',a,QT);add('qt_second_',a*a,QT)
        cols=['q_history','q_downside','t_history'];a=jj[cols].to_numpy(float);add('jointqt_mean_',a,cols);add('jointqt_second_',a*a,cols)
        a=jj[selected_joint_fields].to_numpy(float)
        add('jointmatched_mean_',a,selected_joint_fields);add('jointmatched_second_',a*a,selected_joint_fields)
        for prefix,col in [('joint_coarse_','coarse_label'),('joint_fine_','fine_label')]:
            levels=sorted(jj.loc[validw,col].unique());add(prefix,np.column_stack([jj[col].eq(k) for k in levels]) if levels else np.zeros((len(roster),0)),levels)
    phi=np.column_stack(columns);x=(count@phi)/frame.n.to_numpy()[:,None]
    # Team-mean products can express interior mixture effects; the worker-level
    # second moments above alone are still additive member scores.
    pair_sources=['old_coarse_','old_fine_','new_coarse_','new_fine_','selected_behavior_mean_']
    if domain=='qt_common':pair_sources+=['qt_mean_','joint_coarse_','joint_fine_','jointmatched_mean_']
    for source_name in pair_sources:
        inds=blocks[source_name];ii,jj=np.triu_indices(len(inds));a=x[:,inds]
        start=len(names);extra=a[:,ii]*a[:,jj];x=np.column_stack([x,extra])
        names += [f'product_{names[inds[i]]}__{names[inds[j]]}' for i,j in zip(ii,jj)]
        blocks['product_'+source_name]=list(range(start,len(names)))
    nfeat=len(names)
    x=np.column_stack([x,x*20/frame.n.to_numpy()[:,None]])
    names += ['invn_'+z for z in names]
    def use(*ks):
        inds=sum([blocks[k] for k in ks],[]);return inds+[k+nfeat for k in inds]
    models={'source':use('source'),'old_coarse':use('source','old_coarse_'),'old_fine':use('source','old_fine_'),
      'new_coarse':use('source','new_coarse_'),'new_fine':use('source','new_fine_'),
      'structure_mean':use('source','struct_mean_'),'structure_moments':use('source','struct_mean_','struct_second_'),
      'behavior_same_fields_mean':use('source','selected_behavior_mean_'),
      'behavior_same_fields_moments':use('source','selected_behavior_mean_','selected_behavior_second_'),
      'behavior_same_fields_quadratic':use('source','selected_behavior_mean_','selected_behavior_second_','product_selected_behavior_mean_')}
    for method in ['old_coarse','old_fine','new_coarse','new_fine']:
        models[method+'_quadratic']=use('source',method+'_','product_'+method+'_')
    if domain=='qt_common':
        models.update(QT=use('source','qt_mean_','qt_second_'),QT_structure=use('source','qt_mean_','qt_second_','struct_mean_','struct_second_'),
          QT_new_fine=use('source','qt_mean_','qt_second_','new_fine_'),joint_coarse=use('source','joint_coarse_'),
          joint_fine=use('source','joint_fine_'),joint_continuous_QT=use('source','jointqt_mean_','jointqt_second_'),
          joint_same_fields_mean=use('source','jointmatched_mean_'),
          joint_same_fields_moments=use('source','jointmatched_mean_','jointmatched_second_'),
          QT_quadratic=use('source','qt_mean_','qt_second_','product_qt_mean_'),
          joint_coarse_quadratic=use('source','joint_coarse_','product_joint_coarse_'),
          joint_fine_quadratic=use('source','joint_fine_','product_joint_fine_'),
          joint_same_fields_quadratic=use('source','jointmatched_mean_','jointmatched_second_','product_jointmatched_mean_'))
    return x,models,names,valid,blocks,phi

def center(a,codes):
    n=np.bincount(codes);a=np.asarray(a,float)
    if a.ndim==1:
        means=np.bincount(codes,weights=a)/n;return a-means[codes]
    sums=np.zeros((len(n),a.shape[1]));np.add.at(sums,codes,a);return a-sums[codes]/n[codes,None]

def weights(f):
    g=f[['panel_id','image','building']].drop_duplicates();g['npan']=g.groupby(['building','image']).panel_id.transform('size')
    ni=g[['building','image']].drop_duplicates().groupby('building').size();n=f.groupby('panel_id').size()
    w=dict(zip(g.panel_id,1/(len(ni)*g.npan*g.building.map(ni))))
    return f.panel_id.map(w).to_numpy()/f.panel_id.map(n).to_numpy()

def describe(f,counts,phi,blocks,condition,domain,build):
    rows=[]
    for method in ['old_coarse_','old_fine_','new_coarse_','new_fine_','joint_coarse_','joint_fine_']:
        if method not in blocks:continue
        cc=counts@phi[:,blocks[method]]
        cfg=['|'.join(map(str,map(int,row))) for row in cc]
        ff=f.copy();ff['configuration']=cfg
        for panel,g in ff.groupby('panel_id',sort=False):
            base={k:g.iloc[0][k] for k in ['panel_id','pool_id','image','building','condition','difficulty','source_domain','n']}
            for outcome in YCOLS:
                a=g[['configuration',outcome]].dropna();nn=len(a)
                if nn<2:continue
                groups=a.groupby('configuration')[outcome];size=groups.size();mu=groups.mean();means=a.configuration.map(mu)
                total=float(np.var(a[outcome],ddof=0));within=float(np.mean((a[outcome]-means)**2));between=total-within
                substitutable=size[size>=2]
                rows.append(dict(base,domain=domain,method=method.rstrip('_'),outcome=outcome,teams=len(g),valid_teams=nn,
                    configurations=len(size),substitutable_configurations=len(substitutable),single_member_configurations=int((size==1).sum()),
                    members_in_substitutable_configurations=int(substitutable.sum()),total_variance=total,within_configuration_variance=within,
                    between_configuration_variance=between,between_share=between/total if total>1e-12 else np.nan,
                    degenerate_no_total_variation=total<=1e-12,complete_finite_panel=len(g)==924))
    return rows

def run(condition,domain):
    out=HERE/condition/domain;out.mkdir(parents=True,exist_ok=True)
    frame,panels,roster,count=load(condition);source=inputs(condition);allrows=[];all_desc=[];cover=[];fits=[]
    code_sha=sha(Path(__file__))
    for build in sorted(frame.building.unique()):
        bp=out/'building_batches'/build
        checkpoint=bp.with_name(build+'_COMPLETE.json')
        if checkpoint.exists():
            cached=json.loads(checkpoint.read_text())
            if cached.get('code_sha256')==code_sha:
                cover.append(cached['support'])
                if cached.get('has_results'):
                    for filename,dest in [('PREDICTION.csv.gz',allrows),('DECOMPOSITION.csv.gz',all_desc),('MODELS.csv.gz',fits)]:
                        dest.extend(pd.read_csv(bp.with_name(build+'_'+filename)).to_dict('records'))
                print(json.dumps(dict(building=build,resumed=True)),flush=True);continue
        xp,models,names,valid,blocks,phi=feature_matrix(roster,count,frame,build,source,domain)
        target=valid&frame.building.eq(build).to_numpy();train=valid&~frame.building.eq(build).to_numpy()
        ft=frame.loc[target].reset_index(drop=True);xx=xp[target];ct=count[target]
        cv=dict(condition=condition,domain=domain,building=build,valid_target_rows=int(target.sum()),target_panels=ft.panel_id.nunique(),
          all_target_rows=int(frame.building.eq(build).sum()),valid_train_rows=int(train.sum()),known_workers=int((phi.sum(axis=1)!=0).sum()))
        cover.append(cv)
        if not target.any() or not train.any():
            js(checkpoint,dict(code_sha256=code_sha,support=cv,has_results=False));continue
        desc=describe(ft,ct,phi,blocks,condition,domain,build);all_desc.extend(desc)
        b_rows=[];b_fits=[]
        for outcome in YCOLS:
            tr=train&frame[outcome].notna().to_numpy();te=ft[outcome].notna().to_numpy()
            a=frame.loc[tr].copy();xa=xp[tr]
            enough=a.groupby('panel_id').panel_id.transform('size').ge(2).to_numpy();a=a.loc[enough];xa=xa[enough]
            z=ft.loc[te].copy();xz=xx[te]
            enough=z.groupby('panel_id').panel_id.transform('size').ge(2).to_numpy();z=z.loc[enough];xz=xz[enough]
            if len(a)<2 or len(z)<2 or a.building.nunique()<3:continue
            co,_=pd.factorize(a.panel_id);tc,_=pd.factorize(z.panel_id)
            xa=center(xa,co);ya=center(a[outcome].to_numpy(),co);xz=center(xz,tc);yz=center(z[outcome].to_numpy(),tc);w=weights(a)
            groups=z.groupby('panel_id',sort=False).indices
            for model,ix in models.items():
                v=xa[:,ix];scale=np.sqrt((v*v*w[:,None]).sum(axis=0));active=scale>1e-10;scale=np.where(active,scale,1.);v=v/scale;v[:,~active]=0
                coef=np.linalg.solve((v*w[:,None]).T@v+RIDGE*np.eye(len(ix)),(v*w[:,None]).T@ya)
                tx=xz[:,ix]/scale;tx[:,~active]=0;pred=tx@coef
                for panel,ii in groups.items():
                    first=z.iloc[ii[0]];base={k:first[k] for k in ['panel_id','pool_id','image','building','condition','difficulty','source_domain','n']}
                    baseline=float(np.mean(yz[ii]**2));mse=float(np.mean((yz[ii]-pred[ii])**2))
                    b_rows.append(dict(base,domain=domain,model=model,outcome=outcome,teams=len(ii),mse=mse,baseline_mse=baseline,
                        response_r2=1-mse/baseline if baseline>1e-12 else np.nan,mae=float(np.mean(np.abs(yz[ii]-pred[ii]))),
                        train_teams=len(a),train_buildings=a.building.nunique(),active_features=int(active.sum())))
                b_fits.append(dict(condition=condition,domain=domain,heldout_building=build,outcome=outcome,model=model,ridge=RIDGE,
                    predictors='|'.join(names[i] for i in ix),coefficients=json.dumps((coef/scale).tolist()),train_teams=len(a),train_buildings=a.building.nunique()))
        allrows.extend(b_rows);fits.extend(b_fits)
        save(pd.DataFrame(b_rows),out/'building_batches'/f'{build}_PREDICTION.csv.gz')
        save(pd.DataFrame(desc),out/'building_batches'/f'{build}_DECOMPOSITION.csv.gz')
        save(pd.DataFrame(b_fits),out/'building_batches'/f'{build}_MODELS.csv.gz')
        js(checkpoint,dict(code_sha256=code_sha,support=cv,has_results=True))
        print(json.dumps(cv),flush=True)
    save(pd.DataFrame(allrows),out/'PANEL_PREDICTION.csv.gz');save(pd.DataFrame(all_desc),out/'PANEL_CONFIGURATION_DECOMPOSITION.csv.gz')
    save(pd.DataFrame(cover),out/'SUPPORT.csv');save(pd.DataFrame(fits),out/'FITTED_MODELS.csv.gz')
    summarize(out)

def summarize(out):
    p=pd.read_csv(out/'PANEL_PREDICTION.csv.gz');d=pd.read_csv(out/'PANEL_CONFIGURATION_DECOMPOSITION.csv.gz')
    rows=[];br=[];rng=np.random.default_rng(SEED)
    for scope in ['all','n','difficulty','source_domain']:
        fields=['condition','domain','model','outcome']+([] if scope=='all' else [scope])
        for key,g in p.groupby(fields,dropna=False):
            meta=dict(zip(fields,key));meta.update(stratum=scope,stratum_value='all' if scope=='all' else str(meta.pop(scope)))
            b=g.groupby(['building','image'])[['mse','baseline_mse','mae']].mean().groupby('building').mean()
            den=b.baseline_mse.mean();r2=1-b.mse.mean()/den if den>1e-12 else np.nan
            ids=rng.integers(0,len(b),(2000,len(b)));ms=b.mse.to_numpy()[ids].mean(axis=1);bs=b.baseline_mse.to_numpy()[ids].mean(axis=1)
            boot=np.divide(ms,bs,out=np.full_like(ms,np.nan),where=bs>1e-12);lo,hi=np.nanquantile(1-boot,[.025,.975]) if np.isfinite(boot).any() else [np.nan,np.nan]
            rows.append(dict(meta,panels=g.panel_id.nunique(),images=g.image.nunique(),buildings=len(b),valid_member_references=int(g.teams.sum()),
                mse=float(b.mse.mean()),baseline_mse=float(den),response_r2=r2,r2_ci_low=lo,r2_ci_high=hi,mae=float(b.mae.mean())))
            if scope=='all':
                for building,r in b.iterrows():br.append(dict(meta,building=building,**r.to_dict()))
    save(pd.DataFrame(rows),out/'PREDICTION_SUMMARY.csv');save(pd.DataFrame(br),out/'PREDICTION_BUILDINGS.csv')
    dd=[]
    for key,g in d.groupby(['condition','domain','method','outcome']):
        b=g.groupby(['building','image'])[['total_variance','within_configuration_variance','between_configuration_variance']].mean().groupby('building').mean()
        den=b.total_variance.mean();dd.append(dict(zip(['condition','domain','method','outcome'],key),panels=g.panel_id.nunique(),images=g.image.nunique(),buildings=len(b),
          total_variance=den,within_variance=b.within_configuration_variance.mean(),between_variance=b.between_configuration_variance.mean(),
          between_share=b.between_configuration_variance.mean()/den if den>1e-12 else np.nan,
          substitutable_configurations=int(g.substitutable_configurations.sum()),single_member_configurations=int(g.single_member_configurations.sum())))
    save(pd.DataFrame(dd),out/'DECOMPOSITION_SUMMARY.csv')
    js(out/'COMPLETION.json',dict(status='complete',ridge=RIDGE,metrics=YCOLS,endpoint_recalculation=False,
        unit='finite conditional member panels; image then building equal',prediction_rows=len(p),decomposition_rows=len(d)))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['derive','run','summary']);ap.add_argument('--condition',choices=['manual','semi']);ap.add_argument('--domain',choices=['geometry_common','qt_common'],default='geometry_common');args=ap.parse_args()
    if args.action=='derive':derive_geometry()
    elif args.action=='run':run(args.condition,args.domain)
    else:summarize(HERE/args.condition/args.domain)
