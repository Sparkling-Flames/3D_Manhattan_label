"""Descriptive tables and fixed-image-panel plots; no inference or worker ranking."""
import argparse
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True);a=p.parse_args();out=a.results
    panel=json.loads(a.input.read_text(encoding='utf-8'))
    strata={}
    for im in panel['images']:
        for c in {r['condition'] for r in im['annotations']}:
            gates={r['main_consensus_gate']['status'] for r in im['annotations'] if r['condition']==c and r['independent'] and r['consensus_eligible']}
            if len(gates)>1:raise ValueError('mixed_strata_need_separate_aggregation')
            if gates:strata[im['code'],c]=next(iter(gates))
    q=pd.read_csv(out/'individual_quality.csv');e=pd.read_csv(out/'consensus_endpoints.csv');r=pd.read_csv(out/'replay_summary.csv')
    for frame in (e,r):frame['stratum']=[strata[i,c] for i,c in zip(frame.image,frame.condition)]
    primary=q[q.quality_candidate & q.independent & q.status.eq('ok')]
    qt=primary.groupby(['reference','representation','condition']).iou.agg(['count','mean','median']).reset_index()
    et=e[e.evaluation_status.eq('ok')].groupby(['reference','representation','stratum','condition','method']).iou.agg(['count','mean','median']).reset_index()
    qt.to_csv(out/'quality_group_summary.csv',index=False);et.to_csv(out/'consensus_group_summary.csv',index=False)
    wide=q[q.reference.eq('original')].pivot(index=['image','id'],columns='representation',values='iou')
    counter=wide[(wide.explicit_visible>.95)&(wide.bev_and_prism_proxy<.8)].sort_values('bev_and_prism_proxy')
    counter.to_csv(out/'representation_counterexamples.csv')
    selection=[('manual','main_candidate'),('manual','oos_doorway_exploratory'),('semi','main_candidate'),('oos','oos_doorway_exploratory')]
    selected=[];curves=[]
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    colors={'mv50':'#137c8b','mv_strict':'#d48d24','medoid':'#8558a5'}
    for ax,(condition,stratum) in zip(axes.flat,selection):
        eligible=e[e.condition.eq(condition)&e.stratum.eq(stratum)&e.reference.eq('original')&e.representation.eq('explicit_visible')&e.method.eq('mv50')&e.evaluation_status.eq('ok')&(e.k>=10)&e.used_k.eq(e.k)]
        images=set(eligible.image)
        selected.extend(dict(image=i,condition=condition,stratum=stratum) for i in sorted(images))
        sub=r[r.image.isin(images)&r.condition.eq(condition)&r.reference.eq('original')&(r.k<=10)]
        for method,color in colors.items():
            line=sub[sub.method.eq(method)].groupby('k').agg(iou_mean=('iou_mean','mean'),change_mean=('change_mean','mean'),images=('image','nunique')).reset_index()
            if len(line):
                assert line.images.eq(len(images)).all()
                ax.plot(line.k,line.iou_mean,label=method,color=color)
                curves.extend(dict(condition=condition,stratum=stratum,method=method,**row) for row in line.to_dict('records'))
        ax.set_title(f'{condition} / {stratum}\nFixed images: {len(images)}',fontsize=10)
        ax.set(xlabel='Number of independent annotations (k)',ylabel='Mean ERP IoU to original GT',xlim=(1,10),ylim=(0,1))
        ax.grid(alpha=.2)
        if images:ax.legend(fontsize=8)
    fig.suptitle('Exploratory replay: same images at every k; 100 permutations, no confidence bands')
    fig.savefig(out/'fixed_panel_replay.png',dpi=170);plt.close(fig)
    pd.DataFrame(selected).to_csv(out/'fixed_panel_selection.csv',index=False)
    pd.DataFrame(curves).to_csv(out/'fixed_panel_curves.csv',index=False)
    s=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    def table(frame):
        f=frame.copy()
        for c in f.select_dtypes('float'):f[c]=f[c].round(4)
        return '| '+' | '.join(f.columns)+' |\n| '+' | '.join(['---']*len(f.columns))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in f.itertuples(index=False,name=None))
    text=f'''# 9/29 全量复核后第一轮数值基线

本轮实际执行完成。输入为接入线程核验后的快照：{s['annotations']} 份历史人员记录、{s['images']} 张人员研究图、{s['reference_only_images']} 张仅 GT 参考图、27 个历史人员别名、22 栋建筑。原始 GT 259 份、人工修订 GT 30 份。2923 份保留、11 份待定保留、85 份复核排除、133 份历史不接受；独立共识可用资格 2909 份，其中主候选2395、OOS/门洞探索485、稳定非正交单列29。方法能否计算仍需另判。

运行：512×256 栅格，100 次固定种子随机人员排列。原始/修订 GT 并列；GT 没有进入共识生成。全部产生 {s['quality_rows']} 条参考比较、{s['endpoint_rows']} 条端点记录、{s['replay_rows']} 条重放摘要。记录数不是独立样本量。

## GT 相对差异

以下仅取上游主质量候选、独立人员且该指标可计算的记录。分母随方法和 GT 版本变化；不是配对的方法优劣检验，不可直接把 manual 与 semi 的差异当条件因果效应或人员能力差。

{table(qt)}

ERP 墙带和 BEV 不是同一个评价对象。原始 GT 比较中有 {len(counter)} 条保留/待定记录同时出现显式可见 ERP IoU>0.95、BEV IoU<0.8。下面列数值反例，不裁决标注或 GT 哪个正确，也不把这些全部解释为遮挡效应。

{table(counter.head(6).reset_index())}

## 共识比较

下表仅为主共识候选、原始 GT、显式可见表示的图片等权端点描述；包括本来就只有少数人的图。跨方法均值没有建筑层置信区间，不声称显著胜出。各场景/条件/GT 的完整表见 consensus_group_summary.csv。

{table(et[et.reference.eq('original')&et.representation.eq('explicit_visible')&et.stratum.eq('main_candidate')])}

![固定图片面板重放](fixed_panel_replay.png)

图中每层仅保留独立人数>=10、所有投票可渲染且原始 GT 可计算的固定图片，k=1…10 始终同一批图；清单见 fixed_panel_selection.csv。这是可计算完整案例子集，不能代表被排除的图片。先在每图内平均100次排列，再对图片等权平均；无置信带。各算法是否接近GT与结果是否稳定是两条问题，输出变化另见 fixed_panel_curves.csv。曲线不用于反过来定义简单/困难。

## 失败和解释边界

- STAPLE 本地缺少 SimpleITK，全部明确 unavailable；没有声称跑过。其余五种是两个 MV、medoid、单正确率 EM 适配和经验 greedy 适配，后两者不是论文完整复现。
- 显式与旧包络各有 44 与 48 个对象无法渲染；具体原因在 representation_failures.csv。相机不在所标多边形内不自动等于标错，可能涉及空间范围或表示假设。GT 无法计算会影响多份比较，不能将比较失败数当异常人员数。
- 新旧表示还使用不同像素约定，这轮差异不能全部归于顺序；严格控制变量留给下一轮。任何低 resultant 圆周/球面中心都可能不稳定，尚未选可靠性阈值，不据此给人员评级。
- BEV 长度以相机高度1归一化；棱柱指标采用中位高度，只是代理。近地平线深度放大、边界采样误差仍需敏感性分析。
- 近180°中间节点完整保留。共线点可能是停止分支，角度残差不能裁决其语义。当前共识仍是mask基线，未得到点对融合、多个有效房间或自由删点搜索结果。
- 主质量资格2030份不等于最终可评分2030份；借用点不作为独立完整投票。原始/修订GT覆盖不平衡，不做择优参考，也不把不同覆盖均值解释成修订效果。

## 下一步与当前判断

最值得先推进的是明确几何表示和参考差异，再比较结构约束融合与多模式候选。当前证据支持把IoU、质心、边界差异和几何诊断分开报告；尚不足以验证一种总分或声称分离人员/图片噪声。多数支持是行为共识证据，几何一致是模型证据，两者均不能代替缺失的视觉证据。

Pro任务已具体化为三套可执行路线、参数初值/敏感性、局部2/3对整体投票、停止点保留、多模式重放与交叉人员×图片可识别性分析。人员分类、正式难度与权重选择暂不落实为结论。完整任务见同包PROMPT.md。

本轮不修改原始坐标、GT、配对、确认环序、清洗裁决或正式协议。新增源码做定向不变量测试；本包单独验证输入和依赖。文档索引与项目地图只登记探索入口，没有升格为正式方法。
'''
    (out/'REPORT.md').write_text(text,encoding='utf-8')
    print('wrote descriptive summaries and fixed-panel figure; selected groups',len(selected))


if __name__=='__main__':main()
