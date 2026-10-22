"""Outcome-free actual joint-class replacement registration; no fusion calls."""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_k]='1'
import collections,gzip,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
V3=ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021'
COMP=V3/'composition'
TAX=V3/'taxonomy'
SEED='joint-exchange-directions-v1-20261022'
FEATURES=['q_history','q_downside','t_history','turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history']

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def h(*x):return digest([SEED,*x])
def team_key(pool,ws):return pool+'__'+digest(sorted(ws))[:20]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,df):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    b=df.to_csv(index=False).encode('utf-8-sig')
    with tmp.open('wb') as f:f.write(gzip.compress(b,compresslevel=5,mtime=0) if path.suffix=='.gz' else b);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def save(path,data):
    path=Path(path);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False));tmp.replace(path)
def counts(ws,labels):return collections.Counter(labels[w] for w in ws)
def vecstr(ws,labels):return '|'.join(f'{k}:{v}' for k,v in sorted(counts(ws,labels).items()))

def inputs():
    panels=pd.read_csv(COMP/'PANELS.csv',keep_default_na=False)
    labels=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz')
    labels=labels[labels.known & (labels.heldout_building!='ALL')].copy()
    centers=labels.groupby(['condition','heldout_building','selected_family','coarse_label'])[FEATURES].mean().reset_index()
    sizes=labels.groupby(['condition','heldout_building','coarse_label']).size().rename('historical_members').reset_index()
    centers=centers.merge(sizes,on=['condition','heldout_building','coarse_label'])
    write(HERE/'JOINT_TRAINING_CLASS_CENTERS.csv.gz',centers)
    return panels,labels,centers

def make_event(meta,A,B,C,labels,**extra):
    A,B,C=[tuple(sorted(t)) for t in [A,B,C]];aa,bb,cc=map(set,[A,B,C]);D=aa&bb
    assert len(A)==len(B)==len(C) and D==aa&cc
    assert counts(A,labels)==counts(B,labels) and counts(A,labels)!=counts(C,labels)
    keys=[team_key(meta['pool_id'],w) for w in [A,B,C]]
    d={k:meta[k] for k in ['pool_id','image','building','condition','layer','difficulty']}
    d.update(method_id='V3_JOINT_QT',tier='coarse',n=len(A),m_AB=len(A)-len(D),m_AC=len(A)-len(D),m_BC=len(A)-len(bb&cc),
             event_id=h('event',extra,keys)[:24],physical_triple_id=digest(sorted(keys))[:24],oriented_triple_id=digest(keys)[:24],
             team_A=keys[0],team_B=keys[1],team_C=keys[2],A_member_workers='|'.join(A),B_member_workers='|'.join(B),C_member_workers='|'.join(C),
             common_background='|'.join(sorted(D)),outgoing_block_X='|'.join(sorted(aa-D)),same_count_block_Y='|'.join(sorted(bb-D)),changed_count_block_Z='|'.join(sorted(cc-D)),
             A_counts=vecstr(A,labels),B_counts=vecstr(B,labels),C_counts=vecstr(C,labels),composition_turnover_AC=sum(abs(counts(A,labels)[k]-counts(C,labels)[k]) for k in set(labels.values()))//2,
             label_scope='target_building_excluded',selection_uses_target_endpoints=False,**extra)
    return d

