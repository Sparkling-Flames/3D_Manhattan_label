"""Read real exported arrays for the expanded historical image set; no inference.

Candidate kernels are exact dot products after per-image L2 normalization. This
is a declared follow-up alternative to per-channel z scaling; no corpus-fitted
transform is used here. Train-only centering/PCA/ridge/kNN follow in prediction.
"""
from __future__ import annotations
import argparse, collections, hashlib, itertools, json, subprocess
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
FACES=('front','right','back','left','up','down')
YAWS=(0,90,180,270)


def normalize_rows(x):
    x=np.asarray(x,np.float64);norm=np.linalg.norm(x,axis=1)
    good=np.isfinite(x).all(1)&(norm>1e-15)
    out=np.full_like(x,np.nan);out[good]=x[good]/norm[good,None]
    return out,good


def extract_one(z,model):
    f={}
    def avg(keys):return np.mean([z[k] for k in keys],axis=0,dtype=np.float64).astype(np.float32)
    if model in ('hohonet','bilayout'):
        layers=['encoder_stage2','encoder_stage4','compressed','refined','shared'] if model=='hohonet' else ['fc','fg_enclosed','fg_extended']
        for layer in layers:
            for pool in ('global','regions'):
                f[f'{model}__{layer}__{pool}']=avg([f'yaw{a}__{layer}__{pool}' for a in YAWS]).ravel()
        if model=='hohonet':f['hohonet__legacy_current']=z['legacy_single_phase_mean'].ravel()
    elif model=='ulayout':
        for layer in ('compressed','transformer'):
            for pool in ('global','local16'):f[f'ulayout__{layer}__{pool}']=avg([f'yaw{a}_{layer}_{pool}' for a in YAWS]).ravel()
    elif model=='dinov3':
        for layer in (3,6,9,11,12):
            for pool in ('global','local16'):
                f[f'dinov3__block{layer}__panorama_{pool}']=z[f'panorama_block{layer}_patch_{pool}'].ravel()
                f[f'dinov3__block{layer}__faces_{pool}']=avg([f'{a}_block{layer}_patch_{pool}' for a in FACES]).ravel()
            f[f'dinov3__block{layer}__panorama_mean']=z[f'panorama_block{layer}_patch_global'][:768]
            f[f'dinov3__block{layer}__faces_concat']=np.concatenate([z[f'{a}_block{layer}_patch_global'] for a in FACES])
            f[f'dinov3__block{layer}__faces_local96']=np.concatenate([z[f'{a}_block{layer}_patch_local16'].ravel() for a in FACES])
        f['dinov3__cls__panorama']=z['panorama_block12_cls_global'].ravel()
        f['dinov3__cls__faces']=avg([f'{a}_block12_cls_global' for a in FACES]).ravel()
    else:
        assert int(z['feature_schema_version'])==2
        for layer in (5,7,9,11):
            for pool in ('global','local16'):
                f[f'da3__layer{layer}__faces_{pool}']=avg([f'{a}_view0_out_layer_{layer}_{pool}' for a in FACES]).ravel()
            f[f'da3__layer{layer}__faces_concat']=np.concatenate([z[f'{a}_view0_out_layer_{layer}_global'] for a in FACES])
    return f


def dense_corners(points):
    from tools.thesis_main.analysis.quality_core.geometry_metrics import _interp_periodic
    a=np.asarray(points,float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<4 or len(a)%2:raise ValueError('unusable model corner shape')
    a=a.reshape(-1,2,2);x=np.mod(a[:,:,0].mean(1),1024)
    top=np.min(a[:,:,1],axis=1);bot=np.max(a[:,:,1],axis=1)
    return np.stack([np.clip(np.rint(_interp_periodic(x,y,1024)),0,511) for y in (top,bot)])


def distance(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])+1)
    uni=a[1]-a[0]+b[1]-b[0]+2-inter
    return 1-float(inter.sum()/uni.sum())


