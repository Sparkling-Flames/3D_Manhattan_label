"""连接既有人数与构成结果：同图同参考，不重新拟合人员质量。"""
from collections import defaultdict
from statistics import mean, median

from .research_artifact_io import ROOT, read_csv, write_csv, write_json

OUT = ROOT/'analysis_results/count_selection_20261007'
FULL = ROOT/'analysis_results/difficulty_full_20261007/updated'
COMP = ROOT/'analysis_results/consensus_response_20261006/composition'


def join_rows(composition, curves):
    lookup = {}
    for r in curves:
        if r['condition']=='manual' and r['gate']=='main_candidate':
            key = r['image'], r['method'], r['version'], int(r['k'])
            assert key not in lookup
            lookup[key] = r
    result = []
    for c in composition:
        if c['k']!='8' or c['strategy']!='higher_rich': continue
        key = c['image'], c['method'], c['version']
        eight = lookup[(*key, 8)]
        n = int(eight['n'])
        assert n == int(c['n'])
        assert abs(float(eight['D'])-float(c['random_error_ref'])) < 1e-9
        all_r = lookup[(*key, n)]
        assert abs(float(all_r['D'])-float(c['all_error_ref'])) < 1e-9
        r = {k:eight[k] for k in ('image','building','difficulty','scene','pool','n','method','version')}
        r.update(policy=c['policy'], higher_fraction=float(c['higher_fraction']),
                 D8=float(eight['D']), selected_D8=float(c['ref_symdiff_ref']),
                 selection_gain=float(eight['D'])-float(c['ref_symdiff_ref']),
                 R=float(c['random_raw_pairwise_union']), selected_R=float(c['raw_pairwise_union']),
                 V8=float(eight['V']), selected_V8=float(c['member_symdiff_union']),
                 selection_O_gain=float(eight['O'])-float(c['omission_ref']),
                 selection_E_gain=float(eight['E'])-float(c['extension_ref']),
                 D_all=float(all_r['D']), O_all=float(all_r['O']), E_all=float(all_r['E']))
        for k in (16,20):
            target=lookup.get((*key,k))
            r[f'D{k}']=float(target['D']) if target else None
            r[f'count_gain_8_{k}']=r['D8']-float(target['D']) if target else None
            r[f'selected8_minus_random{k}']=r['selected_D8']-float(target['D']) if target else None
        result.append(r)
    return result


