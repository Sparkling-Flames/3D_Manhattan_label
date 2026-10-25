#!/usr/bin/env python3
"""Independent additional base orders versus the frozen eight policy bases.

Only analysis is implemented here. Every order is the frozen stable binary
partition of its natural base; this code never changes classes or fusion.
The path resample keeps k, natural, and all four policies paired. Buildings
are resampled separately with observed paths fixed.
"""
from pathlib import Path
import argparse, hashlib, json, os, warnings
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[name]='1'
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore', category=RuntimeWarning)

META=['pool_id','image','building','condition','layer','difficulty','pool_n']
POLICIES=['joint_highq_first','structure_moreturn_first','joint_fast_first','structure_dominant_first']
PHASES=['early_3_to_half','low_3_to_6','late_20_to_Nminus1','full']
COMPONENTS=['B8_floor_block','B8_direction_block','B8_height_block','iou_2d','S_bottom_deg','dir','Hmean']
FIELDS=['B8L2','D10','score_failure_nonpolicy','incomplete_nonpolicy','nodes','floor_turn5_n',
        'source_time_total_seconds','labor_kind_code']+COMPONENTS
METRICS=['paired_Q_delta','paired_D10_delta','Q_p10_delta_common','Q_sd_delta_common_ddof1',
         'failure_delta','incomplete_delta','Q_loss_gt5_rate','Q80_reached_delta','Q90_reached_delta',
         'labor_ratio_legal','QT_paired_Q_delta','nodes_delta','turn5_delta']+[c+'_delta' for c in COMPONENTS]

def seed_for(master,*parts):
    return int.from_bytes(hashlib.sha256(json.dumps([master,*parts],ensure_ascii=True,
        separators=(',',':')).encode()).digest()[:8],'little')

