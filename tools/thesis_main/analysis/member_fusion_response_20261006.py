"""连接既有共同十图成员均值、8人融合及实际全员终点；不重算几何。"""
import json
from itertools import product

import numpy as np

from .consensus_response_20261006 import ROOT, OUT, SOURCE, read_csv, write_csv

DEST = OUT / 'member_fusion'
POLICIES = ('original', 'revised_where_available')
STRATEGIES = ('lower_rich', 'balanced', 'higher_rich')
METRICS = dict(O='omission_ref', E='extension_ref', D='ref_symdiff_ref')


def member_mean(errors, higher, k, h):
    """固定构成无放回抽组的成员均值期望，支持多分项。"""
    result = np.zeros(errors.shape[1:])
    if h:
        result += h / k * errors[higher].mean(axis=0)
    if k-h:
        result += (k-h) / k * errors[~higher].mean(axis=0)
    return result


def run():
    block = json.loads((ROOT/'analysis_results/worker_profiles_20261003/block.json').read_text(encoding='utf-8'))
    images, workers = block['images'], block['workers'].split('|')
    people = {(r['image'], r['worker'], r['version']): r for r in read_csv(OUT/'individual_reference.csv') if r['condition']=='manual'}
    labels = {(r['image'], r['policy'], r['worker']): r['higher']=='True' for r in read_csv(SOURCE/'assignments.csv')}
    fusion = {(r['image'], r['policy'], r['method'], r['version'], r['strategy']): r for r in read_csv(OUT/'composition/per_image.csv') if r['k']=='8'}
    full = {(r['image'], r['method'], r['version']): r for r in read_csv(OUT/'all_pool_summary.csv') if r['condition']=='manual'}
    rows=[]
    for image, calibration, evaluation, method in product(images, POLICIES, POLICIES, ('mv50','mv_strict')):
        version = 'manual_revision' if evaluation!='original' and (image,workers[0],'manual_revision') in people else 'original'
        errors = np.array([[float(people[image,w,version][m]) for m in METRICS.values()] for w in workers])
        higher = np.array([labels[image,calibration,w] for w in workers])
        assert len(workers)==24 and higher.sum()==12
        endpoint = full[image,method,version]
        for strategy in STRATEGIES:
            source = fusion[image,calibration,method,version,strategy]
            k,h=int(source['k']),int(source['higher_n'])
            mean = member_mean(errors,higher,k,h)
            row=dict(image=image,difficulty=source['difficulty'],calibration=calibration,evaluation=evaluation,
                     version=version,method=method,strategy=strategy,k=k,higher_n=h,n=24,
                     R=float(source['raw_pairwise_union']),V=float(source['member_symdiff_union']))
            for j,(short,metric) in enumerate(METRICS.items()):
                f=float(source[metric]); all_field={'O':'all_omission_ref','E':'all_extension_ref','D':'all_error_ref'}[short]
                row.update({f'M_{short}':float(mean[j]),f'F_{short}':f,f'B_{short}':float(mean[j]-f),
                            f'all_M_{short}':float(errors[:,j].mean()),f'all_F_{short}':float(endpoint[all_field])})
            for prefix in ('M','F','B','all_M','all_F'):
                assert abs(row[prefix+'_D']-row[prefix+'_O']-row[prefix+'_E'])<1e-12
            rows.append(row)
    contrasts=[]
    for image,calibration,evaluation,method in product(images,POLICIES,POLICIES,('mv50','mv_strict')):
        group={r['strategy']:r for r in rows if (r['image'],r['calibration'],r['evaluation'],r['method'])==(image,calibration,evaluation,method)}
        hi,lo=group['higher_rich'],group['lower_rich']
        item={key:hi[key] for key in ('image','difficulty','calibration','evaluation','version','method')}
        for metric in METRICS:
            for prefix in ('M','F','B'):
                item[f'delta_{prefix}_{metric}']=hi[f'{prefix}_{metric}']-lo[f'{prefix}_{metric}']
            assert abs(item[f'delta_F_{metric}']-item[f'delta_M_{metric}']+item[f'delta_B_{metric}'])<1e-12
        contrasts.append(item)
    DEST.mkdir(parents=True,exist_ok=True)
    write_csv(DEST/'per_image.csv',rows)
    write_csv(DEST/'contrasts.csv',contrasts)
    (DEST/'field_contract.json').write_text(json.dumps(dict(schema='member_fusion_response_v1',
        source=['../individual_reference.csv','../composition/per_image.csv','../all_pool_summary.csv',str((SOURCE/'assignments.csv').relative_to(ROOT))],
        panel='Same 24 Manual workers x 10 images; k=8; existing building-held-out Q labels, no selection changes.',
        references='calibration selects existing Q assignments; evaluation chooses original or revision where available (4 revised, 6 original). version is actual GT. Repeated original rows under two evaluation policies are not independent observations.',
        metrics='O=omission/GT area, E=extension/GT area, D=O+E; M=expected member mean, F=expected fusion error, B=M-F. B is reduction, not efficiency, ability, spatial complementarity or causal attribution.',
        full='all_M averages 24 people, all_F is actual full-24 consensus for the same rule/reference. Repeated across strategies/calibrations, not independent outputs; 8->24 changes size and composition.',
        RV='Existing R and V retain fixed full-pool union denominator; do not subtract from GT-normalized losses.',
        contrast='delta is higher_rich minus lower_rich; delta_F=delta_M-delta_B. No benefit ratios or B-vs-M correlation.',
        check='Fixed-composition expectation tested against enumerated teams; D=O+E and contrast identity checked.'),ensure_ascii=False,indent=2),encoding='utf-8')
    report(rows,contrasts,images)
    plot(rows,images)
    print(json.dumps(dict(rows=len(rows),contrasts=len(contrasts))))


