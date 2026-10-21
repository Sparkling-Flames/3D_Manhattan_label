#!/usr/bin/env python3
"""Derive explanatory tables only from six saved endpoints, with zero scoring.

Reference assignments here are paired-angle visualization diagnostics; fusion
identity remains the saved immutable observation-to-group assignment. No new
endpoint, reference, rule, threshold or quality value is constructed.
"""
import collections, importlib.util, itertools, sys
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import export_cases as e
HERE=e.HERE
FOCUS={
 'V3_jtc28_pure_positive_n10_m8':{
 'A': [('left_outer_r4','node_005'),('left_return_r5','node_008'),('right_r1','node_001'),('right_r2','node_007'),('right_alternative_x870','node_006')],
 'B': [('left_outer_r4','node_000'),('left_return_r5','node_011'),('right_r1','node_010'),('right_r2','node_007'),('right_alternative_x870','node_006')],
 'C': [('left_outer_r4','node_004'),('left_return_r5','node_005'),('right_r1','node_001'),('right_r2','node_002')]},
 'V3_jtc28_pure_counterexample_n15_m8':{
 'A':[('left_outer_r4','node_000'),('left_return_r5_primary','node_011'),('left_return_r5_secondary','node_013'),('right_r1','node_009'),('right_r2','node_007')],
 'B':[('left_outer_r4','node_000'),('left_return_r5_primary','node_009'),('left_return_r5_secondary','node_012'),('right_r1','node_010'),('right_r2','node_007')],
 'C':[('left_outer_r4','node_000'),('left_return_r5_primary','node_010'),('left_return_r5_secondary','node_012'),('right_r1','node_009'),('right_r2','node_007')]}}

