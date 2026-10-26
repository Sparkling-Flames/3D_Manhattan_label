"""Restore named frozen loss blocks from saved raw measurements, without fusion.

This separate supplement does not replace paired-Q/labor/precision main results.
Prior named-block missingness was an export issue; use old/new common observed k
after the deterministic restoration and record that support explicitly.
"""
from pathlib import Path
import argparse, hashlib, io, json, os, sys
for env in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[env]='1'
import numpy as np
import pandas as pd
import analyze_policy32 as P

RAW=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
BLOCKS=['B8_floor_block','B8_direction_block','B8_global_height_block',
        'B8_local_height_block','B8_height_block','D10_direction_block']
NAMES=[x+'_delta' for x in BLOCKS]+['paired_Q_delta_on_block_support','paired_D10_delta_on_block_support']


def bootstrap_means(delta, draws):
    """Equivalent whole-path resampling by integer occurrence weights."""
    B,R=draws.shape;w=np.zeros((B,R),float)
    np.add.at(w,(np.repeat(np.arange(B),R),draws.ravel()),1)
    valid=np.isfinite(delta);num=w@np.where(valid,delta,0);den=w@valid.astype(float)
    return np.divide(num,den,out=np.full(num.shape,np.nan),where=den>0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--replicates',type=int,default=2000);ap.add_argument('--only-pool')
    args=ap.parse_args();base=args.base.resolve();sys.path.insert(0,str(base/'engine26'))
    from derive_frozen_blocks import add_blocks_frame
    meta=pd.read_csv(base/'analysis_policy26/COMMON_IMAGES.csv')
    if args.only_pool:meta=meta[meta.pool_id.eq(args.only_pool)].reset_index(drop=True)
    out=base/'analysis_policy26/restored_components';out.mkdir(parents=True,exist_ok=True)
    original_metrics=list(P.F.METRICS);P.F.METRICS=NAMES
    # Complete raw values are joined only to the exact old-policy endpoint keys.
    needed=set()
    for pid in meta.pool_id:
        z=pd.read_csv(base/'analysis_policy26/inputs_old16'/(pid+'.csv.gz'),usecols=['team_key'])
        needed.update(z.team_key)
    saved=[]
    for path in [base/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz',
                 base/'inputs_cache26/precision25/NEW_ENDPOINT_SCALARS.csv.gz']:
        for z in pd.read_csv(path,usecols=lambda c:c in ['team_key']+RAW,chunksize=60000,low_memory=False):
            z=z[z.team_key.isin(needed)]
            if not z.empty:saved.append(z)
    raw=pd.concat(saved,ignore_index=True).drop_duplicates('team_key').set_index('team_key')
    assert needed.issubset(set(raw.index)), 'Some exact old policy teams have no raw scalar measurements'
    allphase=[];allk=[];allsupport=[];point_arrays={};boot_arrays={}
    restored=[]
    for i,row in meta.iterrows():
        pid=row.pool_id;part=out/'parts'/pid;part.mkdir(parents=True,exist_ok=True)
        receipt=part/'RECEIPT.json';npz=part/'LOSS_COMPONENT_BOOTSTRAP_CACHE.npz'
        if receipt.exists() and npz.exists():
            ph=pd.read_csv(part/'IMAGE_PHASE.csv');kr=pd.read_csv(part/'IMAGE_K.csv.gz');sp=pd.read_csv(part/'FIXED_SUPPORT.csv.gz')
            allphase.append(ph);allk.append(kr);allsupport.append(sp)
            count_file=part/'BLOCK_COUNTS.json'
            if count_file.exists():
                restored.append(json.loads(count_file.read_text()))
            elif (out/'BLOCK_FIELD_RESTORATION_COUNTS.csv').exists():
                old_counts=pd.read_csv(out/'BLOCK_FIELD_RESTORATION_COUNTS.csv')
                old_counts=old_counts[old_counts.pool_id.eq(pid)]
                if len(old_counts)==1:
                    restored.append(old_counts.iloc[0].to_dict())
                    P.atomic_bytes(count_file,json.dumps(restored[-1]).encode())
            with np.load(npz) as z:
                for pol in P.F.POLICIES:
                    for ver in P.VERSIONS:
                        point_arrays[(pid,pol,ver)]=z[pol+'__'+ver+'__point']
                        boot_arrays[(pid,pol,ver)]=z[pol+'__'+ver+'__boot']
            continue
        old=pd.read_csv(base/'analysis_policy26/inputs_old16'/(pid+'.csv.gz'),low_memory=False)
        for c in RAW:
            old[c]=old[c].fillna(old.team_key.map(raw[c])) if c in old else old.team_key.map(raw[c])
        old['analysis_source']='old16'
        new=pd.read_csv(base/'new_endpoints26/stage1/prefix_values'/(pid+'.csv.gz'),low_memory=False)
        new=new[new.new_index.between(0,15)&new.policy.isin(P.F.POLICIES+['natural_random'])].copy()
        new['analysis_source']='new16';new['legacy_batch']='new16'
        before=pd.concat([old,new],ignore_index=True)
        for c in RAW+['B8L2','D10']:before[c]=pd.to_numeric(before[c],errors='coerce')
        data=add_blocks_frame(before,check_existing=True)
        restored.append(dict(pool_id=pid,rows=len(data),old_named_floor_nonmissing=int(before.B8_floor_block.notna().sum()),
                             restored_named_floor_nonmissing=int(data.B8_floor_block.notna().sum())))
        P.atomic_bytes(part/'BLOCK_COUNTS.json',json.dumps(restored[-1]).encode())
        ks=np.arange(1,int(row.pool_n)+1);masks=P.F.phase_masks(ks,int(row.pool_n))
        stable_pool=int(hashlib.sha256(pid.encode()).hexdigest()[:8],16)
        image_phase=[];image_k=[];support=[];cache={}
        for policy in P.F.POLICIES:
            vals={};bs={};validcounts={}
            for vi,version in enumerate(P.VERSIONS):
                use=data if version=='pooled32' else data[data.analysis_source.eq(version)]
                bases=sorted(set.intersection(*[set(use.loc[use.policy.eq(p),'base_path_id']) for p in P.F.POLICIES]))
                assert len(bases)==(32 if version=='pooled32' else 16)
                matrices=[]
                for pol in ['natural_random',policy]:
                    g=use[use.policy.eq(pol)]
                    matrices.append({c:g.pivot(index='base_path_id',columns='k',values=c).reindex(index=bases,columns=ks).to_numpy(float)
                                     for c in BLOCKS+['B8L2','D10']})
                n,p=matrices
                valid=np.isfinite(n['B8L2'])&np.isfinite(p['B8L2'])
                for c in BLOCKS:valid &= np.isfinite(n[c])&np.isfinite(p[c])
                validcounts[version]=valid.sum(axis=0)
                delta=np.stack([np.where(valid,p[c]-n[c],np.nan) for c in BLOCKS+['B8L2','D10']],axis=-1)
                count=np.isfinite(delta).sum(axis=0)
                vals[version]=np.divide(np.nansum(delta,axis=0),count,out=np.full(count.shape,np.nan),where=count>0)
                mapping=use.drop_duplicates('base_path_id').set_index('base_path_id').legacy_batch.to_dict()
                draws=P.resamples(bases,mapping,np.random.default_rng(np.random.SeedSequence([P.DEFAULT_SEED,stable_pool,vi])),args.replicates)
                bs[version]=bootstrap_means(delta.reshape(len(bases),-1),draws).reshape(args.replicates,len(ks),len(NAMES))
                for j,k in enumerate(ks):
                    image_k.append(dict(**row.to_dict(),policy=policy,version=version,k=int(k),base_paths=len(bases),
                        paired_Q_and_raw_block_paths=int(validcounts[version][j]),**dict(zip(NAMES,vals[version][j]))))
            common=np.isfinite(np.stack([vals[v] for v in P.VERSIONS])).all(axis=0)
            for version in P.VERSIONS:
                point=np.full((len(P.F.PHASES),len(NAMES)),np.nan)
                boot=np.full((args.replicates,len(P.F.PHASES),len(NAMES)),np.nan,dtype=np.float32)
                for ph,phase in enumerate(P.F.PHASES):
                    for mi,metric in enumerate(NAMES):
                        keep=masks[ph]&common[:,mi]
                        point[ph,mi]=P.F.fixed_mean(vals[version][:,mi],keep,0)
                        boot[:,ph,mi]=P.F.fixed_mean(bs[version][:,:,mi],keep,1)
                        support.append(dict(pool_id=pid,image=row.image,policy=policy,version=version,phase=phase,metric=metric,
                            candidate_k=int(masks[ph].sum()),common_k=int(keep.sum()),fixed_k_list='|'.join(map(str,ks[keep])),
                            support_basis='old16/new16/pooled32 common k after frozen raw-to-loss derivation',
                            valid_bootstraps=int(np.isfinite(boot[:,ph,mi]).sum())))
                    image_phase.append(dict(**row.to_dict(),policy=policy,version=version,phase=phase,**dict(zip(NAMES,point[ph]))))
                point_arrays[(pid,policy,version)]=point;boot_arrays[(pid,policy,version)]=boot
                cache[policy+'__'+version+'__point']=point;cache[policy+'__'+version+'__boot']=boot
        ph=pd.DataFrame(image_phase);kr=pd.DataFrame(image_k);sp=pd.DataFrame(support)
        P.save(ph,part/'IMAGE_PHASE.csv');P.save(kr,part/'IMAGE_K.csv.gz');P.save(sp,part/'FIXED_SUPPORT.csv.gz')
        buf=io.BytesIO();np.savez_compressed(buf,**cache);P.atomic_bytes(npz,buf.getvalue())
        with np.load(npz) as z:
            for key in cache:assert np.array_equal(z[key],cache[key],equal_nan=True)
        P.atomic_bytes(receipt,json.dumps(dict(pool_id=pid,complete=True,replicates=args.replicates,
            new_fusion=False,main_Q_D10_labor_results_changed=False,blocks=BLOCKS)).encode())
        allphase.append(ph);allk.append(kr);allsupport.append(sp)
        print('restored policy loss blocks',i+1,len(meta),pid,flush=True)
    summary=[]
    for pi,policy in enumerate(P.F.POLICIES):
        for vi,version in enumerate(P.VERSIONS):
            point=np.stack([point_arrays[(pid,policy,version)] for pid in meta.pool_id])
            boot=np.stack([boot_arrays[(pid,policy,version)] for pid in meta.pool_id])
            rows=P.F.aggregate(point,boot,meta,version,policy,
                np.random.default_rng(np.random.SeedSequence([P.DEFAULT_SEED,999,pi,vi])),args.replicates)
            for r in rows:r['version']=r.pop('batch');r['support_basis']='restored raw-to-loss common k'
            summary.extend(rows)
    P.save(pd.DataFrame(summary),out/'POLICY_LOSS_COMPONENT_SUMMARY.csv')
    P.save(pd.concat(allphase,ignore_index=True),out/'POLICY_LOSS_COMPONENT_IMAGE_PHASE.csv')
    P.save(pd.concat(allk,ignore_index=True),out/'POLICY_LOSS_COMPONENT_IMAGE_K.csv.gz')
    P.save(pd.concat(allsupport,ignore_index=True),out/'POLICY_LOSS_COMPONENT_FIXED_SUPPORT.csv.gz')
    if restored:P.save(pd.DataFrame(restored),out/'BLOCK_FIELD_RESTORATION_COUNTS.csv')
    P.atomic_bytes(out/'RECEIPT.json',json.dumps(dict(complete=len(meta)==157,images=len(meta),buildings=int(meta.building.nunique()),
        blocks_are_dimensionless_losses_lower_better=True,source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        main_Q_D10_labor_results_changed=False,new_endpoints=0,new_orders=0,
        source_formula='personnel_population_curves_v2_20261023/code/enrich_cached_geometry.py:score_blocks',
        support='Restored raw-to-loss measurements, then common k across old16/new16/pooled32; separate from old named-field export support',
        replicate_seed=P.DEFAULT_SEED,replicates=args.replicates)).encode())


if __name__=='__main__':main()
