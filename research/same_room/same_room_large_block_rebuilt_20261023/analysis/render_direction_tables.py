#!/usr/bin/env python3
"""Join existing direction statistics to exact fold roles and member designs.

No classification, new fusion, endpoint selection, or re-estimation of the
main effect. Numerical results are copied from DIRECTION_RESULTS.csv with
their explicit weighting/support fields; exact-member and D-context indices
are added from the frozen design.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

def write_csv(x,p):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    x.to_csv(p,index=False,compression='gzip' if str(p).endswith('.gz') else None)

def h(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),default=lambda v:v.item() if isinstance(v,np.generic) else str(v)).encode()).hexdigest()[:20]
def workers(x):return '|'.join(sorted(set('|'.join(x.fillna('').astype(str)).split('|'))-{''}))
def fmt(x,d=3):
    try:return f'{float(x):.{d}f}' if np.isfinite(float(x)) else '—'
    except (TypeError,ValueError):return '—'

def subset_mask(d,subset):
    ordinary=d.ordinary_comparable.astype(str).str.lower().eq('true')
    pure=d.D_n.eq(0)
    door=d.layer_a.str.contains('doorway')|d.layer_b.str.contains('doorway')
    return {'ordinary_all':ordinary,'ordinary_pure':ordinary&pure,
      'ordinary_mixed':ordinary&~pure,'ordinary_mixed_less_half':ordinary&~pure&(2*d.m<d.n),
      'doorway':~ordinary&door,'other_nonordinary':~ordinary&~door}.get(subset,pd.Series(False,index=d.index))

def make_index(d,roles,out):
    k=['method','condition','building','source_role_key','target_role_key','source_class',
      'target_class','source_class_fold_key','target_class_fold_key','n','m','D_class_counts',
      'ordinary_comparable','layer_a','layer_b','scope_comparable']
    rmap={(r.condition,r.method,r.heldout_building,r.class_id):r.role_zh for r in roles.itertuples()}
    rows=[]
    for vals,z in d.groupby(k,dropna=False,sort=True,observed=True):
        r=dict(zip(k,vals));r['background_coverage_id']='DBC_'+h(list(vals))
        counts=json.loads(r['D_class_counts'])
        r['D_semantic_counts']=json.dumps({cl+':'+rmap.get((r['condition'],r['method'],r['building'],cl),'未知类别'):n for cl,n in counts.items()},ensure_ascii=False,sort_keys=True)
        r.update(D_n=int(z.D_n.iloc[0]),m_over_n=float(z.m.iloc[0]/z.n.iloc[0]),
          source_role=z.source_role.iloc[0],target_role=z.target_role.iloc[0],
          events=len(z),pairs=z.pair_key.nunique(),pair_keys_json=json.dumps(sorted(z.pair_key.unique())),
          groups='|'.join(sorted(set('|'.join(z.groups.astype(str)).split('|')))),
          D_member_union=workers(z.D_members),X_member_union=workers(z.X_members),
          Y_member_union=workers(z.Y_members),Z_member_union=workers(z.Z_members),
          source_member_union=workers(pd.concat([z.X_members,z.Y_members])),
          D_exact_sets_json=json.dumps(sorted(set(z.D_members.fillna('').astype(str))),ensure_ascii=False),
          event_ids='|'.join(sorted(z.event_id)))
        rows.append(r)
    ix=pd.DataFrame(rows);write_csv(ix,out/'DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz')
    # One row per fold/direction gives real common workers and the historical
    # center used to interpret the role, without mixing numbered fold labels.
    fk=['method','condition','building','source_class','target_class','source_role_key','target_role_key']
    rows=[]
    for vals,z in d.groupby(fk,dropna=False,sort=True):
        r=dict(zip(fk,vals));r.update(source_role=z.source_role.iloc[0],target_role=z.target_role.iloc[0],
          source_workers=workers(pd.concat([z.X_members,z.Y_members])),target_workers=workers(z.Z_members),
          pairs=z.pair_key.nunique(),events=len(z),actual_n_m='|'.join(f'{int(n)}/{int(m)}' for n,m in sorted(set(zip(z.n,z.m)))),
          source_class_fold_key=z.source_class_fold_key.iloc[0],target_class_fold_key=z.target_class_fold_key.iloc[0])
        for prefix in ['source','target']:
            rr=roles[(roles.method==r['method'])&(roles.condition==r['condition'])&
              (roles.heldout_building==r['building'])&(roles.class_id==r[prefix+'_class'])]
            assert len(rr)==1
            for col in ['selected_family','members','turn_history_mean','complex_turn_history_mean',
              'short_history_mean','redundancy_history_mean','q_history_mean','t_history_mean']:
                r[prefix+'_'+col]=rr.iloc[0][col]
        rows.append(r)
    folds=pd.DataFrame(rows);write_csv(folds,out/'FOLD_DIRECTION_ROLES_MEMBERS.csv')
    return ix,folds

def main():
    p=argparse.ArgumentParser();p.add_argument('--design-dir',type=Path,required=True)
    p.add_argument('--direction-results',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--quality-structure-common',type=Path)
    p.add_argument('--reuse-design-index',action='store_true',help='Read the frozen design index without rewriting its gzip')
    p.add_argument('--design-only',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cols=['event_id','pair_key','method','condition','building','groups','source_role_key','target_role_key',
      'source_role','target_role','source_class','target_class','source_class_fold_key','target_class_fold_key',
      'n','m','D_n','D_class_counts','D_members','X_members','Y_members','Z_members','ordinary_comparable',
      'layer_a','layer_b','scope_comparable']
    d=pd.read_csv(a.design_dir/'STRICT_ABC_EVENTS.csv.gz',usecols=cols,keep_default_na=False)
    roles=pd.read_csv(a.design_dir/'CLASS_ROLES_AND_MEMBERS.csv',keep_default_na=False)
    if a.reuse_design_index:
        ix=pd.read_csv(a.out/'DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz',keep_default_na=False)
        folds=pd.read_csv(a.out/'FOLD_DIRECTION_ROLES_MEMBERS.csv',keep_default_na=False)
    else:ix,folds=make_index(d,roles,a.out)
    receipt={'version':'SRLB_DIRECTION_DISPLAY_20261023_v1','new_fusion_calls':0,'retrained_classes':0,
      'design_events':len(d),'background_context_rows':len(ix),'fold_direction_rows':len(folds),
      'role_rule':'historical fold center; source/target role keys preserve family and k; no numeric-id pooling',
      'member_union_rule':'unions document coverage, not one actual simultaneous team; event_ids join frozen design',
      'design_only':a.design_only,'design_index_reused_without_write':a.reuse_design_index}
    if not a.design_only:
        if a.direction_results is None:raise ValueError('--direction-results required')
        stats=pd.read_csv(a.direction_results,low_memory=False)
        joint_path=a.quality_structure_common or a.direction_results.parent.parent/'reader_tables/QUALITY_STRUCTURE_COMMON_SUPPORT.csv'
        joint=pd.read_csv(joint_path,low_memory=False) if joint_path.exists() else None
        small=[];extended=[]
        metrics={'Q_同类幅度':'B8L2_within','Q_对称跨类幅度':'B8L2_cross','Q_额外幅度':'B8L2_extra',
          'Q_BA':'B8L2_BA','Q_CA':'B8L2_CA','Q_CB':'B8L2_CB','Q_C减源类双队均值':'B8L2_CS',
          'D10_BA':'D10_BA','D10_CA':'D10_CA','D10_CB':'D10_CB',
          '转折_BA':'fusion_turn_n_BA','转折_CA':'fusion_turn_n_CA','转折_CB':'fusion_turn_n_CB',
          '转折_同类幅度':'fusion_turn_n_within','转折_对称跨类幅度':'fusion_turn_n_cross',
          '短转折_CA':'fusion_short_turn_edges_CA',
          '近共线分段_CA':'fusion_redundancy_n_CA','底面误差_CA':'S_bottom_deg_CA',
          '方向误差_CA':'dir_CA','高度比例_CA':'height_mean_ratio_CA',
          'Q与时间共同支持_Q_CA':'QT_Q_CA','Q与时间共同支持_劳动比_CA':'QT_time_ratio_CA',
          'Q与时间共同支持_Q_BA':'QT_Q_BA','Q与时间共同支持_劳动比_BA':'QT_time_ratio_BA',
          'Q与时间共同支持_Q_CB':'QT_Q_CB','Q与时间共同支持_劳动比_CB':'QT_time_ratio_CB',
          'Q与时间共同支持_劳动对数比_CA':'QT_time_logratio_CA',
          '新增评分失败_CA':'new_score_failure_CA','恢复评分_CA':'recovered_score_CA',
          '新增不完整_CA':'new_incomplete_CA','恢复完整_CA':'recovered_complete_CA',
          '降质超过5分_CA':'CA_loss_gt5_fraction'}
        for i,r in stats.iterrows():
            mask=(subset_mask(d,r['subset'])&(d.method==r['method'])&(d.condition==r['condition'])&
              (d.source_role_key==r['source_role_key'])&(d.target_role_key==r['target_role_key']))
            z=d[mask];assert len(z)==int(r.attempted_events),(i,len(z),r.attempted_events)
            row={'方向结果键':'DIRRES_'+h([r['subset'],r.method,r.condition,r.source_role_key,r.target_role_key]),
              '分类方案':r.method,'条件':r.condition,'支持层':r['subset'],
              '源类中文角色':r.source_role,'目标类中文角色':r.target_role,
              '源类历史对齐键':r.source_role_key,'目标类历史对齐键':r.target_role_key,
              '实际源成员':r.source_workers,'实际目标成员':r.target_workers,
              '楼外折与原编号':'|'.join(sorted({f'{x.building}:{x.source_class}→{x.target_class}' for x in z[['building','source_class','target_class']].drop_duplicates().itertuples()})),
              '实际n_m':r.actual_n_m,'D人数最小':int(z.D_n.min()),'D人数最大':int(z.D_n.max()),
              'D构成种类数':len(z[['building','D_class_counts']].drop_duplicates()),
              '图对数':int(r.pairs),'建筑数':int(r.buildings),'配置数':int(r.configurations),
              '尝试事件':int(r.attempted_events),'共同六端点Q事件':int(r.common6_Q_events),
              '共同Q时间事件':int(r.joint_QT_events),
              '跨类额外Q幅度正向图对比例':r.positive_Q_extra_pair_fraction}
            for label,col in metrics.items():
                for weight,cn in [('pair_equal','图对等权'),('building_equal','建筑等权')]:
                    row[label+'_'+cn]=r.get(weight+'__'+col,np.nan)
            j=None
            if joint is not None:
                jj=joint[(joint.method==r.method)&(joint.condition==r.condition)&(joint['subset']==r['subset'])&
                    (joint.source_role_key==r.source_role_key)&(joint.target_role_key==r.target_role_key)]
                if len(jj)>1:raise ValueError('nonunique quality-structure joint direction')
                if len(jj)==1:j=jj.iloc[0]
            row['原结构定位分项支持']='各分项自身六端点有效；不自动等于六端点Q共同支持'
            row['共同Q结构_状态']='matched_saved_joint_row' if j is not None else 'no_matching_saved_joint_row'
            for col,zh in [('events','事件数'),('pairs','图对数'),('buildings','建筑数')]:
                row['共同Q结构_'+zh]=j.get(col,np.nan) if j is not None else np.nan
            joint_metrics={'Q':'B8L2','转折':'fusion_turn_n','短转折':'fusion_short_turn_edges',
              '近共线分段':'fusion_redundancy_n','底面误差':'S_bottom_deg','方向误差':'dir',
              'Hmean':'Hmean','Hcenter':'Hcenter','参考节点召回':'ref_node_recall_5','参考边召回':'ref_edge_recall_5'}
            for zh,metric in joint_metrics.items():
                for count in ['events','pairs']:
                    row[f'共同Q结构_{zh}_有效{count}']=j.get(metric+'_common_'+count,np.nan) if j is not None else np.nan
                for ef in ['within','cross','extra','BA','CA','CB','CS']:
                    for weight,cn in [('pair_equal','图对等权'),('building_equal','建筑等权')]:
                        row[f'共同Q结构_{zh}_{ef}_{cn}']=j.get(weight+'__'+metric+'_'+ef,np.nan) if j is not None else np.nan
            small.append(row)
            ext=r.to_dict();ext['direction_result_key']=row['方向结果键'];ext['fold_class_links']=row['楼外折与原编号'];
            ext['D_n_min']=row['D人数最小'];ext['D_n_max']=row['D人数最大'];ext['D_background_pattern_n']=row['D构成种类数'];extended.append(ext)
        table=pd.DataFrame(small);write_csv(table,a.out/'DIRECTION_READABLE_ZH.csv')
        write_csv(pd.DataFrame(extended),a.out/'DIRECTION_RESULTS_WITH_DESIGN_LINKS.csv')
        lines=['# 当前类别方向、实际成员与背景的结果整理','','本表接入主统计的已计算结果，不重新分类或选择团队。中文角色由目标建筑外的历史中心解释；TURN2、TURN3、JOINT及联合Q/T的对齐键分别保留。','','`DIRECTION_READABLE_ZH.csv` 给出逐方向结果与真实成员；`FOLD_DIRECTION_ROLES_MEMBERS.csv` 给出各楼外折原编号和中心；`DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz` 可按 n/m、D 构成、事件键定位完整精确 ABC。成员并集表示该方向覆盖过的人，不表示他们组成同一队。实际标签、画像和冻结原答使用匿名人员编号 Wxxx；本表沿用编号，不补造姓名。','','Q单位为分；转折为个；劳动比为 C/A 的分层算术平均，使用Q和时间共同可评且单一同来源支持。图对等权强调当前观察图对集合，建筑等权强调建筑间的表现。劳动比不是几何均值，也不等于把全部团队劳动时间加总后的总量比，更不自动对应实际交付时长。','','以下列表分别给出当前真实支持。跨类额外幅度为 (|C−A|+|C−B|)/2−|B−A|；有符号结果同时保留 B−A、C−A、C−B、C−(A+B)/2，不能从幅度更大推断必然升质。']
        lines += ['', '**分项支持：** CSV原转折、底面和位置列来自各分项自身六端点有效支持，可能包含Q不可评分的几何候选，不能直接当作Q变化的共同支持解释。另追加 `共同Q结构_` 列，按相同method/condition/subset/历史role key连接 `reader_tables/QUALITY_STRUCTURE_COMMON_SUPPORT.csv`；先要求六队Q可评，再保留各分项有限值及有效分母。原列不替换；没有相应联合行时保留缺失。下表的转折列使用新增共同Q结构值。']
        for (method,sub),zz in table.groupby(['分类方案','支持层'],sort=True):
            lines+=['',f'## {method} · {sub}','','|源类 → 目标类（历史角色）|图对/楼|图对内配置数|Q C−A|Q C−B|Q额外幅度|共同Q转折 C−A|共同Q/T劳动比 C/A|新增评分失败比例 C−A|','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
            for _,r in zz.iterrows():
                lines.append('|'+str(r['源类中文角色'])+' → '+str(r['目标类中文角色'])+'|'+f"{r['图对数']}/{r['建筑数']}"+'|'+str(r['配置数'])+'|'+'|'.join(fmt(r.get(k)) for k in ['Q_CA_图对等权','Q_CB_图对等权','Q_额外幅度_图对等权','共同Q结构_转折_CA_图对等权','Q与时间共同支持_劳动比_CA_图对等权','新增评分失败_CA_图对等权'])+'|')
        lines+=['','## 阅读与采用范围','','这些结果是同一图对内固定背景、同人数和同替换块规模的匹配比较，再按配置、图对和建筑汇总。不同方向或 n/m 支持不同，不能把它们的均值相减当作规模因果效应；固定 A 与固定 XYZ 的规模/背景变化另见 `anchor_paths/`。','','历史“较多转折”是人员在楼外历史上的倾向，当前图的实际结构变化必须读转折、短转折、近共线及定位指标；类名不能替代几何。Q 接近子域说明的是该有限支持下的条件性差异，不用于计算“历史 Q 解释了总体差异的百分比”。','','新增评分失败与恢复采用全部尝试事件分母。评分不可用的端点仍在设计和状态表，质量均值只使用相应共同可评支持。']
        (a.out/'DIRECTION_RESULTS_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        receipt['direction_result_rows']=len(table)
        receipt['quality_structure_joint_source']=str(joint_path) if joint is not None else None
        receipt['quality_structure_joint_matched_rows']=int((table['共同Q结构_状态']=='matched_saved_joint_row').sum())
        (a.out/'FIELD_CONTRACT_ZH.md').write_text('''# 方向可读表的字段支持

- 方案与角色：method + condition + source_role_key + target_role_key；role key含历史family/类数，跨折不按同编号拼接。
- 人员与背景：成员并集说明覆盖；每折名单与历史中心见FOLD_DIRECTION_ROLES_MEMBERS.csv。精确ABC及D/X/Y/Z通过背景索引的event_ids连接冻结设计。
- 原Q幅度：同一事件六端点Q共同可评，within=|B−A|、cross=(|C−A|+|C−B|)/2、extra=cross−within；有符号BA/CA/CB/CS另保留。
- 原转折、短转折、近共线、底面、方向和高度列：各分项自身六端点有限支持；这可以含Q不可评分的候选几何。不要直接把这些均值与Q均值当同样本机制对照。
- 新增“共同Q结构_”列：从QUALITY_STRUCTURE_COMMON_SUPPORT.csv按同方案/条件/层/两端role key精确连接；六队先均Q可评，再使用该分项有效值；events/pairs单列。无匹配联合行时为缺失，不回退成原较宽分项。
- Q/T：六端点Q及记录时间共同可用，且所有团队时间同一来源语义；劳动比为逐事件/配置/图对/楼的算术汇总，不是几何均值或并行时长。
- 失败与恢复：全部尝试分母；缺失Q不补零。降质>5分使用共同Q支持，与失败分母不同。
- 正向图对比例：先在图对内按配置汇总，再判断该图对额外幅度是否严格大于零；不同于原始事件的升质比例。

本补充只连接与说明已保存表，不改原事件、大表gzip或评分。
''',encoding='utf-8')
    # The base design receipt may already be included in the frozen large-table
    # package. A small-table joint-support extension gets its own identity.
    extension={k:receipt.pop(k) for k in ['design_index_reused_without_write',
        'quality_structure_joint_source','quality_structure_joint_matched_rows'] if k in receipt}
    base_receipt=a.out/'DIRECTION_DISPLAY_RECEIPT.json'
    if not a.reuse_design_index:
        base_receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    elif not base_receipt.exists():raise ValueError('frozen base direction receipt is required for reuse')
    if not a.design_only:
        extension.update(version='SRLB_DIRECTION_JOINT_DISPLAY_20261023_v1',
          base_receipt_sha256=hashlib.sha256(base_receipt.read_bytes()).hexdigest(),
          readable_csv_sha256=hashlib.sha256((a.out/'DIRECTION_READABLE_ZH.csv').read_bytes()).hexdigest(),
          base_receipt_not_rewritten=a.reuse_design_index,new_fusion_calls=0,new_classification=0,
          original_metric_columns_preserved=True,missing_joint_rows_remain_missing=True)
        (a.out/'DIRECTION_JOINT_SUPPORT_RECEIPT.json').write_text(json.dumps(extension,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'base':receipt,'joint_extension':extension},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
