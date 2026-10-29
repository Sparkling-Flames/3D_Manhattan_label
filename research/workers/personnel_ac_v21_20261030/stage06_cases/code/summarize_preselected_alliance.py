"""Trace-backed facts for the capacity-preselected seven-union illustration."""
import argparse,gzip,itertools,json
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--case-root',required=True);a=p.parse_args();root=Path(a.case_root)
    end=pd.read_csv(root/'figures/SEVEN_ALLIANCE_ENDPOINTS.csv');pairs=pd.read_csv(root/'figures/ALL_21_CONTRASTS_ORIGINAL_ORIENTATION.csv')
    teams={};traces={}
    for r in end.to_dict('records'):
        with gzip.open(root/'trace_endpoints'/(r['team_key']+'.json.gz'),'rt') as f:t=json.load(f)
        groups=t['full_state']['identity_groups'];selected={g['feature_id'] for g in groups if g['selected']}
        edges=t['full_state']['ring_diagnostics']['edges'];assignments=t['full_state']['assignments']
        traces[r['alliance']]=t
        teams[r['alliance']]={
          'team_key':r['team_key'],'n':t['k'],'all_identity_groups_n':len(groups),'selected_groups_n':len(selected),
          'unselected_groups_n':sum(not g['selected'] for g in groups),
          'all_groups_unanimous':all(g['support']==t['k'] for g in groups),
          'all_source_rings_cover_every_selected_group':all(len(selected)>=3 and len([f for f in x['feature_ids'] if f in selected])==len(selected) and set(f for f in x['feature_ids'] if f in selected)==selected for x in assignments),
          'source_rings_n':len(assignments),'connection_edge_n':len(edges),
          'edge_direct_supports':[x.get('direct_support') for x in edges],
          'edge_projected_supports':[x.get('projected_support') for x in edges],
          'location_policy':t['full_state']['node_consensus']['location_policy'],
          'all_group_centers_resolved':all(g['center'] is not None for g in groups),
          'top_position_subgroup_counts':[len(g['top_position_groups_9deg']) for g in groups],
          'bottom_position_subgroup_counts':[len(g['bottom_position_groups_9deg']) for g in groups],
          'record_time_by_kind':json.loads(t['record_time_by_kind_json'])}
    assert len(teams)==7
    with gzip.open(next((root/'traces').glob('*.json.gz')),'rt') as f:case=json.load(f)
    used=set().union(*(set(t['member_workers']) for t in traces.values()))
    original=[r for r in case['pool']['records'] if r['worker_id'] in used]
    roster=[]
    for record in original:
        label=case['frozen_lobo_labels'][record['worker_id']]
        own={key:(json.dumps(value,ensure_ascii=False,separators=(',',':')) if isinstance(value,(list,dict)) else value) for key,value in record.items()}
        own.update({'history_'+key:value for key,value in label.items()})
        own['source_corner_pair_count']=len(record['points'])//2
        roster.append(own)
    pd.DataFrame(roster).to_csv(root/'ALL35_PERSONNEL_AND_COMPLETE_ORIGINALS.csv',index=False,encoding='utf-8-sig')
    (root/'SINGLE_POOL_MINIMAL_INPUT.json').write_text(json.dumps({'images':[case['pool']]},ensure_ascii=False,separators=(',',':'))+'\n')
    (root/'CURRENT_TARGET_REFERENCE.json').write_text(json.dumps(case['reference'],ensure_ascii=False,indent=2)+'\n')
    facts={'image':case['event']['image'],'selection_basis':'capacity preselected before results',
      'used_people':len(used),'original_answer_corner_pair_counts':sorted({len(r['points'])//2 for r in original}),
      'B8L2_range':[float(end.B8L2.min()),float(end.B8L2.max())],
      'D10_range':[float(end.D10.min()),float(end.D10.max())],
      'area_h2_range':[float(end.geometry_area_h2.min()),float(end.geometry_area_h2.max())],
      'height_h_range':[float(end.height_mean_h.min()),float(end.height_mean_h.max())],
      'max_centroid_distance_h':float(pairs.geometry_centroid_distance_h.max()),
      'max_pair_bev_1_minus_iou':float(pairs.geometry_bev_distance_1_minus_iou.max()),
      'single_source_labor_pairs':int(pairs.labor_same_single_source_valid.sum()),
      'source_count_matched_labor_pairs':int(pairs.labor_source_count_matched_valid.sum()),
      'teams':teams,'no_new_fusion_or_scores':True}
    (root/'MECHANISM_FACTS.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    # Full values remain in CSV/JSON; prose reports enough precision to identify
    # the source cell without pretending sub-unit differences are a universal law.
    table=end[['alliance','n','B8L2','D10','nodes','ref_node_recall_9','geometry_area_h2','height_mean_h']].copy()
    table.columns=['联盟','人数','B8L2','D10','节点','参考节点保留率9°','面积h²','平均高度/h']
    lines=['| '+' | '.join(table.columns)+' |','|'+ '|'.join(['---']*len(table.columns))+'|']
    for row in table.itertuples(index=False,name=None):
        lines.append('| '+' | '.join(str(v).replace('|','+') if i==0 else str(int(v)) if i in [1,4] else f'{float(v):.4f}' for i,v in enumerate(row))+' |')
    c2,c3=traces['C2'],traces['C3'];time2=c2['source_time_total_seconds'];time3=c3['source_time_total_seconds']
    text='''# pa4otMbVnkk-06：35人、17/10/8三类的全部七个联盟

这张图在查看替换效果以前按容量指定，普通Manual、primary目标、OPPJOINT K3楼外冻结标签。C1有17人、C2有10人、C3有8人；七个非空联盟全部执行，21对比较全部保留。它用于展示真实图片池中类别叠加会发生什么，不承担代表全部图片的任务。七个联盟人数不同，这一页不能代替固定人数、固定背景的等量替换分析。

## 七队实际结果

'''+ '\n'.join(lines)+'''

数值来源是 `figures/SEVEN_ALLIANCE_ENDPOINTS.csv`。完整21对的原登记方向已由`input_orientation_sign`恢复，见 `figures/ALL_21_CONTRASTS_ORIGINAL_ORIENTATION.csv`；规范存储方向仍在原事件和查看器中明确保留。

## 结构稳定，但共识位置与质量仍发生变化

35份原答都包含4个角点对。七队各有4个身份对应组，28个组全部得到该队全员支持；没有被隐去的低票组，也没有临界票数导致增删节点。各队全部来源环覆盖其四个入选组，连接正常。参考节点和边的9°保留率均为1。完整票账和连接记录在`tables/`与每队`trace_endpoints/`中，`MECHANISM_FACTS.json`逐队列出这些检查。

因此，这张图的变化可以具体定位到相同结构中的位置估计。原生节点位置政策是“所有身份组成员、每人等权坐标中位数”；加入或移除不同成员会改变中位位置，既能改变底面轮廓、面积和质心，也能改变顶部或高度。不能从“节点数没变”推断输出完全没变。七队面积范围为'''+f"{facts['area_h2_range'][0]:.4f}–{facts['area_h2_range'][1]:.4f} h²"+'''，平均高度范围为'''+f"{facts['height_h_range'][0]:.4f}–{facts['height_h_range'][1]:.4f} h"+'''，两队质心最大距离为'''+f"{facts['max_centroid_distance_h']:.5f} h"+'''。这些单位是相机高度归一化单位，并非房间实测米数。

C2单类10人的B8L2为91.9857，C3单类8人为99.3001；相应方向损失从0.108640降到0.002177，边界损失从0.007534降到0.000145，高度损失从0.002683降到0.000012。分项方向一致，显示这里是同一基本结构上的定位与形状精度变化。比较不同人数的单类队仍同时包含人员数量差异，不能仅凭此例给C2或C3贴永久优劣标签。

人数增加也没有保证Q上升：C3的8人队为99.3001，加入完整C1后25人为98.9252，加入完整C2后18人为98.8444，全部35人为98.1804。相反，C2加入完整C3后从91.9857上升到98.8444。所有这些方向都在全部21对表中，未只保留改善方向。

固定同一C3的8人背景，比较“C1+C3”与“C2+C3”，B8L2只相差−0.0807；相应单类C1→C2相差−4.7068。这提示共同背景能显著改变两类队的实际响应。这里前一比较仍是25→18人，背景所占比例和中位数位置也同时变化；等人数的整类补偿链应与本页并列解释，不把这个差异写成已分离的纯背景因果效应。

## 记录劳动：只解释合法同源部分

C1含1份旧审计来源、16份用户处理报告来源；C2、C3和C2+C3则全是同一用户处理报告来源。本页21对均不满足完全相同的来源计数向量；只有C2、C3、C2+C3彼此的3对满足全部已知且同一单一来源。包含C1的原始总秒数保留作来源审计，但不作合法劳动差值解释。

C2的10人总记录劳动为'''+f'{time2:.3f}秒（每人{time2/c2["k"]:.3f}秒）'+'''，C3的8人为'''+f'{time3:.3f}秒（每人{time3/c3["k"]:.3f}秒）'+'''。C2→C3同时提高Q、减少人数、增加总记录劳动'''+f'{time3-time2:.3f}秒（{100*(time3/time2-1):.2f}%）'+'''；它展示的不是“更多人一定更慢”或“高Q必然省时”，而是本图这些具体成员、类型和人数的记录结果。记录劳动不是融合CPU时间，也不是新做的同步标注时长试验。

## 可以直接核查的材料

- `PA4_06_ALLIANCE_VIEWER_ZH.html`：原图完整嵌入；21对均可切换，逐人开关完整原答，显示所有入选及未入选组、来源顺序、连接边票和完整JSON。联盟方向与规范存储方向分开标明。
- `figures/SEVEN_ALLIANCES_ERP.png`、`SEVEN_ALLIANCES_BEV.png`与同名PDF：七队共同目标、统一坐标范围。底面图不按各队分别缩放。
- `figures/SEVEN_ALLIANCES_ALL_VOTES.png`与CSV：全部28组及C1/C2/C3实际支持人数。
- `MECHANISM_EXPORT_RECEIPT.json`：7个已有注册端点的完整状态回放与已存几何哈希、Q、分项和状态一致；新增物理团队为0。
- `ALL35_PERSONNEL_AND_COMPLETE_ORIGINALS.csv`：本图35人名单、冻结楼外类别及历史字段、完整原答坐标与原答ID；`SINGLE_POOL_MINIMAL_INPUT.json`和`CURRENT_TARGET_REFERENCE.json`给出该合法目标的完整单池输入与参考。

本例没有证据支持“互斥表达同时过票”或“结构因未过门槛丢失”；这些机制应由其它完整案例检查。原图和完整原答已提供，若人工认为当前目标边界之外的门洞或通道需要另一个目标解释，应明确指出位置后作为空间归属问题讨论，不能在本轮根据Q更高重选参考。
'''
    (root/'REPORT_ALLIANCE_PA4_06_ZH.md').write_text(text)
    print(json.dumps({k:v for k,v in facts.items() if k!='teams'}),flush=True)

if __name__=='__main__':main()