def frozen_predictions(events,labels):
    """Replay only frozen class interactions, never read target endpoint outcomes."""
    fit=pd.concat([pd.read_csv(V3/'utility/cross_panel_LOBO'/c/'new_joint/FITS.csv.gz') for c in ['manual','semi']],ignore_index=True)
    fit=fit[fit.model.eq('class_coarse_interaction')]
    fmap={(r.condition,r.heldout_building,r.outcome):r for r in fit.itertuples()}
    origins={(c,b):g.set_index('worker_id').origin.to_dict() for (c,b),g in labels.groupby(['condition','heldout_building'])}
    out=[]
    for e in events:
        row=dict(event_id=e['event_id']);key=(e['condition'],e['building']);om=origins[key]
        for outcome in ['B8L2','log_total_time']:
            f=fmap.get((*key,outcome))
            if f is None:continue
            names=f.predictors.split('|');coef=json.loads(f.coefficient_json);pp={}
            for side in ['A','B','C']:
                cv={k:int(v) for k,v in (t.split(':') for t in e[side+'_counts'].split('|'))};ws=e[side+'_member_workers'].split('|');n=e['n']
                base={'source_new':sum(om[w]=='new' for w in ws)/n}
                base.update({'coarse_'+k:v/n for k,v in cv.items()})
                def value(name):
                    if name.startswith('invn_'):return 20/n*value(name[5:])
                    if name.startswith('product__'):
                        _,a,b=name.split('__');return base.get(a,0.)*base.get(b,0.)
                    return base.get(name,0.)
                pp[side]=float(sum(value(nm)*b for nm,b in zip(names,coef)))
            tag='Q' if outcome=='B8L2' else 'logtime'
            row.update({f'pred_{tag}_{a}{b}':pp[b]-pp[a] for a,b in [('A','B'),('A','C'),('B','C')]})
            row['trained_n_min']=int(f.train_n_min);row['trained_n_max']=int(f.train_n_max)
            row['outside_trained_n_range']=e['n']<f.train_n_min or e['n']>f.train_n_max
        if 'pred_Q_BC' in row and 'pred_logtime_BC' in row:
            row['pred_QT_both_improve_BC']=row['pred_Q_BC']>0 and row['pred_logtime_BC']<0
            row['pred_balanced_BC']=row['pred_Q_BC']-10*row['pred_logtime_BC']
        out.append(row)
    return pd.DataFrame(out)

