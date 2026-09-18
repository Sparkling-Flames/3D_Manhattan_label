"""Post-hoc model/crowd comparison; predictions never contribute human votes.
Uses frozen yaw-zero outputs for primary comparison, other yaws only for sensitivity.
Geometry coverage is metric coverage, NOT semantic correctness or probability calibration.
"""
from pathlib import Path
import json,gzip,itertools,collections,hashlib
import numpy as np,pandas as pd
import legacy_reproduction as old
import spherical_followup as sp
R=Path(__file__).resolve().parents[1]
FAMILIES=['bi_enclosed','bi_extended','hohonet','ulayout_boundary']
def curve_of_points(ns,p):
    n=ns['normalize_geometry'](p)
    if not n['valid']:return None,n['reason']
    return sp.spherical_boundary(old.pairs3(n))
def valid_curve(a):
    return a.shape==(2,1024) and np.isfinite(a).all() and (a[0]<a[1]).all() and (a>=-.5).all() and (a<512).all()
def run():
    inp=R/'inputs/frozen';out=R/'results';out.mkdir(exist_ok=True)
    data=json.loads((inp/'key39/data.json').read_text());ns=old.legacy_functions(data)
    human=[json.loads(l) for l in gzip.open(inp/'human/responses.jsonl.gz','rt')]
    audit=pd.read_csv(out/'all_response_audit.csv');kept=audit[audit.geometry_eligible].set_index('id');images=sorted(set(kept.image_id))
    cv={};availability=[];features=[];compact={};distrows=[];summ=[];target=[]
    for iid in images:
        arrays={f:np.load(R/'model_snapshot'/f/(iid+'.npz'),allow_pickle=False)for f in ['hohonet','bilayout','ulayout']}
        cv[iid]={};compact[iid]={};feat={'image_id':iid,'building':iid.split('_')[0]}
        for yaw in [0,90,180,270]:
            z=arrays['bilayout'];h=arrays['hohonet'];u=arrays['ulayout'];ys={}
            for name,zs,key in [('bi_enclosed',z,f'yaw{yaw}__post__corners_enclosed'),('bi_extended',z,f'yaw{yaw}__post__corners_extended'),('hohonet',h,f'yaw{yaw}__post__cor_id')]:
                p=zs[key];a,reason=curve_of_points(ns,p.tolist());ys[name]=a
                availability.append(dict(image_id=iid,source=name,yaw=yaw,available=a is not None,reason=reason,point_count=len(p)))
                if yaw==0:
                    compact[iid][name]=p.tolist();feat[name+'_corners']=len(p)//2
            name='ulayout_boundary';a=u[f'yaw{yaw}_boundary_pixels_float'].astype(float)
            ok=valid_curve(a);ys[name]=a if ok else None
            availability.append(dict(image_id=iid,source=name,yaw=yaw,available=ok,reason='ok'if ok else'invalid_dense_boundary',point_count=None))
            if yaw==0:compact[iid][name]=a.tolist()
            cv[iid][yaw]=ys
        for a,b in itertools.combinations(FAMILIES,2):
            aa,bb=cv[iid][0][a],cv[iid][0][b]
            feat['gap_'+a+'__'+b]=sp.solid_iou(aa,bb)if aa is not None and bb is not None else np.nan
        for name in FAMILIES:
            values=[sp.solid_iou(cv[iid][0][name],cv[iid][yaw][name]) for yaw in [90,180,270]if cv[iid][0][name]is not None and cv[iid][yaw][name]is not None]
            feat['rotation_'+name]=np.mean(values)if values else np.nan
        features.append(feat)
    frame=pd.DataFrame(features).set_index('image_id')
    for r in human:
        cid=r['canonical_annotation_id']
        if cid not in kept.index:continue
        a,reason=curve_of_points(ns,r['effective_points_1024x512'])
        availability.append(dict(image_id=r['image_id'],id=cid,source='human',yaw=0,available=a is not None,reason=reason,point_count=r['effective_point_count']))
        if a is None:continue
        iid=r['image_id'];y=cv[iid][0]
        row=dict(id=cid,image_id=iid,code=kept.loc[cid,'code'],worker=r['worker_id'],condition=r['raw_condition'],building=r['building_id'],imputed_point=r['imputed_point'])
        row['all_models_available']=all(y[f] is not None for f in FAMILIES)
        for name in FAMILIES:row['d_'+name]=sp.solid_iou(a,y[name])if y[name]is not None else np.nan
        row['bi_gap']=frame.loc[iid,'gap_bi_enclosed__bi_extended']
        delta=row['d_bi_extended']-row['d_bi_enclosed'];row['bi_distance_advantage_enclosed']=delta
        for cut in [.05,.1,.2]:
            de,dx=row['d_bi_enclosed'],row['d_bi_extended']
            state='unavailable'if not np.isfinite([de,dx]).all()else('both'if max(de,dx)<=cut else('enclosed_only'if de<=cut else('extended_only'if dx<=cut else'neither')))
            row[f'bi_state_{cut:.2f}']=state
        row['candidate_direction_status']='heads_too_close'if row['bi_gap']<.02 else('both_far'if min(row['d_bi_enclosed'],row['d_bi_extended'])>.1 else('near_tie'if abs(delta)<.01 else('enclosed_closer'if delta>0 else'extended_closer')))
        distrows.append(row)
    df=pd.DataFrame(distrows);df.to_csv(out/'human_model_distances.csv',index=False)
    for (iid,cond),rows in df.groupby(['image_id','condition']):
        cm=rows[rows.all_models_available];common=dict(image_id=iid,code=rows.iloc[0].code,condition=cond,building=rows.iloc[0].building,N_human_spherical=len(rows),N_all_models=len(cm))
        for cut in [.05,.1,.2]:
            for names in [['bi_enclosed'],['bi_extended'],['hohonet'],['ulayout_boundary'],['bi_enclosed','bi_extended'],['hohonet','ulayout_boundary'],FAMILIES]:
                ds=cm[['d_'+f for f in names]];covered=(ds.min(axis=1)<=cut)
                summ.append(dict(**common,candidates='+'.join(names),cut=cut,covered_n=int(covered.sum()),coverage=float(covered.mean())if len(cm)else np.nan))
        hr=[r for r in human if r['image_id']==iid and r['raw_condition']==cond and r['canonical_annotation_id']in set(rows.id)]
        curves=[curve_of_points(ns,r['effective_points_1024x512'])[0] for r in hr]
        d=[sp.solid_iou(a,b)for a,b in itertools.combinations(curves,2)]
        target.append(dict(**common,human_mean_pair_solid_distance=float(np.mean(d))if d else np.nan,bi_both_fraction=float((rows['bi_state_0.10']=='both').mean()),bi_neither_fraction=float((rows['bi_state_0.10']=='neither').mean()),candidate_all4_neither_fraction=float((cm[['d_'+f for f in FAMILIES]].min(axis=1)>.1).mean())if len(cm)else np.nan))
    pd.DataFrame(summ).to_csv(out/'model_candidate_coverage.csv',index=False)
    pd.DataFrame(target).to_csv(out/'model_linkage_targets.csv',index=False)
    pd.DataFrame(availability).to_csv(out/'model_geometry_availability.csv',index=False)
    frame.reset_index().to_csv(out/'model_image_features.csv',index=False)
    old.save_json(out/'model_geometry_compact.json',compact)
    diag={'images':len(images),'human_distance_rows':len(df),'all_four_available_rows':int(df.all_models_available.sum()),'head_gap_quantiles':frame.gap_bi_enclosed__bi_extended.quantile([0,.25,.5,.75,.9,1]).to_dict(),'head_gaps_below_002':int((frame.gap_bi_enclosed__bi_extended<.02).sum()),'direction_status':df.candidate_direction_status.value_counts().to_dict(),'bi_states_010':df['bi_state_0.10'].value_counts().to_dict(),'primary_source_yaw':0,'heads_are_human_votes':False,'semantic_validation':False}
    old.save_json(out/'model_linkage_summary.json',diag)
    print(json.dumps(old.safe_json(diag),ensure_ascii=False,indent=2));print(pd.DataFrame(summ).query('cut==.1').groupby('candidates').agg(image_condition_mean=('coverage','mean'),covered=('covered_n','sum'),denominator=('N_all_models','sum')).to_string())
if __name__=='__main__':run()
