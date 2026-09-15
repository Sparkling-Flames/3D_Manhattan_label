"""Existing numerical output analysis for B/C/D; never runs a visual model."""
from __future__ import annotations
import argparse,itertools,json,collections,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_core import _dense_boundaries, _d_mask
NUMERIC=ROOT.parent/'numerics'
FACES=['front','right','back','left','up','down']


def archive(path):
    with np.load(path,allow_pickle=False) as z:return {k:z[k] for k in z.files}


def round_bounds(pixels):
    x=np.asarray(pixels,float)
    if x.shape!=(2,1024) or not np.isfinite(x).all():raise ValueError('invalid dense boundary')
    x=np.clip(np.rint(x),0,511).astype(np.int32)
    return np.minimum(x[0],x[1]),np.maximum(x[0],x[1])


def corners_bounds(corners):
    g=normalize_geometry(corners)
    return (_dense_boundaries(g['pairs']) if g['valid'] else None),g


def pair_median(values):
    return median([_d_mask(a,b) for a,b in itertools.combinations(values,2)])


def model_feedback(numerics=NUMERIC):
    rows=[];phases=[];quality=[];sample={};failures=[]
    references={r['image_id']:r for r in load(BUNDLE/'human/references.jsonl.gz')};refdense={i:_dense_boundaries(r['pairs']) for i,r in references.items() if r['current_quality_status'] not in {'missing','reference_not_geometry_ready','not_evaluable_bad_gt'}}
    allids=[r['image_id'] for r in load(BUNDLE/'metadata/images.jsonl')]
    for image in allids:
        try:
            hh=archive(numerics/f'predictions/hohonet/{image}.npz');bi=archive(numerics/f'predictions/bilayout/{image}.npz');ul=archive(numerics/f'predictions/ulayout/{image}.npz')
            hstatus=load(BUNDLE/f'models/hohonet/{image}.json');bstatus=load(BUNDLE/f'models/bilayout/{image}.json')
            assert hstatus['status']=='ok' and bstatus['status']=='ok'
            hv=[];uv=[];bev=[];bxv=[];hp=[];bep=[];bxp=[];hpc=[];bepc=[];bxpc=[];head_dist=[]
            raw_hh_post_delta=[]
            for yaw in (0,90,180,270):
                h=round_bounds((hh[f'yaw{yaw}__raw__bon']/np.pi+.5)*512-.5)
                u=round_bounds(ul[f'yaw{yaw}_boundary_pixels_float'])
                # Bi raw horizontal depth gives a continuous boundary, independent
                # of postprocessed corner count. Its original 256 pixel centers
                # are interpolated periodically to the 1024-pixel canvas.
                xs=(np.arange(256)+.5)*4-.5;ratio=float(bi[f'yaw{yaw}__raw__ratio'][0]);raw=[]
                for key in ('new_depth','depth'):
                    dep=bi[f'yaw{yaw}__raw__{key}'];assert np.all(dep>0) and ratio>0
                    pix=np.array([(np.arctan2(-ratio,dep)/np.pi+.5)*512-.5,(np.arctan2(1,dep)/np.pi+.5)*512-.5])
                    curve=np.array([np.interp(np.arange(1024),xs,band,period=1024) for band in pix]);raw.append(round_bounds(curve))
                hpix=hh[f'yaw{yaw}__post__cor_id'];epix=bi[f'yaw{yaw}__post__corners_enclosed'];xpix=bi[f'yaw{yaw}__post__corners_extended']
                ph,gh=corners_bounds(hpix);pe,ge=corners_bounds(epix);px,gx=corners_bounds(xpix)
                for model,g,c in [('hohonet',gh,hpix),('bi_enclosed',ge,epix),('bi_extended',gx,xpix)]:
                    phases.append(dict(image_id=image,model=model,yaw=yaw,point_count=len(c),geometry_valid=g['valid'],geometry_failure=g['reason'],boundary_coordinate_convention='exported floating pixels; no point edits'))
                hv.append(h);uv.append(u);bev.append(raw[0]);bxv.append(raw[1]);hp.append(ph);bep.append(pe);bxp.append(px);hpc.append(len(hpix));bepc.append(len(epix));bxpc.append(len(xpix));head_dist.append(_d_mask(raw[0],raw[1]))
                raw_hh_post_delta.append(float(np.max(np.abs(hh[f'yaw{yaw}__post__y_bon_']-((hh[f'yaw{yaw}__raw__bon']/np.pi+.5)*512-.5)))))
            r=dict(image_id=image,building=image.split('_')[0],hohonet_rotation_dmask=pair_median(hv),ulayout_rotation_dmask=pair_median(uv),bi_enclosed_rotation_dmask=pair_median(bev),bi_extended_rotation_dmask=pair_median(bxv),
              hohonet_topology_change=float(len(set(hpc))>1),bi_enclosed_topology_change=float(len(set(bepc))>1),bi_extended_topology_change=float(len(set(bxpc))>1),hohonet_point_count_mean=np.mean(hpc),bi_enclosed_point_count_mean=np.mean(bepc),bi_extended_point_count_mean=np.mean(bxpc),
              bi_heads_boundary_difference=median(head_dist),bi_heads_point_count_disagreement=float(np.mean(np.array(bepc)!=np.array(bxpc))),bi_raw_head_height_difference=float(np.mean([abs(float(bi[f'yaw{y}__raw__height_enclosed'][0])-float(bi[f'yaw{y}__raw__height_extended'][0])) for y in (0,90,180,270)])),
              hohonet_bi_enclosed_difference=median([_d_mask(a,b)for a,b in zip(hv,bev)]),hohonet_bi_extended_difference=median([_d_mask(a,b)for a,b in zip(hv,bxv)]),hohonet_ulayout_difference=median([_d_mask(a,b)for a,b in zip(hv,uv)]),bi_enclosed_ulayout_difference=median([_d_mask(a,b)for a,b in zip(bev,uv)]),bi_extended_ulayout_difference=median([_d_mask(a,b)for a,b in zip(bxv,uv)]),
              hohonet_fallback_warning_phases=sum(bool(p.get('postprocess_warning')) for p in hstatus['phases']),hohonet_raw_vs_exported_boundary_max_pixel_difference=max(raw_hh_post_delta),
              hohonet_postprocessing_displacement=median([_d_mask(a,b)for a,b in zip(hv,hp) if b is not None]),bi_enclosed_postprocessing_displacement=median([_d_mask(a,b)for a,b in zip(bev,bep) if b is not None]),bi_extended_postprocessing_displacement=median([_d_mask(a,b)for a,b in zip(bxv,bxp) if b is not None]))
            r['three_architecture_disagreement_enclosed']=np.mean([r['hohonet_bi_enclosed_difference'],r['hohonet_ulayout_difference'],r['bi_enclosed_ulayout_difference']])
            r['three_architecture_disagreement_extended']=np.mean([r['hohonet_bi_extended_difference'],r['hohonet_ulayout_difference'],r['bi_extended_ulayout_difference']])
            rows.append(r)
            for name,curves in [('hohonet',hv),('bi_enclosed',bev),('bi_extended',bxv),('ulayout',uv)]:
                if image in refdense:
                    quality.append(dict(image_id=image,model=name,reference_status=references[image]['current_quality_status'],reference_error_yaw_mean=np.mean([_d_mask(a,refdense[image])for a in curves]),not_a_GT_evaluation=True))
            sample[image]=np.array([hv[0],bev[0],bxv[0],uv[0]],dtype=np.int16)
        except Exception as exc:failures.append(dict(image_id=image,error=repr(exc)))
    write_csv('B/model_feedback.csv',rows);write_csv('B/model_phase_geometry_audit.csv',phases);write_csv('B/model_reference_comparisons.csv',quality);write_csv('B/model_feedback_failures.csv',failures)
    np.savez_compressed(OUT/'B/model_phase0_boundaries.npz',image_ids=np.array(list(sample)),boundaries=np.array(list(sample.values())),model_names=np.array(['hohonet','bi_enclosed','bi_extended','ulayout']))
    print('B images',len(rows),'failures',len(failures),flush=True)
    return pd.DataFrame(rows)


