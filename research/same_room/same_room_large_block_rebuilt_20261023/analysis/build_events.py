"""Join the preregistered strict ABC design to every native endpoint.

This module never selects or generates a team. All missing and failure states
are retained. Quality repetition uses all six endpoints on common support.
"""
from __future__ import annotations
import argparse, gzip, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

VERSION = 'SRLB_REBUILT_20261023_v1'
METRICS = ['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','S_bottom_deg','dir','Hmean','Hcenter',
 'height_mean_ratio','iou_2d','IoU3D100','omission','extension',
 'ref_node_recall_5','ref_edge_recall_5','diag_corner_recall_05',
 'diag_wall_coverage_05','geometry_area_h2','height_mean_h',
 'top_y_mean_px','bottom_y_mean_px','centroid_x_h','centroid_z_h',
 'reference_node_shortfall','identity_groups_n','minimum_support',
 'recorded_time_total_seconds']

def boolean(x):
    return x.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])

def write_csv(df, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if str(path).endswith('.gz'):
        with gzip.GzipFile(filename='',mode='wb',fileobj=path.open('wb'),mtime=0) as f:
            f.write(df.to_csv(index=False).encode())
    else: df.to_csv(path,index=False)

def endpoint_frame(native):
    native=Path(native)
    if native.is_file():return pd.read_csv(native,low_memory=False)
    files=sorted(native.glob('parts/*/*.scalars.csv.gz'))
    if not files: raise ValueError('No complete endpoint scalar files found')
    return pd.concat([pd.read_csv(p,low_memory=False) for p in files],ignore_index=True)

def main(design,native,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(design,keep_default_na=False)
    if d.event_id.duplicated().any():raise ValueError('Duplicate exact ABC events')
    s=endpoint_frame(native)
    if s.team_key.duplicated().any():raise ValueError('Duplicate native endpoint key')
    s=s.set_index('team_key',drop=False)
    roles=['A','B','C']; views=['a','b']
    ids={v:{r:s.index.get_indexer(d[f'team_{r}_{v}']) for r in roles} for v in views}
    missing=sum(int((ii<0).sum()) for rr in ids.values() for ii in rr.values())
    if missing:raise ValueError(f'{missing} endpoint references missing; do not manufacture failed outcomes')
    outcols={c:d[c].to_numpy() for c in d.columns}
    def values(metric,kind='numeric'):
        if metric not in s:
            arr=np.full(len(s),np.nan) if kind=='numeric' else np.full(len(s),'')
        elif kind=='numeric':arr=pd.to_numeric(s[metric],errors='coerce').to_numpy(float)
        elif kind=='bool':arr=boolean(s[metric]).to_numpy()
        else:arr=s[metric].fillna('').astype(str).to_numpy()
        return {v:np.column_stack([arr[ids[v][r]] for r in roles]) for v in views}
    q=values('B8L2'); complete=values('complete_evaluable','bool')
    q6=np.all(np.isfinite(q['a']),axis=1)&np.all(np.isfinite(q['b']),axis=1)
    outcols['Q_common6']=q6
    outcols['complete6']=np.all(complete['a'],axis=1)&np.all(complete['b'],axis=1)
    for v in views:
        for j,r in enumerate(roles):
            outcols[f'Q_{r}_{v}']=q[v][:,j]
            outcols[f'complete_{r}_{v}']=complete[v][:,j]
    outcols['attempted_endpoints']=np.full(len(d),6)
    outcols['score_failure_fraction']=(~np.isfinite(np.column_stack([q['a'],q['b']]))).mean(axis=1)
    outcols['incomplete_fraction']=(~np.column_stack([complete['a'],complete['b']])).mean(axis=1)
    for r,j in [('B',1),('C',2)]:
        outcols[f'new_incomplete_{r}A']=np.column_stack([
            complete[v][:,0]&~complete[v][:,j] for v in views]).mean(axis=1)
        outcols[f'recovered_complete_{r}A']=np.column_stack([
            ~complete[v][:,0]&complete[v][:,j] for v in views]).mean(axis=1)
        outcols[f'new_score_failure_{r}A']=np.column_stack([
            np.isfinite(q[v][:,0])&~np.isfinite(q[v][:,j]) for v in views]).mean(axis=1)
        outcols[f'recovered_score_{r}A']=np.column_stack([
            ~np.isfinite(q[v][:,0])&np.isfinite(q[v][:,j]) for v in views]).mean(axis=1)
    for metric in METRICS:
        vv=values(metric)
        valid=np.all(np.isfinite(vv['a']),axis=1)&np.all(np.isfinite(vv['b']),axis=1)
        within=[];cross=[];effects={k:[] for k in ['BA','CA','CB']}
        for v in views:
            x=vv[v];delta={'BA':x[:,1]-x[:,0],'CA':x[:,2]-x[:,0],'CB':x[:,2]-x[:,1]}
            for k,z in delta.items():
                outcols[f'{metric}_{v}_{k}']=z;effects[k].append(z)
            within.append(np.abs(delta['BA']))
            cross.append((np.abs(delta['CA'])+np.abs(delta['CB']))/2)
        for k,arr in [('within',within),('cross',cross),*effects.items()]:
            outcols[f'{metric}_{k}']=np.where(valid,np.column_stack(arr).mean(axis=1),np.nan)
        outcols[f'{metric}_extra']=outcols[f'{metric}_cross']-outcols[f'{metric}_within']
        outcols[f'{metric}_CS']=(outcols[f'{metric}_CA']+outcols[f'{metric}_CB'])/2
    t=values('recorded_time_total_seconds'); ts=values('time_source_kinds','str')
    tvalid=np.all(np.column_stack([t['a'],t['b']])>0,axis=1)
    sem=np.column_stack([ts['a'],ts['b']])
    same_semantics=np.all(sem==sem[:,[0]],axis=1)&(sem[:,0]!='')
    same_semantics &= np.array(['|' not in k for k in sem[:,0]])
    t6=tvalid&same_semantics
    outcols['time_common6']=t6;outcols['QT_common6']=t6&q6
    outcols['time_semantics']=np.where(t6,sem[:,0],'not_common_complete_single_semantics')
    for name in list(outcols):
        if name.startswith('recorded_time_total_seconds_'):
            outcols[name]=np.where(t6,outcols[name],np.nan)
    for k,j,l in [('BA',1,0),('CA',2,0),('CB',2,1)]:
        rat=np.column_stack([t[v][:,j]/t[v][:,l] for v in views])
        outcols['time_ratio_'+k]=np.where(t6,rat.mean(axis=1),np.nan)
        outcols['time_logratio_'+k]=np.where(t6,np.log(rat).mean(axis=1),np.nan)
        outcols['QT_Q_'+k]=np.where(t6&q6,outcols['B8L2_'+k],np.nan)
        outcols['QT_time_ratio_'+k]=np.where(t6&q6,rat.mean(axis=1),np.nan)
        outcols['QT_time_logratio_'+k]=np.where(t6&q6,np.log(rat).mean(axis=1),np.nan)
        # A useful supplementary comparison may retain four complete endpoints
        # even when the third arm mixes time semantics. Its support is explicit
        # and is never substituted for the all-six matched magnitude comparison.
        t4=np.column_stack([t[v][:,jj] for v in views for jj in [j,l]])
        sem4=np.column_stack([ts[v][:,jj] for v in views for jj in [j,l]])
        good4=np.all(t4>0,axis=1)&np.all(sem4==sem4[:,[0]],axis=1)&(sem4[:,0]!='')
        good4 &= np.array(['|' not in kind for kind in sem4[:,0]])
        q4=np.all(np.isfinite(np.column_stack([q[v][:,jj] for v in views for jj in [j,l]])),axis=1)
        outcols['QT4_common_'+k]=good4&q4
        outcols['QT4_Q_'+k]=np.where(good4&q4,np.column_stack([q[v][:,j]-q[v][:,l] for v in views]).mean(axis=1),np.nan)
        outcols['QT4_time_ratio_'+k]=np.where(good4&q4,rat.mean(axis=1),np.nan)
        outcols['QT4_time_logratio_'+k]=np.where(good4&q4,np.log(rat).mean(axis=1),np.nan)
    # Pair repetition: two-sided selection is kept separate from source-only selection.
    for eps in [0.,2.]:
        tag='eps'+str(int(eps))
        for k in ['BA','CA','CB']:
            a=outcols['B8L2_a_'+k];b=outcols['B8L2_b_'+k]
            sa=np.where(a>eps,1,np.where(a< -eps,-1,0));sb=np.where(b>eps,1,np.where(b< -eps,-1,0))
            states={'both_near_zero':(sa==0)&(sb==0),
                'same_nonzero':(sa==sb)&(sa!=0),'both_gain':(sa==1)&(sb==1),
                'both_loss':(sa==-1)&(sb==-1),'opposite':sa*sb==-1,
                'one_response':(sa==0)^(sb==0),'sign_agree_including_zero':sa==sb,
                'both_response':(sa!=0)&(sb!=0)}
            for name,mask in states.items():outcols[f'{tag}_{k}_{name}']=np.where(q6,mask.astype(float),np.nan)
            # Symmetric source orientation; count only the source trigger after common support.
            outcols[f'{tag}_{k}_source_trigger_n']=np.where(q6,(sa!=0).astype(int)+(sb!=0).astype(int),0)
            outcols[f'{tag}_{k}_source_same_n']=np.where(q6,2*states['same_nonzero'].astype(int),0)
            outcols[f'{tag}_{k}_source_opposite_n']=np.where(q6,2*states['opposite'].astype(int),0)
    for k in ['BA','CA','CB']:
        a=outcols['B8L2_a_'+k];b=outcols['B8L2_b_'+k]
        outcols[f'{k}_loss_gt5_fraction']=np.where(q6,((a< -5).astype(float)+(b< -5).astype(float))/2,np.nan)
        outcols[f'{k}_gain_gt5_fraction']=np.where(q6,((a>5).astype(float)+(b>5).astype(float))/2,np.nan)
        outcols[f'{k}_any_loss_gt5']=np.where(q6,((a< -5)|(b< -5)).astype(float),np.nan)
        ta=outcols['fusion_turn_n_a_'+k];tb=outcols['fusion_turn_n_b_'+k]
        st=np.isfinite(ta)&np.isfinite(tb)&q6
        outcols[f'{k}_same_nonzero_turn_step']=np.where(st,((ta==tb)&(ta!=0)).astype(float),np.nan)
        outcols[f'{k}_same_nonzero_turn_q_opposite']=np.where(st,((ta==tb)&(ta!=0)&(a*b<0)&(np.abs(a)>2)&(np.abs(b)>2)).astype(float),np.nan)
        outcols[f'{k}_zero_turn_q_opposite']=np.where(st,((ta==0)&(tb==0)&(a*b<0)&(np.abs(a)>2)&(np.abs(b)>2)).astype(float),np.nan)
    e=pd.DataFrame(outcols)
    e['D_empty']=e.D_members.fillna('').eq('')
    e['replacement_fraction']=pd.to_numeric(e.m)/pd.to_numeric(e.n)
    e['ratio_band']=np.select([e.m==e.n,2*e.m>e.n,2*e.m==e.n],['all','more_than_half','half'],default='less_than_half')
    e['difficulty_pair']=e.difficulty_a.astype(str)+' / '+e.difficulty_b.astype(str)
    e['history_Q_block_range']=e[['q_X','q_Y','q_Z']].apply(pd.to_numeric,errors='coerce').max(axis=1)-e[['q_X','q_Y','q_Z']].apply(pd.to_numeric,errors='coerce').min(axis=1)
    e.loc[e[['q_X','q_Y','q_Z']].apply(pd.to_numeric,errors='coerce').isna().any(axis=1),'history_Q_block_range']=np.nan
    # Exact known-count fields, when supplied, determine full historical support.
    for r in ['X','Y','Z']:
        for name in [f'q_{r}_known_n',f'q_known_n_{r}']:
            if name in e:e.loc[pd.to_numeric(e[name],errors='coerce')<e.m,'history_Q_block_range']=np.nan
    e['analysis_version']=VERSION
    write_csv(e,out/'EVENT_Q_STRUCTURE_EFFECTS.csv.gz')
    statuscols=['event_id','pair_key','method','condition','building','image_a','image_b','n','m',
      'Q_common6','complete6','time_common6','QT_common6','score_failure_fraction','incomplete_fraction']
    statuscols += [f'team_{r}_{v}' for v in views for r in roles]
    statuscols += [f'complete_{r}_{v}' for v in views for r in roles]
    write_csv(e[statuscols],out/'EVENT_ENDPOINT_STATUS.csv.gz')
    receipt={'version':VERSION,'design_sha256':hashlib.sha256(Path(design).read_bytes()).hexdigest(),
      'events':len(e),'unique_endpoints':len(s),'all_endpoint_references':6*len(e),'missing_references':missing,
      'common_six_quality_events':int(q6.sum()),'complete_six_events':int(e.complete6.sum()),
      'common_six_time_events':int(t6.sum()),'joint_quality_time_events':int((t6&q6).sum()),
      'Q_unavailable_endpoints':int(s.B8L2.isna().sum()),'endpoint_rows_read_to_end':len(s),
      'fields':list(e.columns),'fusion_calls_in_this_script':0}
    (out/'EVENT_JOIN_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k!='fields'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--design',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.design,a.native,a.out)
