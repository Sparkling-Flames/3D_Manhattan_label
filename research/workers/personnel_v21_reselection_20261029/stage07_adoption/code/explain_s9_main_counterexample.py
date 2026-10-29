#!/usr/bin/env python3
"""Read six existing OPPJOINT ABC traces; no new teams, labels or fusion.

Writes the target-scope / vote / source-ring evidence and one diagnostic figure.
Run with PYTHONPATH=/tmp/hohonet_v21_deps python <this file> from the work root.
"""
from pathlib import Path
import sys,json,gzip,hashlib,importlib.util,math,shutil
import numpy as np,pandas as pd
from shapely.geometry import Polygon

W=Path(__file__).resolve().parents[2]
R=W.parent/'HOHONET_v21_20261029'
O=W/'stage07_adoption/main_direction_counterexample'
T=O/'traces'
spec=importlib.util.spec_from_file_location('case_render',W/'cases/code/render_exact_abc_case.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
plt=v.plt
events=pd.read_csv(O/'S9_09_EXACT_EVENTS.csv.gz',keep_default_na=False)
cases=[v.read(T/(eid+'.json.gz')) for eid in events.event_id]
dr=json.loads((R/'research/data/releases/v2.1/difficulty_records.json').read_text())
dr=next(x for x in dr['records'] if x['image']=='S9hNv5qa7GM-09')
old=next(x for x in dr['candidates'] if x['role']=='selected_gt')['floor']
ref=cases[0]['reference']
meta=cases[0]['pool']['meta']
old_poly=Polygon(old);current_poly=Polygon(ref['floor_xz_h'])
adjudication={
 'repository_commit':'a476461d7ede8db95da43de4139e612c05e618bc',
 'data_release':'v2.1','current_reference':ref,
 'difficulty_record':dr,
 'source_files':['research/data/releases/v2.1/difficulty_records.json','research/data/releases/v2.1/reference_catalog.json','research/data/releases/v2.1/reference_bindings.csv'],
 'current_pool_target_id':meta['reference_id'],
 'binding_unchanged':True,
 'interpretation':'Current official pool binds all 35 records to the sole admitted four-corner target. Six-corner local expressions resemble the previous wider GT; retained as scope-expression risk, not a newly admitted target or fictitious structure.'}
(O/'S9_09_EXISTING_SCOPE_ADJUDICATION.json').write_text(json.dumps(adjudication,ensure_ascii=False,indent=2)+'\n')

arms=[];vv=[];rings=[];es=[];raw=[]
numeric=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','boundary_loss','direction_loss','height_loss','global_height_loss','local_height_loss','omission','extension','height_mean_h','height_mean_ratio','geometry_area_h2','centroid_x_h','centroid_z_h','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','minimum_support','source_time_total_seconds','source_time_known_n','target_time_known_n','recorded_time_total_seconds','target_individual_B8L2_mean']
for case in cases:
 e=case['event'];eid=e['event_id'];arms0=case['arms'];pool=case['pool'];
 group=v.votes(case)
 def role(x):
  return '共同三角之一' if x<780 else '矩形止界角点' if x<820 else '旧分支三个角点之一'
 group['local_role']=group.azimuth_px.map(role);vv.append(group)
 row={k:e[k] for k in ['event_id','block_id','background_id','background_replicate','background_target_n','pool_id','image','method','source_class','target_class','n','m','D','X','Y','Z','A_members','B_members','C_members','A_team_key','B_team_key','C_team_key','A_class_vector','B_class_vector','C_class_vector']}
 cg=group[group.arm.eq('C')]
 rr=cg[cg.local_role.eq('矩形止界角点')];bb=cg[cg.local_role.eq('旧分支三个角点之一')]
 row.update(rectangle_corner_support=int(rr.support.iloc[0]),branch_corner_support_min=int(bb.support.min()),branch_corner_support_max=int(bb.support.max()),C_selected_nodes=arms0['C']['nodes'],C_failure=not bool(arms0['C']['connection_available']),C_geometry_reason=arms0['C']['geometry_reason'],C_score_status=arms0['C']['score_status'])
 for arm,a in arms0.items():
  scalar={k:a.get(k) for k in numeric}
  scalar.update(event_id=eid,block_id=e['block_id'],background_id=e['background_id'],arm=arm,team_key=a['team_key'],members=e[arm+'_members'],score_status=a.get('score_status'),geometry_status=a.get('geometry_status'),geometry_reason=a.get('geometry_reason'),connection_available=a.get('connection_available'),order_status=a.get('order_status'),time_source_kinds=a.get('time_source_kinds'))
  points=(a.get('geometry')or{}).get('points');p=v.points3d(points) if points else None
  if p is not None:
   poly=Polygon(p[1][:,:2]);scalar['diagnostic_iou_current_target']=poly.intersection(current_poly).area/poly.union(current_poly).area
   scalar['diagnostic_iou_previous_GT']=poly.intersection(old_poly).area/poly.union(old_poly).area
   scalar['diagnostic_current_target_extra_area_h2']=poly.difference(current_poly).area
  arms.append(scalar)
  row[arm+'_Q']=a.get('B8L2');row[arm+'_D10']=a.get('D10');row[arm+'_source_record_seconds']=a.get('source_time_total_seconds');row[arm+'_nodes']=a.get('nodes')
  selected={g['feature_id'] for g in a['full_state']['identity_groups'] if g['selected']}
  for assignment in a['full_state']['assignments']:
   present=set(assignment['feature_ids']);rings.append(dict(event_id=eid,arm=arm,worker=assignment['worker'],object_id=assignment['id'],source_feature_ring='|'.join(assignment['feature_ids']),selected_feature_ids='|'.join(sorted(selected)),selected_count=len(selected),observed_selected_count=len(selected&present),covers_all_selected=selected.issubset(present),missing_selected='|'.join(sorted(selected-present)),native_source_ring_confirmed=assignment.get('source_ring_confirmed'),native_source_order_status=assignment.get('source_order_status')))
 for metric in ['Q','D10','source_record_seconds']:
  for ab in ['BA','CA','CB']:
   a,b=row[ab[0]+'_'+metric],row[ab[1]+'_'+metric]
   row[ab+'_'+metric]=(a-b) if a is not None and b is not None else None
 for ab in ['BA','CA','CB']:
  a,b=row[ab[0]+'_source_record_seconds'],row[ab[1]+'_source_record_seconds']
  row[ab+'_source_record_pct']=(a/b-1)*100 if a is not None and b else None
 row['mechanism']=('half_vote_incompatible_rings' if row['C_failure'] else 'four_corner_target_retained' if row['C_nodes']==4 else 'six_corner_previous_scope_branch_selected')
 es.append(row)
 for block in ['D','X','Y','Z']:
  for worker in e[block].split('|'):
   r=next(r for r in pool['records'] if r['worker_id']==worker)
   raw.append(dict(event_id=eid,block=block,worker=worker,object_id=r['object_id'],raw_corner_count=len(r['points'])//2,raw_Q=r.get('B8L2'),source_time_seconds=r.get('source_time_seconds'),time_source_kind=r.get('time_source_kind'),points_json=json.dumps(r['points'],separators=(',',':'))))

es=pd.DataFrame(es);arms=pd.DataFrame(arms);votes=pd.concat(vv,ignore_index=True);rings=pd.DataFrame(rings)
es.to_csv(O/'S9_09_ALL_SIX_EVENTS_WITH_MECHANISM.csv',index=False,encoding='utf-8-sig')
arms.to_csv(O/'S9_09_ABC_ALL_COMPONENTS.csv',index=False,encoding='utf-8-sig')
votes.to_csv(O/'S9_09_ALL_VOTE_GROUPS.csv',index=False,encoding='utf-8-sig')
rings.to_csv(O/'S9_09_SOURCE_RING_COVERAGE.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(raw).to_csv(O/'S9_09_DXYZ_RAW_ANSWERS.csv',index=False,encoding='utf-8-sig')

# Grouping stability is tested through original observation IDs, not feature IDs.
links=[]
for block in events.block_id.unique():
 cc=[c for c in cases if c['event']['block_id']==block]
 for left,right in zip(cc[:-1],cc[1:]):
  la=left['arms']['C'];ra=right['arms']['C']
  def mapping(a):
   return {(m['id'],m['source_pair_index']):g['feature_id'] for g in a['full_state']['identity_groups'] for m in g['members']}
  lm,rm=mapping(la),mapping(ra);common=sorted(set(lm)&set(rm));diff=0;total=0
  for i,x in enumerate(common):
   for y in common[i+1:]:
    total+=1;diff+=((lm[x]==lm[y])!=(rm[x]==rm[y]))
  links.append(dict(block_id=block,left_event=left['event']['event_id'],right_event=right['event']['event_id'],common_workers='|'.join(sorted(set(left['event']['C_members'].split('|'))&set(right['event']['C_members'].split('|')))),common_raw_observations=len(common),common_observation_pairs=total,coassignment_changed_pairs=diff,left_D=left['event']['D'],right_D=right['event']['D'],D_removed='|'.join(sorted(set(left['event']['D'].split('|'))-set(right['event']['D'].split('|')))),D_added='|'.join(sorted(set(right['event']['D'].split('|'))-set(left['event']['D'].split('|'))))))
links=pd.DataFrame(links);links.to_csv(O/'S9_09_BACKGROUND_PATH_GROUP_STABILITY.csv',index=False,encoding='utf-8-sig')

# One complete-path figure, with no invented ring for the failed middle C.
from PIL import Image
original=W/'cases/originals/S9hNv5qa7GM-09.png'
shutil.copy2(original,O/'S9hNv5qa7GM-09_original.png')
im=np.asarray(Image.open(original).convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
fig,ax=plt.subplots(3,3,figsize=(17.7,11.7),gridspec_kw={'height_ratios':[1.05,1.05,.95]})
colors=['#176c8c','#ad3e5b','#cb6928']
path=cases[:3]
for j,case in enumerate(path):
 e=case['event'];a=case['arms']['C'];p=a['geometry'].get('points');color=colors[j];ev=es[es.event_id.eq(e['event_id'])].iloc[0]
 title=['背景 ①：矩形角 7 票，分支各 5 票','背景 ②：两种表达各 6 票','背景 ③：矩形角 5 票，分支各 7 票'][j]
 ax[0,j].imshow(im,extent=[0,1024,512,0]);v.erp(ax[0,j],ref['points_1024x512'],'#111111',1.6,.96,'--');v.erp(ax[0,j],p,color,2.2,1.)
 ax[0,j].set(xlim=(0,1024),ylim=(512,0),xlabel='ERP 水平像素',ylabel='ERP 竖直像素')
 ax[0,j].set_title(title+'\nC Q='+v.number(a.get('B8L2'))+'；C−B='+v.number(ev.CB_Q),fontsize=12)
 v.bev(ax[1,j],ref['points_1024x512'],'#111111',2.,.96,'--',True)
 closed=np.vstack([old,old[0]]);ax[1,j].plot(closed[:,0],closed[:,1],color='#9761a0',ls=':',lw=1.7,alpha=.9,label='旧 GT 范围（仅对照）')
 members={r['worker_id']:r for r in case['pool']['records']}
 for worker in e['Z'].split('|'):v.bev(ax[1,j],members[worker]['points'],color,.7,.22)
 for worker in e['D'].split('|'):v.bev(ax[1,j],members[worker]['points'],'#666666',.7,.18)
 v.bev(ax[1,j],p,color,2.5,1.,dots=True)
 if not p:
  for g in a['full_state']['identity_groups']:
   if g['selected']:
    center=np.asarray(g['center']);bottom=center[1];u=bottom[0]*2*np.pi/1024;r=1/np.tan((bottom[1]/512-.5)*np.pi)
    ax[1,j].scatter([-np.sin(u)*r],[np.cos(u)*r],c=color,s=36,zorder=8)
    ax[0,j].scatter(center[:,0],center[:,1],c=color,s=20,edgecolors='white',linewidths=.5,zorder=8)
  ax[1,j].text(.03,.91,'7 个入选节点；无可用完整原答环\n仅画点，不补连边',transform=ax[1,j].transAxes,color=color,fontsize=10)
 ax[1,j].set(xlim=(-.8,1.97),ylim=(-.53,1.2),xlabel='x / 相机高',ylabel='z / 相机高');ax[1,j].set_aspect('equal');ax[1,j].grid(alpha=.15);ax[1,j].plot(0,0,'k+',ms=8)
 change=['固定 X/Y/Z；D 含 W120、W124','D 中 W120 → W122','D 中 W124 → W102'][j]
 ax[1,j].set_title(change,fontsize=11)
 gg=votes[(votes.event_id==e['event_id'])&(votes.arm=='C')].sort_values('azimuth_px')
 for k,r in enumerate(gg.itertuples()):
  alpha=.95 if r.selected else .22
  ax[2,j].bar(k,r.D_support,color='#909aa5',alpha=alpha,width=.75)
  ax[2,j].bar(k,r.replacement_support,bottom=r.D_support,color=color,alpha=alpha,width=.75)
  ax[2,j].text(k,r.support+.12,str(r.support),ha='center',fontsize=10)
 ax[2,j].axhline(6,color='#a92f3e',ls='--',lw=1.4)
 ax[2,j].set_xticks(np.arange(len(gg)),['共角' if r.local_role=='共同三角之一' else '止界角' if r.local_role=='矩形止界角点' else '分支角' for r in gg.itertuples()],fontsize=9)
 ax[2,j].set(ylim=(0,13.5),ylabel='独立人员票数');ax[2,j].grid(axis='y',alpha=.15)
 ax[2,j].set_title('灰色＝共同背景 D；有色＝固定 Z；浅色＝未入选',fontsize=10)
from matplotlib.lines import Line2D
fig.legend(handles=[Line2D([0],[0],color='#111111',ls='--',lw=2,label='当前裁定目标（四角）'),Line2D([0],[0],color='#9761a0',ls=':',lw=2,label='旧 GT 范围（六角，仅几何对照）'),Line2D([0],[0],color='#cb6928',lw=2.5,label='C 融合；细线为完整原答'),Line2D([0],[0],color='#a92f3e',ls='--',label='固定投票门槛＝6')],loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(.5,.005))
fig.suptitle('S9-09｜OPPJOINT K4，n=12、m=6｜同一换入块在不同背景下：改善 → 连接失败 → 范围外扩\nX/Y/Z 均不变；只沿已保存事件更换背景成员。所有队伍沿用当前唯一准入目标，不改评分或空间绑定。',fontsize=14,y=.994)
fig.tight_layout(rect=[0,.047,1,.949],h_pad=2.2,w_pad=2.0)
v.save_figure(fig,O/'S9_09_SCOPE_AND_HALF_VOTE_PATH.png',dpi=160)
v.save_figure(fig,O/'S9_09_SCOPE_AND_HALF_VOTE_PATH.pdf')
plt.close(fig)

def fmt(x,d=2):return '失败' if pd.isna(x) else f'{x:.{d}f}'
lines=['|块／背景|事件 ID|A Q|B Q|C Q|C−A|C−B|C 节点|止界／分支票|结果|','|---|---|---:|---:|---:|---:|---:|---:|---|---|']
for i,r in es.iterrows():
 lines.append(f'|{1 if i<3 else 2}／{i%3+1}|`{r.event_id}`|{fmt(r.A_Q)}|{fmt(r.B_Q)}|{fmt(r.C_Q)}|{fmt(r.CA_Q)}|{fmt(r.CB_Q)}|{r.C_nodes}|{r.rectangle_corner_support}／{r.branch_corner_support_min}|'+('连接失败' if r.C_failure else '四角保留，小幅改善' if r.C_nodes==4 else '旧范围分支进入，明显下降')+'|')
paired=es[es.C_Q.notna()];neg=arms[(arms.arm=='C')&arms.nodes.eq(6)]
paired_b=arms[(arms.arm=='B')&arms.event_id.isin(neg.event_id)]
source_note='用户处理后的库存记录时间；W002 沿用 v1 时间来源，其余为 new 批处理记录。全 12 人来源时间已知，target-specific 时间为 0；合计为记录劳动秒数，不是新测生产用时。'
report=f'''# 主方向反例机制：S9-09 的范围表达与半票连接冲突

**结论：这里的主要代价是已裁定目标范围之外的延伸，并在两种范围表达票数打平时触发连接失败。高度误差与方向误差不是这三个降质事件的主因。** OPPJOINT K4 的楼外低历史 Q → 高历史 Q 方向、n=12/m=6 在本图共有 **6 个既有严格 ABC 事件、2 组固定 X/Y/Z、每组 3 个背景**；4 个 C 可评分，1 个改善、3 个明显下降，另 2 个 C 连接失败。A/B 各 6 队均可评分。全部事件保留，未据结果改类、改目标或删队。

这不是阶段06的 TARGET_DSTRUCT x8-08 失败案例。它属于**本轮采用的 OPPJOINT 主方向**，用于说明主方法的目标范围与背景条件。

## 1. 先读已有裁定：六角分支有历史来源，不能说凭空增加错误结构

仓库 `difficulty_records.json` 已记载用户曾指出“这个有两个空间”，随后确认新四角范围；正式说明是“新范围已固定，原跨空间隐藏分支不再计入”。`selection_reason` 为“采用本次明确确认的新空间，原空间仅对照”。当前 v2.1 的目标是 `{meta['reference_id']}`，参考版本 `{meta['reference_version']}`，人工难度继续为**中等**。几何四角/H=0 不覆写人工难度。

当前官方池将 35 份记录全部绑定 `sole_admitted_space`。本分析完整沿用该绑定，不把六角作答另行准入，不以它们“更像旧 GT”替换正式分数。现有完整几何说明：负向 C 的新增分支十分接近旧六角 GT，因此应解释为**当前目标内比较时的范围表达差异／旧范围延伸风险**，而不是“高 Q 成员总会多画错误细节”。既有空间裁定已足以解释，不要求用户重新裁决。

原图可见窄走道、两侧开口与实体近墙；旧跨出部分不能在本视角全部直接辨认。关于目标边界的采用依据是既有人工作业记录，不从这张全景重新推断空间归属。[裁定原记录与新旧几何](main_direction_counterexample/S9_09_EXISTING_SCOPE_ADJUDICATION.json)已独立保存；[完整原图](main_direction_counterexample/S9hNv5qa7GM-09_original.png)来自官方 Release，仅提取本图，大小与 ZIP CRC 通过。

## 2. 六个事件全部结果

{chr(10).join(lines)}

4 个三队可评分事件中，C−A 平均 **{paired.CA_Q.mean():+.2f}**，C−B 平均 **{paired.CB_Q.mean():+.2f}**；三队可评分时同类绝对 Q 变化 {abs(paired.BA_Q).mean():.2f}，跨类绝对 Q 变化 {abs(paired.CA_Q).mean():.2f}。2 个 C 失败单列为 **2/6**，没有按 0 分填补或从登记分母中删除。三个负向可评分事件的 C−B 均低于 −18 分。

4 个可评分事件的 C−B 库存记录时间均值 **{paired.CB_source_record_pct.mean():+.2f}%**；6 个登记事件含失败 C 的相同记录时间对比为 **{es.CB_source_record_pct.mean():+.2f}%**。{source_note}

[完整六事件与 D/X/Y/Z、ABC 成员](main_direction_counterexample/S9_09_ALL_SIX_EVENTS_WITH_MECHANISM.csv) · [18 端点全分项](main_direction_counterexample/S9_09_ABC_ALL_COMPONENTS.csv) · [完整原答及归属块](main_direction_counterexample/S9_09_DXYZ_RAW_ANSWERS.csv)

## 3. 固定换入块，背景怎样改变结果

第一组 X/Y/Z 完全固定，Z 为 **W002、W109、W112、W115、W126、W130**。其中 W002 支持矩形止界角，另外 5 人共同支持旧分支的三个角；因此不能把整个高 Q 类说成同一张图上都画相同结构。

1. 背景① D=`W105|W110|W118|W120|W124|W127`：矩形止界角 7 票，分支每角 5 票，门槛 6。C 保持四角矩形，相对 B 提高 **+3.49 Q**，底点与边界也改善。
2. 背景②将 W120 换为 W122：止界角与分支各 6 票，**两种互斥局部表达都达到门槛**，共同三角之外又选出 4 个局部点，共 7 节点。每个原答只包含止界角或分支三角的一套表达，没有任何原答环覆盖全部 7 点；冻结融合返回 `no_source_ring_covering_all_selected_nodes` / `no_connection`。本分析不手工补连边。
3. 背景③再将 W124 换为 W102：止界角降至 5，分支三角升至 7，C 可沿六角来源环连接，但从当前四角目标向外伸出，相对 B **−18.75 Q**。

第二组固定块同样出现 6:6 失败、5:7 降质、4:8 降质。因此风险不依赖第一组的单一路径。**背景中的目标类人数**与**实际支持某局部表达的票数**并不相同：第二组背景目标类人数为 0 时也可形成 6:6。这正是需要保存具体成员和原答，而不能只报类别人数的原因。

已对四对相邻背景 C 队的共同原观察逐对检查分组关系：共有 {int(links.common_observation_pairs.sum())} 对原观察，{int(links.coassignment_changed_pairs.sum())} 对共同归组关系改变。这里的主要开关是局部表达的支持票跨门槛，不是把已有观察大规模重新对应；坐标中位数随成员改变，仍有小幅位置变化。[归组核对](main_direction_counterexample/S9_09_BACKGROUND_PATH_GROUP_STABILITY.csv) · [全部 125 个候选组票账](main_direction_counterexample/S9_09_ALL_VOTE_GROUPS.csv) · [每人原答环覆盖](main_direction_counterexample/S9_09_SOURCE_RING_COVERAGE.csv)

![固定 XYZ 的三个背景：ERP、底面及局部投票](main_direction_counterexample/S9_09_SCOPE_AND_HALF_VOTE_PATH.png)

图中黑虚线为当前采用目标，紫点线仅为旧 GT 范围对照；失败 C 只画选中点，不画推测的完整环。三列属于同一 OPPJOINT n12/m6 成员块路径。

## 4. 降质体现在哪些分项

三个可评分负向 C 中，平均外扩项从 B 的 **{paired_b.extension.mean():.3f}** 上升到 C 的 **{neg.extension.mean():.3f}**；底面 IoU 从 **{paired_b.iou_2d.mean()*100:.2f}%** 降到 **{neg.iou_2d.mean()*100:.2f}%**，三维代理 IoU 从 **{paired_b.IoU3D100.mean():.2f}** 降到 **{neg.IoU3D100.mean():.2f}**。平均底点误差从 **{paired_b.S_bottom_deg.mean():.3f}°** 到 **{neg.S_bottom_deg.mean():.3f}°**，边界损失从 **{paired_b.boundary_loss.mean():.4f}** 到 **{neg.boundary_loss.mean():.4f}**。

与此同时，平均方向损失从 **{paired_b.direction_loss.mean():.4f}** 降到 **{neg.direction_loss.mean():.4f}**，高度损失从 **{paired_b.height_loss.mean():.4f}** 降到 **{neg.height_loss.mean():.4f}**；遗漏项 C 平均仅 **{neg.omission.mean():.4f}**。所以“更差”主要落在**范围/外扩、底面覆盖及边界**，不能把所有几何分项都说成恶化。三个六角 C 与旧 GT 的额外诊断底面 IoU 为 **{neg.diagnostic_iou_previous_GT.min()*100:.2f}%–{neg.diagnostic_iou_previous_GT.max()*100:.2f}%**；这是帮助解释结构来源的几何对照，没有另算旧参考 Q 或改变正式评价。

## 5. 对采用判断的影响

OPPJOINT 的群体质量差异仍按全体图／楼结果判断。本图增加一条明确适用边界：**在当前目标空间已裁定、但原答仍保留旧跨空间分支的图片上，换入更高历史 Q 成员并不保证当前目标质量提高；若背景把两个局部表达推到半票附近，既可能扩大范围，也可能失去可连接的来源环。**

因此 S9-09 作为“目标范围表达与背景票数的反例”进入主文，不能当作普通正确性差异来解释。人员类、参与者空间绑定与分数全部保持冻结；后续若正式空间归属记录更新，需单独版本化重算，不能在本轮为改善结论自行改池。当前无需因此否定多数图片上的主方向，也不能把失败藏进可评分均值。

## 6. 复算与实际保存

这里只重放 **6 个既有事件、18 个既有端点**以取 full_state；未新增团队、未重拟标签、未更改融合/评分。最大标量差 {max(x['maximum_scalar_difference'] for x in json.loads((T/'TRACE_SCALAR_PARITY.json').read_text())):.2g}。[重放命令](main_direction_counterexample/EXACT_REPLAY_COMMAND.json) · [逐端点核分](main_direction_counterexample/traces/TRACE_SCALAR_PARITY.json) · [原始六事件全部指标](main_direction_counterexample/S9_09_ALL_SIX_EVENT_METRICS.csv.gz) · [实际说明/作图代码](code/explain_s9_main_counterexample.py)。六份压缩 trace 中包含完整原答、完整 ABC 几何、对应组、门槛和原答环序；以精确 event ID 命名，可按表定位。

代码使用从官方参考和原答导出的相机高归一化坐标；3D 为当前冻结代理，非新测物理房间尺寸。读取提交 `{adjudication['repository_commit']}`，底层数据 v2.1。
'''
(W/'stage07_adoption/MAIN_DIRECTION_COUNTEREXAMPLE_MECHANISM.md').write_text(report,encoding='utf-8')
receipt=json.loads((W/'cases/originals/ORIGINALS_RECEIPT.json').read_text());receipt['images']=[r for r in receipt['images'] if r['image_code']=='S9hNv5qa7GM-09'];receipt['archives']=receipt['archives'][-1:]
(O/'S9_09_ORIGINAL_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
# Read every produced table and decode the plotted PNG, preserving true row counts.
checks={}
for p in sorted(O.glob('*.csv')):
 df=pd.read_csv(p);checks[p.name]={'rows':len(df),'columns':len(df.columns)}
with Image.open(O/'S9_09_SCOPE_AND_HALF_VOTE_PATH.png') as image:image.load();checks['PNG']={'size':list(image.size)}
assert len(es)==6 and len(arms)==18 and int(es.C_failure.sum())==2
assert int(links.coassignment_changed_pairs.sum())==0
checks.update(existing_events=6,replayed_existing_endpoints=18,new_teams=0,new_labels=0,new_targets=0,all6_rows_read=True,complete_trace_files=6,report_exists=(W/'stage07_adoption/MAIN_DIRECTION_COUNTEREXAMPLE_MECHANISM.md').exists())
(O/'READ_CHECK.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'saved_report':str(W/'stage07_adoption/MAIN_DIRECTION_COUNTEREXAMPLE_MECHANISM.md'),'events':6,'C_failures':2,'paired_CA':paired.CA_Q.mean(),'paired_CB':paired.CB_Q.mean(),'coassignment_changes':int(links.coassignment_changed_pairs.sum()),'files':checks},ensure_ascii=False),flush=True)