def known_rotations():
    frames=[([0,0,1],[0,-1,0]),([1,0,0],[0,-1,0]),([0,0,-1],[0,-1,0]),([-1,0,0],[0,-1,0]),([0,-1,0],[0,0,-1]),([0,1,0],[0,0,1])]
    return np.array([np.stack((np.cross(f,u),-np.asarray(u),f),axis=1) for f,u in frames],float)


def camera_diagnostics(ext):
    rotations=ext[:,:3,:3];translations=ext[:,:3,3];centers=-np.linalg.solve(rotations,translations[...,None])[...,0]
    pr=np.linalg.inv(rotations)@np.tile(known_rotations().transpose(0,2,1),(2,1,1));pr=pr.reshape(2,6,3,3);c=centers.reshape(2,6,3)
    rel=pr[:,:,None].transpose(0,1,2,4,3)@pr[:,None];angles=np.rad2deg(np.arccos(np.clip((np.trace(rel,axis1=-2,axis2=-1)-1)/2,-1,1)))
    cd=np.linalg.norm(c[:,:,None]-c[:,None],axis=-1);baseline=float(np.linalg.norm(np.median(c[0],axis=0)-np.median(c[1],axis=0)))
    return angles,cd,baseline


def da3_geometry(numerics=NUMERIC):
    masks=archive(BUNDLE/'projection/conservative_nadir_masks.npz');rows=[];faces=[];errors=[];angdiff=[];singles={}
    for r in load(BUNDLE/'models/da3/multiview/status.json'):
        pid=r['pair_id'];a=archive(numerics/f'geometry/da3_multiview/{pid}.geometry.npz')
        try:
            assert a['image_ids'].tolist()==r['image_ids']
            ang,centers,baseline=camera_diagnostics(a['extrinsics']);angdiff.append(np.max(np.abs(ang-a['same_capture_panorama_rotation_degrees'])))
            upper=np.triu_indices(6,1);av=np.concatenate([ang[j][upper] for j in (0,1)]);cv=np.concatenate([centers[j][upper]for j in (0,1)])
            row=dict(pair_id=pid,image_a=r['image_ids'][0],image_b=r['image_ids'][1],building=r['image_ids'][0].split('_')[0],relation_eligible=r['main_room_evaluation_eligible'],max_same_capture_angle=float(np.max(av)),median_same_capture_angle=float(np.median(av)),median_center_distance=float(np.median(cv)),max_center_distance=float(np.max(cv)),predicted_capture_baseline=baseline,center_spread_over_baseline=float(np.max(cv)/baseline) if baseline>1e-12 else np.nan,
                passes_rotation_consistency_at_5deg=bool(np.max(av)<=5),passes_rotation_consistency_at_10deg=bool(np.max(av)<=10),passes_rotation_consistency_at_20deg=bool(np.max(av)<=20),passes_rotation_consistency_at_40deg=bool(np.max(av)<=40),rotation_consistency_is_necessary_not_sufficient=True)
            c=a['reprojection_candidates'];assert c.shape[1]==10
            for policy in ['all','nadir_excluded']:
                keep=np.ones(len(c),bool)
                if policy=='nadir_excluded':
                    sx=np.rint(c[:,1]).astype(int);sy=np.rint(c[:,2]).astype(int);tx=np.rint(c[:,4]).astype(int);ty=np.rint(c[:,5]).astype(int)
                    assert all((v>=0).all() and (v<504).all() for v in (sx,sy,tx,ty))
                    sm=np.stack([masks[FACES[int(v)%6]][yy,xx] for v,yy,xx in zip(c[:,0],sy,sx)])
                    tm=np.stack([masks[FACES[int(v)%6]][yy,xx] for v,yy,xx in zip(c[:,3],ty,tx)])
                    keep=sm&tm
                row[policy+'_projectable_candidates']=int(keep.sum())
                for tol in (.01,.05,.10):row[f'{policy}_predicted_depth_agreement_{tol}']=float(np.mean(c[keep,8]<=tol)) if keep.any() else np.nan
                row[policy+'_relative_depth_error_median']=median(c[keep,8])
            # Fit a separate scale to each single-inference face, then compare log
            # depth shape, not arbitrary metric depths. This is predictive geometry
            # change, NOT verified occlusion removal or physical correspondence.
            for capture,image in enumerate(r['image_ids']):
                if image not in singles:singles[image]=archive(numerics/f'geometry/da3/{image}.npz')
                single=singles[image]
                for face_idx,face in enumerate(FACES):
                    x=single[face+'_depth_stride8'][0];y=a['depth_stride8'][capture*6+face_idx]
                    assert x.shape==y.shape==(63,63)
                    for policy in ['all','nadir_excluded']:
                        keep=(x>0)&(y>0)&np.isfinite(x)&np.isfinite(y)
                        if policy=='nadir_excluded':keep&=masks[face][::8,::8]
                        ld=np.log(y[keep])-np.log(x[keep]);ls=float(np.median(ld));res=np.abs(ld-ls)
                        faces.append(dict(pair_id=pid,image_id=image,capture=capture,face=face,mask_policy=policy,n_pixels=int(keep.sum()),log_scale_fit=ls,median_abs_log_depth_shape_change=median(res),p90_abs_log_depth_shape_change=float(np.quantile(res,.9)),relation_eligible=r['main_room_evaluation_eligible'],max_same_capture_angle=row['max_same_capture_angle']))
            rows.append(row)
        except Exception as exc:errors.append(dict(pair_id=pid,error=repr(exc)))
    write_csv('D/pair_geometry_audit.csv',rows);write_csv('D/scale_free_face_changes.csv.gz',faces);write_csv('D/geometry_failures.csv',errors)
    frame=pd.DataFrame(rows);write_json(OUT/'D/geometry_summary.json',dict(pairs=len(frame),relation_eligible=int(frame.relation_eligible.sum()),angle_quantiles=frame.max_same_capture_angle.quantile([0,.25,.5,.75,1]).to_dict(),eligible_angle_quantiles=frame[frame.relation_eligible].max_same_capture_angle.quantile([0,.5,1]).to_dict(),angle_export_recompute_max_difference=max(angdiff),valid_relation_and_angle_counts={str(cut):int((frame.relation_eligible&(frame.max_same_capture_angle<=cut)).sum())for cut in [5,10,20,40]},errors=errors,numerical_projection_not_physical_correspondence=True))
    print('D pairs',len(frame),'errors',len(errors),'minmaxangle',frame.max_same_capture_angle.min(),flush=True)


