"""Joint ring-axis constraints and paired diagnostic scoring; never edit annotations."""
import copy
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from scipy.optimize import minimize_scalar
from tools.label_studio.panorama_studio.geometry import project_pixel
from .extend_scope_references_20261028 import ROOT,OUT as EXT
from .scope_reference_reconstruction_20261016 import source_planes,geometry,floor
from .scope_quality_scoring_20261016 import scoring_engine,score_task
from .quality_b8l2_d10_20261017 import dual_scores

OUT=EXT/'orthogonal_v2_user_axes'


def write(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def axis(points):
    e=np.roll(points,-1,axis=0)-points;l=np.linalg.norm(e,axis=1)
    assert (l>1e-10).all()
    t=np.arctan2(e[:,1],e[:,0])
    a=np.angle(np.sum(l*np.exp(4j*t)))/4
    residual=np.abs((t-a+np.pi/4)%(np.pi/2)-np.pi/4)
    return float(a),float(np.degrees(residual).max())


def constrain_ring(points,angle):
    """Least squares over shared edge-coordinate groups, with fixed edge directions."""
    p=np.asarray(points,float);c,s=np.cos(angle),np.sin(angle);rotation=np.array([[c,-s],[s,c]])
    local=p@rotation;e=np.roll(local,-1,axis=0)-local
    horizontal=np.abs(e[:,0])>=np.abs(e[:,1]);out=local.copy()
    for dim in [0,1]:
        parent=list(range(len(p)))
        def root(i):
            while parent[i]!=i:i=parent[i]
            return i
        for i,h in enumerate(horizontal):
            if (dim==1 and h) or (dim==0 and not h):parent[root((i+1)%len(p))]=root(i)
        for group in set(root(i) for i in range(len(p))):
            indices=[i for i in range(len(p)) if root(i)==group]
            out[indices,dim]=local[indices,dim].mean()
    result=out@rotation.T;old=Polygon(p);new=Polygon(result)
    newedges=np.roll(result,-1,axis=0)-result;oldedges=np.roll(p,-1,axis=0)-p
    assert new.is_valid and new.area>0 and old.exterior.is_ccw==new.exterior.is_ccw,'invalid_polygon_or_ring_reversal'
    assert (np.linalg.norm(newedges,axis=1)>1e-8).all(),'wall_collapsed'
    assert ((newedges*oldedges).sum(axis=1)>0).all(),'edge_direction_reversal'
    assert axis(result)[1]<1e-8,'not_rectilinear'
    return result


def points_for(bottom,heights):
    pairs=[]
    for (x,z),h in zip(bottom,heights):pairs.extend([project_pixel([x,h,z],1024,512),project_pixel([x,-1,z],1024,512)])
    np.testing.assert_allclose(floor(pairs),bottom,atol=1e-8)
    np.testing.assert_allclose(np.asarray(geometry(pairs)['top3d'])[:,1],heights,atol=1e-8)
    return pairs


def user_axis_projection(p):
    initial,residual=axis(p)
    margin=min(np.pi/8,np.radians(45-residual)*.9)
    assert margin>0,'no_stable_edge_direction_assignment'
    def loss(a):
        try:return float(((constrain_ring(p,a)-p)**2).sum())
        except AssertionError:return float('inf')
    fit=minimize_scalar(loss,bounds=(initial-margin,initial+margin),method='bounded',options={'xatol':1e-14})
    assert fit.success and np.isfinite(fit.fun)
    assert abs(fit.x-initial)<margin*.999,'axis_solution_at_search_boundary'
    return float(fit.x),constrain_ring(p,fit.x)


def build():
    OUT.mkdir(exist_ok=True)
    plan=dict(version='orthogonal_scope_v2_user_axes_20261028',scope='43 confirmed spaces plus two explicit user revisions and all 30 saved manual GT, OOS audit only',
        axis='scope: unrounded source axis; manual GT: optimize joint vertex displacement around user geometry common axis, never snap back to MP3D shape',
        solver='joint least squares equality constraints per horizontal/vertical edge, original order and edge direction fixed',
        micro_screen=dict(max_ERP_pixel_move=.1,max_3D_h_move=.002,max_relative_area_percent=.05),
        screen_meaning='engineering screen for precision-only auto candidates, not a quality tolerance; explicit revised GT always manual review',
        heights='retain original full-pair heights or authorized explicit source plane; retain height-break vertices',
        scoring='same Manual objects per reference, original unorthogonal full reference or same-height diagnostic candidate; no max-Q selection',
        adoption='independent version only; no formal references or labels overwritten; no new fusion')
    if (OUT/'PLAN.json').exists():assert json.loads((OUT/'PLAN.json').read_text(encoding='utf-8'))==plan
    else:write('PLAN.json',plan)
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    planes=source_planes({'data':data})
    source_by_image={o['image_id']:planes[o['object_id']] for o in data['objects'] if o['object_kind']=='gt_original'}
    refs=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json').read_text(encoding='utf-8'))
    lookup={r['target_id']:r for r in refs}
    views=json.loads((ROOT/'research/data/scope_redundant_vertices_20261016/scope_views.json').read_text(encoding='utf-8'))
    extension={r['target_id']:r for r in json.loads((EXT/'REFERENCES.json').read_text(encoding='utf-8'))}
    selected=[(lookup[v['target_id']],v,'confirmed_scope') for v in views]
    selected += [(r,None,'explicit_user_revised_GT') for r in refs if r['role']=='user_revised_gt']
    assert len(selected)==45
    inventory=pd.read_json(ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json')
    manual=[]
    for o in data['objects']:
        if o['object_kind']!='gt_manual_revision':continue
        ref=lookup.get(o['object_id']);own=inventory[inventory.image_id.eq(o['image_id'])]
        oos=bool(own.is_oos.any());current=bool(ref and ref['current_target']);holds=ref['image_analysis_hold_reasons'] if ref else []
        status='current_in_use' if current and not oos and not holds else 'OOS_no_orthogonalization' if oos else 'excluded_hold' if holds else 'historical_not_current'
        manual.append(dict(object_id=o['object_id'],image=o['image_code'],image_id=o['image_id'],axis_residual_deg=axis(floor(o['points_1024x512']))[1],in_current_catalog=ref is not None,current_target=current,is_oos=oos,holds='|'.join(holds),quality_usable_bound=int((own.quality_usable&own.chosen_target_id.eq(o['object_id'])).sum()),adoption=status))
        if not oos:
            if ref is None:
                ref=dict(target_id=o['object_id'],image_id=o['image_id'],image_code=o['image_code'],points_1024x512=o['points_1024x512'],floor_xz_h=floor(o['points_1024x512']).tolist(),full_reference_available=True)
            selected.append((ref,None,'current_saved_manual_GT' if status=='current_in_use' else 'historical_or_held_manual_GT'))
    write('MANUAL_GT_EXTENSION_PLAN.json',dict(reason='follow-up authorization to inspect currently adopted manual GT beyond two explicit 20261015 revisions',
        selection='all 30 inspected; four OOS never orthogonalized; current, held and historical non-OOS candidates explicitly separated',saved_manual_versions=len(manual),additional_candidates=len(selected)-45,
        adoption='all saved-manual candidates require review, even if movement is small; no formal replacement'))
    pd.DataFrame(manual).to_csv(OUT/'SAVED_MANUAL_GT_AUDIT.csv',index=False,encoding='utf-8')
    results=[];audit=[]
    for ref,view,kind in selected:
        iid=ref['image_id'];tid=ref['target_id'];source=source_by_image.get(iid)
        source_angle=source_residual=None
        if source:
            raw=source['source_json_geometry']
            xyz=np.array([p['xyz'] for p in raw['layoutPoints']['points']]);radius=np.linalg.norm(xyz[:,[0,2]],axis=1)/raw['cameraHeight']
            az=(np.array([p['coords'][0] for p in raw['layoutPoints']['points']])-.5)*2*np.pi
            source_floor=np.column_stack([radius*np.sin(az),-radius*np.cos(az)])
            source_angle,source_residual=axis(source_floor)
        base=extension.get(tid,ref)
        oldpoints=base.get('points_1024x512');rawfloor=np.array(base['floor_xz_h'])
        original_complete=bool(ref['full_reference_available'])
        if oldpoints is None:
            heights=np.full(len(rawfloor),source['plane'][2]);oldpoints=points_for(rawfloor,heights)
        else:heights=np.asarray(geometry(oldpoints)['top3d'])[:,1]
        kept=list(range(len(rawfloor)));mapping=None
        if view and ref['image_code']!='e9zR4mvMWw7-09':
            np.testing.assert_allclose(rawfloor,view['original_floor'],atol=1e-8)
            v=view['precision_floor_view'];candidate=[i-1 for i in v['kept_1based']]
            # Keep all original vertices when a removed node carries a height break.
            removable=True
            for i in set(kept)-set(candidate):
                before=max((j for j in candidate if j<i),default=candidate[-1]);after=min((j for j in candidate if j>i),default=candidate[0])
                edge=rawfloor[after]-rawfloor[before];t=np.dot(rawfloor[i]-rawfloor[before],edge)/np.dot(edge,edge)
                if abs(heights[i]-(heights[before]+t*(heights[after]-heights[before])))>1e-8:removable=False
            if removable:kept=candidate;mapping=v
        p=rawfloor[kept];h=heights[kept];fit_angle,oldres=axis(p)
        chosen_angle=source_angle if source_residual is not None and source_residual<1e-6 else fit_angle
        row=dict(image=ref['image_code'],image_id=iid,target_id=tid,kind=kind,raw_nodes=len(rawfloor),kept_nodes=len(p),source_axis_residual_deg=source_residual,before_axis_residual_deg=oldres,original_complete=original_complete)
        try:
            if kind=='confirmed_scope':new=constrain_ring(p,chosen_angle)
            else:chosen_angle,new=user_axis_projection(p)
        except AssertionError as exc:
            audit.append(dict(row,status='construction_failed',reason=str(exc)));continue
        newpoints=points_for(new,h);baseline=np.asarray(oldpoints).reshape(-1,2,2)[kept].reshape(-1,2)
        pix=np.asarray(newpoints)-baseline;pix[:,0]=(pix[:,0]+512)%1024-512
        move=float(np.linalg.norm(new-p,axis=1).max());px=float(np.linalg.norm(pix,axis=1).max())
        area=100*(Polygon(new).area-Polygon(rawfloor).area)/Polygon(rawfloor).area
        symmetric=100*Polygon(new).symmetric_difference(Polygon(rawfloor)).area/Polygon(rawfloor).area
        micro=px<=.1 and move<=.002 and symmetric<=.05 and kind=='confirmed_scope' and source_residual is not None and source_residual<1e-6
        status='precision_candidate' if micro else 'requires_review'
        audit.append(dict(row,status=status,after_axis_residual_deg=axis(new)[1],max_move_h=move,max_move_pixel=px,area_change_percent=area,symmetric_difference_percent=symmetric))
        results.append(dict(**row,status=status,reference_version='orthogonal_scope_v2_user_axes_20261028',axis_radians=chosen_angle,axis_source='user_geometry_minimum_displacement' if kind!='confirmed_scope' else 'unrounded_source' if source_residual is not None and source_residual<1e-6 else 'fitted_requires_review',
            original_points=oldpoints,original_floor=rawfloor.tolist(),kept_1based=[i+1 for i in kept],source_mapping=mapping,
            floor_xz_h=new.tolist(),points_1024x512=newpoints,geometry=geometry(newpoints),source_plane=source['plane'] if source else None,
            baseline_identity='existing_complete_reference' if original_complete else 'same_height_unorthogonal_diagnostic_candidate',adopted=False))
    pd.DataFrame(audit).to_csv(OUT/'GEOMETRY_AUDIT.csv',index=False,encoding='utf-8')
    write('REFERENCES.json',results)
    print(pd.DataFrame(audit).groupby(['kind','status']).size().to_string(),flush=True)
    return results,data


def compare(refs,data):
    inventory=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json').read_text(encoding='utf-8'))
    q={r['object_id']:r for r in inventory};objects=[o for o in data['objects'] if o['object_kind']=='annotation' and o['condition']=='manual']
    metrics=['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']
    rows=[]
    with scoring_engine() as (engine,models),(OUT/'PAIRED_MEASUREMENTS.jsonl').open('w',encoding='utf-8') as log:
        for ref in refs:
            own=[o for o in objects if o['image_id']==ref['image_id']]
            for obj in own:
                pair={}
                for name,points in [('before',ref['original_points']),('after',ref['points_1024x512'])]:
                    task=dict(object_id=obj['object_id'],image_id=obj['image_id'],worker_id=obj['worker_id'],condition='manual',current_target_id=ref['target_id'],reference_version=ref['reference_version']+':'+name,annotation_points=obj['points_1024x512'],reference_points=points)
                    result=score_task(task,engine,models)
                    if result['score_status']=='complete':result.update(dual_scores(result,models))
                    pair[name]=result
                record=q[obj['object_id']];both=all(r['score_status']=='complete' for r in pair.values())
                row=dict(target_id=ref['target_id'],image=ref['image'],object_id=obj['object_id'],worker_id=obj['worker_id'],kind=ref['kind'],candidate_status=ref['status'],baseline_identity=ref['baseline_identity'],original_bound_target=record['chosen_target_id'],original_quality_usable=record['quality_usable'],original_exclusions='|'.join(record['quality_exclusion_reasons']),common_score=both)
                for m in metrics:
                    row[m+'_before']=pair['before'].get(m);row[m+'_after']=pair['after'].get(m)
                    row[m+'_delta']=pair['after'][m]-pair['before'][m] if both else None
                rows.append(row);log.write(json.dumps(dict(object_id=obj['object_id'],target_id=ref['target_id'],results=pair),ensure_ascii=False,allow_nan=False)+'\n')
            log.flush();print('paired',ref['image'],len(own),flush=True)
    d=pd.DataFrame(rows);d.to_csv(OUT/'PAIRED_SCORES.csv',index=False,encoding='utf-8')
    summaries=[]
    for (target,image),g in d[d.common_score].groupby(['target_id','image']):
        r=dict(target_id=target,image=image,records=len(g),workers=g.worker_id.nunique(),kind=g.kind.iloc[0],candidate_status=g.candidate_status.iloc[0])
        for m in metrics:
            r[m+'_mean_delta']=g[m+'_delta'].mean();r[m+'_median_abs_delta']=g[m+'_delta'].abs().median();r[m+'_max_abs_delta']=g[m+'_delta'].abs().max()
        for m in ['B8L2','D10']:
            a=g[m+'_before'].rank(method='min');b=g[m+'_after'].rank(method='min')
            r[m+'_changed_ranks']=int((a!=b).sum());r[m+'_max_rank_shift']=float((a-b).abs().max())
        summaries.append(r)
    pd.DataFrame(summaries).to_csv(OUT/'SCORE_SUMMARY.csv',index=False,encoding='utf-8')
    assert d.loc[d.common_score,'dir_delta'].eq(0).all(),'annotation-only direction changed'
    write('CHECKS.json',dict(reference_candidates=len(refs),paired_objects=len(d),common_scored=int(d.common_score.sum()),dir_delta_max=float(d.dir_delta.abs().max()),new_fusion=0,annotations_changed=False,formal_reference_adoptions=0))


def figure():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    refs=json.loads((OUT/'REFERENCES.json').read_text(encoding='utf-8'))
    selected=[r for r in refs if r['kind']=='explicit_user_revised_GT']
    audit=pd.read_csv(OUT/'GEOMETRY_AUDIT.csv');tid=audit[audit.kind.eq('confirmed_scope')].sort_values('max_move_pixel').iloc[-1].target_id
    selected.append(next(r for r in refs if r['target_id']==tid))
    fig,axes=plt.subplots(3,2,figsize=(16,11),layout='constrained',gridspec_kw={'width_ratios':[2.4,1]})
    for axs,r in zip(axes,selected):
        photo=ROOT/'data/mp3d_layout/img_v'/ (r['image_id']+'.jpg')
        axs[0].imshow(Image.open(photo),extent=[0,1024,512,0])
        for points,color,label in [(r['original_points'],'#00ddcc','修正前'),(r['points_1024x512'],'#ff4488','正交候选')]:
            g=geometry(points)
            for level in ['top3d','bottom3d']:
                vertices=np.asarray(g[level]);pixels=[]
                for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
                    for t in np.linspace(0,1,100):pixels.append(project_pixel(a*(1-t)+b*t,1024,512))
                pixels=np.asarray(pixels);jumps=np.flatnonzero(np.abs(np.diff(pixels[:,0]))>512)+1;pixels[jumps]=np.nan
                axs[0].plot(pixels[:,0],pixels[:,1],color=color,lw=1,alpha=.9,label=label if level=='bottom3d' else None)
            p=floor(points);closed=np.vstack([p,p[0]])
            axs[1].plot(closed[:,0],closed[:,1],color=color,lw=1.5,marker='o',ms=3,label=label)
        for i,(x,z) in enumerate(r['floor_xz_h']):axs[1].annotate(str(r['kept_1based'][i]),(x,z),fontsize=9)
        axs[1].scatter([0],[0],color='black',s=12);axs[1].set_aspect('equal');axs[1].grid(alpha=.2)
        row=audit[audit.target_id.eq(r['target_id'])].iloc[0]
        axs[0].set_title(f"{r['image']}：最大移动 {row.max_move_pixel:.4f} px；{r['status']}")
        axs[0].set_xlim(0,1024);axs[0].set_ylim(512,0);axs[0].axis('off');axs[0].legend(loc='lower left',fontsize=8)
        axs[1].set_title('俯视图，标注保留的原编号');axs[1].legend(fontsize=8)
    fig.suptitle('正交候选：人工GT按用户几何拟合轴，确认裁切沿源共同轴\n原答未修改；叠线用于查看范围，不能单凭Q增减决定采用',fontsize=13)
    fig.savefig(OUT/'正交候选_原图与俯视对照.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    refs,data=build();compare(refs,data);figure()
