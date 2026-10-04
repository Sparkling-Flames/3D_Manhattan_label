"""Reference-only evaluation after all candidate construction; no winner selection.
Raw fields and unsupported fixed-longitude pairs retained. Declared-arc metrics
on nonmonotone rings include all source edges, not a silently sorted envelope.
"""
from pathlib import Path
import json,itertools,argparse
import numpy as np
import pandas as pd
from arc_consensus import Ring,Unsupported,footprint,area_scores
from quality import directed,unit_arcs
from continuous_metrics import fixed_longitude
from baseline_points import point_baseline
from compression_study import dump
ROOT=Path(__file__).resolve().parents[1]

def eval_one(c,g,step=.05):
    row={}
    _,A=footprint(c);_,G=footprint(g);row.update(area_scores(A,G))
    row['centroid_dx_h']=A.centroid.x-G.centroid.x;row['centroid_dz_h']=A.centroid.y-G.centroid.y
    for s,name in enumerate(['top','bottom']):
        a=directed(c,g,s,step);b=directed(g,c,s,step)
        for k in ['mean_deg','mean_absolute_numerical_bound_deg','max_lower_deg','max_upper_deg','p95_deg']:
            row[f'{name}_c2g_{k}']=a[k];row[f'{name}_g2c_{k}']=b[k]
        row[name+'_arc_mean_deg']=(a['mean_deg']+b['mean_deg'])/2
        row[name+'_arc_mean_bound_deg']=(a['mean_absolute_numerical_bound_deg']+b['mean_absolute_numerical_bound_deg'])/2
        row[name+'_length_deg']=float(np.degrees(unit_arcs(c,s)[2].sum()))
        row[name+'_gt_length_deg']=float(np.degrees(unit_arcs(g,s)[2].sum()))
        row[name+'_unnormalized_c2g_deg2']=row[name+'_length_deg']*a['mean_deg']
    try:row.update(fixed_longitude(c,g));row['fixed_longitude_status']='ok'
    except Unsupported as e:row.update(fixed_longitude_status='unsupported',fixed_longitude_reason=str(e))
    return row

