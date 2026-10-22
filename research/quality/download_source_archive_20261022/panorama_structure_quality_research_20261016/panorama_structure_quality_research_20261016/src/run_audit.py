from __future__ import annotations
import argparse,json,hashlib,sys,shutil
from pathlib import Path
from dataclasses import replace,asdict
import numpy as np,pandas as pd
from shapely.geometry import Polygon
from structure_quality import *


def readj(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def writej(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometry_from_points(points):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():raise ValueError('invalid paired ERP input')
    top,bottom=p[::2],p[1::2]
    if not np.allclose(top[:,0],bottom[:,0],atol=1e-8,rtol=0):raise ValueError('unconfirmed shared x; no repair')
    v=(bottom[:,1]/512.-.5)*np.pi
    if (v<=0).any() or (v>=np.pi/2).any():raise ValueError('bottom not between horizon and nadir')
    u=bottom[:,0]/1024.*2*np.pi;r=1/np.tan(v)
    x,z=-r*np.sin(u),r*np.cos(u)
    yt=r*np.tan((.5-top[:,1]/512.)*np.pi)
    return dict(bottom3d=np.column_stack((x,-np.ones(len(x)),z)).tolist(),top3d=np.column_stack((x,yt,z)).tolist(),points_1024x512=p.tolist())
def xz(g):return np.asarray(g['bottom3d'],float)[:,[0,2]]
def prism_iou(g,h):
    a,b=Polygon(valid_ring(xz(g))),Polygon(valid_ring(xz(h)))
    # Archived comparator is a corner-mean height prism, not an exact variable roof solid.
    ha=np.mean(np.asarray(g['top3d'])[:,1]-np.asarray(g['bottom3d'])[:,1]);hb=np.mean(np.asarray(h['top3d'])[:,1]-np.asarray(h['bottom3d'])[:,1])
    it=a.intersection(b).area*min(ha,hb)
    return float(100*it/(a.area*ha+b.area*hb-it))
def clean_id(x):return str(x).strip()
def flat_results(a,b):
    s=structure(a,b);d=length_dsc(a,b);bi=boundary_iou(a,b)
    return {k:v for k,v in s.items() if k not in ('pairs','answer_features','reference_features')}|d|{'boundary_iou_010':bi},s

def main(root,out):
    root,out=Path(root),Path(out);(out/'results').mkdir(exist_ok=True,parents=True);(out/'inputs').mkdir(exist_ok=True)
    feedback=root/'research/quality_ab_feedback_handoff_20261015'; prior=root/'research/quality_combination_review_20261016/pro_original/results'
    f=pd.read_csv(feedback/'FEEDBACK_30_JOINED.csv');g=readj(feedback/'geometries.json');metric=pd.read_csv(prior/'GEOMETRY_PARITY_30.csv')
    current=pd.read_csv(root/'research/descriptive_statistics_rescored_20261016/quality_records.csv')
    hist=pd.read_csv(feedback/'prior_AB/results/SCORES_1145.csv')
    refs=readj(root/'research/scope_quality_rescore_20261016/reference_catalog.json');refs={r['target_id']:r for r in refs}
    for d in (f,current,hist):
        if 'object_id' in d:d['object_id']=d.object_id.map(clean_id)
    print('HISTCOLS',list(hist.columns),flush=True)
    summary={'version':VERSION,'configuration':asdict(Config()),'execution_scope':'frozen coordinate snapshots + current eligibility/reference registry; fresh loader and LFS NOT recovered','sources':{}}
    for path in [feedback/'FEEDBACK_30_JOINED.csv',feedback/'geometries.json',feedback/'quality_ab_human_review_20261015_v1.json',prior/'GEOMETRY_PARITY_30.csv',root/'research/descriptive_statistics_rescored_20261016/quality_records.csv',root/'research/scope_quality_rescore_20261016/reference_catalog.json',feedback/'prior_AB/results/SCORES_1145.csv',root/'research/same_room_quality_curves_20261015/current_common_worker_inputs.json']:
        if path.exists():
            summary['sources'][str(path.relative_to(root))]={'sha256':sha(path),'bytes':path.stat().st_size}
    # Frozen scalar score parity, not full geometric recomputation.
    scalar=[]
    for name,d in [('current891',current),('historical1145',hist)]:
        for model in ['WQ','A10','B8L2']:
            col=model if model in d else {'A10':'Q_A10','B8L2':'Q_B8L2'}.get(model,model)
            if col not in d:continue
            vals=old_score(d.iou_2d,d.S_bottom_deg,d.dir,d.Hmean,d.Hcenter,model)
            err=vals-d[col].to_numpy(float)
            scalar.append({'set':name,'model':model,'n':len(d),'max_abs_error':float(np.max(abs(err))),'mean_abs_error':float(np.mean(abs(err)))})
    pd.DataFrame(scalar).to_csv(out/'results/scalar_parity.csv',index=False)
    # identity/reference comparison, no selection by score
    key=['object_id','reference_id']
    assert not current.duplicated('object_id').any()
    overlap=current.merge(hist,on=key,suffixes=('_current','_historical'),how='inner')
    overlap.to_csv(out/'results/same_identity_reference_overlap.csv',index=False)
    summary['current_counts']={'n':len(current),'images':current.image_id.nunique(),'workers':current.worker_id.nunique(),'by_condition':current.groupby('condition').agg(n=('object_id','size'),images=('image_id','nunique'),workers=('worker_id','nunique')).to_dict('index'),'minimum_source_workers':int(current.pool_source_workers.min()),'excluded_workers_present':sorted(set(current.worker_id)&{'W019','W026'})}
    summary['historical_counts']={'n':len(hist),'same_object_reference_overlap':len(overlap),'current_not_in_historical_same_key':len(current)-len(overlap),'note':'same ID alone not sufficient; reference geometry version must also be unchanged'}
    # All thirty remain a historical coarse human panel. Eligibility mapping is reported, not changed.
    rows=[];details={};coordinate_parity=[]
    for _,row in f.iterrows():
        m=metric[metric.case_id==row.case_id].iloc[0];ga,gr=g[row.object_id],g[row.reference_id];a,b=xz(ga),xz(gr)
        measured={'iou_2d':floor_iou(a,b),'dir':direction_rms(a),'Hmean':abs(mean_height(ga)/mean_height(gr)-1),'IoU3D100':prism_iou(ga,gr)}
        cur=current[current.object_id==row.object_id]
        cur_match=len(cur)==1 and str(cur.iloc[0].reference_id)==str(row.reference_id)
        # compare actual reference floor AND top coordinates when id is reused.
        refgeo_same=False
        if cur_match and row.reference_id in refs and refs[row.reference_id].get('geometry'):
            rg=refs[row.reference_id]['geometry']
            # cyclic serialization differs; point set complete pair matching, no transformed registration
            va=np.c_[np.asarray(gr['bottom3d']),np.asarray(gr['top3d'])];vb=np.c_[np.asarray(rg['bottom3d']),np.asarray(rg['top3d'])]
            refgeo_same=va.shape==vb.shape and min(np.max(abs(va-np.roll(vb,k,axis=0))) for k in range(len(va)))<1e-7
            if not refgeo_same and va.shape==vb.shape:refgeo_same=min(np.max(abs(va-np.roll(vb[::-1],k,axis=0))) for k in range(len(va)))<1e-7
        r=row.to_dict()|dict(current_record_present=len(cur)==1,current_reference_id_same=cur_match,current_full_reference_geometry_same=bool(refgeo_same))
        r['answer_camera_inside']=Polygon(a).contains(Point(0,0));r['reference_camera_inside']=Polygon(b).contains(Point(0,0))
        r.update({k:float(m[k]) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']})
        for k,v in measured.items():r['independent_'+k]=v;r['abs_error_'+k]=abs(v-m[k])
        gm=geometry_from_points(ga['points_1024x512'])
        coordinate_parity.append({'case':row.case_id,'max_bottom_coordinate_error':float(np.max(abs(np.array(gm['bottom3d'])-np.array(ga['bottom3d'])))),'max_top_coordinate_error':float(np.max(abs(np.array(gm['top3d'])-np.array(ga['top3d']))))})
        try:
            scores,detail=flat_results(a,b);r.update(scores);details[row.case_id]=detail
            for kappa in [1.,1.5,2.,3.]:
                cfg=replace(Config(),structure_scale=kappa)
                r[f'RCS_k{kappa:g}']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['C'],cfg)
            r['RCS_sum']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['C'],pool='sum')
            r['RCS_max']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['C'],pool='max')
            r['RCS_noSb']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['C'],keep_bottom=False)
            r['RCS_position_only']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['corner_position_C'])
            r['LDSC_replace_D']=candidate_score(m.iou_2d,m.S_bottom_deg,m.Hmean,m.Hcenter,r['length_dsc'])
            r['status']='ok'
        except ValueError as exc:r['status']=str(exc)
        rows.append(r)
    df=pd.DataFrame(rows);df.to_csv(out/'results/review30_results.csv',index=False);writej(out/'results/review30_correspondences.json',details);pd.DataFrame(coordinate_parity).to_csv(out/'results/ERP_coordinate_parity.csv',index=False)
    summary['review30']={'n':len(df),'current_identity_reference_geometry_compatible':int(df.current_full_reference_geometry_same.sum()),'independent_geometry_max_abs_errors':{k:float(df['abs_error_'+k].max()) for k in ['iou_2d','dir','Hmean','IoU3D100']},'Sb_Hcenter':'carried unchanged from frozen per-case metrics; not independently reproduced'}
    print(df[['case_id','grade','B8L2','C','RCS_k2','length_dsc','current_record_present','current_full_reference_geometry_same']].to_string(index=False),flush=True)
    # recover distinct unchanged actual responses from snapshot; never fused candidates.
    contexts=readj(root/'research/same_room_quality_curves_20261015/current_common_worker_inputs.json');records={};conflicts=[]
    for context in contexts:
        for rec in context['records']:
            oid=clean_id(rec['object_id']);item=rec|{'image_id':context['image_id'],'image_code':context['image_code']}
            if oid in records:
                if records[oid]['points']!=item['points'] or records[oid]['image_id']!=item['image_id']:conflicts.append(oid)
            else:records[oid]=item
    if conflicts:raise ValueError(f'conflicting duplicated snapshot objects {conflicts}')
    real=[];pairinputs=[];matchaudit=[]
    for oid,rec in records.items():
        c=current[current.object_id==oid]
        audit={'object_id':oid,'snapshot_image_id':rec['image_id'],'current_present':len(c)==1}
        if len(c)!=1:audit['status']='not_in_current891';matchaudit.append(audit);continue
        c=c.iloc[0];rid=str(c.reference_id);audit['reference_id']=rid
        if rec['image_id']!=c.image_id or clean_id(rec['worker'])!=clean_id(c.worker_id):raise ValueError('identity mismatch')
        if rid not in refs or not refs[rid].get('full_reference_available') or not refs[rid].get('geometry'):
            audit['status']='current_reference_geometry_unavailable';matchaudit.append(audit);continue
        ga=geometry_from_points(rec['points']);gr=refs[rid]['geometry'];a,b=xz(ga),xz(gr)
        try:
            i= floor_iou(a,b);dd=direction_rms(a);hm=abs(mean_height(ga)/mean_height(gr)-1);i3=prism_iou(ga,gr)
            errs={k:abs(v-float(c[k])) for k,v in [('iou_2d',i),('dir',dd),('Hmean',hm),('IoU3D100',i3)]}
            audit.update({'abs_error_'+k:v for k,v in errs.items()})
            # Matching archived four independent observables verifies but does not replace full loader provenance.
            if max(errs.values())>1e-5:
                audit['status']='geometry_metric_version_mismatch';matchaudit.append(audit);continue
            scores,detail=flat_results(a,b)
            d={k:c[k] for k in ['object_id','record_id','image_id','image_code','worker_id','condition','reference_id','current_target_id','use_panel','pool_source_workers','difficulty_class','WQ','A10','B8L2','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']}
            d.update(scores);d['RCS_k2']=candidate_score(i,c.S_bottom_deg,hm,c.Hcenter,scores['C']);d['RCS_noSb']=candidate_score(i,c.S_bottom_deg,hm,c.Hcenter,scores['C'],keep_bottom=False)
            d['review30_seen']=oid in set(f.object_id);real.append(d)
            pairinputs.append({'object_id':oid,'reference_id':rid,'current_target_id':c.current_target_id,'image_id':c.image_id,'worker_id':c.worker_id,'condition':c.condition,'answer':ga,'reference':gr,'frozen_Sb':float(c.S_bottom_deg),'frozen_Hcenter':float(c.Hcenter),'source':'current_common_worker_inputs.json','live_loader_verified':False})
            audit['status']='matched_frozen_current_reference';matchaudit.append(audit)
        except ValueError as exc:audit['status']='not_evaluable:'+str(exc);matchaudit.append(audit)
    pd.DataFrame(real).to_csv(out/'results/current_matched_geometry_results.csv',index=False);pd.DataFrame(matchaudit).to_csv(out/'results/current_geometry_match_audit.csv',index=False);writej(out/'inputs/current_matched_pairs.json',pairinputs)
    summary['supplement']={'distinct_snapshot_responses':len(records),'distinct_snapshot_images':len({c['image_id'] for c in contexts}),'repeated_context_conflicts':len(conflicts),'current_matched_n':len(real),'current_matched_images':len({d['image_id'] for d in real}),'match_dispositions':pd.DataFrame(matchaudit).status.value_counts().to_dict(),'interpretation':'purposive same-room subset, not a representative or blind validation set; no new grades assigned'}
    # Current reference self-comparison. Unique refs by full ordered geometry for measurement; IDs preserved.
    selfrows=[];seen={}
    for rid in current.reference_id.dropna().unique():
        if rid not in refs or not refs[rid].get('geometry'):continue
        rg=refs[rid]['geometry']
        try:
            p=xz(rg);dd=direction_rms(p);c=structure(p,p)['C']
            selfrows.append({'reference_id':rid,'image_id':refs[rid]['image_id'],'vertices':len(p),'D_reference':dd,'B8L2_self':float(old_score(1,0,dd,0,0)),'RCS_self':candidate_score(1,0,0,0,c),'C_self':c,'status':'ok'})
        except ValueError as exc:selfrows.append({'reference_id':rid,'status':str(exc)})
    pd.DataFrame(selfrows).to_csv(out/'results/current_reference_self_test.csv',index=False)
    writej(out/'results/audit_summary.json',summary)
    for src,dest in [(feedback/'FEEDBACK_30_JOINED.csv','FEEDBACK_30_JOINED.csv'),(feedback/'geometries.json','geometries30.json'),(prior/'GEOMETRY_PARITY_30.csv','frozen_metrics30.csv')]:shutil.copy2(src,out/'inputs'/dest)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);args=p.parse_args();main(args.repo,args.out)
