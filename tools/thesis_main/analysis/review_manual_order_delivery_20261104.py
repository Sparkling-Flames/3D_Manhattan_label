"""Local independent replay of shared-x, centers and saved geometry; no adoption."""
from pathlib import Path
import gzip,json
import numpy as np
import pandas as pd
from .shared_x_reanalysis_20260922 import shared_x
from .paired_split_research.study import angular
from .research_round_20260929 import reconstruct
from .ring_correspondence_20261007 import build
from .consensus_delivery_20261008 import WORKING_GAP
from .scope_quality_scoring_20261016 import scoring_engine
from .quality_b8l2_d10_20261017 import dual_scores
from .wall_consensus_quality_20261015 import measured

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/fusion/manual_order_delivery_review_20261104'
DELIVERY=OUT/'received/research/fusion/manual_order_impact_20261104'

def read(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return json.load(f)

def main():
    objects={o['object_id']:o for o in read(ROOT/'research/data/releases/v2.1/analysis_input/data.json.gz')['objects']}
    ready=0;maxdiff=0.
    for o in objects.values():
        if o['preprocessing_status']!='ready':
            assert o.get('points_1024x512') is None
            continue
        ready+=1;before=np.asarray(o['before_preprocessing_points']);after=shared_x(before,o['links_zero_based'])
        diff=float(np.max(np.abs(after-np.asarray(o['preprocessed_points']))));maxdiff=max(maxdiff,diff)
        assert diff<1e-9 and np.array_equal(before[:,1],after[:,1])
        assert np.array_equal(after[o['ordered_source_point_indices']],o['points_1024x512'])
    with gzip.open(DELIVERY/'endpoints/ENDPOINTS.jsonl.gz','rt',encoding='utf-8') as f:endpoints=[json.loads(line) for line in f]
    centers=[];geo=[];source_count=0;unique=set();scores=[]
    with scoring_engine() as (_,models):
        for e in endpoints:
            sources={r['id']:r for r in e['source_records']}
            for oid,r in sources.items():
                assert r['points']==objects[oid]['points_1024x512'];source_count+=1;unique.add(oid)
            for n in e['fixed_nodes']:
                a=np.array([np.array(sources[m['id']]['points']).reshape(-1,2,2)[m['pair_index']] for m in n['members']])
                assert np.array_equal(a[:,0,0],a[:,1,0])
                distances=np.maximum(angular(a[:,0]-.5,a[:,0]-.5),angular(a[:,1]-.5,a[:,1]-.5))
                anchor=np.argmin(distances.sum(axis=1));dx=(a[:,0,0]-a[anchor,0,0]+512)%1024-512
                x=(a[anchor,0,0]+np.median(dx))%1024
                calculated=[[x,np.median(a[:,0,1])],[x,np.median(a[:,1,1])]]
                diff=float(np.max(np.abs(np.array(calculated)-n['points'])));assert diff<1e-9
                centers.append(dict(review_id=e['review_id'],feature_id=n['feature_id'],difference=diff,within_pair_x_difference=n['points'][0][0]-n['points'][1][0]))
            byid={n['feature_id']:n for n in e['fixed_nodes']}
            points=[p for fid in e['manual_feature_order'] for p in byid[fid]['points']]
            g=reconstruct({'points':points},coordinate_convention='continuous')
            geo.append(dict(review_id=e['review_id'],status=g['status'],reason=g.get('reason'),polygon_valid=g.get('polygon_valid'),camera_in_visible_kernel=g.get('camera_in_visible_kernel')))
            if e['B8L2'] is not None:
                s=dual_scores(e,models);scores.append(max(abs(s[k]-e[k]) for k in s));assert scores[-1]<1e-8
    candidate=read(DELIVERY/'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz')
    c=candidate[0];state=build(c['source_records'],gap=WORKING_GAP)
    assert state['node_consensus']['nodes']==c['nodes'],'Four-person native grouping differs'
    trace=[]
    for label,index in [('F2',1),('F9',8)]:
        n=c['nodes'][index]
        for m in n['members']:
            o=objects[m['id']];i=m['pair_index'];a,b=o['ordered_source_point_indices'][2*i:2*i+2]
            trace.append(dict(label=label,feature_id=n['feature_id'],worker=m['worker'],object_id=m['id'],source_pair_index=i,
                              before_top_x=o['before_preprocessing_points'][a][0],before_bottom_x=o['before_preprocessing_points'][b][0],
                              processed_top_x=o['points_1024x512'][2*i][0],processed_bottom_x=o['points_1024x512'][2*i+1][0],
                              fused_top_x=n['points'][0][0],fused_bottom_x=n['points'][1][0]))
    candidate_geometry=[]
    with scoring_engine() as (engine,models):
        for branch in candidate:
            ns={n['feature_id']:n for n in branch['nodes']}
            points=[p for fid in branch['manual_feature_order'] for p in ns[fid]['points']]
            g=reconstruct({'points':points},coordinate_convention='continuous')
            state={'n':len(branch['source_records']),'node_consensus':{'nodes':branch['nodes']},'candidate':{'points':points,'footprint':g['floor'].tolist() if g['floor'] is not None else None,'geometry_status':g['status']}}
            reference=branch['reference']
            score=measured(engine,state,{'floor':reference['floor_xz_h'],'points':reference['points_1024x512']})
            qs=dual_scores(score,models) if score['score_status']=='complete_conditional' else {'B8L2':None,'D10':None}
            for key,value in qs.items():assert value is None if branch['score'].get(key) is None else abs(value-branch['score'][key])<1e-8
            candidate_geometry.append(dict(version=branch['version'],status=g['status'],reason=g.get('reason'),polygon_valid=g.get('polygon_valid'),camera_in_visible_kernel=g.get('camera_in_visible_kernel'),score_status=score['score_status'],**qs))
    for name,rows in [('F2_F9_SOURCE_TRACE.csv',trace),('NODE_CENTER_REPLAY.csv',centers),('GEOMETRY_REPLAY.csv',geo),('COORDINATE_BRANCH_GEOMETRY.csv',candidate_geometry)]:
        pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')
    result=dict(inventory_objects=len(objects),ready_objects_replayed=ready,preprocessing_max_difference=maxdiff,source_occurrences=source_count,unique_sources=len(unique),nodes_replayed=len(centers),node_center_max_difference=max(r['difference'] for r in centers),endpoints=len(endpoints),geometry_statuses=pd.Series([r['status'] for r in geo]).value_counts().to_dict(),camera_kernel_false=sum(r['camera_in_visible_kernel'] is False for r in geo),scores_from_saved_components=len(scores),score_max_difference=max(scores),four_person_grouping_replayed_identical=True,formal_outputs_modified=False)
    (OUT/'LOCAL_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