def save(frame,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(path,index=False,compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None)

def num(s):
    return pd.to_numeric(s.replace({'True':1,'False':0,'true':1,'false':0}),errors='coerce')

def time_kind(x):
    if pd.isna(x):return ''
    s=str(x)
    if s.startswith('['):
        try:
            v=json.loads(s)
            return str(v[0]) if isinstance(v,list) and len(v)==1 else ''
        except ValueError:return ''
    return '' if '|' in s or ',' in s or not s else s

def enrich(d,scalars):
    wanted=['team_key','source_time_known_n','time_source_kinds','time_source_kinds_json']+COMPONENTS
    # A header read makes this work with both canonical CSVs and native shards.
    files=scalars if isinstance(scalars,list) else [scalars]
    tables=[]
    for path in files:
        columns=pd.read_csv(path,nrows=0).columns
        tables.append(pd.read_csv(path,usecols=[c for c in wanted if c in columns],low_memory=False))
    e=pd.concat(tables,ignore_index=True).drop_duplicates('team_key',keep='first')
    add=[c for c in e if c=='team_key' or c not in d]
    d=d.merge(e[add],on='team_key',how='left',validate='many_to_one')
    kindcol='time_source_kinds' if 'time_source_kinds' in d else 'time_source_kinds_json'
    d['labor_kind']=d[kindcol].map(time_kind) if kindcol in d else ''
    for f in FIELDS:
        if f not in d:d[f]=np.nan
        if f!='labor_kind_code':d[f]=num(d[f])
    known=num(d['source_time_known_n']) if 'source_time_known_n' in d else np.nan
    ok=(known==d.k)&(d.source_time_total_seconds>0)&d.labor_kind.ne('')
    d.loc[~ok,'source_time_total_seconds']=np.nan
    return d

def q10(a):
    s=np.sort(a,axis=1);n=np.isfinite(a).sum(axis=1)
    rank=np.maximum(n-1,0)*.1;lo=np.floor(rank).astype(int);hi=np.ceil(rank).astype(int)
    low=np.take_along_axis(s,lo[:,None,:],axis=1)[:,0,:]
    high=np.take_along_axis(s,hi[:,None,:],axis=1)[:,0,:]
    return np.where(n>0,low+(high-low)*(rank-lo),np.nan)

def stats(n,p):
    good=np.isfinite(n['B8L2'])&np.isfinite(p['B8L2'])
    nq=np.where(good,n['B8L2'],np.nan);pq=np.where(good,p['B8L2'],np.nan)
    dq=pq-nq
    tg=(n['source_time_total_seconds']>0)&(p['source_time_total_seconds']>0)&(n['labor_kind_code']==p['labor_kind_code'])
    ratio=np.where(tg,p['source_time_total_seconds']/n['source_time_total_seconds'],np.nan)
    out=[np.nanmean(dq,axis=1),np.nanmean(np.where(good,p['D10']-n['D10'],np.nan),axis=1),
         q10(pq)-q10(nq),np.nanstd(pq,axis=1,ddof=1)-np.nanstd(nq,axis=1,ddof=1),
         np.mean(p['score_failure_nonpolicy']-n['score_failure_nonpolicy'],axis=1),
         np.mean(p['incomplete_nonpolicy']-n['incomplete_nonpolicy'],axis=1),
         np.nanmean(np.where(good,dq< -5,np.nan),axis=1),
         np.mean((p['B8L2']>=80).astype(float)-(n['B8L2']>=80).astype(float),axis=1),
         np.mean((p['B8L2']>=90).astype(float)-(n['B8L2']>=90).astype(float),axis=1),
         np.nanmean(np.where(good,ratio,np.nan),axis=1),
         np.nanmean(np.where(tg,dq,np.nan),axis=1),
         np.nanmean(p['nodes']-n['nodes'],axis=1),
         np.nanmean(p['floor_turn5_n']-n['floor_turn5_n'],axis=1)]
    out += [np.nanmean(np.where(good,p[c]-n[c],np.nan),axis=1) for c in COMPONENTS]
    return np.stack(out,axis=-1)

def matrices(g,bases,ks):
    assert not g.duplicated(['base_path_id','k']).any()
    return {c:g.pivot(index='base_path_id',columns='k',values=c).reindex(index=bases,columns=ks).to_numpy(float) for c in FIELDS}

def phases(k,N):
    return [(k>=3)&(k<=N//2),(k>=3)&(k<=min(6,N)),(k>=20)&(k<N),k==N]

def summarize(point,boot,meta,B,seed,batch,policy):
    out=[];build=[]
    for difficulty,g in [('全部',meta)]+list(meta.groupby('difficulty')):
        pools=g.pool_id.tolist();xx=np.stack([point[p] for p in pools]);zz=np.stack([boot[p] for p in pools])
        buildings=sorted(g.building.unique());bxx=[];bzz=[];sums=[];counts=[]
        for b in buildings:
            ids=np.flatnonzero(g.building.to_numpy()==b)
            bxx.append(np.nanmean(xx[ids],axis=0));bzz.append(np.nanmean(zz[ids],axis=0))
            sums.append(np.nansum(xx[ids],axis=0));counts.append(np.isfinite(xx[ids]).sum(axis=0))
            for j,phase in enumerate(PHASES):
                for c,m in enumerate(METRICS):
                    vals=xx[ids,j,c]
                    build.append(dict(batch=batch,policy=policy,difficulty=difficulty,building=b,
                        phase=phase,metric=m,value=np.nanmean(vals),images=np.isfinite(vals).sum()))
        bxx=np.array(bxx);bzz=np.array(bzz);sums=np.array(sums);counts=np.array(counts)
        weights=np.random.default_rng(seed_for(seed,'buildings',difficulty,batch)).multinomial(len(buildings),
                    np.repeat(1/len(buildings),len(buildings)),size=B)
        numr=weights@sums.reshape(len(buildings),-1);den=weights@counts.reshape(len(buildings),-1)
        bi=np.divide(numr,den,out=np.full_like(numr,np.nan),where=den>0).reshape((B,)+xx.shape[1:])
        numr=weights@np.nan_to_num(bxx).reshape(len(buildings),-1);den=weights@np.isfinite(bxx).reshape(len(buildings),-1)
        bb=np.divide(numr,den,out=np.full_like(numr,np.nan),where=den>0).reshape((B,)+xx.shape[1:])
        for weighting,estimate,pathdraw,bldraw in [('image_equal',np.nanmean(xx,axis=0),np.nanmean(zz,axis=0),bi),
                ('building_equal',np.nanmean(bxx,axis=0),np.nanmean(bzz,axis=0),bb)]:
            for j,phase in enumerate(PHASES):
                for c,m in enumerate(METRICS):
                    vals=xx[:,j,c];pdra=pathdraw[:,j,c];bdra=bldraw[:,j,c]
                    out.append(dict(batch=batch,policy=policy,difficulty=difficulty,phase=phase,metric=m,
                        weighting=weighting,estimate=estimate[j,c],path_MCSE=np.nanstd(pdra,ddof=1),
                        path_lo=np.nanquantile(pdra,.025),path_hi=np.nanquantile(pdra,.975),
                        building_lo=np.nanquantile(bdra,.025),building_hi=np.nanquantile(bdra,.975),
                        images=np.isfinite(vals).sum(),candidate_images=len(g),buildings=len(buildings),
                        positive_images=np.sum(vals>1e-9),negative_images=np.sum(vals< -1e-9),
                        nearzero_images=np.sum(np.abs(vals)<=1e-9),valid_path_bootstraps=np.isfinite(pdra).sum(),
                        bootstrap_replicates=B))
    return out,build

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--old',type=Path,required=True);ap.add_argument('--new',type=Path,required=True)
    ap.add_argument('--old-endpoints',type=Path,required=True);ap.add_argument('--new-endpoints',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--replicates',type=int,default=1000)
    ap.add_argument('--seed',type=int,default=2026102511);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    old=enrich(pd.read_csv(a.old,low_memory=False),a.old_endpoints);old['source_batch']='old8'
    new=enrich(pd.read_csv(a.new,low_memory=False),[a.old_endpoints,a.new_endpoints]);new['source_batch']='new8'
    d=pd.concat([old,new],ignore_index=True)
    d['labor_kind_code']=pd.Categorical(d.labor_kind).codes
    m=old[META].drop_duplicates('pool_id');m=m[(m.layer=='ordinary_manual')&(m.pool_n>=20)]
    common=set(m.pool_id)
    for policy in POLICIES:
        common &= set(old.loc[old.policy.eq(policy),'pool_id']) & set(new.loc[new.policy.eq(policy),'pool_id'])
    m=m[m.pool_id.isin(common)].sort_values('pool_id').reset_index(drop=True)
    save(m,a.out/'POLICY_COMMON_IMAGES.csv')
    summaries=[];buildingrows=[];imrows=[];krows=[];events=[];seeds=[]
    for batch in ['old8','new8','combined16']:
        use=d[d.pool_id.isin(common)]
        if batch!='combined16':use=use[use.source_batch==batch]
        ps={p:{} for p in POLICIES};bs={p:{} for p in POLICIES}
        for ix,r in m.iterrows():
            pid=r.pool_id;g=use[use.pool_id==pid];N=int(r.pool_n);ks=np.arange(1,N+1)
            bases=sorted(set.intersection(*[set(g.loc[g.policy.eq(p),'base_path_id']) for p in POLICIES]))
            expected=16 if batch=='combined16' else 8
            assert len(bases)==expected,(pid,batch,len(bases))
            ng=g[g.policy.eq('natural_random')&g.base_path_id.isin(bases)]
            n=matrices(ng,bases,ks)
            seed=seed_for(a.seed,'paired_base',pid,batch)
            indices=np.random.default_rng(seed).integers(len(bases),size=(a.replicates,len(bases)))
            seeds.append(dict(batch=batch,pool_id=pid,paths=len(bases),seed=str(seed)))
            masks=phases(ks,N)
            for policy in POLICIES:
                pg=g[g.policy.eq(policy)&g.base_path_id.isin(bases)];p=matrices(pg,bases,ks)
                v=stats({c:x[None] for c,x in n.items()},{c:x[None] for c,x in p.items()})[0]
                z=stats({c:x[indices] for c,x in n.items()},{c:x[indices] for c,x in p.items()})
                pv=np.stack([np.nanmean(v[mask],axis=0) for mask in masks])
                bz=np.stack([np.nanmean(z[:,mask],axis=1) for mask in masks],axis=1).astype(np.float32)
                ps[policy][pid]=pv;bs[policy][pid]=bz
                good=np.isfinite(n['B8L2'])&np.isfinite(p['B8L2'])
                for j,phase in enumerate(PHASES):
                    imrows.append(dict(**r.to_dict(),batch=batch,policy=policy,phase=phase,
                        base_paths=len(bases),attempted_prefixes=int(len(bases)*masks[j].sum()),
                        both_Q_prefixes=int(good[:,masks[j]].sum()),valid_k=int(np.isfinite(v[masks[j],0]).sum()),
                        **dict(zip(METRICS,pv[j]))))
                for j,k in enumerate(ks):
                    krows.append(dict(**r.to_dict(),batch=batch,policy=policy,k=int(k),base_paths=len(bases),
                        both_Q_paths=int(good[:,j].sum()),**dict(zip(METRICS,v[j]))))
                if batch!='combined16':
                    cols=['pool_id','base_path_id','k','team_key','B8L2','D10','score_failure_nonpolicy','incomplete_nonpolicy',
                          'source_time_total_seconds','labor_kind']
                    e=ng[cols].merge(pg[cols],on=['pool_id','base_path_id','k'],suffixes=('_natural','_policy'),validate='one_to_one')
                    e.insert(0,'batch',batch);e.insert(1,'policy',policy);events.append(e)
            if ix%25==0:print('policy',batch,ix+1,'/',len(m),flush=True)
        for policy in POLICIES:
            s,b=summarize(ps[policy],bs[policy],m,a.replicates,a.seed,batch,policy);summaries.extend(s);buildingrows.extend(b)
        del ps,bs
    image=pd.DataFrame(imrows);summary=pd.DataFrame(summaries)
    save(image,a.out/'POLICY_IMAGE_PHASE_COMPARISON.csv');save(pd.DataFrame(krows),a.out/'POLICY_IMAGE_K_COMPARISON.csv.gz')
    save(summary,a.out/'POLICY_PRECISION_SUMMARY.csv');save(pd.DataFrame(buildingrows),a.out/'POLICY_BUILDING_PHASES.csv')
    save(pd.concat(events,ignore_index=True),a.out/'POLICY_COMMON_PAIRED_EVENTS.csv.gz');save(pd.DataFrame(seeds),a.out/'POLICY_BOOTSTRAP_SEEDS.csv')
    keys=['pool_id','policy','phase'];wide=image[image.batch=='old8'][keys+META[1:]+METRICS].merge(
        image[image.batch=='new8'][keys+METRICS],on=keys,suffixes=('_old','_new'),validate='one_to_one')
    for metric in METRICS:wide[metric+'_new_minus_old']=wide[metric+'_new']-wide[metric+'_old']
    save(wide,a.out/'POLICY_INDEPENDENT_BATCH_AGREEMENT.csv')
    rec=dict(source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',new_analysis=True,new_classification=False,
        common_images=len(m),buildings=int(m.building.nunique()),old_bases=8,new_independent_bases=8,
        combined_bases=16,seed=a.seed,replicates=a.replicates,phase=PHASES,policies=POLICIES,
        Q_support='same pool, same k, natural and priority both scoreable',failure_support='all paired attempts except deferred k2',
        aggregation='path mean at k, equal k within phase, then image/building equal; P10/SD within-image common Q paths',
        time='all members known positive, single source semantic kind in both teams and same kind; Q/T common support',
        intervals='separate whole-base and whole-building percentile95; pointwise not simultaneous',
        sources=[str(a.old),str(a.new),str(a.old_endpoints),str(a.new_endpoints)])
    (a.out/'POLICY_ANALYSIS_RECEIPT.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rec,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