def run():
    candidates=[];inputs={}
    for p in sorted((ROOT/'inputs').glob('*.json')):
        image=p.stem;inp=json.loads(p.read_text());inputs[image]=inp['records']
        for r in inp['records']:candidates.append((image,'raw',r['id'],None,r))
        fu=json.loads((ROOT/'results/construction'/f'{image}_exact.json').read_text())
        if fu['status']!='ok_conditional_representation':continue
        exact=fu['methods'][fu['bev_mv50_complete_method']];candidates.append((image,'exact','exact',0.,exact))
        points=point_baseline(inp['records'],5.)['mv50'];dump(ROOT/'results/construction'/f'{image}_point_numeric.json',points)
        if points['status']!='unavailable':candidates.append((image,'point_numeric','point_5deg',None,points))
        for p2 in sorted((ROOT/'results/compression').glob(image+'_*px.json')):
            c=json.loads(p2.read_text());candidates.append((image,c['compression_policy'],p2.stem,c['epsilon_px'],c))
    # Only now open the references; neither raw candidates nor policies use them.
    refs={x['image']:x['references'][0] for x in json.loads((ROOT/'evaluation/references.json').read_text())['images']}
    rows=[];metric_output=ROOT/'results/metrics';metric_output.mkdir(exist_ok=True)
    for image,kind,key,eps,c in candidates:
        rr=dict(image=image,kind=kind,candidate=key,epsilon_px=eps,worker=c.get('worker'),n=len(inputs[image]),pair_count=len(c['points'])//2,reference_id=refs[image]['id'],reference_version='original')
        rr.update(eval_one(c,refs[image]));rows.append(rr)
        print(image,key,'iou',rr.get('iou'),'yaw',rr.get('top_mean_abs_px'),flush=True)
    d=pd.DataFrame(rows);d.to_csv(metric_output/'reference_metrics.csv',index=False)
    refareas=[]
    from shapely.geometry import shape
    for image,g in refs.items():
        _,G=footprint(g);lee=json.loads((ROOT/'results/construction'/f'{image}_lee.json').read_text())
        print('lee fields',lee.keys(),flush=True)
        A=shape(lee['geometry'])
        refareas.append(dict(image=image,n=len(inputs[image]),reference_id=g['id'],**area_scores(A,G)))
    pd.DataFrame(refareas).to_csv(metric_output/'all_roster_lee_reference.csv',index=False)
    # Deterministic descriptive pair comparisons; no p values from correlated pairs.
    inversions=[];summ=[]
    for image,group in d.groupby('image'):
        raw=group[(group.kind=='raw')&(group.fixed_longitude_status=='ok')]
        for side in ['top','bottom']:
            eligible=0;inversion=0;robust=0
            for (_,a),(_,b) in itertools.combinations(raw.iterrows(),2):
                da=a[side+'_arc_mean_deg']-b[side+'_arc_mean_deg'];dy=a[side+'_mean_abs_px']-b[side+'_mean_abs_px']
                if abs(da)<1e-9 or abs(dy)<1e-8:continue
                eligible+=1
                if da*dy<0:
                    inversion+=1;ok=abs(da)>a[side+'_arc_mean_bound_deg']+b[side+'_arc_mean_bound_deg'];robust+=ok
                    inversions.append(dict(image=image,side=side,first=a.candidate,second=b.candidate,arc_difference_deg=da,longitude_difference_px=dy,arc_difference_exceeds_numerical_bound=ok))
            summ.append(dict(image=image,side=side,raw_candidates=len(raw),non_tied_pairs=eligible,discordant_pairs=inversion,discordant_beyond_arc_error_bounds=robust))
    pd.DataFrame(summ).to_csv(metric_output/'metric_order_summary.csv',index=False)
    pd.DataFrame(inversions).to_csv(metric_output/'metric_order_discordances.csv',index=False)
    # Triangle-inequality certificates for the fixed-longitude mean and Jaccard metric.
    certificates=[]
    for image,grp in d.groupby('image'):
        e=grp[grp.kind=='exact'];p=grp[grp.kind=='point_numeric']
        if len(e)!=1 or len(p)!=1:continue
        e=e.iloc[0];p=p.iloc[0]
        loss=pd.read_csv(ROOT/'results/compression'/f'{image}_losses.csv')
        for _,l in loss.iterrows():
            c=grp[(grp.kind==l.policy)&(grp.epsilon_px==l.epsilon_px)].iloc[0]
            for metric in ['top','bottom','bev']:
                if metric=='bev':
                    exactloss=1-e['iou'];pointloss=1-p['iou'];comploss=1-c['iou'];bound=1-l['bev_iou_to_exact']
                else:
                    exactloss=e[metric+'_mean_abs_px'];pointloss=p[metric+'_mean_abs_px'];comploss=c[metric+'_mean_abs_px'];bound=l[metric+'_mean_abs_px']
                certificates.append(dict(image=image,policy=l.policy,epsilon_px=l.epsilon_px,metric=metric,exact_loss=exactloss,compressed_loss=comploss,point_loss=pointloss,gt_free_compression_score_shift_bound=bound,actual_score_shift=abs(comploss-exactloss),bound_passed=abs(comploss-exactloss)<=bound+1e-9,exact_point_gap=exactloss-pointloss,compressed_point_gap=comploss-pointloss,point_order_certified=abs(exactloss-pointloss)>bound+1e-9,point_order_reversed=(exactloss-pointloss)*(comploss-pointloss)<-1e-12))
    pd.DataFrame(certificates).to_csv(metric_output/'compression_score_certificates.csv',index=False)
    dump(metric_output/'summary.json',dict(reference_rows=len(d),raw_rows=int((d.kind=='raw').sum()),original_reference_count=len(refs),fixed_longitude_ok=int((d.fixed_longitude_status=='ok').sum()),visual_adjudication_performed=False))
if __name__=='__main__':run()
