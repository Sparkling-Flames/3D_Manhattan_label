"""Timing repeatability of exact replaced blocks, separated by log semantics.

Times are the frozen snapshot's own values, never imputed from another field.
Unchanged background times cancel; this is a block labor difference, not a
whole-team delivery-time estimate and not a conversion between logging modes.
"""
from pathlib import Path
import argparse,gzip,json,math,collections
import numpy as np
import pandas as pd
from functools import lru_cache
from analyze_exact_changes import read_pool, finite, state_rates, analysis_subsets


def states(a,b,eps):
    x=np.where(a>eps,1,np.where(a < -eps,-1,0));y=np.where(b>eps,1,np.where(b < -eps,-1,0))
    active=(x!=0).sum()+(y!=0).sum()
    same=((x==y)&(x!=0)).sum()
    return {'both_within_5pct':float(np.mean((x==0)&(y==0))),
            'both_faster':float(np.mean((x<0)&(y<0))),'both_slower':float(np.mean((x>0)&(y>0))),
            'opposite':float(np.mean(x*y<0)),'one_within_5pct':float(np.mean((x==0)^(y==0))),
            'source_trigger_trials':int(active),'source_trigger_same':2*same/active if active else np.nan}


def main(repo,design,out,native=None):
    out.mkdir(parents=True,exist_ok=True)
    with gzip.open(repo/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz','rt') as f: obj=json.load(f)
    pools={p['pool_id']:p for p in obj['images']}
    panels=pd.read_csv(design/'PANELS.csv');links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz')
    linked={k:g.sort_values('selected_mask') for k,g in links.groupby('panel_id')}
    @lru_cache(maxsize=3)
    def native_pool(pid):
        return read_pool(native,pid) if native is not None else {}
    rows=[];availability=[]
    for pid,pool in pools.items():
        if pool['meta']['condition']!='manual':continue
        for r in pool['records']:
            availability.append({'pool_id':pid,'image':pool['meta']['image'],'image_id':pool['meta']['image_id'],
               'reference_id':pool['meta']['reference_id'],'worker_id':r['worker_id'],'object_id':r['object_id'],
               'origin':r['origin'],'time_source_kind':r.get('time_source_kind'),
               'snapshot_source_time_seconds':r.get('source_time_seconds'),'snapshot_target_time_seconds':r.get('target_time_seconds'),
               'source_identity':'frozen INPUT_SNAPSHOT record; not replaced by profile record_index join'})
    pd.DataFrame(availability).to_csv(out/'TIMING_INPUT_RECORDS.csv.gz',index=False)
    for p in panels.itertuples():
        g=linked[p.panel_id];cand=p.candidates.split('|');mask=g.selected_mask.to_numpy(int);h=g.hi_selected.to_numpy(int)
        ii,jj=np.triu_indices(len(g),1);rev=h[jj]<h[ii];i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
        removed=mask[i]&~mask[j];added=mask[j]&~mask[i]
        m=np.array([int(x).bit_count() for x in removed]);r=h[j]-h[i]
        rosters=[{x['worker_id']:x for x in pools[pid]['records']} for pid in (p.pool_id_a,p.pool_id_b)]
        unique_masks=sorted(set(removed)|set(added));stats={}
        for bits in unique_masks:
            workers=[w for n,w in enumerate(cand) if bits&(1<<n)]
            rr=[[roster[w] for w in workers] for roster in rosters]
            kinds={str(x.get('time_source_kind','unknown')) for side in rr for x in side}
            kind=next(iter(kinds)) if len(kinds)==1 else 'mixed_semantics'
            ts=[]
            for side in rr:
                vals=[x.get('source_time_seconds') for x in side]
                good=all(v is not None and np.isfinite(v) and v>=0 for v in vals)
                ts.append(sum(vals) if good else np.nan)
            stats[bits]=(kind,ts)
        kinds=np.array([stats[x][0] if stats[x][0]==stats[y][0] else 'mixed_semantics' for x,y in zip(removed,added)])
        t0=np.array([stats[x][1] for x in removed]);t1=np.array([stats[x][1] for x in added])
        valid=np.isfinite(t0).all(axis=1)&np.isfinite(t1).all(axis=1)&(t0>0).all(axis=1)&(t1>0).all(axis=1)&(kinds!='mixed_semantics')
        qd=None
        if native is not None:
            npools=[native_pool(pid) for pid in (p.pool_id_a,p.pool_id_b)]
            nk=[g.team_key_a.tolist(),g.team_key_b.tolist()]
            if all(all(key in npools[s] for key in nk[s]) for s in (0,1)):
                qq=[np.array([npools[s][key].get('B8L2') if finite(npools[s][key].get('B8L2')) else np.nan for key in nk[s]]) for s in (0,1)]
                qd=[v[j]-v[i] for v in qq]
        for mm,rr,kind in sorted(set(zip(m,r,kinds))):
            sel=(m==mm)&(r==rr)&(kinds==kind);ok=sel&valid
            row={'panel_id':p.panel_id,'m':int(mm),'r':int(rr),'time_source_kind':kind,'attempted':int(sel.sum()),'computable':int(ok.sum()),
                 'kind':'same_composition' if rr==0 else ('pure_class_block' if mm==rr else 'mixed_class_block')}
            if ok.any():
                logratio=np.log(t1[ok]/t0[ok]);delta=t1[ok]-t0[ok]
                row.update(states(logratio[:,0],logratio[:,1],np.log(1.05)))
                row.update({'mean_delta_seconds_a':delta[:,0].mean(),'mean_delta_seconds_b':delta[:,1].mean(),
                            'mean_abs_delta_seconds_a':np.abs(delta[:,0]).mean(),'mean_abs_delta_seconds_b':np.abs(delta[:,1]).mean(),
                            'logratio_a':logratio[:,0].mean(),'logratio_b':logratio[:,1].mean(),
                            'mean_abs_logratio_view_gap':np.abs(logratio[:,0]-logratio[:,1]).mean(),
                            'correlation_logratio':np.corrcoef(logratio.T)[0,1] if len(logratio)>2 and np.std(logratio[:,0])>1e-12 and np.std(logratio[:,1])>1e-12 else np.nan,
                            'same_sign_unthresholded':float(np.mean(np.sign(logratio[:,0])==np.sign(logratio[:,1])))})
            if qd is not None:
                both=ok&np.isfinite(qd[0])&np.isfinite(qd[1]);row['same_support_time_quality_n']=int(both.sum())
                if both.any():
                    x,y=qd[0][both],qd[1][both];lr=np.log(t1[both]/t0[both])
                    row.update({'q_'+key:value for key,value in state_rates(x,y,2.).items()})
                    row['q_same_sign_unthresholded']=float(np.mean(np.sign(x)==np.sign(y)))
                    row['time_same_support_same_sign_unthresholded']=float(np.mean(np.sign(lr[:,0])==np.sign(lr[:,1])))
                    row.update({'time_same_support_'+key:value for key,value in states(lr[:,0],lr[:,1],np.log(1.05)).items()})
            rows.append(row)
    df=pd.DataFrame(rows);df.to_csv(out/'BLOCK_TIME_STRATA.csv.gz',index=False)
    meta=panels.copy();meta['mid_n']=[max(3,k,min(N-k,N//2)) for k,N in zip(meta.k_selected,meta.known_common_n)]
    d=df.merge(meta,on='panel_id');nums=[x for x in df.select_dtypes('number').columns if x not in ['m','r']]
    summaries=[];groups=[];buildings=[]
    keys=['kind','m','r','time_source_kind']
    for subset,ss in analysis_subsets(d):
        if not len(ss):continue
        pair=ss.groupby(keys+['building','pair_key','groups'])[nums].mean().reset_index()
        gr=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id').groupby(keys+['building','group_id'])[nums].mean().reset_index()
        gr['subset']=subset;groups.append(gr)
        bb=gr.groupby(keys+['building'])[nums].mean().reset_index();bb['subset']=subset;buildings.append(bb)
        for key,gg in bb.groupby(keys):
            support=ss[(ss.kind==key[0])&(ss.m==key[1])&(ss.r==key[2])&(ss.time_source_kind==key[3])]
            comput=support[support.computable>0]
            row=dict(zip(keys,key));row.update(subset=subset,attempted_contrasts=int(support.attempted.sum()),computable_contrasts=int(support.computable.sum()),
                      pairs=comput.pair_key.nunique(),images=len(set(comput.image_a)|set(comput.image_b)),buildings=comput.building.nunique(),groups=len(set('|'.join(comput.groups).split('|'))-set([''])),panels=comput.panel_id.nunique())
            if 'same_support_time_quality_n' in support:
                row['same_support_time_quality_contrasts']=int(support.same_support_time_quality_n.sum())
            row.update({x:gg[x].mean() for x in nums});summaries.append(row)
    pd.DataFrame(summaries).to_csv(out/'BLOCK_TIME_SUMMARY.csv',index=False)
    pd.concat(groups).to_csv(out/'BLOCK_TIME_GROUPS.csv.gz',index=False)
    pd.concat(buildings).to_csv(out/'BLOCK_TIME_BUILDINGS.csv',index=False)
    (out/'TIMING_RECEIPT.json').write_text(json.dumps({'source':'frozen snapshot source_time_seconds with original time_source_kind','no_imputation':True,
        'estimand':'same exact replaced member block, add/remove active or inherited recorded seconds separately; unchanged core cancels',
        'not_estimand':['calendar completion','parallel delivery','money','cross-semantic labor sum'],
        'contrast_rows':len(df),'logratio_nearzero_threshold':'abs(log(add/remove)) <= log(1.05)',
        'same_supported_quality_comparison':native is not None,'quality_nearzero_threshold':2.},ensure_ascii=False,indent=2))
    print(pd.DataFrame(summaries).query("subset=='ordinary_mid' and kind=='pure_class_block'").to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--design',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--native',type=Path);a=p.parse_args();main(a.repo,a.design,a.out,a.native)
