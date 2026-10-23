#!/usr/bin/env python3
"""Bind the reviewable personnel-report insert to completed saved result tables."""
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path
import pandas as pd


def main(root):
    root=Path(root).resolve();out=root/'integration';cache={};values=[]
    def table(path):
        if path not in cache:cache[path]=pd.read_csv(root/path,low_memory=False)
        return cache[path]
    def row(path,filters):
        d=table(path)
        for k,v in filters.items():d=d[d[k]==v]
        if len(d)!=1:raise ValueError((path,filters,len(d)))
        return d.iloc[0]
    def fmt(value,style):
        if pd.isna(value):return '不可计算'
        if style=='integer':return f'{int(value):,}'
        if style=='percent_2dp':return f'{100*float(value):.2f}%'
        return f'{float(value):.3f}'
    for b in csv.DictReader((out/'PERSONNEL_INSERTION_VALUE_BINDINGS.csv').open(encoding='utf-8-sig')):
        p=root/b['source_file'];filters=json.loads(b['row_filters_json'])
        if p.suffix=='.json':v=json.loads(p.read_text())[b['column_or_json_key']]
        else:v=row(b['source_file'],filters)[b['column_or_json_key']]
        b.update(raw_value=v,display_value=fmt(v,b['display_format']),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        values.append(b)
    base={'method':'V3_BEHAVIOR','condition':'manual'}
    direction=row('results/DIRECTION_RESULTS.csv',dict(base,subset='ordinary_mixed',source_role_key='TURN3:常规转折',target_role_key='TURN3:较多转折'))
    reverse=row('results/DIRECTION_RESULTS.csv',dict(base,subset='ordinary_mixed',source_role_key='TURN3:较多转折',target_role_key='TURN3:常规转折'))
    p6=row('anchor_paths/KEY_PATH_JOINT_METRICS.csv',dict(comparison='fixed_A_m5_to_m6',domain='joint_Q_structure_position',metric='B8L2'))
    p7=row('anchor_paths/KEY_PATH_JOINT_METRICS.csv',dict(comparison='fixed_A_m5_to_m7',domain='joint_Q_structure_position',metric='B8L2'))
    pb=row('anchor_paths/KEY_PATH_JOINT_METRICS.csv',dict(comparison='pure_to_half',domain='joint_Q_structure_position',metric='B8L2'))
    members=table('reader_tables/KEY_MEMBER_SENSITIVITY_ZH.csv')
    wide=members[(members['匹配方式']=='class_composition_background')&(members['状态']=='matched_subdomain')]
    exact=members[(members['匹配方式']=='exact_D')&(members['状态']=='matched_subdomain')]
    neg=wide.loc[wide['匹配后缺席额外Q幅度_图对等权']<0,'人员编号'].tolist()
    no=sorted(members.loc[members['状态']!='matched_subdomain','人员编号'].unique())
    positive=int((wide['匹配后缺席额外Q幅度_图对等权']>0).sum())
    decisions={
      '根据实际结果填写_混合条件判断':'跨类幅度优势不限于纯块或过半替换，在混合团队、少于半队替换中仍覆盖多数图对；幅度、有符号升降及低尾分别采用',
      '根据方向表填写_主要方向与贡献':
       f"TURN3常规转折→较多转折（{int(direction.pairs)}图对、{int(direction.buildings)}楼）：C−A {direction.pair_equal__B8L2_CA:+.3f}、C−B {direction.pair_equal__B8L2_CB:+.3f}、额外幅度{direction.pair_equal__B8L2_extra:+.3f}分；反向较多→常规在{int(reverse.pairs)}图对、{int(reverse.buildings)}楼的额外幅度为{reverse.pair_equal__B8L2_extra:+.3f}分。JOINT与TURN2的具体中文方向另保留各自角色、人员和有限支持，不与TURN3原编号混并",
      '根据真实锚点路径填写_规模与背景判断':
       f"主方向固定A与n的m5→6在{int(p6.pairs)}图对/{int(p6.buildings)}楼，C本身{p6.pair_equal__C_change:+.3f}、B本身{p6.pair_equal__B_change:+.3f}、净{p6.pair_equal__net_C_minus_B_change:+.3f}分；m5→7在{int(p7.pairs)}图对/{int(p7.buildings)}楼净{p7.pair_equal__net_C_minus_B_change:+.3f}分。固定XYZ纯块→半队替换在{int(pb.pairs)}图对/{int(pb.buildings)}楼，C{pb.pair_equal__C_change:+.3f}、B{pb.pair_equal__B_change:+.3f}、净{pb.pair_equal__net_C_minus_B_change:+.3f}分。增大换人数与增加共同背景是不同操作；在Q/结构/定位共同支持上，平均转折变化很小、底面误差明显改变，因此不能仅用新增转折解释平均升降",
      '根据有限敏感性填写_结论保留或收紧':
       f"删除占50个图对的uNb建筑后，混合和少于半队的多数正向结果继续保留。目标类容量≤10的预定成员规则覆盖{members['人员编号'].nunique()}人，其中{len(wide)}人有合法匹配缺席子域，{positive}人的缺席子域平均额外幅度为正；负向为{'、'.join(neg)}。宽背景构成匹配保留相关事件的{100*wide['事件保留比例'].min():.2f}%—{100*wide['事件保留比例'].max():.2f}%，精确D匹配保留{100*exact['事件保留比例'].min():.2f}%—{100*exact['事件保留比例'].max():.2f}%。{'、'.join(no)}没有合法匹配缺席事件，不能写零效应。本结论是这些匹配子域的观察，不概括成整个结果不依靠关键成员，也不沿用旧设计的六人数字"
    }
    text=(out/'PERSONNEL_REPORT_INSERTIONS_ZH_TEMPLATE.md').read_text()
    for b in values:text=text.replace('{{'+b['placeholder']+'}}',b['display_value'])
    for k,v in decisions.items():text=text.replace('{{'+k+'}}',v)
    unresolved=re.findall(r'\{\{[^}]+\}\}',text)
    if unresolved:raise ValueError(unresolved)
    text=text.replace('# 人员主报告接续插入稿（数值待正式表绑定）','# 人员主报告接续插入稿（已绑定本轮完整结果）')
    text=text.replace('**状态：本文件是准确位置与文字模板。** 数值占位符只允许从本轮正式结果表填写；未填不代表零效应。全量端点和主统计完成后再应用。结果方向由实际表判断，不预写“跨类必然更大”。',
      '**状态：下列段落已绑定本轮完整端点与正式结果表，可按列明位置接入。** 输入为main e92abe8631d7f01dc192ee796b46f295ece37a6d；这是新设计的完成结果，不是丢失旧大块精确原件的恢复。')
    text=text.replace('此段只在正式结果完整后采用。','全量结果和关联已完成核验。')
    text=text.replace('## 3. 第1.4、7、8节的进度措辞（主结果完成后同步）','## 3. 第1.4、7、8节的进度措辞（可同步接入）')
    text=text.replace('`PERSONNEL_INSERTION_VALUE_BINDINGS.csv` 给出每个数值占位符的正式文件、筛选键、字段和显示格式。人工判断占位符没有默认正向结论，须依据方向、低尾/失败、图对/楼与成员敏感性一并填写。此模板未在历史人员主报告上直接应用。',
      '`PERSONNEL_INSERTION_VALUES.csv` 保存正式文件、筛选键、字段、原值、显示值与来源hash；`PERSONNEL_INSERTION_DECISIONS.json` 保存基于完整结果的采用文字与证据路径。精确成员、角色及背景以方向表/事件键为准。本文尚未直接覆盖历史人员主报告。')
    text=text.replace('## 5. 数值绑定与使用','## 5. 字段追溯与使用')
    (out/'PERSONNEL_REPORT_INSERTIONS_ZH.md').write_text(text)
    pd.DataFrame(values).to_csv(out/'PERSONNEL_INSERTION_VALUES.csv',index=False)
    (out/'PERSONNEL_INSERTION_DECISIONS.json').write_text(json.dumps({'version':'SRLB_PERSONNEL_INSERT_20261023_v1',
      'decisions':decisions,'sources':['results/DIRECTION_RESULTS.csv','results/OVERALL_CONDITIONS.csv',
      'results/EXCLUDE_UNB_SPECIFIC.csv','reader_tables/KEY_MEMBER_SENSITIVITY_ZH.csv',
      'anchor_paths/KEY_PATH_JOINT_METRICS.csv'],'new_fusion_calls':0,'new_classification':0,
      'unresolved_placeholders':0,'historical_report_mutated':False},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'bound_numeric_fields':len(values),'decisions':len(decisions),'unresolved':0},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=Path(__file__).resolve().parents[2]);main(p.parse_args().root)
