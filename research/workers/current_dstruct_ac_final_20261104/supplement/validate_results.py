"""Independent identity, score-formula, geometry and missingness checks."""
from __future__ import annotations
import gzip,json,math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from design import ROOT,OUT,COMMIT,sha,digest,csv,write_json

def read(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:return json.load(f)
def main():
    spec=json.loads((OUT/'DESIGN.json').read_text())
    for p,h in spec['design_sha256'].items():assert sha(OUT/p)==h,p
    for p,h in spec['source_files'].items():assert sha(ROOT/p)==h,p
    pools={p['pool_id']:p for p in read(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    req=pd.read_csv(OUT/'REQUESTS.csv.gz').set_index('team_key');events=pd.read_csv(OUT/'EVENTS.csv.gz')
    rows={};geo=[];formula=[];labor=[]
    for p in sorted((OUT/'endpoints/pools').glob('*.json.gz')):
        payload=read(p);assert payload['input_pool_sha256']==digest(pools[payload['pool_id']])
        for r in payload['teams']:
            tk=r['team_key'];assert tk not in rows;rows[tk]=r;rr=req.loc[tk];pool=pools[r['pool_id']]
            assert r['method_identity']=='automatic' and not r['manual_order_applied'] and r['original_coordinates_unchanged']
            assert r['repository_commit']==COMMIT and r['underlying_data_version']=='v2.1'
            assert r['input_pool_sha256']==rr.input_pool_sha256==digest(pool)
            assert r['reference_sha256']==digest(pool['reference'])
            assert r['reference_id']==rr.reference_id and r['reference_version']==rr.reference_version
            assert '|'.join(r['member_workers'])==rr.member_workers
            assert '|'.join(sorted(r['member_object_ids']))==rr.member_object_ids
            assert r['k']==rr.n and r['minimum_support']==math.ceil(rr.n/2)
            assert r['full_state']['n']==rr.n and r['full_state']['minimum_support']==math.ceil(rr.n/2)
            assert all(v>=r['minimum_support'] for v in r['node_supports'])
            own=[x for x in pool['records'] if x['worker_id'] in r['member_workers']]
            assert digest(own)==r['input_selected_records_sha256']
            geometry=r.get('geometry') or {};points=geometry.get('points');floor=geometry.get('footprint')
            gr=dict(team_key=tk,pool_id=r['pool_id'],score_status=r['score_status'],Q_available=r.get('B8L2') is not None,n=r['k'],minimum_support=r['minimum_support'],nodes=r['nodes'],shared_x=None,polygon_valid=None,positive_area=None)
            if points is not None:
                pp=np.asarray(points,float);assert pp.ndim==2 and pp.shape[1]==2 and len(pp)==2*r['nodes']
                assert np.isfinite(pp).all();gr['shared_x']=bool(np.array_equal(pp[::2,0],pp[1::2,0]));assert gr['shared_x']
            if floor is not None and len(floor)>=3:
                poly=Polygon(np.asarray(floor,float));gr['polygon_valid']=bool(poly.is_valid);gr['positive_area']=bool(poly.area>0)
            if r.get('B8L2') is not None:
                assert gr['shared_x'] and gr['polygon_valid'] and gr['positive_area']
                I,Sb,D,Hm,Hc=[r[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
                def score(scale):
                    if I==0:return 0.
                    b=Sb**2/32;di=1.5*D**2/(D**2+scale**2);h=(Hm/.8)**2+(Hc/.25)**2
                    return 100*I/(I+math.hypot(1-I+I*b,I*di)+I*h)
                formula.append(dict(team_key=tk,B8L2_residual=score(8)-r['B8L2'],D10_residual=score(10)-r['D10']))
                assert 0<=r['B8L2']<=100 and 0<=r['D10']<=100
            else:
                assert r.get('D10') is None
                assert r['score_status']=='no_connection'
            by=json.loads(r['record_time_by_kind_json'])
            for kind,z in by.items():
                a=[x for x in own if x['time_source_kind']==kind]
                known=[x['source_time_seconds'] for x in a if x['source_time_seconds'] is not None and math.isfinite(x['source_time_seconds'])]
                assert z['n']==len(a) and z['known_n']==len(known)
                assert abs(z['known_sum_seconds']-sum(known))<1e-8
                if len(known)<len(a):assert z['total_seconds'] is None
            positive=[x for x in own if x['source_time_seconds'] is not None and math.isfinite(x['source_time_seconds']) and x['source_time_seconds']>0]
            kinds=sorted(set(x['time_source_kind'] for x in own))
            labor.append(dict(team_key=tk,all_positive_time=len(positive)==len(own),time_sources='|'.join(kinds),strict_same_source_full_team=len(positive)==len(own) and len(kinds)==1))
            geo.append(gr)
    assert set(rows)==set(req.index) and len(rows)==1408 and len(events)==704
    fr=pd.DataFrame(formula);assert fr[['B8L2_residual','D10_residual']].abs().max().max()<1e-8
    pairs=[]
    for e in events.to_dict('records'):
        a,c=rows[e['A_team_key']],rows[e['C_team_key']]
        valid=a.get('B8L2') is not None and c.get('B8L2') is not None
        delta=c['B8L2']-a['B8L2'] if valid else None
        pairs.append(dict(event_id=e['event_id'],pool_id=e['pool_id'],image=e['image'],building=e['building'],direction=e['direction'],n=e['n'],m=e['m'],
                          A_status=a['score_status'],C_status=c['score_status'],AC_common_Q=valid,A_Q=a.get('B8L2'),C_Q=c.get('B8L2'),delta_Q=delta,abs_delta_Q=abs(delta) if valid else None))
    pa=pd.DataFrame(pairs);assert pa.loc[~pa.AC_common_Q,'delta_Q'].isna().all()
    csv(OUT/'audit/GEOMETRY_CHECKS.csv.gz',pd.DataFrame(geo));csv(OUT/'audit/Q_FORMULA_RESIDUALS.csv.gz',fr)
    csv(OUT/'audit/TIME_SOURCE_CHECKS.csv.gz',pd.DataFrame(labor));csv(OUT/'audit/AC_ENDPOINT_SUPPORT.csv.gz',pa)
    bycell=pa.groupby(['direction','n','m','pool_id','image','building']).agg(events=('event_id','size'),common_Q=('AC_common_Q','sum')).reset_index()
    csv(OUT/'audit/CELL_OUTPUT_SUPPORT.csv',bycell)
    receipt=dict(status='passed',frozen_design_unchanged=True,input_identity_verified=True,teams=len(rows),events=len(events),images=events.image.nunique(),buildings=events.building.nunique(),
                 scored_teams=len(fr),unscored_teams=len(rows)-len(fr),AC_common_Q_pairs=int(pa.AC_common_Q.sum()),
                 status_counts=pd.Series([r['score_status'] for r in rows.values()]).value_counts().to_dict(),
                 full_state_preserved=True,fixed_n_nominal_vote_threshold_verified=True,selected_node_supports_meet_threshold=True,
                 Q_formula_max_abs_residual=float(fr.B8L2_residual.abs().max()),D10_formula_max_abs_residual=float(fr.D10_residual.abs().max()),
                 scored_geometry_simple_positive_area=True,shared_x_preserved=True,record_time_reconstructed_from_source_records=True,
                 missing_Q_never_zero=True,manual_orders_added=0,coordinate_changes=0,reference_changes=0,source_commit=COMMIT)
    write_json(OUT/'audit/FINAL_VALIDATION.json',receipt);print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
