"""Produce compact summaries and figures from validated final result tables."""
from pathlib import Path
from collections import defaultdict
import csv,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from explore import save_csv,save_json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results';FIG=ROOT/'figures'
def read(name):
    return list(csv.DictReader((OUT/name).open()))


def main():
    FIG.mkdir(exist_ok=True)
    exact=read('exact_iou_vs_16.csv');expect=read('all_k_expectations.csv')
    samples=read('sample16_offline_curves.csv');cells=read('full_pool_integration_cells.csv')
    sup=read('support_field_identities.csv')
    val=json.loads((OUT/'validation.json').read_text())
    summaries=[]
    for group in val['groups']:
        im=group['image'];n=group['N'];rr=[r for r in exact if r['image']==im]
        worst=max(rr,key=lambda r:abs(float(r['sample16_iou_error'])))
        cc=[r for r in cells if r['image']==im]
        tie=sum(float(c['area_h2']) for c in cc if 2*int(c['support'])==n)
        ss=next(r for r in sup if r['image']==im)
        summaries.append(dict(image=im,N=n,gate=group['gate'],full_tiles=group['full_tiles'],
            exact_k='|'.join(map(str,group['enumerated_k'])),
            max_absolute_sample16_iou_error=abs(float(worst['sample16_iou_error'])),
            worst_method=worst['method'],worst_version=worst['version'],worst_k=int(worst['k']),
            worst_signed_error=float(worst['sample16_iou_error']),
            exact_mean_at_worst=float(worst['exact_iou_mean']),sample16_mean_at_worst=float(worst['sample16_iou_mean']),
            worst_all_subsets=int(worst['all_subsets']),worst_sampled_unique_subsets=int(worst['sampled_unique_subsets']),
            reference_independent_D_union=float(ss['reference_independent_D_union']),
            fullpool_exact_half_support_area_h2=tie,
            fullpool_exact_half_support_area_union=tie/group['domain_area_h2']))
    save_csv(OUT/'group_findings.csv',summaries)
    plt.rcParams.update({'font.size':9,'axes.titlesize':10,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
    ordered=sorted(summaries,key=lambda r:r['max_absolute_sample16_iou_error'])
    fig,ax=plt.subplots(figsize=(10,6),layout='constrained')
    y=np.arange(len(ordered))
    ax.barh(y,[r['worst_signed_error'] for r in ordered],color=['#b76332' if r['worst_signed_error']>0 else '#297090' for r in ordered])
    ax.set_yticks(y,[r['image']+f"  (N={r['N']}, k={r['worst_k']})" for r in ordered])
    ax.axvline(0,color='#555',lw=.8);ax.set_xlim(-.1,.11)
    ax.set_xlabel('Sampled mean IoU minus exact finite-pool mean IoU')
    ax.set_title('16 fixed permutations: largest checked mean error per image\nExact all k for N<=9; exact k=1,2,N-2,N-1,N otherwise')
    ax.grid(axis='x',alpha=.2)
    for yy,r in zip(y,ordered):
        x=r['worst_signed_error'];ax.text(x+(.002 if x>=0 else -.002),yy,f'{x:+.4f}',va='center',ha='left' if x>=0 else 'right',fontsize=8)
    fig.savefig(FIG/'01_sample_error.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(4,3,figsize=(13,11),layout='constrained')
    for ax,group in zip(axes.flat,val['groups']):
        im=group['image'];u=group['domain_area_h2'];n=group['N']
        for method,color,style in [('mv50','#17658a','-'),('mv_strict','#bb6837','--')]:
            rr=[r for r in expect if r['image']==im and r['method']==method and r['version']=='original']
            sr=[r for r in samples if r['image']==im and r['method']==method and r['version']=='original']
            ax.plot([int(r['k']) for r in rr],[float(r['expected_area_h2'])/u for r in rr],style,color=color,label=method+' exact mean',lw=1.6)
            ax.scatter([int(r['k']) for r in sr],[float(r['sampled_area_h2'])/u for r in sr],color=color,s=11,alpha=.6)
        ax.set_title(im+f' | N={n}');ax.set_ylim(0,1.02);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel('Distinct people k');ax.set_ylabel('Fused area / fixed full-pool union');ax.grid(alpha=.15)
        if n==1:ax.set_xlim(.5,1.5);ax.set_xticks([1])
    axes.flat[0].legend(fontsize=7)
    fig.suptitle('Exact all-k expected fused area; dots are the original 16-permutation estimator\nOffline fixed-panel integration only. No reference geometry enters this quantity.',fontsize=12)
    fig.savefig(FIG/'02_exact_area_12_panels.png',dpi=170);plt.close(fig)
    report(summaries,val,exact)


def report(groups,val,exact):
    lines=['# 等权 Lee：12 图有限池精算与 16 排列误差复核','','## 先看结论','',
    '1. **16 排列的误差并非只出现在最初 8 人图。** 在本次已精确穷举的切片里，11 个非单人组的最大参考 IoU 均值偏差都超过 0.02；单人组为 0。这是已冻结的有限人员池与当前固定种子的描述，不是总体误差置信界，也不是所有中间 k 的全局最大值。',
    '2. **所有 k 的平均融合面积、与各版参考的平均交集/遗漏/外扩，以及相邻新增一人的平均变化面积，可以直接解析求得。** 无需百万子集或新增真人投票。IoU 的期望没有被面积期望的比值替代。',
    '3. **奇偶锯齿有确定的投票机制。** MV50 奇→偶只扩张、偶→奇只收缩；严格多数反向。因此期望相邻对称差面积等于两期望面积之差的绝对值。原始 change_mean 是期望 1−IoU，不能用这里的面积量冒充。',
    '4. 全员时只有一个成员集，成员差异为 0 仍是机制事实；不证明达到质量上限，也不证明新人员不会改变结果。','',
    '## 核心数值','',
    '| 图片 | N | 已检查最大偏差的位置 | 16排列均值 | 精确均值 | 差值 |',
    '|---|---:|---|---:|---:|---:|']
    for r in groups:
        lines.append(f"| {r['image']} | {r['N']} | {r['worst_method']} / {r['worst_version']} / k={r['worst_k']} | {r['sample16_mean_at_worst']:.6f} | {r['exact_mean_at_worst']:.6f} | {r['worst_signed_error']:+.6f} |")
    lines += ['',
    '最突出的一例是 7y3sRwLe3Va-12：MV50、k=2 的 16 个已采不同二人组给出 0.640655，全部 276 个二人组均值是 0.548886，相差 +0.091770。另一个方向的例子是 jtcxE69GiFV-12：严格多数 k=2 为 0.378121 对 0.458266，相差 −0.080145。两者不能简单归纳为固定向上或向下偏。',
    '',
    '原 README 中 7y3sRwLe3Va-12 的“单人→全员下降”在补齐所有单人后仍存在：MV50 精确单人均值 0.479262 → 全员 0.388328（原单人采样值 0.494059）。但这是 OOS 固定参考一致性下降，不能据此解释人员能力变差。',
    '',
    'e9zR4mvMWw7-19 的全员 MV50 区域对原始参考为 0.469380，对既有修订参考为 0.810395。参考版本的解释差异仍在；本研究不裁定哪版视觉正确。',
    '',
    '## 精确覆盖及验证','',
    '- 固定输入 SHA-256：`4a7ffc036cfbafc21e8adaa84ead6a101dcf6dda84cc047ee2ad3858f9cc604c`，源提交 `b1ebab888fe8ac736548897f126a8bce7292c114`。',
    '- 12 图、195 份作答；按原 condition/gate/independent/consensus_eligible 保留 177 个候选、18 个排除记录；15 个参考版本分开计算。未修改资格、GT 或 BEV。',
    '- 六个 N≤9 组穷举所有非空子集，共 1,180 个；其余六组精确穷举 k=1、2、N−2、N−1、N；合计 4,554 个成员集。所有组所有 k 的面积类期望均解析计算，共 492 个 method/reference/k 行。',
    '- 精确 IoU 均值/分位数仅在 166 个已穷举 method/reference/k 切片报告。较大组的其他中间 k 没有宣称精确 E[IoU]、IoU 分位数或 Jaccard 成员差异。',
    f"- 全部小组子集及大组代表性切片，共 {sum(g['fresh_current_member_prefixes_checked'] for g in val['groups'])} 个前缀重新只用当前成员切分，分别验证两种规则；与离线全员细分后选择的最大形状对称差 {val['max_refinement_symmetric_difference_h2']:.3g} h²，直接几何 IoU 最大差 {val['max_direct_geometry_iou_error']:.3g}。",
    f"- 面积与支持场有限池恒等式最大数值误差 {val['max_expectation_identity_error']:.3g}；相邻变化公式与穷举/面积差检查最大误差 {val['max_transition_identity_error']:.3g}。",
    '- 492 个原发布采样均值逐项比较，最大差 7.77×10⁻¹⁶；全部 unique_subsets 分母吻合。独立实现没有导入上游或返回包数值函数。',
    '',
    '## 为什么全员 tile 只在离线积分时可用','',
    '把全员足迹边界切成更细的公共分区，只是把每一小片上“这个当前子集有几票”写成常数。当前子集的多数指示函数仍只读取该子集成员的 0/1 票；未来成员的几何只让积分网格更细，不改变这个指示函数。这里用逐前缀重新切分做了数值等价检查。',
    '',
    '这不改变原流程：真实在线/前缀预测仍只用已到人员切分，不能宣称拿到了未来人员、拿未来池评估泛化，或把这一离线方法直接替换原预测实现。当前研究的概率空间是“从这 N 个已冻结真人中均匀无放回选 k 个”，不是人员总体或后验真值概率。',
    '',
    '## 公式（固定池，不含蒙特卡洛）','',
    '令 cell j 面积为 a_j、全池支持数为 s_j、与固定参考 G 的交集面积为 i_j，g=|G|，固定全池并集 U 面积为 u。均匀 k 子集的 cell 支持 X_j 服从 Hypergeom(N,s_j,k)。阈值 t_k：MV50 是 ceil(k/2)，严格多数是 floor(k/2)+1。',
    '',
    '- q_j(k)=P(X_j≥t_k)=Σ[x≥t_k] C(s_j,x) C(N−s_j,k−x) / C(N,k)',
    '- E|M_k|=Σ a_j q_j；E|M_k∩G|=Σ i_j q_j',
    '- E遗漏=g−Σ i_j q_j；E外扩=Σ(a_j−i_j)q_j；固定 g 或 u 归一化保持精确',
    '- p_j=s_j/N；D=∫p(1−p)。D_U=D/u 不依赖 GT。D_G=D/g 随参考面积改变，只用于对应参考版本',
    '- B_G=∫(p−1_G)²/g；平均单人对称差/g=B_G+D_G',
    '- N>1 时 c_k=(N−k)/(k(N−1))：E[B_k]=B_G+c_kD_G，E[D_k]=(1−c_k)D_G；N=1 特判 c=0，不做除零',
    '- 两个不同真人的平均对称差/u=2N/(N−1) D_U（N>1）',
    '- 同 k 两个独立均匀子集的平均对称差=Σ2a_jq_j(1−q_j)。条件在两个子集不同，乘 C(N,k)/(C(N,k)−1)；只有一个子集时设为 0。这也是面积差异，不能冒充原 member_distance_mean 的 Jaccard 距离',
    '',
    '新增一人时，给定 X_j=x，新人支持该 cell 的概率是 (s_j−x)/(N−k)。乘上对应的 0→1 或 1→0 阈值事件，再对 x 求和即得扩张、收缩概率。奇偶方向固定，所以 E|M_{k+1}△M_k|=|E|M_{k+1}|−E|M_k||。此式不允许把 E[1−IoU]写成面积期望的比值。',
    '',
    '## 一个不能忽略的比值反例','',
    '本面板 B6ByNegPMKs-42 的 k=1：真实 E[IoU]=0.323216，而 E交集/E并集=0.200657，相差 −0.122559。结果表把后者列名显式写为 NOT_expected_iou；它仅作防误用诊断。',
    '',
    '## 平票与参考无关的支持分歧','',
    '| 图片 | D / 固定全员并集面积 | 全员恰50%支持面积 / 全员并集 |',
    '|---|---:|---:|']
    for r in groups:
        lines.append(f"| {r['image']} | {r['reference_independent_D_union']:.6f} | {r['fullpool_exact_half_support_area_union']:.6f} |")
    lines += ['',
    '全员恰50%支持面积严格等于该组全员 MV50 与严格多数的面积差；奇数 N 为 0。D_U 可在参考存疑或 OOS 场景中描述本有限池内部几何分歧，但这些组没有共同抽样和难度标尺，不能按此表给图片难度或人员能力排序。',
    '',
    '## 数值警告与边界','',
    '本独立面积积分/代表性几何验证运行采用 Python 3.12.14、NumPy 2.3.5、Shapely 2.1.2、GEOS 3.13.1，捕获 0 条警告；原运行环境及原数值警告保留为独立证据。未出现警告不等于原警告被修复，也不覆盖本研究未运行的大量原 Jaccard 成员对计算。没有做 buffer、吸附、坐标修复或碎片删除。',
    '',
    '不存在缺失的合格候选足迹；若输入改变导致缺失或无效几何，脚本报错，不偷偷减小 N。本轮没有原图，不能视觉判真、重裁 GT、修正门洞适用性，不能从有限面板推真人能力、普遍人数阈值、未来预测或独立验证性能。',
    '',
    '## 最小后续动作','',
    '当前开发图的面积类均值可直接用此解析基线作误差标尺。IoU 的廉价切片先补齐所有单人、二人、倒数二人/一人和全员；小组可全穷举。较大组中间 k 如确实需要期望 IoU，可另做明确精度目标的 Monte Carlo 或更深入联合支持状态计算，不应把 16 个排列当作充分精确。这里没有擅自改原脚本或开展新的人群分类、难度模型或 GT 裁定。',
    '',
    '## 文件','',
    '- `results/all_k_expectations.csv`：所有人数的超几何精确面积期望、面积变化与双子集面积差异',
    '- `results/exact_iou_vs_16.csv`：166 个已穷举切片的精确 IoU 均值/分位数与当前 16 排列差值',
    '- `results/bounded_exact_subset_outcomes.csv`：4,554 个已计算成员集，按规则和参考版本保留的逐集数值',
    '- `results/support_field_identities.csv`、`group_findings.csv`：B/D 恒等式、D_U 与平票面积',
    '- `results/validation.json`、`formula_tests.json`、`published_sample_comparison.json`：检查边界及误差',
    '- `figures/01_sample_error.png`、`02_exact_area_12_panels.png`：已核验采样偏差及12图精确面积曲线',
    '- `src/explore.py` 独立重算；`test_formulas.py` 独立有限组合验证；`make_report.py` 出图/报告',
    '']
    (ROOT/'REPORT_zh.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
