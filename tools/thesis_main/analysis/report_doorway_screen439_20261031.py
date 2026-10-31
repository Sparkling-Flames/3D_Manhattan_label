"""Describe the adopted 584/439 comparison without replacing historical results."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.audit_doorway_delivery_20261031 import paired_metric

BASE=Path(__file__).resolve().parents[3]/'research/data/doorway_review_20261030'
OUT=BASE/'screen439_results_20261031'


def main():
    paths=pd.read_csv(OUT/'PAIRED_PATH_VALUES.csv.gz')
    h=json.loads((OUT/'HEADLINES.json').read_text(encoding='utf8'))['screening_k10']
    pools=json.loads((OUT/'POOLS.json').read_text(encoding='utf8'))
    before=paths[(paths.family=='overall_before')&(paths.k==10)]
    after=paths[(paths.family=='overall_after')&(paths.k==10)]
    paired=before.merge(after,on=['image','base_replicate'],suffixes=('_before','_after'),validate='one_to_one')
    assert len(paired)==4352 and paired.image.nunique()==17
    rows=[]
    for im,g in paired.groupby('image'):
        a,b=g.B8L2_before,g.B8L2_after
        rows.append(dict(image=im,before_n=int(g.pool_n_before.iloc[0]),after_n=int(g.pool_n_after.iloc[0]),
            paired_quality_valid=int((a.notna()&b.notna()).sum()),paired_quality_delta=(b-a).mean(),
            mean_before=a.mean(),mean_after=b.mean(),sd_before=a.std(),sd_after=b.std(),p10_before=a.quantile(.1),p10_after=b.quantile(.1),
            complete_before=g.complete_evaluable_before.mean(),complete_after=g.complete_evaluable_after.mean(),
            complete_delta_pp=100*(g.complete_evaluable_after.mean()-g.complete_evaluable_before.mean())))
    details=pd.DataFrame(rows);details.to_csv(OUT/'PER_IMAGE_K10_COMPARISON.csv',index=False)
    without=paired[paired.image!='B6ByNegPMKs-43']
    sensitivity={m:paired_metric(without[m+'_before'],without[m+'_after'],without.image,set()) for m in ['B8L2','D10','IoU3D100','complete_evaluable']}
    (OUT/'EXCLUDE_SMALL_POOL_COMPARISON.json').write_text(json.dumps(sensitivity,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    q=h['B8L2'];c=h['complete_evaluable']
    bands=pd.read_csv(OUT/'PAIRED_CURVE_BANDS.csv')
    raw=pd.read_csv(OUT/'RAW_ANSWER_COMMON_REFERENCE.csv')
    r=raw[raw.metric=='B8L2'].pivot(index='image',columns='version',values='mean')
    rawdelta=r.overall_after-r.overall_before
    lines=['# 门洞当前双版本：筛前584份／筛后439份','',
        '[打开曲线](index.html) · [17图曲线册](CURVES.pdf) · [逐图10人比较](PER_IMAGE_K10_COMPARISON.csv)','',
        '当前筛后采用21份边界裁决接入后的439份，累计排除145份。533版已计算结果与524版名单均原位归档；524版没有对应已完成曲线。原图、点位、环序、参考、融合算法和每图256条基础顺序保持不变。仅复用精确图片/成员/目标相同的缓存。','',
        '## 10人团队的具体差距','',
        f'- 配对B8L2平均变化：{q["mean"]:+.3f}分；{q["positive"]}图提高、{q["negative"]}图降低、{q["same"]}图不变。质量有效配对{q["paired_finite"]}/{q["attempts"]}。',
        f'- 完整共识可评率平均变化：{100*c["mean"]:+.2f}个百分点；{c["positive"]}图提高、{c["negative"]}图降低、{c["same"]}图不变，分母为全部4352次配对尝试。',
        f'- 各臂分别条件于成功输出的图均B8L2：{details.mean_before.mean():.3f}→{details.mean_after.mean():.3f}；图均完整率：{100*details.complete_before.mean():.2f}%→{100*details.complete_after.mean():.2f}%。',
        f'- 图内Q标准差平均变化{(details.sd_after-details.sd_before).mean():+.3f}分（{(details.sd_after<details.sd_before-1e-9).sum()}图下降）；P10平均变化{(details.p10_after-details.p10_before).mean():+.3f}分（{(details.p10_after>details.p10_before+1e-9).sum()}图提高）。这些量同样受可评分输出及有限人员池影响。',
        f'- 原答按相同整体参考评价，筛后减筛前的逐图等权平均B8L2变化为{rawdelta.mean():+.3f}分（{(rawdelta>1e-9).sum()}图升、{(rawdelta< -1e-9).sum()}图降）；这是原答群体变化，不是融合曲线。','',
        '质量配对差只使用同图、同基础路径、双方都可评分的结果；各臂曲线均值则分别条件于本臂可评分。两者不可互换。完整率保留全部失败尝试，缺失质量不置零。17图等权汇总，建筑是重抽样单位之一，256条路径不是256名独立受试者。','',
        '| 图片 | 筛前→筛后人数 | 配对Q变化 | 形成率变化/百分点 | Q有效配对/256 |',
        '|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["image"]} | {row["before_n"]}→{row["after_n"]} | {row["paired_quality_delta"]:+.3f} | {row["complete_delta_pp"]:+.2f} | {row["paired_quality_valid"]} |')
    lines+=['','## 14人池与支持范围','',
        'B6ByNegPMKs-43从35人筛到14人，曲线只到k=14；k>14是无人员支持，不是质量为0或融合失败。k=10时筛后已用到71.4%的池，筛前仅28.6%。k=13只有14种团队，k=14只有1种团队，路径重复仍按出现频率保留；近满员低波动不能全部归因于标注更一致。',
        f'去掉这张图后，其余16图的k=10配对B8L2变化为{sensitivity["B8L2"]["mean"]:+.3f}分，完整率变化为{100*sensitivity["complete_evaluable"]["mean"]:+.2f}个百分点。',
        '主双版本共同人数支持为k=3—14的17图；超过14人时比较图片逐步减少，详见PAIRED_CURVE_CHANGES.csv中的images和attempts。即使人员容量足够，条件质量仍可能没有有效输出。k=1是原答诊断，k=2仅补充。','',
        '## 不确定性和边界','']
    for metric,label,scale in [('B8L2','B8L2配对差',1),('complete_evaluable','形成率差/百分点',100)]:
        for kind in ['path_stratified','building_cluster']:
            v=bands[(bands.comparison=='screening')&(bands.k==10)&(bands.metric==metric)&(bands.bootstrap==kind)].iloc[0]
            lines.append(f'- {label}，{kind}的95%逐点区间：[{scale*v.pointwise_low:.3f}, {scale*v.pointwise_high:.3f}]。整段同时区间另见表，不能用逐点区间声称整段显著。')
    hold=json.loads((OUT/'EXCLUDE13_HEADLINES.json').read_text(encoding='utf8'))['screening_k10']
    lines += [f'- 排除历史13份资格标记的k=10敏感性：Q差{hold["B8L2"]["mean"]:+.3f}分，形成率差{100*hold["complete_evaluable"]["mean"]:+.2f}个百分点。筛后439份实际含其中10份；移除后429份，不机械减13。该敏感性仅覆盖k=6/10。',
        '- 7份保留记录历史空间归属为空：仍计入整体筛后池，分空间池暂不纳入。分空间变动包含最新人工空间裁决，不能全解释成筛除效应。',
        '- S9hNv5qa7GM-08的空间1、jh4fc5c5qoQ-09的空间2均仅3人，k=3没有形成可评分完整输出：质量曲线留空、完整率保留0，不能写成质量0或没有原始作答。',
        '- 筛选依据原图与原标注的可解释性，未用单人Q裁决；但追加筛选是在已知533版汇总结果后发起，不能称为预注册或对汇总结果完全盲。结果不能外推为总体乱标率，也不能把筛后改善写成随机干预的因果效应。',
        '- GT修订/可疑问题另行收集；本轮没有重修GT或为提高分数改变参考。','']
    (OUT/'RESULTS_ZH.md').write_text('\n'.join(lines),encoding='utf8')
    # Pairwise differences retain fixed support through k=14; show cluster uncertainty.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,metric,label,scale in zip(axes,['B8L2','complete_evaluable'],['配对条件质量差 B8L2','完整共识可评率差（百分点）'],[1,100]):
        g=bands[(bands.comparison=='screening')&(bands.bootstrap=='building_cluster')&(bands.metric==metric)].sort_values('k')
        ax.axhline(0,color='#777',lw=1);ax.plot(g.k,g.delta*scale,color='#0079b8',marker='o');ax.fill_between(g.k,g.pointwise_low*scale,g.pointwise_high*scale,color='#0079b8',alpha=.15)
        ax.set(xlabel='团队人数',ylabel=label,xticks=range(3,15));ax.grid(alpha=.2)
    fig.suptitle('筛后439 − 筛前584：17图共同人数范围；阴影为建筑重抽样95%逐点区间')
    fig.tight_layout();fig.savefig(OUT/'COMPARISON_OVERVIEW.png',dpi=160);plt.close(fig)
    p=OUT/'index.html';html=p.read_text(encoding='utf8')
    html=html.replace('<h2>', '<p>当前唯一双版本为584/439。B6ByNegPMKs-43筛后仅14人，超过容量不画；近满员组合减少，不能据此声称一致性提升。</p><img src="COMPARISON_OVERVIEW.png" alt="双版本配对变化及建筑重抽样区间"><h2>',1)
    p.write_text(html,encoding='utf8')


if __name__=='__main__':main()
