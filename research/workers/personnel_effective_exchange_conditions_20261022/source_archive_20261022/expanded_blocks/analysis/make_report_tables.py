"""Readable tables for prespecified expanded conditions; no selection/fitting."""
from pathlib import Path
import os,json,sys
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from analyze_expanded_results import sha,save_json
from compare_time_aggregates import main as compare_time_aggregates

CONDITIONS=[
 ('A2：A02→A01','A2_relation','class_direction','A02 -> A01',17,9),
 ('A2：A02→A03','A2_relation','class_direction','A02 -> A03',17,9),
 ('M 父内：M01→M00，m5','M_structure','class_direction','M01 -> M00',10,5),
 ('M 父内：M01→M00，m6','M_structure','class_direction','M01 -> M00',10,6),
 ('行为：TURN/K3/E2→E3','V3_BEHAVIOR','class_direction','TURN/K3/E2 -> TURN/K3/E3',10,7),
 ('行为：TURN/K3/E3→E2','V3_BEHAVIOR','class_direction','TURN/K3/E3 -> TURN/K3/E2',10,7),
 ('行为：楼外转折倾向增加（跨特征族）','V3_BEHAVIOR','training_turn_direction','increase',10,7),
 ('行为：楼外转折倾向减少（跨特征族）','V3_BEHAVIOR','training_turn_direction','decrease',10,7)]

def fmt(v,d=2):return '—' if pd.isna(v) else f'{float(v):.{d}f}'
def integer(v):return '—' if pd.isna(v) else str(int(v))
def number(v):return '—' if pd.isna(v) else f'{int(v):,}'
def percent(v):return '—' if pd.isna(v) else f'{100*float(v):.1f}%'
def pct_units(v):return '—' if pd.isna(v) else f'{float(v):.2f}%'
def table(headers,rows):
    esc=lambda v:str(v).replace('|','\\|')
    return '\n'.join(['|'+'|'.join(map(esc,headers))+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(map(esc,r))+'|' for r in rows])+'\n'

