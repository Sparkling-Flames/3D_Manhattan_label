"""Final numerical, identity, support, version and geometry audit."""
from __future__ import annotations
import collections, gzip, json, math
import numpy as np
import pandas as pd
from shapely.geometry import Point,Polygon
from design import ROOT,OUT,COMMIT,sha,digest,csv,write_json
from run_native import read_gz

def main():
    spec=json.loads((OUT/'design/DESIGN.json').read_text())
    for p,h in spec['design_files'].items():assert sha(OUT/p)==h,p
    for p,h in spec['source_files'].items():assert sha(ROOT/p)==h,p
    pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    req=pd.read_csv(OUT/'design/REQUESTS.csv.gz').set_index('team_key')
    ev=pd.read_csv(OUT/'analysis/EVENT_METRICS.csv.gz',low_memory=False);rows={};geometry=[];residual=[]
    for p in sorted((OUT/'endpoints/pools').glob('*.json.gz')):
        payload=read_gz(p)
        assert payload['input_pool_sha256']==digest(pools[payload['pool_id']])
        for r in payload['teams']:
            tk=r['team_key'];assert tk not in rows;rows[tk]=r;q=req.loc[tk];pool=pools[r['pool_id']]
            assert r['method_identity']=='automatic' and not r['manual_order_applied'] and r['original_coordinates_unchanged']
            assert r['repository_commit']==COMMIT and r['data_release']=='v2.1' and r['underlying_data_version']=='v2.1'
            assert r['input_pool_sha256']==q.input_pool_sha256==digest(pool)
            assert r['reference_sha256']==digest(pool['reference'])
            assert r['reference_id']==q.reference_id and r['reference_version']==q.reference_version
            assert '|'.join(r['member_workers'])==q.member_workers and '|'.join(sorted(r['member_object_ids']))==q.member_object_ids
            assert r['k']==q.n and r.get('minimum_support')==math.ceil(q.n/2)
            assert all(v>=r['minimum_support'] for v in r['node_supports'])
            own=[x for x in pool['records'] if x['worker_id'] in r['member_workers']]
            assert digest(own)==r['input_selected_records_sha256']
            geo=r.get('geometry') or {};pp=geo.get('points');floor=geo.get('footprint')
            g=dict(team_key=tk,pool_id=r['pool_id'],Q_available=r.get('B8L2') is not None,score_status=r.get('score_status'),
                   nodes=r.get('nodes'),geometry_points_available=pp is not None,footprint_available=floor is not None,
                   shared_x=None,polygon_valid=None,area_camera_height_squared=None,camera_in_polygon=None,camera_in_kernel=None)
            if pp is not None:
                p=np.asarray(pp,float);assert p.ndim==2 and p.shape[1]==2 and len(p)==2*r['nodes']
                g['shared_x']=bool(np.array_equal(p[::2,0],p[1::2,0]));assert g['shared_x']
            if floor is not None and len(floor)>=3:
                f=np.asarray(floor,float);poly=Polygon(f);g['polygon_valid']=bool(poly.is_valid);g['area_camera_height_squared']=float(poly.area)
                if poly.is_valid and poly.area>0:
                    g['camera_in_polygon']=bool(poly.covers(Point(0,0)))
                    area2=float(np.sum(f[:,0]*np.roll(f[:,1],-1)-np.roll(f[:,0],-1)*f[:,1]))
                    edges=np.roll(f,-1,axis=0)-f;cross=edges[:,0]*(-f[:,1])-edges[:,1]*(-f[:,0])
                    g['camera_in_kernel']=bool(np.all(cross*np.sign(area2)>=-1e-10))
            if r.get('B8L2') is not None:
                assert pp is not None and g['polygon_valid'] and g['area_camera_height_squared']>0
                I,Sb,D,Hm,Hc=[r[k] for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')]
                def formula(scale):
                    if I==0:return 0.
                    b=Sb**2/32;di=1.5*D**2/(D**2+scale**2);h=(Hm/.8)**2+(Hc/.25)**2
                    return 100*I/(I+math.hypot(1-I+I*b,I*di)+I*h)
                residual.append(dict(team_key=tk,B8L2_residual=formula(8)-r['B8L2'],D10_residual=formula(10)-r['D10']))
            else:assert pd.isna(r.get('D10'))
            geometry.append(g)
    assert set(rows)==set(req.index) and len(rows)==4992 and len(ev)==3200
    residual=pd.DataFrame(residual);assert residual[['B8L2_residual','D10_residual']].abs().max().max()<1e-8
    for e in ev.to_dict('records'):
        a,b,c=[rows[e[x+'_team_key']].get('B8L2') for x in 'ABC'];valid=all(x is not None for x in (a,b,c))
        assert bool(e['ABC_scored'])==valid
        if valid:
            w=abs(b-a);gs=(abs(c-a)+abs(c-b))/2-w
            assert abs(e['Q_W']-w)<1e-9 and abs(e['Q_GS']-gs)<1e-9
            assert abs(e['Q_GA']-(abs(c-a)-w))<1e-9 and abs(e['Q_class_shift']-(c-(a+b)/2))<1e-9
        else:assert all(pd.isna(e[k]) for k in ['Q_W','Q_GA','Q_GS','Q_class_shift'])
    geo=pd.DataFrame(geometry);csv(OUT/'audit/GEOMETRY_AUDIT.csv.gz',geo);csv(OUT/'audit/Q_FORMULA_RESIDUALS.csv.gz',residual)
    summary=pd.read_csv(OUT/'analysis/SUMMARY.csv');images=pd.read_csv(OUT/'analysis/IMAGE_METRICS.csv.gz')
    for r in summary[summary.stratum_type=='all'].to_dict('records'):
        z=images[(images.study==r['study'])&(images.direction==r['direction'])&(images.support==r['support'])][r['metric']].dropna()
        assert len(z)==r['images'] and abs(z.mean()-r['image_equal_mean'])<1e-9
    paired=pd.read_csv(OUT/'analysis/PAIRED_FOUR_SUMMARY.csv').set_index('metric')
    mapping={'GS_C1_to_C3':('C1_to_C3','Q_GS'),'GS_C3_to_C1':('C3_to_C1','Q_GS'),'C3_minus_C1_mean_Q':('C1_to_C3','Q_class_shift')}
    for metric,(direction,alias) in mapping.items():
        r=summary[(summary.study=='paired_6_3')&(summary.direction==direction)&(summary.support=='all_four_valid')&(summary.stratum_type=='all')&(summary.metric==alias)].iloc[0]
        for field in ['images','buildings','image_equal_mean','cluster_bootstrap_low','cluster_bootstrap_high']:
            assert abs(r[field]-paired.loc[metric,field])<1e-10,(metric,field)
    ar=json.loads((OUT/'audit/ANALYSIS_RECEIPT.json').read_text())
    for p,h in ar['files'].items():assert sha(OUT/p)==h,p
    receipt=dict(all_checks_passed=True,source_commit=COMMIT,design_hashes_unchanged=True,source_hashes_unchanged=True,endpoint_count=len(rows),event_count=len(ev),
                 exact_team_and_object_bindings=True,references_verified=True,selected_support_thresholds_verified=True,
                 scored_endpoint_count=len(residual),maximum_B8L2_formula_residual=float(residual.B8L2_residual.abs().max()),
                 maximum_D10_formula_residual=float(residual.D10_residual.abs().max()),strict_ABC_formula_verified=True,
                 missing_Q_never_zero=True,image_weighting_reaggregated=True,
                 paired_and_main_common_support_estimates_and_intervals_identical=True,analysis_file_hashes_verified=True,
                 successful_geometry_all_simple_nonzero_area=bool(geo[geo.Q_available].polygon_valid.all()),
                 successful_geometry_all_share_x=bool(geo[geo.Q_available].shared_x.all()),
                 scored_camera_outside_polygon=int((geo.Q_available&geo.camera_in_polygon.eq(False)).sum()),
                 scored_camera_outside_visibility_kernel=int((geo.Q_available&geo.camera_in_kernel.eq(False)).sum()),
                 kernel_audit_is_diagnostic_not_a_changed_scoring_gate=True,automatic_status_counts=pd.Series([r['score_status'] for r in rows.values()]).value_counts().to_dict(),
                 approved_manual_exact_hits=0,new_manual_orders=0,new_coordinate_adjustments=0)
    write_json(OUT/'audit/FINAL_VALIDATION.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
