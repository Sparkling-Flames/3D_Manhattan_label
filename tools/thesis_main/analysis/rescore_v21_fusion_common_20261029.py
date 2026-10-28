"""Rescore the frozen 48-pool method panel without regenerating any geometry."""
import json
import numpy as np
import pandas as pd
from shapely.geometry import shape
from .rebuild_v21_20261028 import OUT, ROOT, read
from . import fusion_common_panel_20261024 as native

TARGET=OUT/'fusion_common_panel'
SOURCE=ROOT/'research/fusion/fusion_common_panel_20261024'


def evaluate(row,geom,pool,engine,models):
    ref=pool['reference'];floor=native.polygon(ref['floor_xz_h']);assert floor is not None
    footprint=geom['footprint'];poly=shape(footprint) if isinstance(footprint,dict) else native.polygon(footprint)
    if poly is not None and (not poly.is_valid or poly.is_empty or poly.area<=0):poly=None
    values=native.floor_metrics(poly,floor)
    if isinstance(footprint,list) and len(footprint)>=3:values.update(native.corner_diagnostics(footprint,ref['floor_xz_h']))
    if row.method!='lee_mv50' and row.full_output:
        m=engine.measure(engine.geometry(geom['points']),engine.geometry(ref['points_1024x512']))
        assert m['status']=='complete',(row.team_key,row.method,m['status'])
        values.update({k:m['metrics'].get(k) for k in native.METRICS if k not in ['B8L2','D10','IoU3D100','iou_2d']})
        values.update(native.dual_scores(m['metrics'],models));values['IoU3D100']=100*m['metrics']['iou_3d_corner_mean']
    return values


def main():
    frame=pd.read_csv(SOURCE/'METHOD_ENDPOINTS.csv');geometry=read(SOURCE/'METHOD_GEOMETRY.json')
    g={(r['team_key'],r['method']):r for r in geometry};assert len(g)==len(frame)==414
    current={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    old={p['pool_id']:p for p in native.read_gz(native.SOURCE/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    deps={r['pool_id']:r for r in read(OUT/'pools/DEPENDENCIES.json')}
    assert frame.team_key.nunique()==138 and frame.pool_id.nunique()==48
    affected={pid for pid in frame.pool_id if deps[pid]['action']=='reuse_geometry_rescore'}
    assert all(deps[pid]['action'] in ['reuse_endpoints','reuse_geometry_rescore'] for pid in frame.pool_id)
    saved=frame.copy();parity=0;updated=0
    with native.scoring_engine(native.ENGINE/'measurement_engine.zip',native.ENGINE/'working_models.py') as (engine,models):
        for idx,row in saved.iterrows():
            if row.pool_id not in affected:continue
            pool=current[row.pool_id];before=old[row.pool_id];geom=g[(row.team_key,row.method)]
            members=set(row.member_workers.split('|'));lookup={r['worker_id']:r['object_id'] for r in pool['records']}
            assert members<=lookup.keys() and {lookup[w] for w in members}==set(row.member_object_ids.split('|'))
            previous=evaluate(row,geom,before,engine,models)
            for key,value in previous.items():
                if key not in saved or value is None:continue
                oldvalue=saved.at[idx,key]
                assert pd.notna(oldvalue) and np.isclose(float(value),float(oldvalue),atol=1e-7,rtol=0),(row.team_key,row.method,key,value,oldvalue)
            parity+=1;new=evaluate(row,geom,pool,engine,models)
            for key in previous:
                if key in frame:frame.at[idx,key]=new.get(key,np.nan)
            frame.at[idx,'reference_id']=pool['meta']['reference_id'];frame.at[idx,'reference_version']=pool['meta']['reference_version']
            frame.at[idx,'reference_nodes']=len(pool['reference']['points_1024x512'])//2
            updated+=1
    frame['full_evaluable']=frame[list(native.METRICS)].notna().all(axis=1)
    for c in ['full_output','floor_output','full_evaluable','below_four','missing_connection','self_intersection']:
        a=frame[c].fillna('missing');b=saved[c].fillna('missing');assert a.equals(b),(c,'support changed')
    assert frame[frame.method.eq('lee_mv50')][['B8L2','D10','IoU3D100']].isna().all().all()
    unchanged=~frame.pool_id.isin(affected);assert frame.loc[unchanged].equals(saved.loc[unchanged])
    TARGET.mkdir(parents=True,exist_ok=True);frame.to_csv(TARGET/'METHOD_ENDPOINTS.csv',index=False)
    native.OUT=TARGET;native.summarize()
    common=pd.read_csv(TARGET/'THREE_METHOD_COMMON_FLOOR.csv');assert common.team_key.nunique()==131
    keys=['team_key','comparison','metric','support_domain']
    old_pairs=pd.read_csv(SOURCE/'COMMON_TEAM_METRICS.csv');new_pairs=pd.read_csv(TARGET/'COMMON_TEAM_METRICS.csv')
    paired=old_pairs.merge(new_pairs,on=keys,how='outer',indicator=True,validate='one_to_one',suffixes=('_old','_v21'))
    assert paired._merge.eq('both').all()
    summary_keys=['condition','layer','difficulty','n','comparison','support_domain','metric']
    old_summary=pd.read_csv(SOURCE/'COMMON_SCENE_SUMMARY.csv');new_summary=pd.read_csv(TARGET/'COMMON_SCENE_SUMMARY.csv')
    comparison=old_summary.merge(new_summary,on=summary_keys,how='outer',indicator=True,validate='one_to_one',suffixes=('_old','_v21'))
    assert comparison._merge.eq('both').all();comparison['delta_change']=comparison.mean_delta_v21-comparison.mean_delta_old
    comparison.drop(columns='_merge').to_csv(TARGET/'COMMON_SCENE_SUMMARY_OLD_V21.csv',index=False)
    receipt=dict(pools=48,teams=138,methods=3,rows=len(frame),affected_pools=len(affected),updated_rows=updated,old_reference_parity_rows=parity,unchanged_rows=int(unchanged.sum()),three_method_common_floor=common.team_key.nunique(),common_metric_rows=len(paired),common_metric_support_unchanged=True,support_unchanged=True,actual_teams_and_geometry_unchanged=True,lee_top_not_applicable=True,new_fusion=False,new_selection=False)
    (TARGET/'CHECKS.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