def main():
    receipt=json.loads((HERE/'FINAL_ANALYSIS_COMPLETION.json').read_text())
    assert receipt['status']=='FINAL_COMPLETE' and receipt['pending_cells']==0
    c=pd.read_csv(HERE/'FINAL_CORE_SUMMARY.csv.gz')
    h=pd.read_csv(HERE/'FINAL_HISTORY_MATCHED_CORE_SUMMARY.csv.gz')
    allcomponents=pd.read_csv(HERE/'FINAL_ALL_COMPONENT_SUMMARY.csv.gz')
    coverage=pd.read_csv(HERE/'FINAL_COVERAGE.csv.gz')
    components=allcomponents.merge(coverage,on='summary_id',validate='many_to_one')
    time_comparison=compare_time_aggregates()
    member=pd.read_csv(HERE/'FINAL_CONDITION_MEMBER_VARIATION.csv.gz')
    def select(data,spec,cohort='all_images'):
        _,method,view,direction,n,m=spec
        mask=(data.layer=='ordinary_manual')&(data.method_id==method)&(data.view==view)&(data.direction==direction)&(data.n==n)&(data.m==m)&(data.cohort==cohort)
        if 'difficulty_stratum' in data:mask &= data.difficulty_stratum.eq('ALL')
        return data[mask]
    def metric(data,name,field='building_mean'):
        x=data[data.metric.eq(name)]
        assert len(x)<=1,(name,len(x))
        return x.iloc[0].get(field,np.nan) if len(x) else np.nan
    def sign(data,name,level):
        return integer(metric(data,name,'positive_'+level))+'/'+integer(metric(data,name,'valid_'+level))
    out=['# 扩展实际成员与共同背景：最终数值表\n',
      '本表由正式完成回执生成。底层数据为 v2；所有效应依次按实际共同背景、图片和建筑等权。'
      '这里的方向为 C−A；同构成与改构成的绝对变化只使用 ABC 共同评分资格。'
      '原始失败和缺失均保留。8 个展示行是预先指定条件及角色方向，历史转折增加／减少行与具体 TURN 角色行存在覆盖重叠，不相加。\n',
      f"已完成 {receipt['complete_cells']} 个单元、{receipt['complete_panels']} 个面板、{receipt['complete_events']:,} 个有向 ABC。\n"]
    stable=[];directional=[];risk=[];cohorts=[];geometry=[];matched=[];members=[];times=[]
    for spec in CONDITIONS:
        data=select(c,spec)
        if not len(data):continue
        label=spec[0];meta=data.iloc[0]
        ci=fmt(metric(data,'abs_Q_change_advantage','building_bootstrap_lo95'))+'～'+fmt(metric(data,'abs_Q_change_advantage','building_bootstrap_hi95'))
        stable.append([label,f'{spec[4]}/{spec[5]}',number(meta.complete_events),
          integer(meta.complete_images)+'/'+integer(meta.complete_buildings),
          fmt(metric(data,'common_quality_within_abs')),fmt(metric(data,'common_quality_cross_abs')),
          fmt(metric(data,'abs_Q_change_advantage')),fmt(metric(data,'abs_Q_change_advantage','building_median')),
          sign(data,'abs_Q_change_advantage','buildings'),percent(metric(data,'fraction_cross_larger_abs_Q')),ci])
        ciq=fmt(metric(data,'cross_B8L2','building_bootstrap_lo95'))+'～'+fmt(metric(data,'cross_B8L2','building_bootstrap_hi95'))
        directional.append([label,fmt(metric(data,'cross_B8L2')),fmt(metric(data,'cross_B8L2','building_median')),
          sign(data,'cross_B8L2','images'),sign(data,'cross_B8L2','buildings'),fmt(metric(data,'cross_D10')),
          fmt(metric(data,'cross_ref_node_recall_5'),3),fmt(metric(data,'cross_ref_edge_recall_5'),3),
          fmt(metric(data,'cross_fusion_turn_n'),3),ciq])
        tq=select(time_comparison,spec)
        assert len(tq)<=1
        gp=tq.iloc[0].geometric_percentage_change if len(tq) else np.nan
        times.append([label,number(metric(data,'cross_recorded_time_pct','valid_events')),
          integer(metric(data,'cross_recorded_time_pct','valid_images'))+'/'+integer(metric(data,'cross_recorded_time_pct','valid_buildings')),
          pct_units(metric(data,'cross_recorded_time_pct')),pct_units(gp),pct_units(metric(data,'cross_recorded_time_pct','building_median')),
          fmt(metric(data,'cross_B8L2_time_qualified')),number(metric(data,'cross_B8L2_time_qualified','valid_events'))])
        qvalid=metric(data,'cross_loss_gt10','valid_events')
        qloss=metric(data,'cross_loss_gt10','event_weighted_mean')*qvalid
        fails=[]
        for a in 'ABC':
            total=metric(data,a+'_failure','valid_events');count=metric(data,a+'_failure','event_weighted_mean')*total
            fails.append(integer(round(count))+'/'+integer(total))
        risk.append([label,*fails,integer(round(qloss))+'/'+integer(qvalid),
          percent(metric(data,'cross_loss_gt10')),percent(metric(data,'cross_failure_or_loss_gt10')),
          number(metric(data,'abs_Q_change_advantage','valid_events')),number(metric(data,'cross_B8L2','valid_events'))])
        cmp=select(components,spec)
        geometry.append([label,*[fmt(metric(cmp,f),4) for f in ['cross_IoU3D100','cross_iou_2d','cross_S_bottom_deg',
          'cross_dir','cross_Hmean','cross_Hcenter','cross_omission','cross_extension',
          'common_geometry_advantage_floor_jaccard_difference','common_geometry_advantage_mean_height_prism_pair_difference']]])
        for cohort in ['priority_seed_images','additional_images']:
            z=select(c,spec,cohort)
            if not len(z):continue
            row=z.iloc[0]
            cohorts.append([label,'原候选图' if cohort.startswith('priority') else '新增覆盖图',
              integer(row.complete_images)+'/'+integer(row.complete_buildings),number(row.complete_events),
              fmt(metric(z,'abs_Q_change_advantage')),sign(z,'abs_Q_change_advantage','buildings'),
              fmt(metric(z,'cross_B8L2')),sign(z,'cross_B8L2','buildings')])
        for match in ['source_matched','source_Q5_matched']:
            z=select(h[h.historical_match_stratum.eq(match)],spec)
            matched.append([label,'来源人数' if match=='source_matched' else '来源人数＋楼外Q5',
              number(metric(z,'cross_B8L2','valid_events')),integer(metric(z,'cross_B8L2','valid_images'))+'/'+integer(metric(z,'cross_B8L2','valid_buildings')),
              fmt(metric(z,'cross_B8L2')),fmt(metric(z,'abs_Q_change_advantage'))])
        z=select(member,spec)
        for role in ['unchanged_source_composition','changed_target_composition']:
            q=z[z.composition_role.eq(role)]
            if not len(q):continue
            r=q.iloc[0]
            members.append([label,'源构成A/B' if role.startswith('unchanged') else '目标构成C',
              integer(r.panels_with_at_least_two_member_sets)+'/'+integer(r.panels),
              integer(r.registered_member_sets_min)+'～'+integer(r.registered_member_sets_max),
              fmt(r['B8L2_std__building_mean']),fmt(r['B8L2_range__building_mean']),fmt(r['B8L2_p90_minus_p10__building_mean']),
              fmt(r['B8L2_q05__building_mean']),percent(r['failed_fraction__building_mean'])])
    out += ['## 1. 变化大小：同构成是否更接近\n',
      '优势 = 改构成 |ΔQ| − 同构成 |ΔQ|。正值表示同构成较近。“跨更大比例”为各背景内严格正优势事件比例再按图、楼等权；与楼均值为正的比例是两件事。\n',
      table(['条件','n/m','事件','图/楼','同构成|ΔQ|','改构成|ΔQ|','优势均值','优势楼中位','优势正楼/有效楼','跨更大比例','优势描述95%区间'],stable),
      '## 2. 方向：改变构成后是否更好\n',
      table(['条件','ΔB8L2','楼中位','Q正图/有效图','Q正楼/有效楼','ΔD10','Δ节点召回5°','Δ边召回5°','Δ有效转折','Q描述95%区间'],directional),
      '## 3. 全失败分母与大损失\n',
      'A/B/C 失败数为有向事件中的失败端点出现次数；复用端点会重复出现，因此不称为独立失败团队数。成员分布表另有每面板唯一团队失败。大损失率列采用楼等权，事件计数独立列出。\n',
      table(['条件','A失败/全事件','B失败/全事件','C失败/全事件','成功降>10/有评分','成功大损失楼均率','失败或降>10楼均率','ABC共同评分事件','AC方向有评分事件'],risk),
      '## 4. 原候选图片与新增覆盖图片\n',
      '新增覆盖是相对每个方法及 n/m 的旧种子图片清单；不冒称外部盲测。\n',
      table(['条件','图片层','图/楼','事件','绝对变化优势','优势正楼/有效楼','ΔQ','Q正楼/有效楼'],cohorts),
      '## 5. 几何、上下界、高度与范围分项\n',
      '底面 IoU、三维代理越高越好；底面球面距离 S、输出自身正交方向残差 dir、冻结高度残差越低越好。dir 不是相对 GT 的旋转误差；三维指标是适用代理。最后两列是形状差异的跨减同优势，正值表示同构成更近。\n',
      table(['条件','ΔIoU3D100','Δ底面IoU','ΔS(°)','Δdir(°)','ΔHmean','ΔHcenter','Δomission','Δextension','底面差异优势','均高棱柱差异优势'],geometry),
      '## 6. 来源与历史Q辅助\n',
      '来源人数为旧批／新增批人数一致；不是对任意批号全部配平。Q5 要求同类和跨类块相对基线的楼外历史Q差都不超过5。主效应未以这些条件筛除样本。\n',
      table(['条件','辅助限制','AC有评分事件','有效图/楼','ΔQ','绝对变化优势'],matched),
      '## 7. 固定构成下具体成员分布\n',
      '每个面板枚举的不同成员集合逐一统计，然后按背景、图、楼等权。源A/B只计一次。目标只有一个实际团队时，标准差与范围记未知。下表是有限枚举内的离散程度，不是总体人员的估计噪声。\n',
      table(['条件','构成','可估波动面板/面板','每面板团队数范围','Q标准差','Q全距','Q90−Q10','Q05','失败团队楼均率'],members),
      '## 8. 正式同源记录时间\n',
      '时间只在三臂单一来源一致、各队全部n人记录完整时使用；下表为记录人秒变化。算术列先计算每事件 100×(C/A−1)，依次对背景、图、楼等权；几何列对 log(C/A) 用同样权重，再以 100×expm1 换算。两列有效事件、背景、图、楼分母逐项相同，不能混称同一个时间均值。楼中位针对算术百分比的楼均值。与同一时间支持上的Q另列，其评分分母可因失败进一步缩小。没有支持记未知。\n',
      table(['条件','时间合格事件','有效图/楼','算术百分比均值','对数均值换算几何百分比','算术楼中位','时间支持ΔQ','其有评分事件'],times),
      '## 文件与统计口径\n',
      '所有注册方向、困难层及门洞／特殊范围均见 `FINAL_CORE_SUMMARY.csv.gz` 和 `FINAL_ALL_COMPONENT_SUMMARY.csv.gz`，不因未出现在以上普通层展示表而删除。精确配置和实际成员覆盖见 `CANONICAL_COVERAGE_SUMMARY.csv`；逐图、逐楼和逐背景表可进一步定位反例。复现与时间资格见 `ANALYSIS_PROTOCOL_ZH.md`。\n']
    path=HERE/'FINAL_TABLES_FOR_REPORT_ZH.md';tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:f.write('\n'.join(out));f.flush();os.fsync(f.fileno())
    tmp.replace(path)
    save_json('REPORT_TABLES_COMPLETION.json',dict(status='complete',path=path.name,sha256=sha(path),
      source_core_sha256=sha(HERE/'FINAL_CORE_SUMMARY.csv.gz'),source_analysis_receipt_sha256=sha(HERE/'FINAL_ANALYSIS_COMPLETION.json'),
      native_fusion_calls=0,scoring_calls=0))
    print(path)

if __name__=='__main__':main()
