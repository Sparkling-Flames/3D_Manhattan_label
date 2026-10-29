"""Read-only mechanism verification of the selected fixed-XZ, two-D-person case."""
from pathlib import Path
import csv,gzip,hashlib,json,math,itertools
from collections import defaultdict
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parents[1];CASE=BASE/'stage06_cases/background_wc2_53'
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obskey(m):return (m['id'],int(m.get('source_pair_index',m['pair_index'])))
def obsmap(e):
 out={}
 for g in e['full_state']['identity_groups']:
  for m in g['members']:
   key=obskey(m);assert key not in out
   out[key]=dict(worker=m['worker'],points=m['points'],feature_id=g['feature_id'],selected=g['selected'],group_support=g['support'])
 return out
def finite_center(g):return g.get('center') is not None and np.isfinite(np.asarray(g['center'])).all()
def save(d,name):
 d=d if isinstance(d,pd.DataFrame) else pd.DataFrame(d)
 with open(OUT/name,'w',encoding='utf-8-sig',newline='') as f:d.to_csv(f,index=False)
def differences(a,b,path='geometry'):
 if isinstance(a,dict):
  assert set(a)==set(b)
  return [r for k in a for r in differences(a[k],b[k],path+'.'+k)]
 if isinstance(a,list):
  assert len(a)==len(b)
  return [r for i,(x,y) in enumerate(zip(a,b)) for r in differences(x,y,f'{path}[{i}]')]
 return [] if a==b else [dict(path=path,before=a,after=b)]
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 selectpath=BASE/'stage05_funnel_bridge/BACKGROUND_WC2_53_REPRESENTATIVE_SELECTION.json'
 selection=json.loads(selectpath.read_text());s=selection['selected_background_comparison']
 ep={tag:load(CASE/'trace_endpoints'/(s[tag+'_team_key']+'.json.gz')) for tag in ['B_A','B_C','F_A','F_C']}
 trace={tag:load(CASE/'traces'/(s[tag+'_event_id']+'.json.gz')) for tag in ['B','F']}
 original=json.loads((BASE/'stage05_funnel_bridge/BACKGROUND_WC2_53_SELECTED_FOUR_GEOMETRIES.json').read_text())
 x=set(s['X_workers'].split('|'));z=set(s['Z_workers'].split('|'));bd=set(s['B_D_workers'].split('|'));fd=set(s['F_D_workers'].split('|'))
 assert len(x)==len(z)==9 and len(bd)==len(fd)==2 and not bd&fd and not x&z
 groups=[];arms=[]
 for tag,e in ep.items():
  branch,arm=tag.split('_');core=x if arm=='A' else z;D=bd if branch=='B' else fd;fs=e['full_state']
  assert set(e['member_workers'])==core|D and len(e['member_workers'])==e['k']==fs['n']==11
  assert fs['minimum_support']==6 and e['minimum_support']==6 and not e['location_unresolved']
  assert e['geometry']==original[tag]['geometry'],'Export must preserve the saved native endpoint geometry exactly'
  selected={g['feature_id'] for g in fs['identity_groups'] if g['selected']}
  assert len(selected)==e['nodes'] and set(fs['candidate']['feature_ids'])==selected
  for g in fs['identity_groups']:
   ws={m['worker'] for m in g['members']};assert len(ws)==g['support'] and bool(g['selected'])==(2*g['support']>=11)
   assert finite_center(g)
   groups.append(dict(arm=tag,feature_id=g['feature_id'],selected=g['selected'],support=g['support'],threshold=6,
    core_support=len(ws&core),background_support=len(ws&D),workers='|'.join(sorted(ws)),center_json=json.dumps(g['center'],separators=(',',':')),
    observation_keys_json=json.dumps(sorted([list(obskey(m)) for m in g['members']]),separators=(',',':'))))
  complete=[a['worker'] for a in fs['assignments'] if selected<=set(a['feature_ids'])]
  ring=fs['ring_diagnostics'];claimed={w for alt in ring['alternatives'] for w in alt['workers']}
  assert set(complete)==claimed and not ring['tied_best']
  arms.append(dict(arm=tag,team_key=e['team_key'],nodes=e['nodes'],all_identity_groups=len(fs['identity_groups']),unselected_groups=sum(not g['selected'] for g in fs['identity_groups']),
    all_group_centers_resolved=True,complete_projected_source_ring_workers='|'.join(sorted(complete)),complete_source_ring_n=len(complete),
    minimum_direct_edge_support=min(q['direct_support'] for q in ring['edges']),minimum_projected_edge_support=min(q['projected_support'] for q in ring['edges']),
    **{k:e[k] for k in ['B8L2','D10','reference_nodes','ref_node_recall_9','ref_edge_recall_9','omission','extension','boundary_loss','direction_loss','height_loss','geometry_area_h2','height_mean_h','score_status']}))
 save(groups,'ALL_FOUR_ENDPOINT_IDENTITY_GROUPS.csv');save(arms,'FOUR_ENDPOINT_MECHANISM_SUMMARY.csv')
 # Match original observation identity and coordinates, never feature-id labels
 # alone, across the two independently recomputed full-team groupings.
 bo,fo=obsmap(ep['B_C']),obsmap(ep['F_C']);bz={k:v for k,v in bo.items() if v['worker'] in z};fz={k:v for k,v in fo.items() if v['worker'] in z}
 assert set(bz)==set(fz)
 obs=[]
 for key,b in bz.items():
  f=fz[key];assert b['worker']==f['worker'] and b['points']==f['points']
  obs.append(dict(worker=b['worker'],object_id=key[0],source_pair_index=key[1],points_json=json.dumps(b['points']),
    B_group=b['feature_id'],F_group=f['feature_id'],B_selected=b['selected'],F_selected=f['selected'],B_group_support=b['group_support'],F_group_support=f['group_support']))
 save(obs,'EXACT_SAME_Z_OBSERVATION_GROUP_ASSIGNMENTS.csv')
 # Compare coassignment of immutable observations, which is invariant to
 # arbitrary renumbering of identity groups between the two teams.
 core_comparisons=[];pair_changes=[]
 for arm,core in [('A',x),('C',z)]:
  b={k:v for k,v in obsmap(ep['B_'+arm]).items() if v['worker'] in core}
  f={k:v for k,v in obsmap(ep['F_'+arm]).items() if v['worker'] in core}
  assert set(b)==set(f) and all(b[k]['worker']==f[k]['worker'] and b[k]['points']==f[k]['points'] for k in b)
  added=removed=0
  for k,l in itertools.combinations(sorted(b),2):
   old=b[k]['feature_id']==b[l]['feature_id'];new=f[k]['feature_id']==f[l]['feature_id']
   if old==new:continue
   added+=int(new);removed+=int(old)
   pair_changes.append(dict(arm=arm,worker1=b[k]['worker'],object_id1=k[0],source_pair_index1=k[1],
    worker2=b[l]['worker'],object_id2=l[0],source_pair_index2=l[1],B_coassigned=old,F_coassigned=new))
  cs={t:sorted(sum(m['worker'] in core for m in g['members']) for g in ep[t+'_'+arm]['full_state']['identity_groups'] if g['selected']) for t in ['B','F']}
  if arm=='A':assert len(b)==50 and (added,removed)==(0,8) and cs=={'B':[6,7,9,9],'F':[6,7,8,9]}
  else:assert len(b)==43 and (added,removed)==(13,4) and cs=={'B':[5,7,7,9],'F':[4,7,7,7,9]}
  core_comparisons.append(dict(arm=arm,immutable_observations=len(b),all_unordered_observation_pairs=len(b)*(len(b)-1)//2,
   new_coassignments=added,removed_coassignments=removed,B_selected_core_support_json=json.dumps(cs['B']),F_selected_core_support_json=json.dumps(cs['F'])))
 save(core_comparisons,'IMMUTABLE_CORE_COASSIGNMENT_SUMMARY.csv')
 save(pair_changes,'IMMUTABLE_CORE_COASSIGNMENT_CHANGES.csv')
 bg={g['feature_id']:g for g in ep['B_C']['full_state']['identity_groups']};fg={g['feature_id']:g for g in ep['F_C']['full_state']['identity_groups']}
 assert bg['node_005']['center']==fg['node_005']['center'] and {obskey(m) for m in bg['node_005']['members']}=={obskey(m) for m in fg['node_005']['members']}
 assert {m['worker'] for m in bg['node_000']['members']}=={'W008','W013','W029'} and bg['node_000']['support']==3 and not bg['node_000']['selected']
 assert {m['worker'] for m in bg['node_009']['members']}=={'W034','W122'} and bg['node_009']['support']==2 and not bg['node_009']['selected']
 assert {m['worker'] for m in fg['node_000']['members']}=={'W008','W013','W017','W029','W034','W126'} and fg['node_000']['support']==6 and fg['node_000']['selected']
 w034=[r for r in obs if r['worker']=='W034' and r['source_pair_index']==0];assert len(w034)==1 and w034[0]['B_group']=='node_009' and w034[0]['F_group']=='node_000'
 assert {obskey(m) for m in fg['node_000']['members'] if m['worker'] in z}=={obskey(m) for m in bg['node_000']['members']}|{obskey(m) for m in bg['node_009']['members'] if m['worker']=='W034'}
 assert [a for a in arms if a['arm']=='B_C'][0]['complete_projected_source_ring_workers']=='W014|W034'
 assert [a for a in arms if a['arm']=='F_C'][0]['complete_projected_source_ring_workers']=='W034'
 edge=[e for e in ep['F_C']['full_state']['ring_diagnostics']['edges'] if e['feature_ids']==['node_005','node_000']];assert len(edge)==1
 assert edge[0]['direct_support']==edge[0]['projected_support']==3 and set(edge[0]['direct_workers'])=={'W008','W013','W034'}
 assert ep['B_C']['ref_matched_nodes_9']==[0,6,7] and ep['F_C']['ref_matched_nodes_9']==[0,2,6,7]
 assert ep['B_C']['ref_edge_recall_9']==ep['F_C']['ref_edge_recall_9']==.25 and ep['F_C']['reference_nodes']==8
 assert ep['F_C']['omission']<ep['B_C']['omission'] and ep['F_C']['boundary_loss']<ep['B_C']['boundary_loss'] and ep['F_C']['direction_loss']<ep['B_C']['direction_loss']
 assert ep['F_C']['extension']>ep['B_C']['extension'] and ep['F_C']['height_loss']>ep['B_C']['height_loss']
 beforepath=CASE/'trace_diagnostics/before_saved.json.gz';afterpath=CASE/'trace_diagnostics/after_trace.json.gz'
 before,after=load(beforepath),load(afterpath);diff=differences(before['geometry'],after['geometry'])
 assert len(diff)==1 and diff[0]['path']=='geometry.footprint[0][1]'
 delta=abs(diff[0]['before']-diff[0]['after']);ulp=max(math.ulp(diff[0]['before']),math.ulp(diff[0]['after']));assert delta==ulp==4.440892098500626e-16
 assert ep['B_A']['geometry']==before['geometry'] and ep['B_A']['full_state']['candidate']==after['full_state']['candidate']
 assert before['geometry']['points']==after['geometry']['points']==ep['B_A']['full_state']['candidate']['points']
 assert before['B8L2']==after['B8L2'] and before['D10']==after['D10']
 records={r['worker']:r for r in trace['F']['pool']['records']};behavior=[]
 for w in sorted(bd|fd):
  r=records[w];behavior.append(dict(worker=w,background='F_neutral' if w in fd else 'B_outside',original_corner_pairs=len(r['points'])//2,
    recorded_individual_B8L2=r.get('B8L2'),recorded_individual_D10=r.get('D10'),source_ring_confirmed=r['ring_confirmed'],object_id=r['id']))
 save(behavior,'FOUR_BACKGROUND_WORKERS_ORIGINAL_ANSWERS.csv')
 files=[selectpath,beforepath,afterpath,*[CASE/'trace_endpoints'/(s[tag+'_team_key']+'.json.gz') for tag in ep],*[CASE/'traces'/(s[tag+'_event_id']+'.json.gz') for tag in trace]]
 receipt=dict(status='passed',scope='fixed-XZ four-endpoint mechanism; no eligibility/reference/label reaudit',
  physical_background_comparison_id=s['physical_background_comparison_id'],same_XZ=True,n=11,m=9,D_each=2,MV50_minimum=6,
  same_Z_original_observations_checked=len(obs),same_Z_original_coordinates_identical=True,all_four_original_native_geometries_preserved_exactly=True,
  immutable_core_coassignment_summary=core_comparisons,common_C_node005_center_and_observation_members_exactly_equal=True,
  all_group_centers_resolved=True,old_C_selected_nodes=4,new_C_selected_nodes=5,
  mechanism='W034/source_pair0 changes identity-group coassignment; four unchanged Z observations plus two F-background observations produce support 6 at the new selected group. Identity regrouping and crossing the full-team MV50 threshold both occur.',
  old_group0_workers=['W008','W013','W029'],old_group9_workers=['W034','W122'],new_group0_workers=['W008','W013','W017','W029','W034','W126'],
  old_C_complete_projected_source_ring_workers=['W014','W034'],new_C_complete_projected_source_ring_workers=['W034'],
  selected_edge005_to000_direct_and_projected_support=3,all_edges_majority_supported=False,
  reference_nodes=8,old_C_ref_node_recall9=.375,new_C_ref_node_recall9=.5,reference_edge_recall9_unchanged=.25,
  improvements=['B8L2','D10','omission_decreased','boundary_loss_decreased','direction_loss_decreased'],
  adverse_components=['extension_increased','height_loss_increased'],
  residual_interpretation='A higher scored conditional output still omits reference structure; one complete source ring and sub-majority edge supports are not evidence of majority support for the whole cycle.',
  one_ulp_scope='B_A derived footprint[0][1] only; ERP points, topology/IDs and other geometry fields exactly identical; exported native geometry remains original; full_state retains the raw trace candidate.',
  one_ulp_absolute_difference=delta,derived_geometry_json_hash_identical=False,
  no_counterfactual_claim_that_removing_one_person_at_changed_n_would_remove_node=True,
  new_fusions=0,new_scores=0,new_teams=0,source_files=[dict(path=str(p.relative_to(BASE)),sha256=sha(p)) for p in files])
 (OUT/'WC2_FULL_STATE_INDEPENDENT_REVIEW.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
 text='''# wc2JMjhGNzB-53 固定X/Z、只换2人背景的机制独审

独审通过。原生团队、参考、标签、全部原答和评分均未修改；本阶段只读既有 full_state。

四个团队均为 n=11、X/Z各9人、D各2人，节点门槛为6。共同Z共有43份角点对观测，逐一核对原对象ID、原始pair索引和坐标，背景更换前后完全相同。

## 确实发生了身份重组与过票

旧B-outside的C队 node_000只有W008/W013/W029三票；W034的原始角点0归在node_009，与W122一起只有两票，两个组都未入选。
新F-neutral的C队中，W034的同一份原始角点0改归前三人的组，再与背景W017、W126的观测形成六票：**4份共同Z观测+2份F背景观测=6**，正好通过冻结MV50，成为第五个节点。
所以不能只说给某个固定旧组加了两票；共同原答的身份分组也改变了。九人块在人数上超过门槛，不代表九人对该节点都有相同表达。

这里的票数说明限于同n=11的实际分组。没有推演“删除一个人后节点必消失”：删人会改变n和门槛，也可能再次改变身份分组，本轮没有做该反事实融合。

按不可变的原始观测对来比较归组（不把节点编号变化算作归组变化），C的43份共同Z观测中有13对新增同组关系、4对解除同组关系。A的50份共同X观测也有8对解除同组关系：W001的一份观测退出原来的九人组，不能把A写成完全不重组。但A四个选中组的X支持数从[6,7,9,9]变为[6,7,8,9]，仍全部达到六票门槛，所以选中节点仍为四个。节点归组的变化是否改变最终结构，取决于它发生在门槛的哪一侧，不能只看有没有归组变化。

## 位置已决，连接仍有条件性

全部四队所有身份组中心都已解决，新旧C队都有可用点序列，因此这不是定位未决或旧字段no_connection造成的对照。
但完整投影来源环由旧C的W014/W034两人减少为新C仅W034一人。
新环边node_005→node_000的直接与投影支持均为3票，低于节点门槛6。
冻结方法可以选取最受支持的完整投影来源环并产生可评分输出，不能把这一输出解释为每条边或整个环都获多数支持。

## 升质仍伴随残余结构及分项问题

旧C B8L2=33.1090、D10=33.7732，新C为67.2328和70.7126。
参考仍有8个节点；9°保留从3/8变为4/8，新增匹配参考节点2（ERP x=16.23），参考边保留仍为25%。
omission、boundary_loss与direction_loss下降，但extension和height_loss增加。
因此这是明显改善而仍不完整的结构表达，不能写成恢复了全部参考结构或所有分项同向改善。

需要人工进一步核查时，可直接查看新增节点的ERP位置x≈8.946、top y≈205.015、bottom y≈317.300，与参考x=16.23附近的短结构是否对应；同时查看接缝附近参考x≈1013/16/18及x≈91/99/108的细转折。
共同七票的node_005位置x≈939.704在两个C输出中完全相同，也应结合原图判断其真实边界含义。票多本身不能代替与图像、正式目标的对应。

背景成员的本图实际标法也有差别：F的W017(C2)与W126(C3)各有8个角点对；B的W027(C3)只有4对、W122(C3)为8对。
历史类别不能替代本图具体成员的原答。此例同时改变了背景具体成员和类别构成，不能单独分离二者。

## 1 ULP处理已核验

B_A的回放仅派生geometry.footprint[0][1]出现一个ULP、4.440892098500626e−16的差异。
ERP所有角点、节点ID顺序和其它geometry字段逐值相同；B8L2/D10相同。
导出端点geometry与原先保存值完全一致，full_state.candidate保留原始回放值；before/after及差异回执均保留。
没有把Q相等当成完整geometry JSON相等，也没有修改正式原生端点。

逐组原始支持与中心、全部43份共同Z观测的跨背景归组、四队几何/评分与四个背景成员原答统计都在本目录CSV中。
WC2_FULL_STATE_INDEPENDENT_REVIEW.json 保存断言、边界和每个原始来源文件哈希；查看器及完整票账仍在 stage06_cases/background_wc2_53。
'''
 (OUT/'README_ZH.md').write_text(text,encoding='utf-8')
 manifest=[]
 for p in sorted(OUT.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts or p.name in ['MANIFEST.csv','READABILITY_RECEIPT.json']:continue
  n=None
  if p.name.endswith('.csv'):
   with open(p,encoding='utf-8-sig',newline='') as f:
    rr=csv.reader(f);header=next(rr);assert len(header)==len(set(header));n=0
    for row in rr:assert len(row)==len(header);n+=1
  elif p.name.endswith('.json'):json.loads(p.read_text())
  elif p.name.endswith('.py'):compile(p.read_text(),str(p),'exec')
  else:p.read_text(encoding='utf-8')
  manifest.append(dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size,rows=n))
 save(manifest,'MANIFEST.csv');proof=dict(status='passed',files=len(manifest),all_csv_read_to_EOF=True,all_json_parsed=True,all_python_compiled=True,new_fusions=0,new_scores=0,formal_sources_unchanged=True)
 (OUT/'READABILITY_RECEIPT.json').write_text(json.dumps(proof,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k!='source_files'},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