def report(rows,contrasts,images):
    text=['# 成员起点、8人融合与全员结果','',
          '2026-10-07。复用共同24人十图、楼外Q分组、两投票规则；无新抽样或几何计算。每个具体组仍只输出一个共识。', '',
          'M为成员平均参考误差的期望，F为融合参考误差的期望，B=M−F是误差减少量。全部按同版GT面积归一化；越小越近，负B表示相对成员均值变差。B大不代表输出更好或融合更有效。', '',
          '## 主对照：原GT校准、原GT评价、MV50','',
          '| 图片 | 上半 M→F | 下半 M→F | 混合 M→F | 全24人 M→F |',
          '|---|---:|---:|---:|---:|']
    for image in images:
        g={r['strategy']:r for r in rows if r['image']==image and r['calibration']==r['evaluation']=='original' and r['method']=='mv50'}
        line=[image]
        for s in ('higher_rich','lower_rich','balanced'):
            r=g[s]; line.append(f"{r['M_D']:.4f}→{r['F_D']:.4f}")
        line.append(f"{r['all_M_D']:.4f}→{r['all_F_D']:.4f}")
        text.append('| '+' | '.join(line)+' |')
    text += ['', '![成员与融合配对](paired_results.png)', '',
             '## 原GT／MV50的遗漏与外扩变化','',
             '下表为M−F：正数减少，负数增加。全员列为全24人均值减实际全员结果。', '',
             '| 图片 | 上半 Δ遗漏／Δ外扩 | 下半 Δ遗漏／Δ外扩 | 全员 Δ遗漏／Δ外扩 |',
             '|---|---:|---:|---:|']
    for image in images:
        g={r['strategy']:r for r in rows if r['image']==image and r['calibration']==r['evaluation']=='original' and r['method']=='mv50'}
        hi,lo=g['higher_rich'],g['lower_rich']
        text.append(f"| {image} | {hi['B_O']:+.4f}／{hi['B_E']:+.4f} | {lo['B_O']:+.4f}／{lo['B_E']:+.4f} | {hi['all_M_O']-hi['all_F_O']:+.4f}／{hi['all_M_E']-hi['all_F_E']:+.4f} |")
    text += ['', '## 本轮解释','',
             '1. **输入较好通常保留终点优势，但并非必然。** 原GT／MV50下，上半组十图M都更低，九图F更低；X7-13反转。X7上组融合遗漏0.0359大于下组0.0230，外扩虽更小（0.0016对0.0086），不足以抵消遗漏差。此处只定位到面积分项，没有自动裁定哪个具体边界错了。',
             '2. **rPc的选人优势来自更好的起点，融合缩小了这项优势。** 上组M低于下组0.1045，F只低0.0417。上组遗漏增加0.0337，外扩减少0.0247，总D略升；下组两项都减少。不能把上组终点较好说成融合获得更多改善。已有人审允许玻璃内／外侧不同目标，本轮不强制恢复某个精细个体。',
             '3. **Uw全员结果的偏离由遗漏增加主导。** 原GT下全员M→F为0.6980→0.8144，遗漏增加0.1604、外扩减少0.0440。修订参考下全员仍从约0.7259升至0.7753；但两类8人组在修订参考下均相对成员均值改善，不能把原GT下的负B固定成人员属性。',
             '4. **yq-32全局两项都改善，仍不能推翻局部简化的人审。** 上组遗漏减少0.0347、外扩减少0.0310；全员也两项减少。已有门前结构简化结论继续保留，面积改善不能直接称为细节恢复。',
             '这些结果完成了成员起点与融合终点的连接；不新增不确定性来源比例。配对图各小图使用自身纵轴，跨图差异读数值，不比较线条倾斜角度。', '',
             '## 固定十图敏感性','',
             '每行始终同十图，修订优先使用4图修订＋6图原GT。上／下指楼外Q分层。各列为图片数，非独立检验。', '',
             '| 校准 | 评价 | 规则 | 上组M更低 | 上组F更低 | M上低但F上高 | 上组B<0 | 下组B<0 |',
             '|---|---|---|---:|---:|---:|---:|---:|']
    for cal,ev,method in product(POLICIES,POLICIES,('mv50','mv_strict')):
        cs=[r for r in contrasts if (r['calibration'],r['evaluation'],r['method'])==(cal,ev,method)]
        selected=[r for r in rows if (r['calibration'],r['evaluation'],r['method'])==(cal,ev,method)]
        counts=[sum(r['delta_M_D'] < -1e-12 for r in cs),sum(r['delta_F_D'] < -1e-12 for r in cs),
                sum(r['delta_M_D'] < -1e-12 and r['delta_F_D'] > 1e-12 for r in cs)]
        counts += [sum(r['B_D'] < -1e-12 for r in selected if r['strategy']==s) for s in ('higher_rich','lower_rich')]
        text.append('| '+' | '.join([cal,ev,method]+list(map(str,counts)))+' |')
    text += ['', '## 数据和解释边界','',
             '- `per_image.csv`：240行，逐图两校准×两评价×两规则×三构成，包含O/E/D的M、F、B和全员M/F，以及原R/V。六张没有修订GT的图在两评价政策中重复，不能当新证据。',
             '- `contrasts.csv`：80行高减低对照，保存各分项ΔF=ΔM−ΔB；`field_contract.json`定义字段。',
             '- 8人是固定构成下所有可行团队的期望，全24人是实际唯一输出。全员结果重复列示用于参照，8人到全员同时改变人数和构成，不能叫纯增人收益。',
             '- 原表来自既定预处理输入及积分结果；本轮仅连接派生表，不替换原标注、参考或纳入规则。',
             '- O/E拆分用于解释参考范围变化，不识别空间互补、人员能力或局部结构正确性。共识应体现纳入人员观察，不强制像GT。',
             '- 本轮到十图解释表为止；不新增分类器、收益率或审核任务。复算：`python -m tools.thesis_main.analysis.member_fusion_response_20261006`。', '']
    (DEST/'REPORT.md').write_text('\n'.join(text),encoding='utf-8')


def plot(rows,images):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(5,2,figsize=(12,15))
    for ax,image in zip(axes.flat,images):
        g={r['strategy']:r for r in rows if r['image']==image and r['calibration']==r['evaluation']=='original' and r['method']=='mv50'}
        for s,c,label in zip(STRATEGIES,['#bd6b24','#888888','#1676a2'],['下半8人','4上＋4下','上半8人']):
            r=g[s]; ax.plot([0,1],[r['M_D'],r['F_D']],marker='o',color=c,label=label)
        ax.plot([2,3],[r['all_M_D'],r['all_F_D']],marker='s',color='#222222',label='全24人')
        ax.set(title=image,xticks=[0,1,2,3],xticklabels=['成员均值','8人融合','全员均值','全员融合'],ylabel='D / GT面积')
        ax.grid(axis='y',alpha=.25)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('原GT校准／评价，MV50；左侧为固定构成期望，右侧为实际全员对照',fontsize=13)
    fig.tight_layout(rect=[0,0,1,.97]); fig.savefig(DEST/'paired_results.png',dpi=140); plt.close(fig)


if __name__=='__main__':
    run()
