#!/usr/bin/env python3
"""Matched fixed-A scale and fixed-XYZ background paths, without new fusion.

This consumes the *new* frozen design and existing scalar endpoints. It does
not regenerate/select teams. Per-view values remain linked to exact endpoints;
cross-view summaries require common support on both stages, both views, and
all three roles. Unknown/missing scores are never treated as zero.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd

VERSION='SRLB_ANCHOR_PATHS_20261023_v1'
METRICS=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','S_bottom_deg','dir','Hmean','Hcenter',
 'height_mean_ratio','iou_2d','IoU3D100','omission','extension',
 'ref_node_recall_5','ref_edge_recall_5','diag_corner_recall_05',
 'diag_wall_coverage_05','geometry_area_h2','height_mean_h',
 'top_y_mean_px','bottom_y_mean_px','centroid_x_h','centroid_z_h',
 'reference_node_shortfall','identity_groups_n','minimum_support',
 'recorded_time_total_seconds','source_time_total_seconds']
SUMMARY_METRICS=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','S_bottom_deg','dir','Hmean','height_mean_ratio',
 'geometry_area_h2','IoU3D100','recorded_time_total_seconds']
EFFECTS=['A_change','B_change','C_change','net_C_minus_B_change',
 'BA_change','CA_change','within_amplitude_change','cross_amplitude_change',
 'extra_amplitude_change']
META=['pair_key','building','groups','method','condition','ordinary_comparable',
 'source_class','target_class','source_role','target_role','source_role_key',
 'target_role_key','image_a','image_b','pool_id_a','pool_id_b','reference_id_a',
 'reference_id_b','difficulty_a','difficulty_b','layer_a','layer_b','scope_comparable']

def boolean(x):
    return x.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])

def write_csv(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if str(path).endswith('.gz'):
        with path.open('wb') as raw, gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as z:
            z.write(df.to_csv(index=False).encode())
    else:df.to_csv(path,index=False)

def h(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]

def selected_endpoints(e,role,view):
    B='B' if role=='A' else 'A'
    return [e[f'team_{r}_{view}'] for r in (role,B,'C')]

def design_transitions(design_dir):
    p=Path(design_dir)
    d=pd.read_csv(p/'STRICT_ABC_EVENTS.csv.gz',keep_default_na=False).set_index('event_id',drop=False)
    fixed=pd.read_csv(p/'FIXED_A_SCALE_PATHS.csv.gz',keep_default_na=False)
    back=pd.read_csv(p/'DESIGN_PATH_LINKS.csv.gz',keep_default_na=False)
    transitions={};stage_coverage=[]
    def add(study,tag,l,s,path):
        e1,e2=d.loc[l.event_id],d.loc[s.event_id]
        assert e1.pair_key==e2.pair_key and e1.method==e2.method
        key='PAT_'+h([study,l.event_id,s.event_id,l.nominal_A_role,s.nominal_A_role])
        if key in transitions:
            transitions[key]['_tags'].add(tag)
            transitions[key]['_path_ids'].add(path)
            return
        row={k:e1[k] for k in META}
        row.update(path_transition_id=key,study_type=study,event_small=l.event_id,
          event_large=s.event_id,nominal_A_role_small=l.nominal_A_role,
          nominal_A_role_large=s.nominal_A_role,m_small=int(e1.m),m_large=int(e2.m),
          n_small=int(e1.n),n_large=int(e2.n),D_n_small=int(e1.D_n),D_n_large=int(e2.D_n),
          D_small=e1.D_members,D_large=e2.D_members,D_class_counts_small=e1.D_class_counts,
          D_class_counts_large=e2.D_class_counts,_tags={tag},_path_ids={path})
        for stage,e,role in [('small',e1,l.nominal_A_role),('large',e2,s.nominal_A_role)]:
            br='B' if role=='A' else 'A'
            for logical,stored in [('A',role),('B',br),('C','C')]:
                row[f'{logical}_members_{stage}']=e[f'{stored}_members']
            for view in 'ab':
                for logical,ep in zip('ABC',selected_endpoints(e,role,view)):
                    row[f'team_{stage}_{logical}_{view}']=ep
        if study=='fixed_A_scale':
            assert row['A_members_small']==row['A_members_large']
            assert row['n_small']==row['n_large']
            assert row['m_small']<row['m_large']
            for view in 'ab':assert row[f'team_small_A_{view}']==row[f'team_large_A_{view}']
            row['fixed_A_endpoint_verified']=True
        else:
            assert row['m_small']==row['m_large']
            assert row['n_small']<row['n_large']
            # Actual nominal XYZ, not merely same class counts.
            for logical in 'ABC':
                old=set(row[f'{logical}_members_small'].split('|'))-set(e1.D_members.split('|'))
                new=set(row[f'{logical}_members_large'].split('|'))-set(e2.D_members.split('|'))
                assert old==new,(key,logical,old,new)
            assert set(e1.D_members.split('|'))-{''} <= set(e2.D_members.split('|'))-{''}
            row['fixed_A_endpoint_verified']=False
        transitions[key]=row
    for path,z in fixed.groupby('fixed_A_path_id',sort=True):
        z=z.sort_values('m').drop_duplicates('m')
        if len(z)<2:continue
        rr=list(z.itertuples(index=False))
        for l,s in zip(rr[:-1],rr[1:]):add('fixed_A_scale','m_adjacent',l,s,path)
        add('fixed_A_scale','m_min_to_max',rr[0],rr[-1],path)
    for path,z in back.groupby('background_path_id',sort=True):
        z=z.sort_values('n').drop_duplicates('n');m=int(z.m.iloc[0])
        rr={int(r.n):r for r in z.itertuples(index=False)}
        nmax=max(rr)
        stages={'pure':m,'half':2*m,'first_below_half':2*m+1,'maximum_D':nmax}
        stage_coverage.append({'background_path_id':path,'pair_key':z.pair_key.iloc[0],
          'method':z.method.iloc[0],'m':m,'n_max':nmax,'pure_supported':m in rr,
          'half_supported':2*m in rr,'first_below_half_supported':2*m+1 in rr})
        for label,left,right in [('pure_to_half','pure','half'),
             ('half_to_first_below_half','half','first_below_half'),
             ('pure_to_max','pure','maximum_D'),('half_to_max','half','maximum_D'),
             ('first_below_half_to_max','first_below_half','maximum_D')]:
            n1,n2=stages[left],stages[right]
            if n1 in rr and n2 in rr and n1<n2:add('fixed_XYZ_background',label,rr[n1],rr[n2],path)
    for row in transitions.values():
        row['comparison_tags']='|'.join(sorted(row.pop('_tags')))
        pp=row.pop('_path_ids');row['path_ids']='|'.join(sorted(pp));row['path_reference_n']=len(pp)
    return pd.DataFrame(transitions.values()),pd.DataFrame(stage_coverage)

def endpoint_frame(native):
    fields={'team_key','complete_evaluable','score_status','score_failure_nonpolicy',
      'incomplete_nonpolicy','time_source_kinds','recorded_time_eligible',*METRICS}
    native=Path(native)
    files=[native] if native.is_file() else sorted(native.glob('parts/*/*.scalars.csv.gz'))
    if not files:raise ValueError('No native scalar endpoints')
    x=pd.concat([pd.read_csv(f,usecols=lambda c:c in fields,low_memory=False) for f in files],ignore_index=True)
    if x.team_key.duplicated().any():raise ValueError('Duplicate native team key')
    return x.set_index('team_key',drop=False)

def metrics_for_paths(t,s,allow_partial=False):
    # Tensor order: transition, stage(small/large), view(a/b), role(A/B/C).
    keys=[f'team_{stage}_{role}_{view}' for stage in ['small','large'] for view in 'ab' for role in 'ABC']
    ids=np.column_stack([s.index.get_indexer(t[k]) for k in keys]).reshape(len(t),2,2,3)
    present=ids>=0;missing=int((~present).sum())
    if missing and not allow_partial:raise ValueError(f'{missing} scalar references absent; wait for completed endpoints or explicitly use --allow-partial')
    safe=ids.clip(min=0)
    out={c:t[c].to_numpy() for c in t}
    out['endpoints_present12']=present.all(axis=(1,2,3))
    out['missing_endpoint_references']=(~present).sum(axis=(1,2,3))
    def values(metric):
        arr=pd.to_numeric(s[metric],errors='coerce').to_numpy(float) if metric in s else np.full(len(s),np.nan)
        vv=arr[safe];vv[~present]=np.nan
        return vv
    def bool_values(metric):
        ar=boolean(s[metric]).to_numpy(float) if metric in s else np.full(len(s),np.nan)
        vv=ar[safe];vv[~present]=np.nan
        return vv
    comp=bool_values('complete_evaluable')
    q=values('B8L2')
    qknown=np.isfinite(q)
    for stage,si in [('small',0),('large',1)]:
        for view,vi in [('a',0),('b',1)]:
            for role,ri in zip('ABC',range(3)):
                suffix=f'{stage}_{role}_{view}'
                out['Q_'+suffix]=q[:,si,vi,ri]
                out['complete_'+suffix]=comp[:,si,vi,ri]
                out['endpoint_present_'+suffix]=present[:,si,vi,ri]
    out['Q_common12']=qknown.all(axis=(1,2,3))
    out['complete12']=(comp==1).all(axis=(1,2,3))
    out['score_failure_fraction12']=np.where(present.all(axis=(1,2,3)),(~qknown).mean(axis=(1,2,3)),np.nan)
    out['incomplete_fraction12']=np.where(present.all(axis=(1,2,3)),(comp!=1).mean(axis=(1,2,3)),np.nan)
    for role,ri in zip('ABC',range(3)):
        valid=present[:,:,:,ri].all(axis=(1,2))
        out[f'{role}_new_score_failure_fraction']=np.where(valid,(qknown[:,0,:,ri]&~qknown[:,1,:,ri]).mean(axis=1),np.nan)
        out[f'{role}_recovered_score_fraction']=np.where(valid,(~qknown[:,0,:,ri]&qknown[:,1,:,ri]).mean(axis=1),np.nan)
        out[f'{role}_new_incomplete_fraction']=np.where(valid,((comp[:,0,:,ri]==1)&(comp[:,1,:,ri]!=1)).mean(axis=1),np.nan)
        out[f'{role}_recovered_complete_fraction']=np.where(valid,((comp[:,0,:,ri]!=1)&(comp[:,1,:,ri]==1)).mean(axis=1),np.nan)
    kinds=s.time_source_kinds.fillna('').astype(str).to_numpy() if 'time_source_kinds' in s else np.full(len(s),'')
    kk=kinds[safe].reshape(len(t),12)
    samekind=(kk==kk[:,[0]]).all(axis=1)&(kk[:,0]!='')&np.array(['|' not in k for k in kk[:,0]])
    samekind &= present.all(axis=(1,2,3))
    out['time_semantics']=np.where(samekind,kk[:,0],'not_common_single_semantics')
    timevalid=np.isfinite(values('recorded_time_total_seconds')).all(axis=(1,2,3))&samekind
    out['time_common12']=timevalid;out['QT_common12']=timevalid&out['Q_common12']
    for metric in METRICS:
        v=values(metric)
        valid=np.isfinite(v).all(axis=(1,2,3))
        if metric in ['recorded_time_total_seconds','source_time_total_seconds']:valid &= samekind
        out[f'{metric}_common12']=valid
        before,after=v[:,0,:,:],v[:,1,:,:]
        change=after-before
        within0=np.abs(before[:,:,1]-before[:,:,0]);within1=np.abs(after[:,:,1]-after[:,:,0])
        cross0=(np.abs(before[:,:,2]-before[:,:,0])+np.abs(before[:,:,2]-before[:,:,1]))/2
        cross1=(np.abs(after[:,:,2]-after[:,:,0])+np.abs(after[:,:,2]-after[:,:,1]))/2
        eff={'A_change':change[:,:,0],'B_change':change[:,:,1],'C_change':change[:,:,2],
          'net_C_minus_B_change':change[:,:,2]-change[:,:,1],
          'BA_change':(after[:,:,1]-after[:,:,0])-(before[:,:,1]-before[:,:,0]),
          'CA_change':(after[:,:,2]-after[:,:,0])-(before[:,:,2]-before[:,:,0]),
          'within_amplitude_change':within1-within0,'cross_amplitude_change':cross1-cross0,
          'extra_amplitude_change':(cross1-within1)-(cross0-within0)}
        for name,vv in eff.items():
            for view,j in [('a',0),('b',1)]:out[f'{metric}_{view}_{name}']=vv[:,j]
            out[f'{metric}_{name}']=np.where(valid,vv.mean(axis=1),np.nan)
        if metric=='B8L2':
            for role,j in zip('ABC',range(3)):
                out[f'{role}_Q_loss_gt5_fraction']=np.where(valid,(change[:,:,j]<-5).mean(axis=1),np.nan)
                out[f'{role}_Q_gain_gt5_fraction']=np.where(valid,(change[:,:,j]>5).mean(axis=1),np.nan)
            for eps in [0,2]:
                for name in ['C_change','B_change','net_C_minus_B_change','CA_change','BA_change']:
                    vv=eff[name];ss=np.where(vv>eps,1,np.where(vv<-eps,-1,0))
                    response=np.select([(ss[:,0]==0)&(ss[:,1]==0),(ss[:,0]==0)^(ss[:,1]==0),
                      (ss[:,0]==ss[:,1])&(ss[:,0]!=0),(ss[:,0]*ss[:,1]<0)],
                      ['both_near_zero','one_sided','both_same_nonzero','both_opposite'],'missing')
                    out[f'eps{eps}_{name}_crossview_state']=np.where(valid,response,'missing')
    f=t.study_type.eq('fixed_A_scale').to_numpy()&out['Q_common12']
    assert np.all(np.abs(out['B8L2_A_change'][f])<1e-10),'Fixed A changed quality despite exact same endpoints'
    return pd.DataFrame(out),missing

def summarize(z,out):
    # Multiple tags denote distinct questions about one exact transition.
    # A transition is unique inside each tag; tags are never pooled as samples.
    zz=z.assign(comparison=z.comparison_tags.str.split('|')).explode('comparison')
    key=['study_type','comparison','method','condition','ordinary_comparable',
      'source_role_key','target_role_key','source_class','target_class','pair_key','building','groups',
      'm_small','m_large','n_small','n_large']
    qrows=[]
    for metric in SUMMARY_METRICS:
        cs=[f'{metric}_{e}' for e in EFFECTS]
        df=zz[key+['path_transition_id',f'{metric}_common12']+cs].copy()
        df=df.rename(columns={f'{metric}_common12':'common_support',**{f'{metric}_{e}':e for e in EFFECTS}})
        g=df.groupby(key,dropna=False,observed=True)
        summ=g[EFFECTS].mean()
        summ['attempted_transitions']=g.size()
        summ['common_transitions']=g.common_support.sum()
        summ['C_change_p10']=g.C_change.quantile(.1)
        summ['C_change_p50']=g.C_change.quantile(.5)
        summ['C_change_p90']=g.C_change.quantile(.9)
        summ['net_change_p10']=g.net_C_minus_B_change.quantile(.1)
        summ['net_change_p90']=g.net_C_minus_B_change.quantile(.9)
        summ=summ.reset_index();summ.insert(0,'metric',metric);qrows.append(summ)
    pairconfig=pd.concat(qrows,ignore_index=True)
    write_csv(pairconfig,out/'PATH_PAIR_CONFIG_SUMMARY.csv.gz')
    pk=['metric','study_type','comparison','method','condition','ordinary_comparable',
      'source_role_key','target_role_key','pair_key','building','groups']
    p=pairconfig.groupby(pk,dropna=False,observed=True)[EFFECTS].mean().reset_index()
    ct=pairconfig.groupby(pk,dropna=False,observed=True).agg(configurations=('m_small','size'),
      attempted_transitions=('attempted_transitions','sum'),common_transitions=('common_transitions','sum')).reset_index()
    p=p.merge(ct,on=pk,validate='one_to_one');write_csv(p,out/'PATH_PAIR_SUMMARY.csv.gz')
    bk=[c for c in pk if c not in ['pair_key','groups']]
    b=p.groupby(bk,dropna=False,observed=True)[EFFECTS].mean().reset_index()
    bc=p.groupby(bk,dropna=False,observed=True).agg(pairs=('pair_key','nunique'),
      attempted_transitions=('attempted_transitions','sum'),common_transitions=('common_transitions','sum')).reset_index()
    b=b.merge(bc,on=bk,validate='one_to_one');write_csv(b,out/'PATH_BUILDING_SUMMARY.csv')
    gk=[c for c in bk if c!='building'];rows=[]
    for keyx,pp in p.groupby(gk,dropna=False,observed=True):
        match=np.ones(len(b),dtype=bool)
        rr=dict(zip(gk,keyx if isinstance(keyx,tuple) else (keyx,)))
        for k,v in rr.items():match&=b[k].eq(v).to_numpy()
        bb=b[match]
        rr.update(pairs=pp.pair_key.nunique(),buildings=pp.building.nunique(),
          attempted_transitions=int(pp.attempted_transitions.sum()),common_transitions=int(pp.common_transitions.sum()))
        for ef in EFFECTS:
            vv=pp[ef].dropna();rr[f'pair_equal__{ef}']=vv.mean();rr[f'building_equal__{ef}']=bb[ef].mean()
            rr[f'positive_pairs__{ef}']=int((vv>0).sum());rr[f'supported_pairs__{ef}']=len(vv)
            rr[f'positive_pair_fraction__{ef}']=(vv>0).mean() if len(vv) else np.nan
        rows.append(rr)
    write_csv(pd.DataFrame(rows),out/'PATH_OVERALL_RESULTS.csv')
    failcols=['score_failure_fraction12','incomplete_fraction12','Q_common12','time_common12','QT_common12']
    failcols += [c for c in zz if c.endswith(('_new_score_failure_fraction','_recovered_score_fraction','_new_incomplete_fraction','_recovered_complete_fraction','_Q_loss_gt5_fraction','_Q_gain_gt5_fraction'))]
    fs=zz.groupby(key,dropna=False,observed=True)[failcols].mean().reset_index()
    counts=zz.groupby(key,dropna=False,observed=True).size().rename('attempted_transitions').reset_index()
    write_csv(fs.merge(counts,on=key),out/'PATH_FAILURE_LOWTAIL_PAIR_CONFIG.csv.gz')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--design-dir',type=Path,required=True)
    ap.add_argument('--native',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--design-only',action='store_true');ap.add_argument('--allow-partial',action='store_true')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    t,coverage=design_transitions(a.design_dir)
    write_csv(t,a.out/'ANCHOR_PATH_TRANSITIONS.csv.gz')
    write_csv(coverage,a.out/'BACKGROUND_STAGE_CAPACITY.csv.gz')
    receipt={'version':VERSION,'new_fusion_calls':0,'new_team_selection':False,
      'transitions':len(t),'unique_physical_events':len(set(t.event_small)|set(t.event_large)),
      'fixed_A_transitions':int(t.study_type.eq('fixed_A_scale').sum()),
      'fixed_XYZ_transitions':int(t.study_type.eq('fixed_XYZ_background').sum()),
      'fixed_A_endpoint_check':'exact same team_key in both views; nominal A remapped from canonical event',
      'background_check':'exact XYZ, same m, nested D; supported stages only',
      'quality_support':'both stages x both views x ABC common numeric support',
      'time_support':'common finite recorded time with one identical provenance kind across 12 references',
      'weighting':'member-path mean within exact pair/role/n_small/n_large/m_small/m_large; equal configs within pair; equal pairs within building',
      'design_only':a.design_only,'partial_input':a.allow_partial}
    if not a.design_only:
        if a.native is None:raise ValueError('--native required unless --design-only')
        s=endpoint_frame(a.native);z,missing=metrics_for_paths(t,s,a.allow_partial)
        write_csv(z,a.out/'ANCHOR_PATH_EFFECTS.csv.gz')
        summarize(z,a.out)
        receipt.update(native_endpoints=len(s),missing_endpoint_references=missing,Q_common12=int(z.Q_common12.sum()),QT_common12=int(z.QT_common12.sum()))
    (a.out/'PATH_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