def feedback(ids):
    result=[];fail=[]
    for i in ids:
        row={'image_id':i};bounds={}
        for model in ('hohonet','bilayout','ulayout'):
            p=B/'models'/model/(i+('.npz' if model!='ulayout' else '.geometry.npz'))
            try:
                with np.load(p,allow_pickle=False) as z:
                    if model=='hohonet':
                        counts=[];bb=[]
                        for yaw in YAWS:
                            counts.append(len(z[f'yaw{yaw}__post__cor_id']))
                            a=np.asarray(z[f'yaw{yaw}__raw__bon']);assert a.shape==(2,1024)
                            bb.append(np.clip(np.rint((a/np.pi+.5)*512),0,511))
                        row['count_hohonet']=float(np.median(counts));row['count_yaw_range_hohonet']=float(np.ptp(counts));bounds['hohonet']=bb
                        state=read(p.with_suffix('.json'));row['hohonet_fallback_phases']=sum(bool(q.get('postprocess_warning')) for q in state['phases'])
                    elif model=='bilayout':
                        for head in ('enclosed','extended'):
                            counts=[];bb=[]
                            for yaw in YAWS:
                                cc=z[f'yaw{yaw}__post__corners_{head}'];counts.append(len(cc));bb.append(dense_corners(cc))
                            row['count_bi_'+head]=float(np.median(counts));row['count_yaw_range_bi_'+head]=float(np.ptp(counts));bounds['bi_'+head]=bb
                        row['bi_head_geometry_gap']=float(np.mean([distance(a,b) for a,b in zip(bounds['bi_enclosed'],bounds['bi_extended'])]))
                        row['bi_height_head_gap']=float(np.mean([np.abs(z[f'yaw{y}__raw__height_enclosed']-z[f'yaw{y}__raw__height_extended']).mean() for y in YAWS]))
                    else:
                        bounds['ulayout']=[np.clip(np.rint(z[f'yaw{y}_boundary_pixels_float']),0,511) for y in YAWS]
                for name,bb in bounds.items():
                    if len(bb)==4:row['rotation_'+name]=float(np.mean([distance(a,b) for a,b in itertools.combinations(bb,2)]))
            except Exception as e:fail.append(dict(image_id=i,model=model,stage='feedback',error=repr(e)))
        for a,b in itertools.combinations(['hohonet','bi_enclosed','bi_extended','ulayout'],2):
            if a in bounds and b in bounds:row['gap_'+a+'_'+b]=float(np.mean([distance(x,y) for x,y in zip(bounds[a],bounds[b])]))
        result.append(row)
    csv('B/model_feedback.csv',result);csv('B/feedback_failures.csv',fail)


def run():
    ids=read(OUT/'inputs/historical_ids.json');dest=OUT/'kernels';dest.mkdir(parents=True,exist_ok=True)
    registry=[];audit=[];fail=[]
    for model in ('hohonet','bilayout','ulayout','dinov3','da3'):
        features=collections.defaultdict(list)
        for i in ids:
            p=B/'models'/model/(i+('.npz' if model in ('hohonet','bilayout') else '.features.npz'))
            try:
                with np.load(p,allow_pickle=False) as a:
                    if 'image_ids' in a:assert a['image_ids'].tolist()==[i]
                    if model in ('hohonet','bilayout'):
                        st=read(p.with_suffix('.json'));assert st['status']=='ok' and sorted(v['yaw'] for v in st['phases'] if v['status']=='ok')==list(YAWS)
                    f=extract_one(a,model)
                    for name,v in f.items():
                        v=np.asarray(v,np.float32)
                        if v.ndim!=1 or not np.isfinite(v).all():raise ValueError('invalid vector '+name)
                        features[name].append((i,v.copy()))
                    nkeys=len(a.files)
                audit.append(dict(image_id=i,model=model,source=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),git_blob=subprocess.check_output(['git','hash-object',str(p)]).decode().strip(),bytes_read=p.stat().st_size,arrays_read=nkeys,status='actual_export_loaded_and_required_candidates_checked'))
            except Exception as e:fail.append(dict(image_id=i,model=model,error=repr(e)))
        for name,values in features.items():
            im=[v[0] for v in values];x=np.stack([v[1] for v in values]);xn,good=normalize_rows(x);gg=xn[good];im=np.asarray(im)[good]
            k=gg@gg.T;k=(k+k.T)/2
            np.savez_compressed(dest/(name+'.npz'),image_ids=im,K=k)
            registry.append(dict(feature=name,family=model,file=name+'.npz',dimension=x.shape[1],available_images=len(im),requested_images=len(ids),pool_kind='additional_numeric_pool' if any(t in name for t in ('mean','concat','local96')) else 'prespecified_layer_and_pool',scaling='per-image L2; training-centering and PCA are fitted only inside folds',full_vector_recoverable_from='original source NPZ; exact Gram suffices for this numerical pipeline'))
        print('ACTUALLY READ',model,len([r for r in audit if r['model']==model]),'historical images',flush=True)
    csv('C/model_array_read_audit.csv',audit);csv('C/model_missing_or_failed.csv',fail);csv('C/candidate_registry.csv',registry);js('kernels/registry.json',registry)
    feedback(ids)
    js('C/coverage.json',dict(target_images=len(ids),actual_read_by_model=dict(collections.Counter(r['model'] for r in audit)),candidate_count=len(registry),failures=fail,dino_not_old_snapshot=True,raw_images_read=0,model_weights_read=0,visual_inference_calls=0,known_da3_joint_geometry_excluded=True))

if __name__=='__main__':run()
