#!/usr/bin/env python3
"""Make the Chinese report and publication plots from saved stability tables."""
from pathlib import Path
import argparse,os,json
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_stability_mpl')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROLES={
 'joint_highq_first':'联合分类中历史Q中心最高类优先',
 'structure_moreturn_first':'历史非冗余转折较多类优先',
 'joint_fast_first':'联合分类中历史相对时间最低类优先',
 'structure_dominant_first':'历史人数最多的结构类优先'}
EN={'joint_highq_first':'Higher-Q role first','structure_moreturn_first':'More-turn role first','joint_fast_first':'Faster role first','structure_dominant_first':'Largest historical structure class first'}

def fmt(x,n=3):return '不可计算' if pd.isna(x) else f'{x:.{n}f}'
def interval(r):return f'[{fmt(r.percentile_2_5)}, {fmt(r.percentile_97_5)}]'
def row(df,**kw):
    z=df
    for c,v in kw.items():z=z[z[c].eq(v)]
    assert len(z)==1,(kw,len(z));return z.iloc[0]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();r=a.root/'results';f=a.root/'figures';f.mkdir(exist_ok=True)
    ni=pd.read_csv(r/'NATURAL_INTERVAL_STABILITY.csv');nc=pd.read_csv(r/'NATURAL_CURVE_STABILITY.csv');ps=pd.read_csv(r/'POLICY_EARLY_STABILITY.csv');im=pd.read_csv(r/'NATURAL_IMAGE_CURVES_REBUILT.csv.gz');pi=pd.read_csv(r/'POLICY_EARLY_IMAGE_REBUILT.csv')
    base=dict(layer='ordinary_manual',difficulty='困难',interval='10_to_20')
    nkey=ni[(ni.layer.isin(['ordinary_manual','doorway_manual','ordinary_semi']))&(ni.interval.isin(['3_to_6','10_to_20']))&ni.metric.isin(['Q_mean','Q_p10','Q_sd_ddof1','score_failure_nonpolicy_rate'])]
    nkey.to_csv(r/'KEY_NATURAL_INTERVALS.csv',index=False)
    pkey=ps[ps.policy_support.eq('common_four_policy_pools')&ps.layer.isin(['ordinary_manual','ordinary_semi'])&ps.difficulty.eq('全部')]
    pkey.to_csv(r/'KEY_POLICY_EARLY_EFFECTS.csv',index=False)
    orders=pd.read_csv(a.root/'inputs/EXACT_ORDER_DESIGN.csv.gz',low_memory=False)
    fields=['pool_id','image','building','condition','layer','difficulty','pool_n','policy','method','tier','target_class','heldout_building','target_members','target_capacity','history_people','history_turn_center','history_q_center','history_t_center']
    roles=orders[orders.policy.ne('natural_random')][fields].drop_duplicates();assert not roles.duplicated(['pool_id','policy']).any();roles['role_zh']=roles.policy.map(ROLES);roles.to_csv(r/'ROLE_LABELS_BY_POOL.csv',index=False)
    # No comparison uses bare fold class codes: display roles aligned from their
    # original historical selection rule, retaining the actual fold labels.
    natural_lines=[]
    for metric,label in [('Q_mean','平均Q'),('Q_p10','图内P10'),('Q_sd_ddof1','图内标准差'),('score_failure_nonpolicy_rate','失败比例')]:
        for weight,wl in [('image_equal','图等权'),('building_equal','楼等权')]:
            x=row(ni,**base,metric=metric,weighting=weight,resampling='path_resampling_fixed_images');y=row(ni,**base,metric=metric,weighting=weight,resampling='building_resampling_fixed_paths')
            scale=100 if metric.endswith('_rate') else 1
            def ci(z):return f'[{fmt(z.percentile_2_5*scale)}, {fmt(z.percentile_97_5*scale)}]'
            natural_lines.append(f'|{label}{"（百分点）" if scale==100 else ""}|{wl}|{fmt(x.estimate*scale)}|{ci(x)}|{ci(y)}|')
    policy_lines=[]
    for layer,ln in [('ordinary_manual','Manual'),('ordinary_semi','Semi')]:
        for policy in ROLES:
            kw=dict(layer=layer,difficulty='全部',policy=policy,policy_support='common_four_policy_pools',metric='paired_Q_delta',weighting='image_equal')
            x=row(ps,**kw,resampling='path_resampling_fixed_images');y=row(ps,**kw,resampling='building_resampling_fixed_paths')
            policy_lines.append(f'|{ln}|{ROLES[policy]}|{fmt(x.estimate)}|{interval(x)}|{interval(y)}|{int(round(x.positive_image_fraction*x.observed_images))}/{int(x.observed_images)}|{int(x.observed_images)}图/{int(x.observed_buildings)}楼|')
    fail_lines=[]
    for policy in ROLES:
        kw=dict(layer='ordinary_manual',difficulty='全部',policy=policy,policy_support='common_four_policy_pools',weighting='image_equal',resampling='building_resampling_fixed_paths')
        q=row(ps,**kw,metric='Q_p10_delta_common');loss=row(ps,**kw,metric='Q_loss_gt5_rate');fail=row(ps,**kw,metric='score_failure_delta')
        fail_lines.append(f'|{ROLES[policy]}|{fmt(q.estimate)}|{fmt(loss.estimate*100,2)}%|{fmt(fail.estimate*100,3)}|')
    hard=im[(im.layer=='ordinary_manual')&(im.difficulty=='困难')&im.k.isin([10,20])];hn=hard.groupby('k').agg(attempts=('paths_attempted','sum'),valid=('quality_valid_paths','sum'))
    # Plots show saved ranges without smoothing or selecting favorable k.
    fig,axes=plt.subplots(1,3,figsize=(16,4.6),layout='constrained');colors={'path_resampling_fixed_images':'#2166ac','building_resampling_fixed_paths':'#d95f02'}
    panels=[('Hard Manual: 10 to 20 annotators',ni,[(m,l) for m,l in [('Q_mean','Mean Q'),('Q_p10','Within-image P10'),('Q_sd_ddof1','Within-image SD')]],base),('Manual: early priority vs paired natural',ps,[(p,EN[p]) for p in ROLES],dict(layer='ordinary_manual',difficulty='全部',policy_support='common_four_policy_pools',metric='paired_Q_delta')),('Semi: early priority vs paired natural',ps,[(p,EN[p]) for p in ROLES],dict(layer='ordinary_semi',difficulty='全部',policy_support='common_four_policy_pools',metric='paired_Q_delta'))]
    for ax,(title,df,items,kw) in zip(axes,panels):
        for i,(key,label) in enumerate(items):
            extra={'metric':key} if df is ni else {'policy':key}
            for typ,off in [('path_resampling_fixed_images',-.12),('building_resampling_fixed_paths',.12)]:
                z=row(df,**kw,**extra,weighting='image_equal',resampling=typ);y=i+off;ax.hlines(y,z.percentile_2_5,z.percentile_97_5,color=colors[typ],lw=2.2);ax.plot(z.estimate,y,'o',color=colors[typ],ms=4)
        ax.axvline(0,color='#444',lw=.8);ax.set_yticks(range(len(items)),[v for _,v in items],fontsize=8);ax.invert_yaxis();ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.2);ax.set_xlabel('Change in B8L2 score units')
    handles=[plt.Line2D([0],[0],color=c,lw=2,label=l) for c,l in [(colors['path_resampling_fixed_images'],'Whole paths; fixed observed images'),(colors['building_resampling_fixed_paths'],'Whole buildings; fixed observed paths')]]
    fig.legend(handles=handles,loc='outside lower center',ncol=2,frameon=False,fontsize=9);fig.savefig(f/'PATH_VS_BUILDING_STABILITY.png',dpi=180);fig.savefig(f/'PATH_VS_BUILDING_STABILITY.pdf');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,ms in zip(axs,[[('Q_mean','Mean Q','#1b7837'),('Q_p10','Within-image P10','#2166ac')],[('Q_sd_ddof1','Within-image SD','#762a83')]]):
        for metric,label,color in ms:
            z=nc[(nc.layer=='ordinary_manual')&(nc.difficulty=='困难')&(nc.metric==metric)&(nc.weighting=='image_equal')&nc.k.ge(3)]
            p=z[z.resampling=='path_resampling_fixed_images'].sort_values('k');b=z[z.resampling=='building_resampling_fixed_paths'].sort_values('k')
            ax.fill_between(b.k,b.percentile_2_5,b.percentile_97_5,color=color,alpha=.10);ax.fill_between(p.k,p.percentile_2_5,p.percentile_97_5,color=color,alpha=.25);ax.plot(p.k,p.estimate,'o-',ms=2.5,color=color,label=label)
        ax.set_xlabel('Annotators k; fixed N >= 20 image panel');ax.grid(alpha=.2);ax.legend(frameon=False);ax.set_ylabel('B8L2 score units')
    axs[0].set_title('Hard Manual: conditional score and low tail');axs[1].set_title('Hard Manual: variability across member prefixes')
    fig.suptitle('29 images, 15 buildings; 24 saved whole paths per image\nDark range: path resampling. Light range: building resampling.',fontsize=11);fig.savefig(f/'HARD_MANUAL_CURVES.png',dpi=180);fig.savefig(f/'HARD_MANUAL_CURVES.pdf');plt.close(fig)
    report=f'''# 已存人数路径的稳定性补充：路径重抽与建筑重抽

## 结论先行

**Manual中，高Q角色和较多转折角色优先进入的前段升质，在完整路径和建筑两种重抽中均保持明显正向。困难图后段的平均Q接近平台，但图内低尾和成员波动仍有改善。两者是不同用途：前者改变进入构成，后者在同一自然人员池中增加人数。**

Semi没有复制Manual的前段平均升质：同一批Semi图片上的高Q／多转折策略差值为负，路径重抽保持这个方向；建筑重抽的范围跨零，说明这批图的负效应不能直接扩大为跨建筑一致规律。这是本轮实际补出的区别。

本专题属于**固定已有精确设计、重新实现分析**。原bootstrap代码未找回；本轮使用真实main `{ 'e92abe8631d7f01dc192ee796b46f295ece37a6d' }` 的原318,816端点、404,082前缀、12,398路径，并读完正式04C的229,050行。没有新增融合、端点、人员顺序、类别或评分。它是独立人数专题，不替代新大块严格ABC的原件或重建结果。

## 1. 困难图的“平台”究竟指什么

固定N≥20的普通Manual困难图为29图、15栋楼，每图24条已保存自然顺序。10→20人时，图等权平均Q从61.243到61.027，差值−0.216；15/29图升、14/29图降。因此应写：**后段平均变化较小，现有结果未显示明确持续升高或下降；低尾与成员波动仍改善。** 不能把平台写成已经证明完全不变。

|指标|计权|10→20点估计|固定图片、完整路径重抽95%范围|固定路径、建筑整块重抽95%范围|
|---|---|---:|---|---|
{chr(10).join(natural_lines)}

图内P10均值由48.513到51.634，图内标准差均值由12.125到9.410。建筑等权下点方向仍分别为正、负，但对应建筑重抽范围跨零。**图等权描述当前观察图片集合，建筑等权强调不同建筑的平均表现；两者并列，不选一个当作唯一正确均值。** 路径重抽范围更窄，仅说明固定这批图片时顺序抽样误差较小，不是跨建筑验证。

质量统计保留真实缺失：困难10人时{int(hn.loc[10,'valid'])}/{int(hn.loc[10,'attempts'])}个前缀可评，20人时{int(hn.loc[20,'valid'])}/{int(hn.loc[20,'attempts'])}可评。每个k先在每张图的可评路径上计算Q均值、P10和SD，再按图／楼汇总；失败比例用全部尝试作分母。29张图在这两个k都至少有可评路径，SD均有至少两条可评路径。无效路径未补零，也未从失败分母中删除。

普通Manual三难度3→6的平均Q改善分别为简单+4.208、中等+7.770、困难+7.966；路径和建筑重抽范围均为正。简单及中等10→20仍显示平均上升；困难图的后段平台不是所有难度共有的曲线形状。17张门洞图、9栋楼10→20的图等权Q差值−3.066，路径范围[−4.798,−1.356]，建筑范围[−7.666,−0.170]；门洞保持单列，6/17图仍改善。

## 2. 类别进入策略的主要方向是否由路径抽样造成

前段定义为每池 `3 ≤ k ≤ floor(N/2)`。每个策略使用原配对自然路径的同一个base_path_id；每次抽中一条base路径时，它的全部k及其策略变换一起进入。先每图每k平均，再在前段k等权平均，最后图等权或建筑等权。

主表使用四策略均存在的共同图集：普通Manual157图22楼，普通Semi21图11楼。角色按照原楼外历史特征对齐，不跨折拼接相同M编号。`results/ROLE_LABELS_BY_POOL.csv`保留实际楼外类别、人数、目标成员及历史中心，`inputs/EXACT_ORDER_DESIGN.csv.gz`保留全部实际进入顺序。

|条件|类别角色优先规则|平均Q差值|固定图片的配对路径重抽95%范围|建筑整块重抽95%范围|平均Q正向图片|支持|
|---|---|---:|---|---|---:|---|
{chr(10).join(policy_lines)}

Manual的高Q和较多转折角色优先适合保留为进入策略；快角色优先保留效率用途，但其平均Q代价不能省略。历史人数最多的结构类别不是自然的最优前段选择。联合Q/T策略与结构策略使用不同历史定义；本分析没有重调分类，也不声称类别优于连续Q/T。

升质不等于零风险。以下为同一Manual157图共同域的图等权结果；Q损失超过5分只在策略与自然两边都可评的同k前缀上计算，失败变化使用全部配对尝试。概率先在每图每k平均再按前段和图片平均，不是把全部前缀当独立样本。

|角色|图内P10平均变化（共同可评路径）|Q损失>5分的前段平均比例|失败比例变化（百分点）|
|---|---:|---:|---:|
{chr(10).join(fail_lines)}

**记录时间已另做一次针对性修正。** 初版仅检查`source_time_known_n == k`，未排除队内混合记录语义；这些旧时间列仍保留，但不再用于同语义成本结论。新`results/time_semantics/`同时要求单队全已知、单一语义、双端同语义及双端Q可评，给出分来源精确配对、支持损失和完整重抽。普通Manual新来源报告时间子域中，快角色优先68图18楼Q+0.228、时间比0.798；高Q123图21楼Q+8.509、比1.119；较多转折102图20楼Q+7.827、比1.215。各策略时间支持不同，不能直接排名；时间比是逐路径、可用k、图片的分层算术平均，不是总劳动相除。全质量共同域157图的结果未改变。完整定义、来源分层、坏尾和建筑范围见`TIME_SEMANTICS_CORRECTION_ZH.md`。历史88图成本结果本轮未按原规则及同语义要求复核，不写成本轮已核结论。 随后按四策略完全相同的pool/base/k取得自然共同QT：新来源普通Manual67图18楼、4,304个配对单位，高Q优先Q+7.419/时间比1.026，较多转折+6.810/1.097，快角色−0.873/0.776；坏尾分别4.4%、5.4%、14.0%。这是仅重新汇总的窄共同域，未另做重抽。失败使用4,613个共同时间尝试另算，详见`FOUR_POLICY_TIME_COMMON_ZH.md`。

## 3. 分位数、标准差和重抽的确切定义

- P10：每图、每k，对可评路径Q使用线性插值经验10%分位数；不是合并所有图片后取P10。
- SD：每图、每k可评路径的样本标准差，`ddof=1`。自然曲线沿用原定义；本轮策略共同支持的波动对照也显式采用ddof=1，不混用原策略某些表的ddof=0。
- 路径重抽：固定图片，每池有放回抽取24条完整自然路径；策略在8条原配对base路径中重抽，保留完整路径及策略配对。同池各策略使用相同重抽索引。
- 建筑重抽：整栋有放回抽取，保留其中所有当前图片及原观察路径。分别估计图等权和楼等权；不把所有图对／前缀视为独立观察。
- 固定2,000次，master seed=`2026102307`，各池与建筑层seed由公开SHA规则派生。保存的范围是逐指标的95%百分位范围，不是同时置信带。两种误差来源分别展示，没有把它们混成一个范围。
- 缺失Q保持NaN。均值/P10需至少1条有效路径，SD需至少2条；若某次重抽对应指标不可算，保留该次缺失并报告`valid_bootstrap_draws`。k=2合同延期保留为延期，不计作普通融合失败。
- 80/90继续使用原阈值；完整04C的既有逐前缀达到状态可由同一Q唯一复算。本轮不重新选择质量阈值，也不把未达到改写为达到。

## 4. 本轮做了什么、哪些保留原身份

|项目|身份|本轮工作|
|---|---|---|
|318,816端点、404,082前缀、12,398顺序|main已有真实原件|读取完整文件，按精确团队键连接，选择必要列形成可下载完整分析输入|
|正式04C 229,050行|main已恢复的正式表|读到结尾；配对团队键及两边Q与原端点连接全部相同|
|自然曲线与策略点估计|原设计上的重新汇总|没有新增团队或评分，主点估计与既有采用结果衔接|
|完整路径／建筑重抽程序和范围|本轮新实现分析|旧bootstrap代码未找回；不是旧区间原样恢复|
|较大块ABC|另一个正在重建的实验|本专题的原件与结果不替代缺失ABC设计或111,054端点|

**采用判断：** 保留Manual前段高Q与较多转折优先的多数升质；保留困难图后段改善图内低尾与成员波动的实际用途；将“路径稳定”与“跨建筑稳定”分开。Semi策略平均作用目前是条件性结果。人数曲线反映人数、具体成员及冻结融合门槛共同作用，满员端点完全相同不证明全员质量正确。

## 5. 复算、数据与接入

建议仓库相对位置：`research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/`。本目录根运行：

```bash
python -m pip install -r requirements.txt
python code/rebuild_path_stability.py --input inputs --out results --replicates 2000 --seed 2026102307
python code/fix_time_semantics.py --root . --replicates 2000 --seed 2026102307
python code/report_time_correction.py --root .
python code/describe_common_time_support.py --root .
python code/make_report.py --root .
python code/finalize_saved_analysis.py --root .
```

`inputs/PREFIX_VALUES_COMPACT.csv.gz`有404,082行，是完整前缀的必要字段投影，不是抽样；包含`pool_id/path_id/base_path_id/k/team_key`、图／楼／条件／难度／参考、Q/D10、结构数、记录时间、失败状态。全部精确进入顺序保存在`inputs/EXACT_ORDER_DESIGN.csv.gz`。复算本分析不需要native融合环境或原图全集。

`code/prepare_fixed_inputs.py`给出从main原分片、连接与正式04C生成紧凑输入的办法。`INPUT_FILES.csv`登记实际取得原字节及commit；原大表缓存不重复交付。`inputs/INPUT_READ_RECEIPT.json`记录完整CSV通读与连接结果，`READ_TO_EOF_RECEIPT.json`登记最终输入与输出通读；最终ZIP内复读由统一交付回执记录。

关键表：`KEY_NATURAL_INTERVALS.csv`、`KEY_POLICY_EARLY_EFFECTS.csv`便于阅读；逐图及逐楼表保留全部支持；`EXACT_BOOTSTRAP_SEEDS.csv`和`POLICY_PAIRED_PATH_SUPPORT.csv`保留重抽单位；`ANALYSIS_RECEIPT.json`登记本轮操作。P10、SD和失败不同分母通过逐图表中的`paths_attempted/quality_valid_paths`及策略`paired_quality_valid`连接，不用队数代替图片数。

图：`figures/PATH_VS_BUILDING_STABILITY.png`并列两种重抽；`figures/HARD_MANUAL_CURVES.png`保留困难图实际逐k形状，没有平滑或按最好人数截断。
'''
    (a.root/'README_ZH.md').write_text(report)
    paragraph='''### 人数过程第6.1节建议追加段落（2026-10-23固定路径重建分析）

在已保存的24条自然路径和8条配对策略路径上，新增完整路径重抽与建筑整块重抽，二者分别解释。普通Manual四策略共同域157图22楼，高Q角色优先前段Q+7.710、多转折优先+6.146；建筑整块重抽的图等权95%百分位范围分别为[6.127,9.407]、[4.413,8.135]，保留其前段进入用途。困难29图15楼10→20人Q差值−0.216，固定图片路径重抽为[−1.344,0.927]，建筑重抽为[−3.007,2.533]；应称后段平均变化较小，未显示明确持续升高或下降。图等权P10+3.122、SD(ddof=1)−2.714，建筑重抽仍分别为正、负；楼等权建筑重抽的范围则跨零，说明图内成员波动的改善不能直接推广为所有建筑一致。Semi21图11楼的高Q／多转折策略负均值在固定图片路径重抽中重复，但建筑重抽跨零。新代码是基于固定设计重新实现的分析，不是遗失bootstrap代码恢复；未新增融合、人员顺序或类别。
'''
    paragraph += '\n记录时间分析已修正队内混合语义：同语义QT要求两队分别全已知且仅一种来源，两端来源一致，并在双端可评Q上联合评价。原时间列标旧口径，新增分来源表及重抽；历史88图成本未在本轮按该合同复核。普通Manual新来源报告时间的快角色优先68图18楼时间比0.798、Q+0.228，但全质量共同域157图的Q−1.651仍保留；不能用不同时间支持的均值比较策略优劣。详见TIME_SEMANTICS_CORRECTION_ZH.md。\n'
    paragraph += '\n只重新汇总四策略相同pool/base/k得到新来源共同QT域67图18楼、4304个配对单位：高Q优先Q+7.419/时间比1.026、较多转折+6.810/1.097、快角色−0.873/0.776，坏尾分别4.4%、5.4%、14.0%；失败另在4613个时间合法尝试域统计。这说明快角色自身时间可用子域的正Q不能代替全质量或完全共同域结论；本补充没有追加重抽或团队。\n'
    (a.root/'PERSONNEL_REPORT_INSERT_ZH.md').write_text(paragraph)
    claims=[['PST01','自然前段是否受路径抽样左右','Manual三难度3→6均Q改善，路径/建筑重抽均正','两种重抽及图/楼等权','普通Manual N≥20：168图22楼','results/NATURAL_INTERVAL_STABILITY.csv; code/rebuild_path_stability.py','保留前段加人的用途'],['PST02','困难后段是否平台','10→20图等权Q−0.216；P10+3.122；SD−2.714','Q两类范围跨零；楼等权建筑范围使P10/SD跨零','29图15楼/24自然路径每图','results/KEY_NATURAL_INTERVALS.csv; results/NATURAL_IMAGE_INTERVALS_REBUILT.csv','平台为小平均变化，不是完全不变'],['PST03','Manual角色优先是否稳定','高Q+7.710，多转折+6.146','共同157图；完整配对路径和建筑重抽均正','157图22楼/8配对路径每图','results/KEY_POLICY_EARLY_EFFECTS.csv; results/ROLE_LABELS_BY_POOL.csv','采用前段策略，保留坏尾和失败'],['PST04','Semi是否复制Manual','高Q−0.875、多转折−0.727','路径范围负，建筑范围跨零','21图11楼/8配对路径每图','results/KEY_POLICY_EARLY_EFFECTS.csv','不采用跨条件统一升质模型'],['PST05','失败是否被可评Q掩盖','困难10/20有效667/696、674/696；策略保留全部尝试失败','Q共同可评，失败全分母','对应同一图/路径支持','results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz; results/POLICY_IMAGE_K_REBUILT.csv.gz','均Q与失败并列'],['PST06','恢复还是新研究','精确设计存续；原bootstrap不在','完整原始键连接；本轮新代码和seed','全404082前缀复算输入','inputs/INPUT_READ_RECEIPT.json; results/ANALYSIS_RECEIPT.json','固定设计重新实现分析；不冒称新大块ABC原件']]
    claims.append(['PST07','记录劳动是否同语义可比','补回7302原答来源；同队单一语义、双端同类来源后重抽','保留旧时间列并标口径；分来源表，旧88图成本未复核','Manual合法QT支持依策略与来源不同','TIME_SEMANTICS_CORRECTION_ZH.md; results/time_semantics/; code/fix_time_semantics.py','新时间结论使用同语义共同QT；全Q与失败不变'])
    pd.DataFrame(claims,columns=['claim_id','研究问题','主结果','敏感性与对照','支持范围','精确表与代码','采用判断']).to_csv(a.root/'CLAIM_INDEX_ZH.csv',index=False)
    print('Saved Chinese report, insert, claim index, key tables and 2 figure pairs')

if __name__=='__main__':main()