def obs(g): return {(m['id'],int(m['pair_index'])) for m in g['members']}
def angular(a,b):
    def ray(p):
        p=np.asarray(p,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
        return np.c_[np.cos(v)*np.sin(u), np.sin(v), -np.cos(v)*np.cos(u)]
    return np.rad2deg(np.arccos(np.clip(ray(a)@ray(b).T,-1,1)))
def load_viewer():
    p=e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py'
    mod=importlib.util.spec_from_file_location('frozen_viewer',p);v=importlib.util.module_from_spec(mod);mod.loader.exec_module(v);return v

def main():
    v=load_viewer(); tables=collections.defaultdict(list); cases=sorted([e.gs.read(p) for p in (HERE/'cases').glob('*.json.gz')],key=lambda c:c['n'])
    maxmederr=0
    for c in cases:
        members={m['worker_id']:m for m in c['members']};base=dict(case_id=c['case_id'],image=c['pool_meta']['image'],n=c['n'])
        ref=np.asarray(c['reference']['points_1024x512']); bg=set(c['event']['common_background'].split('|'))
        refg=v.viewer_geometry(ref)
        for m in c['members']:
            p=np.asarray(m['points']);cost=np.maximum(angular(p[::2],ref[::2]),angular(p[1::2],ref[1::2])); rr,cc=linear_sum_assignment(cost)
            matched={int(i):(int(j),float(cost[i,j])) for i,j in zip(rr,cc)}
            for i in range(len(p)//2):
                j,deg=matched.get(i,(-1,np.nan))
                tables['RAW_REFERENCE_OPPORTUNITIES'].append(dict(base,worker_id=m['worker_id'],object_id=m['id'],
                    class_id=m['class_id'],pair_index=i,raw_pair_count=len(p)//2,assigned_reference_node=j,
                    assigned_paired_bound_deg=deg,within9=deg<=9,top_x=p[2*i,0],top_y=p[2*i,1],bottom_y=p[2*i+1,1]))
        for t in c['teams']:
            st=t['full_state']; gl={g['feature_id']:g for g in st['identity_groups']};selected={g['feature_id'] for g in st['identity_groups'] if g['selected']}
            for a in st['assignments']:
                covers=selected & set(a['feature_ids'])
                tables['SOURCE_RING_COVERAGE'].append(dict(base,arm=t['label'],worker_id=a['worker'],source_order_status=a['source_order_status'],
                    selected_node_n=len(selected),covered_selected_nodes=len(covers),covers_all_selected=set(covers)==selected,
                    projected_feature_ids='|'.join(f for f in a['feature_ids'] if f in selected),
                    missing_selected_nodes='|'.join(sorted(selected-set(a['feature_ids'])))))
            for g in st['identity_groups']:
                for m in g['members']:
                    tables['GROUP_MEMBERS'].append(dict(base,arm=t['label'],feature_id=g['feature_id'],support=g['support'],
                        threshold=t['minimum_support'],selected=g['selected'],worker_id=m['worker'],class_id=members[m['worker']]['class_id'],
                        object_id=m['id'],pair_index=m['pair_index'],source_pair_index=m['source_pair_index'],
                        top_x=m['points'][0][0],top_y=m['points'][0][1],bottom_y=m['points'][1][1]))
                for coord,ix in [('x',(0,0)),('top_y',(0,1)),('bottom_y',(1,1))]:
                    mm=sorted(g['members'],key=lambda m:(m['points'][ix[0]][ix[1]],m['worker']))
                    med=float(np.median([m['points'][ix[0]][ix[1]] for m in mm]));err=abs(med-g['center'][ix[0]][ix[1]])
                    maxmederr=max(maxmederr,err);assert err<1e-8
                    central={(len(mm)-1)//2,len(mm)//2}
                    for rank,m in enumerate(mm):
                        tables['MEDIAN_ORDER_STATISTICS'].append(dict(base,arm=t['label'],feature_id=g['feature_id'],coordinate=coord,
                            selected=g['selected'],support=g['support'],worker_id=m['worker'],rank_1_based=rank+1,
                            value=m['points'][ix[0]][ix[1]],median_value=med,central_rank=rank in central))
            for role,f in FOCUS[c['case_id']][t['label']]:
                g=gl[f];co=collections.Counter(members[m['worker']]['class_id'] for m in g['members'])
                tables['FOCUS_GROUPS'].append(dict(base,arm=t['label'],role=role,feature_id=f,support=g['support'],threshold=t['minimum_support'],
                    selected=g['selected'],**{k+'_votes':co[k] for k in ['M1','M2','M3','M4']},
                    top_x=g['center'][0][0],top_y=g['center'][0][1],bottom_y=g['center'][1][1],
                    background_votes=sum(m['worker'] in bg for m in g['members']),variable_block_votes=sum(m['worker'] not in bg for m in g['members']),
                    background_workers='|'.join(sorted(m['worker'] for m in g['members'] if m['worker'] in bg)),
                    variable_block_workers='|'.join(sorted(m['worker'] for m in g['members'] if m['worker'] not in bg))))
            for ed in st['ring_diagnostics']['edges']:
                tables['SELECTED_RING_EDGE_VOTES'].append(dict(base,arm=t['label'],node_pair='|'.join(ed['feature_ids']),
                    direct_support=ed['direct_support'],projected_support=ed['projected_support'],
                    direct_workers='|'.join(ed['direct_workers']),projected_workers='|'.join(ed['projected_workers'])))
            if t['geometry']['points'] is None: continue
            p=np.asarray(t['geometry']['points']);cost=np.maximum(angular(p[::2],ref[::2]),angular(p[1::2],ref[1::2]));rr,cc=linear_sum_assignment(cost)
            assignment={int(i):(int(j),float(cost[i,j])) for i,j in zip(rr,cc)}
            geom=v.viewer_geometry(p,t['geometry']['footprint'])
            for i,f in enumerate(t['geometry']['feature_ids']):
                j,deg=assignment.get(i,(-1,np.nan))
                tables['SELECTED_CORNER_GEOMETRY'].append(dict(base,arm=t['label'],feature_id=f,support=gl[f]['support'],threshold=t['minimum_support'],
                    reference_assignment_index=j,reference_assignment_bound_deg=deg,reference_assignment_within9=deg<=9,
                    top_x=p[2*i,0],top_y=p[2*i,1],bottom_x=p[2*i+1,0],bottom_y=p[2*i+1,1],
                    floor_x_h=geom['floor'][i,0],floor_z_h=geom['floor'][i,1],derived_height_h=geom['ceiling_xyz'][i,1]+1))
                jnext=(i+1)%len(geom['floor']);delta=geom['floor'][jnext]-geom['floor'][i];heading=float(np.rad2deg(np.arctan2(delta[1],delta[0]))%180)
                tables['SELECTED_WALL_GEOMETRY'].append(dict(base,arm=t['label'],from_feature_id=f,to_feature_id=t['geometry']['feature_ids'][jnext],
                    from_reference_assignment=j,to_reference_assignment=assignment.get(jnext,(-1,0))[0],length_h=float(np.linalg.norm(delta)),
                    heading_deg_mod180=heading,nearest_XZ_axis_angle_deg=min(heading%90,90-heading%90),
                    note='visual geometric diagnostic; not recomputed frozen direction score'))
        for a,b in itertools.combinations(c['teams'],2):
            am={o:g for g in a['full_state']['identity_groups'] for o in obs(g)};bm={o:g for g in b['full_state']['identity_groups'] for o in obs(g)};common=set(am)&set(bm)
            for ob in sorted(set(am)|set(bm)):
                ag,bg=am.get(ob),bm.get(ob);m=next(m for m in (ag or bg)['members'] if (m['id'],m['pair_index'])==ob)
                tables['OBSERVATION_ASSIGNMENT_TRANSMISSION'].append(dict(base,arm_A=a['label'],arm_B=b['label'],object_id=ob[0],pair_index=ob[1],worker_id=m['worker'],
                    status='common' if ob in common else ('removed' if ag else 'incoming'),A_feature_id=ag['feature_id'] if ag else '',B_feature_id=bg['feature_id'] if bg else '',
                    common_groupmates_changed=(obs(ag)&common != obs(bg)&common) if ob in common else None))
    # Same incoming eight, two distinct frozen contexts: link immutable observations
    # only. This is not a controlled n-response, intervention, or new endpoint.
    a,b=cases[0]['teams'][2],cases[1]['teams'][2]
    for ga in a['full_state']['identity_groups']:
      for gb in b['full_state']['identity_groups']:
        overlap=obs(ga)&obs(gb)
        if overlap: tables['SAME_Z_TWO_CONTEXTS_GROUP_LINKS'].append(dict(case_A=cases[0]['case_id'],case_B=cases[1]['case_id'],
            A_feature_id=ga['feature_id'],B_feature_id=gb['feature_id'],A_support=ga['support'],B_support=gb['support'],
            A_threshold=a['minimum_support'],B_threshold=b['minimum_support'],A_selected=ga['selected'],B_selected=gb['selected'],
            common_observations=len(overlap),shared_workers='|'.join(sorted(m['worker'] for m in ga['members'] if (m['id'],m['pair_index']) in overlap)),
            not_controlled_n_curve=True))
    # A bounded local correspondence probe: the eight observations around r5
    # in the n15 C endpoint, only 28 stored raw-answer pairs. Same preprocessing,
    # cyclic matching and frozen per-omission gap. No fusion / threshold change.
    sys.path.insert(0,str(e.ROOT))
    from tools.thesis_main.analysis.ring_correspondence_20261007 import cyclic_match, angular as frozen_angular, _pairs
    from tools.thesis_main.analysis.consensus_delivery_20261008 import WORKING_GAP
    cc=cases[1];tt=cc['teams'][2];mm={m['worker_id']:m for m in cc['members']}
    local={m['worker']:(m['pair_index'],g['feature_id']) for g in tt['full_state']['identity_groups'] if g['feature_id'] in ['node_010','node_012'] for m in g['members']}
    for wa,wb in itertools.combinations(sorted(local),2):
        aa,reason_a=_pairs(mm[wa]);bb,reason_b=_pairs(mm[wb]);assert reason_a is None and reason_b is None
        cost=(frozen_angular(aa[:,0]-.5,bb[:,0]-.5)+frozen_angular(aa[:,1]-.5,bb[:,1]-.5))/2
        zz=cyclic_match(cost,gap=WORKING_GAP);pa,pb=local[wa][0],local[wb][0];matched=[pa,pb] in zz['matches']
        if local[wa][1]==local[wb][1]:assert matched
        tables['LOCAL_R5_PAIRWISE_COMPATIBILITY'].append(dict(case_id=cc['case_id'],arm='C',worker_A=wa,worker_B=wb,
            pair_index_A=pa,pair_index_B=pb,group_A=local[wa][1],group_B=local[wb][1],
            local_mean_top_bottom_angle_deg=float(cost[pa,pb]),frozen_full_ring_pair_matches=matched,
            full_ring_assignment_json=__import__('json').dumps(zz['matches']),gap_per_omitted_node_deg=WORKING_GAP,
            matched_B_index_for_local_A=next((j for i,j in zz['matches'] if i==pa),None),
            matched_A_index_for_local_B=next((i for i,j in zz['matches'] if j==pb),None),
            quality_score_calls=0,new_fusion_calls=0))
    exp=pd.read_csv(e.ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv')
    ids={m['object_id'] for c in cases for m in c['members']};exp=exp[exp.object_id.isin(ids)];e.savecsv('RAW_EXPRESSION_INPUT_ROWS.csv',exp)
    for name,rows in tables.items():e.savecsv(name+'.csv',pd.DataFrame(rows))
    e.gs.save(HERE/'MECHANISM_ANALYSIS_RECEIPT.json',dict(full_state_replays=0,quality_score_calls=0,existing_teams_analyzed=6,local_frozen_pairwise_matching_probes=28,
        all_group_coordinate_median_max_error=maxmederr,reference_assignment='paired max top/bottom angular distance; visualization only, no quality score',
        group_correspondence='immutable record id and pair index; local numeric ids never assumed portable',
        focus_group_definitions=FOCUS,original_expression_rows=len(exp),cross_context_not_n_causal_curve=True))
    print('Saved local votes, all source-ring coverage, immutable regrouping and wall geometry; no fusion or scoring.',flush=True)
if __name__=='__main__':main()