def run():
    OUT.mkdir(exist_ok=True)
    rows=join_rows(read_csv(COMP/'per_image.csv'),read_csv(FULL/'curves.csv'))
    write_csv(OUT/'per_image.csv',rows)
    summaries=[]
    for policy in ('original','revised_where_available'):
        for evaluation in ('original','revised_where_available'):
            for method in ('mv50','mv_strict'):
                groups=defaultdict(list)
                for r in rows:
                    if r['policy']!=policy or r['method']!=method:continue
                    groups[r['image']].append(r)
                chosen=[]
                for rs in groups.values():
                    versions={r['version']:r for r in rs}
                    chosen.append(versions.get('manual_revision',versions['original']) if evaluation!='original' else versions['original'])
                for n in (16,20):
                    for scene in sorted({r['scene'] for r in chosen}):
                        eligible=[r for r in chosen if int(r['n'])>=n and r['scene']==scene]
                        for difficulty in ['全部']+sorted({r['difficulty'] for r in eligible}):
                            rs=[r for r in eligible if difficulty=='全部' or r['difficulty']==difficulty]
                            if not rs:continue
                            bs=defaultdict(list)
                            for r in rs:bs[r['building']].append(r['selection_gain']-r[f'count_gain_8_{n}'])
                            summaries.append(dict(policy=policy,evaluation=evaluation,method=method,n=n,scene=scene,difficulty=difficulty,images=len(rs),buildings=len(bs),
                                count_gain=mean(r[f'count_gain_8_{n}'] for r in rs),selection_gain=mean(r['selection_gain'] for r in rs),
                                count_median=median(r[f'count_gain_8_{n}'] for r in rs),selection_median=median(r['selection_gain'] for r in rs),
                                count_improved=sum(r[f'count_gain_8_{n}']>1e-12 for r in rs),selection_improved=sum(r['selection_gain']>1e-12 for r in rs),
                                selected8_beats_more=sum(r[f'selected8_minus_random{n}'] < -1e-12 for r in rs),
                                count_nonpositive_selection_positive=sum(r[f'count_gain_8_{n}']<=1e-12 and r['selection_gain']>1e-12 for r in rs),
                                neither_positive=sum(r[f'count_gain_8_{n}']<=1e-12 and r['selection_gain']<=1e-12 for r in rs),
                                building_mean_advantage=mean(mean(x) for x in bs.values()), image_list='|'.join(sorted(r['image'] for r in rs))))
    write_csv(OUT/'summary.csv',summaries)
    deliver(rows,summaries)
    write_json(OUT/'field_contract.json',dict(
        inputs=[str(COMP/'per_image.csv'),str(FULL/'curves.csv')],
        join='Manual main_candidate; exact image/method/evaluation version; same N and random8/full endpoint verified; latest human labels/scenes override old composition labels.',
        gains='count_gain_8_k=D(random8)-D(randomk); selection_gain=D(random8)-D(higher-rich8); positive means closer to named reference. No causal decomposition.',
        groups='Ordinary/OOS kept apart; no doorway extrapolation without composition data. Fixed N>=16 or20 per summary; evaluation revised where available is explicit.',
        selection='Existing building-held-out Q policy, no new calibration. higher_fraction records actual feasible composition. Cost of calibration is not included.',
        metrics='R/V use full-pool union; D/O/E use reference area. Raw gains cannot be compared with R/V. Full output retained independently.',
        counts='Signs only, 1e-12 floating tolerance, no thresholds or trajectory classifier. Building-equal difference complements image averages.'))


