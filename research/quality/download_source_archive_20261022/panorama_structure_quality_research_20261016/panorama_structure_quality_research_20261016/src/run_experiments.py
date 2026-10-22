from pathlib import Path
from dataclasses import replace,asdict
import itertools,json,math,hashlib,sys
import numpy as np,pandas as pd
from shapely.geometry import Polygon,LineString
from structure_quality import *
from run_audit import readj,writej,xz,prism_iou
ROOT=Path(__file__).resolve().parents[1]


def angular_boundary_mean(a,b,step_deg=.1):
    """Synthetic-only Sb analogue: spherical arc-length midpoint integration.
    Not asserted to reproduce the current engine's Sb sampling convention.
    """
    def samples(p):
        rr=rays(p);arr=[];weights=[]
        for x,y in zip(rr,np.roll(rr,-1,axis=0)):
            t=np.arctan2(np.linalg.norm(np.cross(x,y)),x@y)
            n=max(1,int(np.ceil(np.degrees(t)/step_deg)));f=(np.arange(n)+.5)/n
            arr.append((np.sin((1-f)*t)[:,None]*x+np.sin(f*t)[:,None]*y)/np.sin(t));weights.append(np.full(n,t/n))
        return np.concatenate(arr),np.concatenate(weights)
    def dists(q,p):
        r=rays(p);s=np.roll(r,-1,axis=0)
        n=np.cross(r,s);n/=np.linalg.norm(n,axis=1)[:,None]
        dot=q@n.T;projection=q[:,None]-dot[:,:,None]*n[None];projection/=np.linalg.norm(projection,axis=2)[:,:,None]
        total=np.arctan2(np.linalg.norm(np.cross(r,s),axis=1),np.sum(r*s,axis=1))
        d1=np.arctan2(np.linalg.norm(np.cross(projection,r[None]),axis=2),np.sum(projection*r[None],axis=2))
        d2=np.arctan2(np.linalg.norm(np.cross(projection,s[None]),axis=2),np.sum(projection*s[None],axis=2))
        on=(d1+d2)<=total[None]+1e-9
        end=np.arctan2(np.linalg.norm(np.cross(q[:,None],r[None]),axis=2),q@r.T)
        dd=np.where(on,np.arcsin(np.clip(abs(dot),0,1)),np.inf)
        return np.minimum(dd.min(axis=1),end.min(axis=1))
    qa,wa=samples(a);qb,wb=samples(b)
    da,db=dists(qa,b),dists(qb,a)
    return float(np.degrees((wa@da+wb@db)/(wa.sum()+wb.sum())))


def rectangle(s=2.):return np.array([[-s,-s],[s,-s],[s,s],[-s,s]],float)
def bump(depth=.3,width=.5,x0=0,s=2.):
    # Outward protrusion in +z. Includes four added turns, valid and orthogonal.
    return np.array([[-s,-s],[s,-s],[s,s],[x0+width/2,s],[x0+width/2,s+depth],[x0-width/2,s+depth],[x0-width/2,s],[-s,s]],float)
def inward(depth=.3,width=.5,x0=0,s=2.):return bump(-depth,width,x0,s)
def heightgeom(p,heights):
    h=np.broadcast_to(heights,(len(p),))
    return dict(bottom3d=np.c_[p[:,0],-np.ones(len(p)),p[:,1]].tolist(),top3d=np.c_[p[:,0],h-1,p[:,1]].tolist())


