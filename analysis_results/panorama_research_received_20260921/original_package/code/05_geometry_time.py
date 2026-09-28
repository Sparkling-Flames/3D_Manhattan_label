"""Actual renderer mechanisms, derivative probes (NOT new people), and frozen-time associations."""
import common as c
import itertools,json,hashlib,collections,math
import numpy as np,pandas as pd
from scipy.stats import spearmanr


def raw_proxy(top,bottom):
    # Exactly the ray/range logic of panorama_studio/geometry.py, Hcam=1.
    u0=(top[0]/1024-.5)*2*np.pi;u1=(bottom[0]/1024-.5)*2*np.pi
    vt=(.5-top[1]/512)*np.pi;vb=(bottom[1]/512-.5)*np.pi
    if min(vt,vb)<np.deg2rad(.5) or max(vt,vb)>np.pi/2:return None
    radius=1/np.tan(vb)
    f=np.array([radius*np.sin(u1),-1.,-radius*np.cos(u1)])
    q=np.array([radius*np.sin(u0),radius*np.tan(vt),-radius*np.cos(u0)])
    return np.r_[f,q]

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    from tools.label_studio.panorama_studio import geometry as geo
    rows,rec,views,reg,elig=c.load();table=[];fits=[];fitraw=[];times=[]
    # Fixed, geometry-blind mechanism panel: two smallest SHA256 IDs per building, plus named approved mapping cases.
    byb=collections.defaultdict(list)
    for v in views.values():
        for cid in v['ids']:byb[v['building']].append(cid)
    chosen=set()
    for b,ids in byb.items():chosen.update(sorted(ids,key=lambda x:hashlib.sha256(x.encode()).hexdigest())[:2])
    chosen.update(['8178591994d42ce3','a4e0cac5adec2e1e'])
    for v in views.values():
        for rr in v['rows']:
            cid=rr['canonical_annotation_id'];r=rec[cid];p=r['p'];links=r['links'];base=dict(id=cid,image_id=v['image_id'],code=v['code'],building=v['building'],worker=rr['worker_id'],pairs=len(links))
            for j,(t,b) in enumerate(links):
                top,bottom=p[t],p[b];rad=raw_proxy(top,bottom)
                vt=(.5-top[1]/512)*np.pi;vb=(bottom[1]/512-.5)*np.pi
                z=dict(base,pair_index=j+1,top_raw_point=int(t)+1,bottom_raw_point=int(b)+1,top_x=top[0],top_y=top[1],bottom_x=bottom[0],bottom_y=bottom[1],
                    horizontal_pair_gap=abs((top[0]-bottom[0]+512)%1024-512),valid_ray_range=rad is not None,
                    legacy_viewer_floor_clamped=not .01<=vb<=1.5,legacy_viewer_top_clamped=not .01<=vt<=1.5,
                    bottom_horizon_distance_deg=np.rad2deg(vb),top_horizon_distance_deg=np.rad2deg(vt))
                if rad is not None:
                    z.update(range_camera_heights=float(np.hypot(rad[0],rad[2])),ceil_height_camera_heights=rad[4])
                    for end in ['top','bottom']:
                        for axis in [0,1]:
                            aa=top.copy();bb=bottom.copy();cc=top.copy();dd=bottom.copy()
                            (aa if end=='top' else bb)[axis]+=1.;(cc if end=='top' else dd)[axis]-=1.
                            plus=raw_proxy(aa,bb);minus=raw_proxy(cc,dd)
                            if plus is not None and minus is not None:
                                # Symmetric finite difference at one pixel; maximum endpoint displacement per pixel.
                                der=(plus-minus)/2.;z[f'{end}_{"x" if axis==0 else "y"}_sensitivity']=max(np.linalg.norm(der[:3]),np.linalg.norm(der[3:]))
                    # Forced shared x in legacy viewer discards independent azimuth; illustrative top-x convention.
                    z['shared_x_floor_motion']=2*z['range_camera_heights']*abs(np.sin(np.pi*z['horizontal_pair_gap']/1024))
                table.append(z)
            if cid in chosen:
                payload={'width':1024,'height':512,'coordinate_mode':'pixels','ordered_pairs':[
                    {'source_pair_id':f'{cid}:p{int(t)+1}:p{int(b)+1}','top':{'x':float(p[t,0]),'y':float(p[t,1])},'bottom':{'x':float(p[b,0]),'y':float(p[b,1])}} for t,b in links]}
                result=geo.analyze(payload);raw=result['raw'];fit=result['fit']
                fits.append(dict(base,raw_surface_valid=raw['surface_valid'],raw_issues=';'.join(raw['issues']),fit_status=fit['status'],fit_reasons=';'.join(fit.get('reasons',[])),
                    fit_residual_mean_deg=fit.get('residual_mean_deg'),fit_residual_max_deg=fit.get('residual_max_deg'),
                    raw_height_spread=(raw.get('metrics') or {}).get('height_relative_spread'),fit_height_spread=(fit.get('metrics') or {}).get('height_relative_spread'),
                    raw_heading_mean_deg=(raw.get('metrics') or {}).get('heading_mean_deg'),fit_heading_mean_deg=(fit.get('metrics') or {}).get('heading_mean_deg')))
                fitraw.append(dict(**base,input=payload,output=result))
            ev=rr.get('evidence') or {}
            # No duration proxy substituted for new unfrozen active time.
            seconds=ev.get('time_active_time_seconds',ev.get('active_time_seconds'))
            ok=(ev.get('time_active_time_formal_available') in ['true',True]) and ev.get('active_time_owner_valid_status')=='owner_valid_complete'
            if seconds is not None and ok and rr['stage']!='scene_stability_stage1':
                try:s=float(seconds)
                except (TypeError,ValueError):continue
                if s>0:times.append(dict(base,active_seconds=s,log_active_seconds=np.log(s),effective_point_count=rr['effective_point_count'],source='frozen_historical_owner_valid_active_time'))
    t=pd.DataFrame(table);ff=pd.DataFrame(fits);tt=pd.DataFrame(times)
    c.save('ray_derivative_probes.csv.gz',t);c.save('regularization_mechanism_panel.csv',ff);c.save('regularization_mechanism_inputs_outputs.json',fitraw)
    valid=t[t.valid_ray_range];summary=dict(responses=2444,bound_pairs=len(t),raw_range_invalid_pairs=int((~t.valid_ray_range).sum()),
        top_bottom_x_not_identical=int((t.horizontal_pair_gap>1e-6).sum()),top_bottom_x_gap_gt1px=int((t.horizontal_pair_gap>1).sum()),
        legacy_floor_clamped_pairs=int(t.legacy_viewer_floor_clamped.sum()),legacy_top_clamped_pairs=int(t.legacy_viewer_top_clamped.sum()),
        relative_range_quantiles=valid.range_camera_heights.quantile([.5,.9,.99]).to_dict(),sensitivity={})
    for col in ['top_x_sensitivity','top_y_sensitivity','bottom_x_sensitivity','bottom_y_sensitivity']:
        summary['sensitivity'][col]=valid[col].quantile([.5,.9,.99]).to_dict()
    dd=valid.dropna(subset=['top_y_sensitivity','bottom_y_sensitivity'])
    summary['bottom_y_greater_than_top_y_share']=(dd.bottom_y_sensitivity>dd.top_y_sensitivity).mean()
    summary['fit_panel']={'responses':len(ff),'buildings':ff.building.nunique(),'statuses':ff.fit_status.value_counts().to_dict(),
        'blocked_reasons':ff.loc[ff.fit_status!='ok','fit_reasons'].value_counts().to_dict(),
        'selection':'2 response IDs per building ordered by SHA256, plus two approved uNb21 cases; not selected for successful fit',
        'median_residual_mean_deg_successful':ff.fit_residual_mean_deg.median(),'max_residual_max_deg_successful':ff.fit_residual_max_deg.max()}
    summary['scope']='Numerical counterfactual sensitivity, not generated annotators. Relative camera-height units. Raw ceiling range borrowed from paired floor, not independently measured ceiling depth. Correct geometry not adjudicated.'
    c.save('geometry_summary.json',summary)
    wr=pd.read_csv(c.ROOT/'results/response_metrics.csv')
    if len(tt):
        tt=tt.merge(wr[['id','pair_disagreement','count_disagreement','N']],on='id',how='left');tt=tt[tt.N>=4]
        for col in ['log_active_seconds','effective_point_count','pair_disagreement','count_disagreement']:
            tt['within_'+col]=tt[col]-tt.groupby('image_id')[col].transform('mean')
        c.save('frozen_time_panel.csv',tt)
        time_summary=dict(responses=len(tt),images=tt.image_id.nunique(),workers=tt.worker.nunique(),buildings=tt.building.nunique(),new_unfrozen_time_used=0,
            descriptive_spearman={},within_image_spearman={})
        for target in ['effective_point_count','pair_disagreement','count_disagreement']:
            time_summary['descriptive_spearman'][target]=float(spearmanr(tt.log_active_seconds,tt[target],nan_policy='omit').statistic)
            time_summary['within_image_spearman'][target]=float(spearmanr(tt.within_log_active_seconds,tt['within_'+target],nan_policy='omit').statistic)
        c.save('time_summary.json',time_summary)
    print(json.dumps(c.clean(summary),ensure_ascii=False,indent=2));print('TIME',json.dumps(c.clean(time_summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