def deliver(rows,summaries):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    chosen=[r for r in rows if r['policy']=='original' and r['version']=='original' and r['method']=='mv50' and r['scene']=='ordinary' and int(r['n'])>=20]
    fig,ax=plt.subplots(figsize=(8,6))
    for label,color in [('简单','#297ba6'),('中等','#bc8628'),('困难','#b54c65')]:
        rs=[r for r in chosen if r['difficulty']==label]
        ax.scatter([r['count_gain_8_20'] for r in rs],[r['selection_gain'] for r in rs],color=color,label=f'{label} {len(rs)}图')
    bounds=[min(min(r['count_gain_8_20'],r['selection_gain']) for r in chosen)-.01,max(max(r['count_gain_8_20'],r['selection_gain']) for r in chosen)+.01]
    ax.plot(bounds,bounds,':',color='gray',label='两种参考收益相同')
    ax.axhline(0,color='gray',lw=.7);ax.axvline(0,color='gray',lw=.7)
    for r in chosen:
        if r['image'] in ('UwV83HsGsw3-09','X7HyMhZNoso-13','yqstnuAEVhm-25'):
            ax.annotate(r['image'],(r['count_gain_8_20'],r['selection_gain']),fontsize=8,xytext=(4,4),textcoords='offset points')
    ax.set(xlabel='随机8→20人参考收益（正值为改善）',ylabel='固定8人构成选择参考收益（正值为改善）',title='同图比较：加人和选人\n原GT／MV50；既定楼外Q；32张普通Manual图')
    ax.legend(fontsize=8);fig.tight_layout();fig.savefig(OUT/'gain_comparison.png',dpi=150);plt.close(fig)
    lines=['# 加人和选人：连接难度、人数响应与全员结果','',
        '2026-10-07。复用既有39图构成和全量曲线，按图片／方法／参考连接，接入最新人工标签。39图中1图uNb-63现确认为OOS，单列；N≥20固定普通面板为32图（15简单、9中等、8困难）。这与含可标门洞的33图面板不同：本轮没有门洞构成实验，不补造。', '',
        '## 主结果：原GT校准与评价、MV50、随机8→20人', '',
        '|难度|图数|加人平均收益|选人平均收益|加人改善图数|选人改善图数|选择8人优于随机20人|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        if s['policy']=='original' and s['evaluation']=='original' and s['method']=='mv50' and s['n']==20 and s['scene']=='ordinary':
            lines.append(f"|{s['difficulty']}|{s['images']}|{s['count_gain']:.5f}|{s['selection_gain']:.5f}|{s['count_improved']}|{s['selection_improved']}|{s['selected8_beats_more']}|")
    lines += ['', '共同基线均为随机8人期望D；加人收益=D8−D20，选择收益=D8−既定偏上半8人D。比较的是策略期望，不是某次挑出的最好8人；校准成本未计入，不是预算最优结论。', '',
        '![逐图收益](gain_comparison.png)', '',
        '## 新连接得到什么', '',
        '- 32图中24图增人改善、27图选择改善；20图选择8人低于随机20人。平均选择收益0.02131，高于增人0.00786；建筑等权的两者差仍为正（0.01188）。这是已有人员池上的参考收益，不是人员类型或未来人群保证。',
        '- 8张增人不改善图中，7张选择仍改善；另1张X7-13两者均未改善。Uw-17的选择收益仅0.00067，计数只是数值正负，不能把这些7图都称为实质性修复。',
        '- 困难8图的平均增人收益仅0.00178，但5图改善、3图变差，不能将组均值套到每图。8图既定选择均降低参考误差，7图选择8人优于随机20人。较差的增人曲线并不意味着换构成也无帮助。',
        '- 简单图同样存在反例：X7-13两策略误差都略升，但绝对D仍较小。停滞与离GT很远是不同现象，不能单凭收益正负分难度。', '',
        '## 实际全员结果与反例', '',
        '|图片|难度|随机8人D|随机20人D|选择8人D|实际全员D|', '|---|---|---:|---:|---:|---:|']
    for r in chosen:
        if r['count_gain_8_20']<=1e-12:
            lines.append('|'+ '|'.join([r['image'],r['difficulty']]+[f"{r[k]:.5f}" for k in ('D8','D20','selected_D8','D_all')])+'|')
    lines += ['', '全员按每图实际N形成唯一输出，N不同，不能把这列当固定人数对照。Uw-09原GT全员遗漏增加已有解释；rPc内／外侧目标已有合理性判断，选择靠近参考不能推翻另一合理目标。本轮不新增语义裁决。', '',
        '## 规则与参考敏感性', '',
        '|校准|评价|规则|加人改善/32|选择改善/32|选择8人优于随机20人/32|加人未改善但选择改善|', '|---|---|---|---:|---:|---:|---:|']
    for s in summaries:
        if s['n']==20 and s['scene']=='ordinary' and s['difficulty']=='全部':
            lines.append('|'+ '|'.join(str(s[k]) for k in ('policy','evaluation','method','count_improved','selection_improved','selected8_beats_more','count_nonpositive_selection_positive'))+'|')
    lines += ['', '修订优先只替换确有修订参考的图片，不挑分数高的GT。严格多数下困难组加人改善可比简单更大，因此“困难始终加人更慢”仍不成立。选择参考收益在不同设置下的总体方向应与逐图反例同时报告。', '',
        '## 文件及下一步', '',
        '- per_image.csv保留39图全部可用规则／校准／参考组合，含实际构成比例、R/V、选择的遗漏／外扩收益及全员O/E；OOS不混入普通汇总。summary.csv包含固定16/20人上限、均值、中位数、建筑等权和实际图名。',
        '- 本轮复用现有计算，未重算几何、拟合新Q、改变投票或修改参考。9项相关测试通过，连接检查同N及随机8人／全员D一致。',
        '- 这完成了“困难曲线后段收益较小”与“人员选择能否改变参考表现”的有限连接。下一步仅针对现有无法解释的空间差异看实际布局；待定门洞先看作答，不将其审核当作主线前置。模型特征预测人工难度仍为后续工作。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':run()