def real_evaluations():
    d=pd.read_csv(ROOT/'results/review30_results.csv');d=d.rename(columns={k:'RCS01_'+k[4:] for k in d if k.startswith('RCS_')});g=readj(ROOT/'inputs/geometries30.json');rows=[];details={}
    configs={'working':working_config(),'initial_tight':Config(),
             'no_merge':replace(working_config(),same_sign_merge_deg=0),
             'k1':replace(working_config(),structure_scale=1),
             'k2':replace(working_config(),structure_scale=2),
             'narrow_position':replace(working_config(),position_free_deg=2,position_zero_deg=6),
             'narrow_angle':replace(working_config(),angle_free_deg=5,angle_zero_deg=30),
             'merge2':replace(working_config(),same_sign_merge_deg=2),
             'merge4':replace(working_config(),same_sign_merge_deg=4),
             'salience005_020':replace(working_config(),salience_free_h=.05,salience_full_h=.2)}
    sensitivity=[]
    for _,r in d.iterrows():
        a,b=xz(g[r.object_id.strip()]),xz(g[r.reference_id]);s=structure(a,b,working_config());details[r.case_id]=s
        out=r.to_dict()|{k:v for k,v in s.items() if k not in ('pairs','answer_features','reference_features')}
        out['Q_RCS02']=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,s['C'],working_config())
        out['Q_RCS02_noSb']=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,s['C'],working_config(),keep_bottom=False)
        out['Q_RCS02_no_structure']=float(old_score(r.iou_2d,r.S_bottom_deg,0,r.Hmean,r.Hcenter,'noD'))
        out['Q_LDSC_only_replacement']=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,r.length_dsc,working_config())
        out['Q_RCS02_plus_intrinsic_D']=100/(100/out['Q_RCS02']+1.5*r.dir**2/(r.dir**2+64))
        out['algorithm_id']=VERSION;rows.append(out)
        for name,cfg in configs.items():
            ss=structure(a,b,cfg);q=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,ss['C'],cfg)
            sensitivity.append({'case_id':r.case_id,'phase':r.phase,'current_same_reference':r.current_full_reference_geometry_same,'grade':r.grade,'configuration':name,'C':ss['C'],'Q':q})
    pd.DataFrame(rows).to_csv(ROOT/'results/review30_working.csv',index=False);writej(ROOT/'results/review30_working_correspondences.json',details);pd.DataFrame(sensitivity).to_csv(ROOT/'results/working_parameter_sensitivity.csv',index=False);writej(ROOT/'results/working_and_ablation_configs.json',{k:asdict(v) for k,v in configs.items()})
    # Current 227 fixed-reference responses, no fitted human labels.
    current=pd.read_csv(ROOT/'results/current_matched_geometry_results.csv').set_index('object_id');current=current.rename(columns={k:'RCS01_'+k[4:] for k in current if k.startswith('RCS_')});pairs=readj(ROOT/'inputs/current_matched_pairs.json');rows=[]
    for p in pairs:
        r=current.loc[p['object_id']];a,b=xz(p['answer']),xz(p['reference']);s=structure(a,b,working_config())
        out=r.to_dict()|{'object_id':p['object_id']};out.update({k:v for k,v in s.items() if k not in ('pairs','answer_features','reference_features')})
        out['Q_RCS02']=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,s['C'],working_config());out['Q_RCS02_noSb']=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,s['C'],working_config(),keep_bottom=False)
        out['Q_noD']=float(old_score(r.iou_2d,r.S_bottom_deg,0,r.Hmean,r.Hcenter,'noD'));out['algorithm_id']=VERSION
        for name in ['k1','k2','merge2','merge4','salience005_020']:
            cfg=configs[name];ss=structure(a,b,cfg);out['Q_'+name]=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,ss['C'],cfg)
        out['answer_geometry_sha256']=hashlib.sha256(json.dumps(p['answer'],sort_keys=True,separators=(',',':')).encode()).hexdigest();out['reference_geometry_sha256']=hashlib.sha256(json.dumps(p['reference'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        rows.append(out)
    pd.DataFrame(rows).to_csv(ROOT/'results/current227_working.csv',index=False)


def synthetic_experiments():
    r=rectangle();inputs=[]
    def add(name,a,b=r,family='',severity=0,hm=0,hc=0):inputs.append({'case':name,'family':family,'severity':severity,'answer':a.tolist(),'reference':b.tolist(),'Hmean_control':hm,'Hcenter_control':hc})
    add('identity',r,family='identity')
    for d in [.005,.01,.02,.04,.08,.12,.3,.6,1.0]:
        add(f'omit_bump_depth_{d:g}',r,bump(d),family='omission',severity=d)
        add(f'add_bump_depth_{d:g}',bump(d),r,family='spurious_structure',severity=d)
    for e in [.001,.01,.03,.1,.2,.4]:
        a=np.array([[-2,-2],[2,-2],[2,2-e],[2-e,2],[-2,2]],float)
        add(f'bevel_{e:g}',a,family='tiny_bevel',severity=e)
    add('wrong_bump_position',bump(.3,x0=.9),bump(.3,x0=-.9),family='same_count_wrong_position')
    add('inward_instead_outward',inward(.3),bump(.3),family='same_count_wrong_sign')
    for t in [.01,.03,.1,.2,.5]:add(f'translate_x_{t:g}',r+[t,0],family='translation',severity=t)
    for s in [1.01,1.05,1.1,1.2,1.5]:add(f'scale_{s:g}',r*s,family='scale',severity=s-1)
    for ang in [.5,1,2,3,5,10,20,45]:
        t=np.radians(ang);rot=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]]);add(f'rotate_{ang:g}',r@rot,family='relative_rotation',severity=ang)
    for shear in [.01,.03,.05,.1,.2]:
        a=r@np.array([[1,shear],[0,1.]])
        add(f'shear_{shear:g}',a,family='shear',severity=shear)
        add(f'sheared_reference_self_{shear:g}',a,a,family='reference_self',severity=shear)
        add(f'straighten_reference_{shear:g}',r,a,family='reference_straightening',severity=shear)
    for h in [.01,.03,.05,.1,.2,.4]:
        add(f'global_height_error_{h:g}',r,family='height_mean_algebraic',severity=h,hm=h)
        add(f'local_height_error_{h:g}',r,family='height_center_algebraic',severity=h,hc=h)
    rows=[]
    for q in inputs:
        a,b=np.asarray(q['answer']),np.asarray(q['reference']);s=structure(a,b,working_config());initial=structure(a,b,Config());i=floor_iou(a,b);dd=direction_rms(a);sb=angular_boundary_mean(a,b);ld=length_dsc(a,b);bi=boundary_iou(a,b)
        hm,hc=q['Hmean_control'],q['Hcenter_control']
        row={k:v for k,v in q.items() if k not in ('answer','reference')}|{'I':i,'D':dd,'Sb_synthetic_arc_analogue':sb,'C':s['C'],'C_initial':initial['C'],'structure_precision':s['precision'],'structure_recall':s['recall'],**ld,'boundary_iou':bi,'B8L2_arc_analogue':float(old_score(i,sb,dd,hm,hc)),'Q_RCS02_arc_analogue':candidate_score(i,sb,hm,hc,s['C'],working_config()),'Q_RCS02_floor_only':candidate_score(i,0,hm,hc,s['C'],working_config()),'Q_initial_arc_analogue':candidate_score(i,sb,hm,hc,initial['C'],Config()),'B_floor_only':float(old_score(i,0,dd,hm,hc))}
        rows.append(row)
    pd.DataFrame(rows).to_csv(ROOT/'results/synthetic_controls.csv',index=False);writej(ROOT/'inputs/synthetic_geometry_controls.json',inputs)
    # A true same-surface subdivision exposes corner-mean prism comparator's representation dependence.
    p=r;h=np.array([1.,2.,3.,2.]);g=heightgeom(p,h);mid=(p[0]+p[1])/2;pp=np.insert(p,1,mid,axis=0);hh=np.insert(h,1,(h[0]+h[1])/2);gg=heightgeom(pp,hh)
    special={'description':'identical piecewise-linear wall upper edge; add one exact interpolated same-wall vertex','original_wall_mean_height':mean_height(g),'subdivided_wall_mean_height':mean_height(gg),'original_corner_mean_height':float(h.mean()),'subdivided_corner_mean_height':float(hh.mean()),'same_geometry_corner_mean_prism_IoU100':prism_iou(g,gg),'structure_C':structure(p,pp,working_config())['C'],'geometry_original':g,'geometry_subdivided':gg}
    writej(ROOT/'results/height_subdivision_counterexample.json',special)


