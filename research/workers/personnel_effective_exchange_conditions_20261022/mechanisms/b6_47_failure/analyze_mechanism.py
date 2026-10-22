#!/usr/bin/env python3
"""Describe saved native failure states; no fusion, scoring, or repair."""
import collections, importlib.util, itertools
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import export_cases as e
from shapely.geometry import Polygon, LineString
from shapely.validation import explain_validity

HERE=e.HERE
FOCUS={
 'B6_47_invalid_floor_n20_m4':{
  'A':{'r6':'node_009','r7':'node_011','r8_primary':'node_010','r8_separate':'node_008','r9':'node_004'},
  'B':{'r6':'node_005','r7':'node_009','r8_primary':'node_006','r8_separate':'node_012','r9':'node_007'},
  'C':{'r6':'node_006','r7':'node_007','r8_primary':'node_008','r8_separate':'node_012','r9':'node_009'}},
 'B6_47_invalid_floor_n22_m4':{
  'A':{'r6':'node_010','r7':'node_012','r8_primary':'node_011','r8_separate':'node_009','r9':'node_004'},
  'B':{'r6':'node_005','r7':'node_009','r8_primary':'node_006','r8_separate':'node_013','r9':'node_007'},
  'C':{'r6':'node_006','r7':'node_007','r8_primary':'node_008','r8_separate':'node_013','r9':'node_009'}}}

