"""Evaluate the user's explicit F2/F9 coordinate candidate as a separate branch.

This never updates the 57 fixed-coordinate endpoints or original preprocessing.
"""
from __future__ import annotations
from copy import deepcopy
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import apply_manual_ring_orders_20261104 as fixed
from .research_round_20260929 import reconstruct
from .scope_quality_scoring_20261016 import scoring_engine


def main():
    out=fixed.OUT.parent/'coordinate_candidate';out.mkdir(parents=True,exist_ok=True)
    rid='fdca268760f9dcc2c83ace58'
    original=fixed.read(fixed.SOURCE/'prepared'/f'{rid}.json.gz')
    case=deepcopy(original)
    orders=pd.read_csv(fixed.RETURN/'VALIDATED_ENDPOINT_ORDERS.csv.gz')
    order=orders.set_index('review_id').loc[rid,'manual_feature_order'].split('|')
    refs,path=fixed.load_references();ref=refs[(case['reference_id'],case['reference_version'])]
    nodes={n['feature_id']:n for n in case['nodes']}
    # F labels are the one-based display order in the frozen node binding.
    assert case['nodes'][1]['feature_id']=='node_001'
    assert case['nodes'][8]['feature_id']=='node_010'
    assert abs(nodes['node_001']['points'][0][0]-439.5927)<.0001
    assert abs(nodes['node_010']['points'][0][0]-438.0147)<.0001
    changes=[]
    for label,fid in [('F2','node_001'),('F9','node_010')]:
        for side,point in zip(['top','bottom'],nodes[fid]['points']):
            changes.append(dict(display_label=label,feature_id=fid,side=side,
                old_x=point[0],new_x=438.8037,delta_x=438.8037-point[0],old_y=point[1],new_y=point[1]))
            point[0]=438.8037
    assert case['records']==original['records']
    for a,b in zip(original['nodes'],case['nodes']):
        assert a['feature_id']==b['feature_id'] and a['support']==b['support'] and a['members']==b['members']
        for x,y in zip(a['points'],b['points']):
            assert x[1]==y[1]
            if a['feature_id'] not in ['node_001','node_010']:assert x==y
    pd.DataFrame(changes).to_csv(out/'EXPLICIT_COORDINATE_EDITS.csv',index=False)
    helpers=fixed.diagnostic_modules();rows=[];full=[]
    identity=dict(team_key=case['team_key'],review_id=rid,image=case['image'],image_id=case['image_id'],
        condition=case['condition'],k=case['k'],pool_id=case['team_key'].rsplit('__',1)[0],
        reference_id=case['reference_id'],reference_version=case['reference_version'])
    with scoring_engine() as (engine,models):
        for version,c in [('manual_order_fixed_coordinates',original),('user_F2_F9_shared_x_candidate',case)]:
            state=fixed.saved_state(c,order)
            score=fixed.evaluate(state,ref,engine,models,helpers,identity)
            geo=reconstruct(state['candidate'],coordinate_convention='continuous')
            geo.update(fixed.geometry_details(geo,order))
            row={k:v for k,v in score.items() if not isinstance(v,(dict,list))}
            row.update(connection_version=version,node_count=len(c['nodes']),
                polygon_valid=geo.get('polygon_valid'),camera_relation=geo.get('camera_relation'),
                camera_in_visible_kernel=geo.get('camera_in_visible_kernel'),
                polygon_validation=geo.get('polygon_validation'),
                nonadjacent_intersections=len(geo['nonadjacent_intersections']),
                reconstruction_status=geo['status'],reconstruction_reason=geo.get('reason'))
            rows.append(row)
            full.append(dict(version=version,score=score,geometry_audit=fixed.clean(geo),
                nodes=c['nodes'],source_records=c['records'],manual_feature_order=order,reference=ref))
    frame=pd.DataFrame(rows);frame.to_csv(out/'CANDIDATE_SCORE_COMPARISON.csv',index=False)
    with gzip.open(out/'CANDIDATE_FULL_STATE.json.gz','wt',encoding='utf8') as f:
        json.dump(fixed.clean(full),f,ensure_ascii=False,allow_nan=False)
    links=pd.read_csv(fixed.RETURN/'AFFECTED_CURRENT_REFERENCES.csv.gz')
    links=links[links.team_key.eq(case['team_key'])];links.to_csv(out/'ACTUAL_DOWNSTREAM_REFERENCES.csv',index=False)
    candidate=rows[1]
    receipt=dict(source_commit=fixed.BASE_COMMIT,team_key=case['team_key'],intervention='user_explicit_cross_node_coordinate_candidate',
        candidate_not_promoted_to_fixed_coordinate_branch=True,exact_requested_x=438.8037,
        full_precision_mean_of_original_centers=float((original['nodes'][1]['points'][0][0]+original['nodes'][8]['points'][0][0])/2),
        changed_nodes=['node_001','node_010'],changed_coordinate_scalars=4,changed_y_scalars=0,
        node_count_preserved=9,node_identity_preserved=True,votes_preserved=True,member_records_preserved=True,
        reference_preserved=True,manual_order_preserved=True,original_branch_not_modified=True,
        scoring_status=candidate['score_status'],B8L2=candidate.get('B8L2'),D10=candidate.get('D10'),
        complete_evaluable=candidate['complete_evaluable'],polygon_valid=candidate['polygon_valid'],
        camera_in_visible_kernel=candidate['camera_in_visible_kernel'],
        nonadjacent_intersections=candidate['nonadjacent_intersections'],
        actual_reference_rows=len(links),modules=links.groupby('module').size().to_dict(),
        human_time_seconds=None,old_Q_is_not_zero=True,new_fusions=0,
        method_relation='Coordinate intervention after fusion centers; different from within-pair source preprocessing.')
    fixed.write_json(out/'CHECKS.json',receipt)
    print(json.dumps(fixed.clean(receipt),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