def build_features(numerics=NUMERIC):
    dest=OUT/'features';dest.mkdir(exist_ok=True,parents=True);registry={};hashes={};equiv=[]
    feat=pd.read_csv(OUT/'A/interpretable_inputs.csv').set_index('image_id');ids=sorted({r['image_id'] for r in load(BUNDLE/'human/responses.jsonl.gz')});fi=feat.loc[ids]
    def put(name,x,columns=None,family='exploratory',model='',layer='',pool='',prespecified=False):
        x=np.asarray(x,dtype=np.float32);assert x.shape[0]==len(ids)
        file=name+'.npz';np.savez_compressed(dest/file,image_ids=np.array(ids),X=x)
        digest=hashlib.sha256(x.tobytes()).hexdigest();duplicate=hashes.get((x.shape,digest));hashes[x.shape,digest]=name
        registry[name]=dict(file=file,dimensions=x.shape[1],family=family,model=model,layer=layer,pool=pool,prespecified=prespecified,columns=columns or [],exact_duplicate_of=duplicate)
        if duplicate:equiv.append(dict(feature=name,exactly_equal_to=duplicate,dimensions=x.shape[1]))
    def cats(cols):
        # Vocabulary is an input-schema listing, not fitted target information.
        # The numeric evaluator removes every training-constant column, exactly
        # ignoring unseen categories in ridge/PCA and uniform-neighbor ranking.
        z=pd.get_dummies(fi[cols].fillna('unknown').astype(str),dtype=float)
        return z.to_numpy(),z.columns.tolist()
    cat,cn=cats(['scene']);human,hn=cats(['scene','doorway']);vis,vn=cats(['floor_boundary','ceiling_boundary','connected_space','reflection_glass','low_contrast']);allx,an=cats(['scene','doorway','floor_boundary','ceiling_boundary','connected_space','reflection_glass','low_contrast'])
    put('A_scene_encoded',cat,cn,'A',prespecified=True);put('A_scene_doorway',human,hn,'A',prespecified=True);put('A_AI_traits',vis,vn,'A',prespecified=True);put('A_all_traits',allx,an,'A',prespecified=True)
    corrected,cc=cats(['scene','doorway','floor_boundary_rechecked','ceiling_boundary_rechecked','connected_space_rechecked','reflection_glass_rechecked','low_contrast_rechecked']);put('A_21_rechecked',corrected,cc,'A_sensitivity')
    feedback=pd.read_csv(OUT/'B/model_feedback.csv').set_index('image_id').reindex(ids)
    excluded={'building','hohonet_raw_vs_exported_boundary_max_pixel_difference'}
    bc=[c for c in feedback if c not in excluded];bx=feedback[bc].to_numpy(float)
    put('B_feedback',bx,bc,'B',prespecified=True);put('AB_traits_feedback',np.column_stack([allx,bx]),an+bc,'increment',prespecified=True)
    for model in ['hohonet','bi','ulayout']:
        cols=[c for c in bc if c.startswith(model+'_') and not any(other in c for other in ['hohonet','bi_','ulayout'] if other not in [model,model+'_'])]
        if cols:put('B_single_'+model,feedback[cols].to_numpy(),cols,'B_ablation',model=model)
    for excluded_model in ['hohonet','bi','ulayout']:
        cols=[c for c in bc if excluded_model not in c and not c.startswith('three_architecture')]
        put('B_without_'+excluded_model,feedback[cols].to_numpy(),cols,'B_ablation')
    for model,layers in [('hohonet',['encoder_stage2','encoder_stage4','compressed','refined','shared']),('bilayout',['fc','fg_enclosed','fg_extended']),('ulayout',['compressed','transformer'])]:
        data={i:archive(numerics/f'features/{model}/{i}.npz') for i in ids}
        for layer in layers:
            for pool in ['global','local16']:
                x=np.stack([data[i][layer+'__'+pool].ravel() for i in ids]);put('C_'+model+'_'+layer+'_'+pool,x,family='C',model=model,layer=layer,pool=pool,prespecified=True)
        if model=='hohonet':
            legacy=np.stack([data[i]['legacy_single_phase_mean']for i in ids]);put('C_hohonet_legacy_single_phase',legacy,family='C',model=model,layer='legacy',pool='mean',prespecified=True)
            shared=np.stack([data[i]['shared__global']for i in ids]);rot=np.stack([data[i]['shared__phase_sd']for i in ids]);put('C_hohonet_shared_with_phase_sd',np.column_stack([shared,rot]),family='C_exploratory',model=model,layer='shared',pool='rotation_sd')
            put('ABC_traits_feedback_shared',np.column_stack([allx,bx,shared]),family='increment',model=model,layer='shared',pool='global',prespecified=True)
    data={i:archive(numerics/f'features/da3/{i}.npz')for i in ids}
    for layer in [5,7,9,11]:
        global_faces=np.stack([np.stack([data[i][f'{f}_view0_out_layer_{layer}_global']for f in FACES])for i in ids])
        local_faces=np.stack([np.stack([data[i][f'{f}_view0_out_layer_{layer}_local16']for f in FACES])for i in ids])
        put(f'C_da3_layer{layer}_global',global_faces.mean(1),family='C',model='da3',layer=str(layer),pool='six_face_mean',prespecified=True)
        put(f'C_da3_layer{layer}_local16',local_faces.reshape(len(ids),-1),family='C',model='da3',layer=str(layer),pool='six_face_local16_flatten',prespecified=True)
        put(f'C_da3_layer{layer}_face_globals',global_faces.reshape(len(ids),-1),family='C_exploratory',model='da3',layer=str(layer),pool='six_face_global_concat')
        cells=local_faces.reshape(len(ids),96,1536)
        put(f'C_da3_layer{layer}_local_moments',np.column_stack([cells.mean(1),cells.std(1)]),family='C_exploratory',model='da3',layer=str(layer),pool='96_strip_channel_moments')
    old=archive(BUNDLE/'history/historical_image_features.npz');oi={str(i):j for j,i in enumerate(old['image_ids'])}
    for key in old:
        if key=='image_ids':continue
        put('C_historical_'+key,old[key][[oi[i]for i in ids]],family='C_historical',model='historical_hohonet',layer=key,pool='historical',prespecified=True)
    dm=pd.DataFrame(load(BUNDLE/'history/d_model_feat.jsonl')).set_index('image_id').reindex(ids)
    cols=[c for c in dm if c.startswith('d_model_feat') and 'delta' not in c]
    if cols:put('C_historical_frozen_distances',dm[cols].to_numpy(float),cols,family='C_historical',model='historical_frozen_reference',prespecified=True)
    write_json(dest/'registry.json',registry);write_csv('C/exact_feature_equivalence.csv',equiv)
    print('FEATURES',len(registry),[(k,v['dimensions'])for k,v in registry.items()],flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('route',choices=['B','C','D']);ap.add_argument('--numeric-root',type=Path,default=NUMERIC);args=ap.parse_args()
    if args.route=='B':model_feedback(args.numeric_root)
    if args.route=='C':build_features(args.numeric_root)
    if args.route=='D':da3_geometry(args.numeric_root)