def native():
    panels,labs,centers=inputs();events=[];capacities=[];teams={};domains=[]
    lookup={(c,b):g for (c,b),g in labs.groupby(['condition','heldout_building'])}
    c_lookup={(c,b):g.set_index('coarse_label') for (c,b),g in centers.groupby(['condition','heldout_building'])}
    for (pool,domain),group in panels.groupby(['pool_id','source_domain'],sort=True):
        meta=group.iloc[0].to_dict();fold=lookup[(meta['condition'],meta['building'])].set_index('worker_id');lm=fold.coarse_label.to_dict();cm=c_lookup[(meta['condition'],meta['building'])]
        universe=meta['domain_workers'].split('|');ws=sorted(set(universe)&lm.keys());unknown=sorted(set(universe)-lm.keys());U=len(ws);cap=counts(ws,lm)
        domains.append(dict(pool_id=pool,condition=meta['condition'],building=meta['building'],source_domain=domain,original_U=len(universe),known_U=U,known_workers='|'.join(ws),unknown_workers='|'.join(unknown)))
        for m in [4,6]:
            for src,dst in itertools.permutations(sorted(cap),2):
                nvals=sorted({n for n in [12,20,U-2*m] if n>=10 and n+2*m<=U})
                feasible=cap[src]>=2*m and cap[dst]>=m
                if not feasible or not nvals:
                    capacities.append(dict(pool_id=pool,condition=meta['condition'],building=meta['building'],source_domain=domain,U=U,m=m,source_class=src,target_class=dst,source_capacity=cap[src],target_capacity=cap[dst],status='insufficient_capacity',n='',theoretical_ordered_ABC=0,registered_ABC=0));continue
                dc=cm.loc[dst,FEATURES]-cm.loc[src,FEATURES]
                qt=('q_up' if dc.q_history>0 else 'q_down')+'__'+('faster' if dc.t_history<0 else 'slower')
                for n in nvals:
                    theory=math.comb(cap[src],m)*math.comb(cap[src]-m,m)*math.comb(cap[dst],m)*math.comb(U-3*m,n-m)
                    capacities.append(dict(pool_id=pool,condition=meta['condition'],building=meta['building'],source_domain=domain,U=U,m=m,source_class=src,target_class=dst,source_capacity=cap[src],target_capacity=cap[dst],status='registered',n=n,theoretical_ordered_ABC=str(theory),registered_ABC=2))
                for seed in range(2):
                    sid=h('member_path',pool,domain,m,src,dst,seed)
                    sw=sorted([w for w in ws if lm[w]==src],key=lambda w:h(sid,'source',w));tw=sorted([w for w in ws if lm[w]==dst],key=lambda w:h(sid,'target',w))
                    X,Y,Z=sw[:m],sw[m:2*m],tw[:m];rest=sorted(set(ws)-set(X+Y+Z),key=lambda w:h(sid,'background',w))
                    for n in nvals:
                        D=rest[:n-m];ev=make_event(meta,D+X,D+Y,D+Z,lm,stage='joint_native_pure',panel_id=f'{pool}__{domain}__m{m}__{src}_to_{dst}__s{seed}__n{n}',source_domain=domain+'_labelled',member_path=sid[:24],path_seed=seed,selected_family=str(fold.selected_family.iloc[0]),coarse_k=int(fold.coarse_k.iloc[0]),source_class=src,target_class=dst,training_QT_direction=qt,design_scope='whole_class_block',event_mode='pure_same_background',eligible_U=U)
                        for feature,val in dc.items():ev['class_center_delta_'+feature]=float(val)
                        events.append(ev)
                        for side,ww in zip('ABC',[D+X,D+Y,D+Z]):
                            key=ev['team_'+side];teams[key]={k:meta[k] for k in ['pool_id','image','building','condition','difficulty','layer']};teams[key].update(team_key=key,n=n,k=n,member_workers='|'.join(sorted(ww)))
    E=pd.DataFrame(events).drop_duplicates('event_id');P=frozen_predictions(E.to_dict('records'),labs);E=E.merge(P,on='event_id',validate='one_to_one')
    T=pd.DataFrame(teams.values()).sort_values('team_key');idx=pd.read_csv(COMP/'delivery/ENDPOINT_KEY_INDEX.csv.gz');keycol='team_key';cached=set(idx[keycol]);T['cached']=T.team_key.isin(cached)
    write(HERE/'NATIVE_DOMAINS.csv',pd.DataFrame(domains));write(HERE/'NATIVE_CAPACITY.csv.gz',pd.DataFrame(capacities));write(HERE/'NATIVE_EVENTS_REGISTERED.csv.gz',E);write(HERE/'NATIVE_ALL_TEAMS.csv.gz',T);write(HERE/'NATIVE_TEAM_REQUEST.csv.gz',T[~T.cached])
    summary=E.groupby(['condition','source_domain','m_AB']).agg(events=('event_id','size'),physical_triples=('physical_triple_id','nunique'),pools=('pool_id','nunique'),buildings=('building','nunique'),n_min=('n','min'),n_max=('n','max')).reset_index();write(HERE/'NATIVE_REGISTRATION_SUMMARY.csv',summary)
    receipt=dict(stage='before_any_new_target_endpoints',seed=SEED,events=len(E),physical_triples=E.physical_triple_id.nunique(),unique_teams=len(T),cached_teams=int(T.cached.sum()),new_endpoint_requests=int((~T.cached).sum()),label_sha256=sha(TAX/'JOINT_LABELS_LOBO.csv.gz'),panel_sha256=sha(COMP/'PANELS.csv'),request_sha256=sha(HERE/'NATIVE_TEAM_REQUEST.csv.gz'),events_sha256=sha(HERE/'NATIVE_EVENTS_REGISTERED.csv.gz'),target_endpoint_outcomes_used=False,native_calls=0,all_class_directions_kept=True,paths_per_feasible_cell=2,all_concrete_members_exhaustive=False)
    save(HERE/'NATIVE_DESIGN_FREEZE.json',receipt);print(json.dumps(receipt,ensure_ascii=False));print(summary.to_string(index=False))

if __name__=='__main__':native()