def obs(g):return {(m['id'],int(m['pair_index'])) for m in g['members']}
def load_viewer():
 p=e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py'
 spec=importlib.util.spec_from_file_location('frozen_viewer',p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
def angular(a,b):
 def ray(p):
  p=np.asarray(p,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
  return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
 return np.rad2deg(np.arccos(np.clip(ray(a)@ray(b).T,-1,1)))
def intersections(floor,ids):
 n=len(floor);rows=[]
 for i in range(n):
  for j in range(i+1,n):
   if j==(i+1)%n or i==(j+1)%n:continue
   a=LineString([floor[i],floor[(i+1)%n]]);b=LineString([floor[j],floor[(j+1)%n]])
   if a.intersects(b):
    p=a.intersection(b)
    rows.append(dict(edge_1='|'.join([ids[i],ids[(i+1)%n]]),edge_2='|'.join([ids[j],ids[(j+1)%n]]),
      intersection_wkt=p.wkt,intersection_x_h=p.x if p.geom_type=='Point' else None,
      intersection_z_h=p.y if p.geom_type=='Point' else None))
 return rows

def main():
 v=load_viewer();tables=collections.defaultdict(list);max_error=0
 cases=[e.gs.read(p) for p in sorted((HERE/'cases').glob('*.json.gz'))]
 for c in cases:
  base=dict(case_id=c['case_id'],image=c['pool_meta']['image'],n=c['n']);ref=np.asarray(c['reference']['points_1024x512'])
  bg=set(c['event']['common_background'].split('|'));mm={m['worker_id']:m for m in c['members']}
  for m in c['members']:
   p=np.asarray(m['points']);gg=v.viewer_geometry(p);po=Polygon(gg['floor']);cost=np.maximum(angular(p[::2],ref[::2]),angular(p[1::2],ref[1::2]))
   rr,cc=linear_sum_assignment(cost);assign={int(i):(int(j),float(cost[i,j])) for i,j in zip(rr,cc)}
   tables['RAW_MEMBER_GEOMETRY'].append(dict(base,worker_id=m['worker_id'],class_id=m['class_id'],point_pairs=len(p)//2,
    footprint_valid=po.is_valid,validity_reason=explain_validity(po),native_individual_B8L2=m.get('B8L2'),
    source_time_seconds=m.get('source_time_seconds'),time_source_kind=m.get('time_source_kind'),
    block='background' if m['worker_id'] in bg else next(a for a,t in zip('XYZ',c['teams']) if m['worker_id'] in t['member_workers'])))
   for i in range(len(p)//2):
    j,deg=assign.get(i,(-1,np.nan))
    tables['RAW_REFERENCE_OPPORTUNITIES'].append(dict(base,worker_id=m['worker_id'],object_id=m['id'],class_id=m['class_id'],
     pair_index=i,assigned_reference_index=j,paired_bound_deg=deg,within9=deg<=9,
     top_x=p[2*i,0],top_y=p[2*i,1],bottom_y=p[2*i+1,1],floor_x_h=gg['floor'][i,0],floor_z_h=gg['floor'][i,1]))
  for t in c['teams']:
   base_t=dict(base,arm=t['label'],team_key=t['team_key']);st=t['full_state'];gg={g['feature_id']:g for g in st['identity_groups']}
   selected={g['feature_id'] for g in gg.values() if g['selected']};floor=np.asarray(t['geometry']['footprint'])
   tables['ENDPOINT_VALIDITY_DIAGNOSTIC'].append(dict(base_t,score_status=t['score_status'],native_geometry_status=t['geometry']['geometry_status'],
    native_geometry_reason=t['geometry']['reason'],footprint_valid=Polygon(floor).is_valid,validity_reason=explain_validity(Polygon(floor)),
    ring_source_support=st['ring_diagnostics']['alternatives'][0]['support'],ring_source_workers='|'.join(st['ring_diagnostics']['alternatives'][0]['workers']),
    ring_confirmed=st['ring_diagnostics']['ring_confirmed'],ring_policy=st['ring_diagnostics']['policy']))
   for r in intersections(floor,t['geometry']['feature_ids']):tables['SELF_INTERSECTIONS'].append(dict(base_t,**r))
   for a in st['assignments']:
    cover=selected & set(a['feature_ids'])
    tables['SOURCE_RING_COVERAGE'].append(dict(base_t,worker_id=a['worker'],selected_nodes=len(selected),covered_selected_nodes=len(cover),
     covers_all_selected=cover==selected,source_order_status=a['source_order_status'],
     original_assignment='|'.join(a['feature_ids']),projected_assignment='|'.join(f for f in a['feature_ids'] if f in selected)))
   for edge in st['ring_diagnostics']['edges']:
    tables['SELECTED_RING_EDGE_VOTES'].append(dict(base_t,node_pair='|'.join(edge['feature_ids']),direct_support=edge['direct_support'],
     projected_support=edge['projected_support'],direct_workers='|'.join(edge['direct_workers']),projected_workers='|'.join(edge['projected_workers'])))
   for g in gg.values():
    for ob in g['members']:
     tables['GROUP_MEMBERS'].append(dict(base_t,feature_id=g['feature_id'],support=g['support'],selected=g['selected'],threshold=t['minimum_support'],
      worker_id=ob['worker'],class_id=mm[ob['worker']]['class_id'],object_id=ob['id'],pair_index=ob['pair_index'],
      source_pair_index=ob['source_pair_index'],top_x=ob['points'][0][0],top_y=ob['points'][0][1],bottom_y=ob['points'][1][1]))
    for coord,ix in [('x',(0,0)),('top_y',(0,1)),('bottom_y',(1,1))]:
     arr=sorted(g['members'],key=lambda o:(o['points'][ix[0]][ix[1]],o['worker']));med=float(np.median([o['points'][ix[0]][ix[1]] for o in arr]));err=abs(med-g['center'][ix[0]][ix[1]])
     max_error=max(max_error,err);assert err<1e-8
     for rank,o in enumerate(arr):
      if rank not in {(len(arr)-1)//2,len(arr)//2}:continue
      tables['GROUP_MEDIAN_CONTRIBUTORS'].append(dict(base_t,feature_id=g['feature_id'],coordinate=coord,worker_id=o['worker'],
       rank_1_based=rank+1,value=o['points'][ix[0]][ix[1]],median_value=med,selected=g['selected']))
   for role,f in FOCUS[c['case_id']][t['label']].items():
    g=gg[f];votes=collections.Counter(mm[o['worker']]['class_id'] for o in g['members'])
    tables['FOCUS_GROUPS'].append(dict(base_t,role=role,feature_id=f,support=g['support'],threshold=t['minimum_support'],selected=g['selected'],
     **{cl+'_votes':votes[cl] for cl in ['J1','J2','J3','J4','J5']},
     background_votes=sum(o['worker'] in bg for o in g['members']),variable_block_votes=sum(o['worker'] not in bg for o in g['members']),
     background_workers='|'.join(sorted(o['worker'] for o in g['members'] if o['worker'] in bg)),
     variable_block_workers='|'.join(sorted(o['worker'] for o in g['members'] if o['worker'] not in bg)),
     top_x=g['center'][0][0],top_y=g['center'][0][1],bottom_y=g['center'][1][1]))
   p=np.asarray(t['geometry']['points']);vg=v.viewer_geometry(p,floor);cost=np.maximum(angular(p[::2],ref[::2]),angular(p[1::2],ref[1::2]));rr,cc=linear_sum_assignment(cost)
   assign={int(i):(int(j),float(cost[i,j])) for i,j in zip(rr,cc)}
   for i,f in enumerate(t['geometry']['feature_ids']):
    j,deg=assign.get(i,(-1,np.nan))
    tables['SELECTED_CORNER_GEOMETRY'].append(dict(base_t,feature_id=f,assigned_reference_index=j,paired_bound_deg=deg,within9=deg<=9,
     top_x=p[2*i,0],top_y=p[2*i,1],bottom_y=p[2*i+1,1],floor_x_h=floor[i,0],floor_z_h=floor[i,1],
     height_h=vg['ceiling_xyz'][i,1]+1,endpoint_valid=Polygon(floor).is_valid))
  for a,b in itertools.combinations(c['teams'],2):
   aa={o:g for g in a['full_state']['identity_groups'] for o in obs(g)};bb={o:g for g in b['full_state']['identity_groups'] for o in obs(g)};common=set(aa)&set(bb)
   for ob in sorted(set(aa)|set(bb)):
    ag,bg=aa.get(ob),bb.get(ob);m=next(x for x in (ag or bg)['members'] if (x['id'],x['pair_index'])==ob)
    tables['OBSERVATION_ASSIGNMENT_TRANSMISSION'].append(dict(base,arm_A=a['label'],arm_B=b['label'],worker_id=m['worker'],object_id=ob[0],pair_index=ob[1],
     status='common' if ob in common else ('removed' if ag else 'incoming'),A_group=ag['feature_id'] if ag else '',B_group=bg['feature_id'] if bg else '',
     common_groupmates_changed=(obs(ag)&common != obs(bg)&common) if ob in common else None))
 # A bounded correspondence diagnostic, not a new fusion: why the adjacent
 # two-person n22 group cannot simply be added to the nine-vote group.
 from tools.thesis_main.analysis.ring_correspondence_20261007 import cyclic_match, angular as frozen_angular, _pairs
 c=cases[1];t=c['teams'][2];mm={m['worker_id']:m for m in c['members']};gl={g['feature_id']:g for g in t['full_state']['identity_groups']}
 for a in gl['node_013']['members']:
  for b in gl['node_008']['members']:
   aa,ra=_pairs(mm[a['worker']]);bb,rb=_pairs(mm[b['worker']]);assert ra is None and rb is None
   cost=(frozen_angular(aa[:,0]-.5,bb[:,0]-.5)+frozen_angular(aa[:,1]-.5,bb[:,1]-.5))/2
   mat=cyclic_match(cost,gap=e.WORKING_GAP);pa,pb=a['pair_index'],b['pair_index']
   tables['LOCAL_R8_FULL_RING_CORRESPONDENCE'].append(dict(case_id=c['case_id'],arm='C',worker_A=a['worker'],worker_B=b['worker'],
    pair_index_A=pa,pair_index_B=pb,group_A='node_013',group_B='node_008',local_mean_top_bottom_angle_deg=float(cost[pa,pb]),
    full_ring_matched=[pa,pb] in mat['matches'],matched_B_for_A=next((j for i,j in mat['matches'] if i==pa),None),
    gap_per_omitted_node_deg=e.WORKING_GAP,full_ring_matches_json=__import__('json').dumps(mat['matches'])))
 for name,rows in tables.items():e.csv(name+'.csv',pd.DataFrame(rows))
 e.save(HERE/'MECHANISM_ANALYSIS_RECEIPT.json',dict(existing_endpoints_analyzed=6,new_fusion_calls=0,score_calls=0,
  median_max_abs_error=max_error,focus_group_definitions=FOCUS,
  reference_matching='paired max top/bottom angles, Hungarian assignment, visualization only; no replacement of native identity or score',
  intersection_check='Shapely validity and nonadjacent straight segment intersections of unchanged native footprint',
  no_repairs=True,source_ring_unconfirmed_kept=True,local_pairwise_correspondence_probes=18))
 print('Saved local pair votes, raw validity, exact intersections and source-ring transmission; zero fusion and scoring.',flush=True)

if __name__=='__main__':main()