def checks_and_descriptions():
    ds=pd.read_csv(ROOT/'results/review30_working.csv');c=pd.read_csv(ROOT/'results/current227_working.csv')
    rank={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}
    results=[];reversals=[]
    for subset,z in [('historical_ordinary24',ds[ds.case_id.str.startswith('N')]),('current_same_reference20',ds[ds.current_full_reference_geometry_same]),('historical_doorway6',ds[ds.case_id.str.startswith('D')])]:
        for model in ['WQ','A10','B8L2','IoU3D100','Q_RCS02','Q_RCS02_noSb','Q_LDSC_only_replacement']:
            den=bad=ties=0
            for i in range(len(z)):
                for j in range(i):
                    a,b=z.iloc[i],z.iloc[j];diff=rank[a.grade]-rank[b.grade]
                    if diff==0:continue
                    den+=1;sd=a[model]-b[model]
                    if abs(sd)<1e-8:ties+=1
                    elif diff*sd<0:
                        bad+=1;reversals.append({'subset':subset,'model':model,'case_a':a.case_id,'grade_a':a.grade,'score_a':a[model],'case_b':b.case_id,'grade_b':b.grade,'score_b':b[model]})
            results.append({'subset':subset,'model':model,'n_cases':len(z),'different_grade_pairs':den,'reversed_pairs':bad,'score_ties':ties,'inference':'descriptive_only_correlated_pairs_post_exposure'})
    pd.DataFrame(results).to_csv(ROOT/'results/ordinal_descriptions.csv',index=False);pd.DataFrame(reversals).to_csv(ROOT/'results/ordinal_reversals.csv',index=False)
    # No inference from these scalar trends. No scores fitted to these rows.
    sums=[]
    for (image,condition),z in c.groupby(['image_id','condition']):
        sums.append({'image_id':image,'image_code':z.image_code.iloc[0],'condition':condition,'n':len(z),'B_mean':z.B8L2.mean(),'RCS_mean':z.Q_RCS02.mean(),'mean_delta':(z.Q_RCS02-z.B8L2).mean(),'max_decrease':(z.Q_RCS02-z.B8L2).min(),'max_increase':(z.Q_RCS02-z.B8L2).max()})
    pd.DataFrame(sums).to_csv(ROOT/'results/current227_image_descriptions.csv',index=False)
    c.assign(delta=c.Q_RCS02-c.B8L2).sort_values('delta').to_csv(ROOT/'results/current227_delta_ordered.csv',index=False)
    # Boundary quadrature convergence on the 30 unaltered stored pairs.
    g=readj(ROOT/'inputs/geometries30.json');conv=[]
    for _,row in ds.iterrows():
        a,b=xz(g[row.object_id.strip()]),xz(g[row.reference_id]);v={s:length_dsc(a,b,step=s)['length_dsc'] for s in [.01,.005,.0025]}
        conv.append({'case':row.case_id,'DSC_step_01':v[.01],'DSC_step_005':v[.005],'DSC_step_0025':v[.0025],'max_step_difference':max(v.values())-min(v.values())})
    pd.DataFrame(conv).to_csv(ROOT/'results/boundary_quadrature_convergence.csv',index=False)
    # Scope summary strictly reports what was executed.
    qself=pd.read_csv(ROOT/'results/current_reference_self_test.csv')
    summary={'working_algorithm':VERSION,'working_config':asdict(working_config()),'current_geometry_n':len(c),'images':c.image_id.nunique(),'human_review_current_compatible_n':int(ds.current_full_reference_geometry_same.sum()),'overlap_current227_human30':int(c.review30_seen.sum()),'eligible_union_n':len(c)+int(ds.current_full_reference_geometry_same.sum())-int(c.review30_seen.sum()),'current227_condition_counts':c.condition.value_counts().to_dict(),'review30_camera_outside_cases':ds[~ds.answer_camera_inside].case_id.tolist(),'current_references_n':len(qself),'current_reference_B_self_min':float(qself.B8L2_self.min()),'current_reference_B_self_below99':int((qself.B8L2_self<99).sum()),'current_reference_B_self_below95':int((qself.B8L2_self<95).sum()),'boundary_quadrature_max_DSC_change':float(max(x['max_step_difference'] for x in conv)),'current227_mean_delta_descriptive_only':float((c.Q_RCS02-c.B8L2).mean()),'current227_delta_min':float((c.Q_RCS02-c.B8L2).min()),'current227_delta_max':float((c.Q_RCS02-c.B8L2).max()),'limitations':['not a fresh loader execution','LFS and release binaries unavailable','original panoramas not viewed','Sb and Hcenter frozen, not independently remeasured','no new blind human labels','no doorway-specific parameter fitting','no downstream worker/fusion replay','geometric feature significance is not semantic necessity']}
    writej(ROOT/'results/experiment_summary.json',summary)
    print(ds[['case_id','grade','B8L2','C','Q_RCS02','Q_RCS02_noSb','Q_LDSC_only_replacement']].round(4).to_string(index=False));print(json.dumps(summary,ensure_ascii=False,indent=2));print(pd.DataFrame(results).to_string(index=False))

if __name__=='__main__':
    real_evaluations();synthetic_experiments();checks_and_descriptions()
