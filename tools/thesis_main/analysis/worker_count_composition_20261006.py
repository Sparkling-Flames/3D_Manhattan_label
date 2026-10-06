"""高人数固定池：复用Lee细分及有限池概率，计算人数、构成与区域变化。"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import warnings

import numpy as np

from research.worker_subtype_returns_20261004.pro.src.finite_pool import (
    marginal, coupled, next_member_loss,
)
from .lee_tile_precision_20261003 import integration_basis, subset_mask
from .lee_tile_stage1_20261002 import METHODS
from .research_artifact_io import ROOT, INVENTORY, read_csv, write_csv, write_json
from .research_round_20260929 import prepare_record, reconstruct
from .worker_count_metrics_20261006 import (
    FIELDS, area_summary, fit_labels, feasible_compositions, summarize,
)

OUT = ROOT / 'analysis_results/worker_count_composition_20261006'
PROFILES = ROOT / 'analysis_results/worker_profiles_20261003'


def probabilities(patterns, masks, sizes, draws, method):
    return np.array([marginal(sizes, tuple((int(p) & m).bit_count() for m in masks),
                              draws, method) for p in patterns])


def collect():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle = load_current_bundle()
    panel, mapping = project_bundle(bundle)
    objects = {mapping['records'][r['object_id']]: r for r in bundle['data']['objects']}
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    context = {r['image']: r for r in inventory['images']}
    groups, coverage, notices = [], [], []

    def prepare(r):
        p = prepare_record(dict(r, source_pair_indices=objects[r['id']]['ordered_source_pair_indices']))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            g = reconstruct(p)
        notices.extend(dict(record=r['id'], message=str(w.message)) for w in caught)
        state = g['representations']['declared_footprint']
        p.update(footprint=g['floor'].tolist() if state['status']=='ok' else None,
                 footprint_state=state)
        return p

    for im in panel['images']:
        for condition in ('manual', 'semi'):
            parts = defaultdict(list)
            for r in im['annotations']:
                if r['condition']==condition and r['independent'] and r['consensus_eligible']:
                    parts[r['main_consensus_gate']['status']].append(r)
            for gate, rs in parts.items():
                if len(rs) < 16:
                    continue
                row = dict(image=im['code'], building=im['building'], condition=condition,
                           gate=gate, n=len(rs), workers='|'.join(sorted(r['worker'] for r in rs)),
                           status='outside_main_quality', reason='existing_quality_gate')
                for field in ('difficulty', 'd_model_feat_static', 'bilayout_legacy_band',
                              'scope_explicit_tag', 'detail_explicit_tag'):
                    row[field] = context[im['code']][field]
                if gate=='main_candidate' and all(r['quality_candidate'] for r in rs):
                    records = [prepare(r) for r in sorted(rs, key=lambda r: r['worker'])]
                    refs = [prepare(r) for r in im['references']]
                    failed = [r['id'] for r in records if r['footprint'] is None]
                    original = next((r for r in refs if r['version']=='original'), None)
                    row.update(status='selected', reason='')
                    if failed:
                        row.update(status='whole_pool_unavailable', reason='|'.join(failed))
                    elif original is None or original['footprint'] is None:
                        row.update(status='reference_unavailable', reason='original')
                    groups.append(dict(image=im['code'], building=im['building'], condition=condition,
                                       status=row['status'], records=records, references=refs))
                coverage.append(row)
    return dict(schema='worker_count_composition_input_v1',
                source_manifest='analysis_results/research_input_20260929/manifest.json',
                groups=groups, coverage=coverage, warnings=notices)


def image_effects(rows, coverage, out):
    """逐图效应与既有图片描述并列，不拟合新的难度或人员分数。"""
    indexed = {(r['image'],r['condition'],r['method'],r['scenario'],r['policy'],r['strategy'],r['k']):r
               for r in rows if r['version']=='original'}
    effects = []
    for m in coverage:
        if m['status']!='selected':
            continue
        for method in METHODS:
            def value(scenario, policy, strategy, k):
                r=indexed.get((m['image'],m['condition'],method,scenario,policy,strategy,k))
                return r['ref_symdiff_ref'] if r else None
            row=dict(m, method=method)
            at8=value('uniform','none','random',8)
            row['random8_error_ref']=at8
            for k in (16,20):
                end=value('uniform','none','random',k)
                row[f'random{k}_minus8_error_ref']=end-at8 if end is not None else None
            lo=value('composition','original','lower_rich',8)
            hi=value('composition','original','higher_rich',8)
            row['higher8_minus_lower8_error_ref']=hi-lo if hi is not None else None
            end=value('uniform','none','random',20)
            row['higher8_minus_random20_error_ref']=hi-end if hi is not None and end is not None else None
            effects.append(row)
    write_csv(out/'image_effects.csv',effects)


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    write_json(out/'design.json', dict(schema='worker_count_composition_v1',
        contract='consensus_research_20260923_v1', min_n=16,
        uniform='每图1到N；有限池中均匀无放回抽k人；Manual与Semi分开',
        composition='Manual：每个偶数k及全池N；可行最低/约半/最高上半组人数；不删除人员补成相同比例',
        calibration='既有24人10图，目标整栋剔除；新建筑用全部10图。原GT与修订优先分别校准。',
        policies=list(METHODS), inference='固定观测池的解析期望，无MC；不估计总体能力、最佳人数或停止规则',
        sampling='同k换组为两次独立抽组，允许成员重叠；增一人为原组加一名未入组成员',
        references='原GT为主，已有修订GT在相同图片上并列；不选更高分参考'))
    data = collect()
    write_json(out/'input.json', data)
    write_csv(out/'coverage.csv', data['coverage'])
    block = json.loads((PROFILES/'block.json').read_text(encoding='utf-8'))
    workers = block['workers'].split('|')
    matrices = {p: read_csv(PROFILES/f'matrix_{p}_iou.csv') for p in ('original','revised_where_available')}
    train_buildings = {r['building'] for r in matrices['original']}
    groups = [g for g in data['groups'] if g['status']=='selected']
    panels = {'common10': (set(block['images']), 24)}
    for condition in ('manual','semi'):
        for limit in (16,20,24):
            panels[f'{condition}_n{limit}'] = ({g['image'] for g in groups if g['condition']==condition and len(g['records'])>=limit}, limit)
    panels['manual_external_n16'] = ({g['image'] for g in groups if g['condition']=='manual' and g['building'] not in train_buildings},16)
    # Images may have both conditions: use condition-specific rows when summarizing below.
    rows, assignments, notices = [], [], list(data['warnings'])
    bases = {}
    for ix, g in enumerate(groups):
        rs = g['records']; n = len(rs)
        refs = {r['version']:r['footprint'] for r in g['references'] if r['footprint'] is not None}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            basis = integration_basis(rs, refs)
        notices.extend(dict(image=g['image'], message=s) for s in basis['warnings']+[str(w.message) for w in caught])
        key = f'g{ix}'
        bases[key+'_patterns'] = basis['patterns']; bases[key+'_area'] = basis['area']
        for v, overlap in basis['overlap'].items():
            bases[key+'_'+v+'_overlap'] = overlap
            bases[key+'_'+v+'_area'] = np.array(basis['references'][v].area)
        ident = dict(image=g['image'], building=g['building'], condition=g['condition'], n=n, basis_key=key)
        full_mask = (1 << n)-1
        support = [int(p).bit_count() for p in basis['patterns']]

        def append(q, method, k, scenario, policy, strategy, higher_n=None, higher_total=None, extra=None):
            for version, ref in basis['references'].items():
                rows.append(dict(ident, scenario=scenario, policy=policy, strategy=strategy,
                    method=method, k=k, version=version, higher_n=higher_n, higher_total=higher_total,
                    higher_fraction=higher_n/k if higher_n is not None else None,
                    **area_summary(basis['area'],basis['overlap'][version],ref.area,q),
                    **(extra or {})))

        for method in METHODS:
            for k in range(1,n+1):
                q = probabilities(basis['patterns'],(full_mask,),(n,),(k,),method)
                extra = dict(add_one_symdiff_union=None, next_person_loss_union=None)
                if k < n:
                    flips = np.array([coupled((n,),(s,),(k,),method,'add',(1,))[0] for s in support])
                    unseen = np.array([next_member_loss((n,),(s,),(k,),method,0) for s in support])
                    extra.update(add_one_symdiff_union=float(basis['area'] @ flips / basis['area'].sum()),
                                 next_person_loss_union=float(basis['area'] @ unseen / basis['area'].sum()))
                append(q,method,k,'uniform','none','random',extra=extra)
        if g['condition']=='manual':
            for policy, matrix in matrices.items():
                labels, train = fit_labels(matrix,workers,g['building'])
                h_mask = subset_mask(j for j,r in enumerate(rs) if labels[r['worker']])
                nh = h_mask.bit_count(); nl = n-nh
                assignments.extend(dict(image=g['image'],building=g['building'],worker=r['worker'],
                    record=r['id'],policy=policy,higher=labels[r['worker']],train_images='|'.join(train),
                    training_scope='external_building' if g['building'] not in train_buildings else 'leave_building_out') for r in rs)
                for k in sorted(set(range(2,n+1,2)) | {n}):
                    for strategy,h in feasible_compositions(nh,nl,k).items():
                        for method in METHODS:
                            q = probabilities(basis['patterns'],(h_mask,full_mask ^ h_mask),(nh,nl),(h,k-h),method)
                            append(q,method,k,'composition',policy,strategy,h,nh)
        print(f'{ix+1}/{len(groups)} {g["image"]} {g["condition"]} N={n}',flush=True)
    write_csv(out/'per_image.csv',rows)
    write_csv(out/'assignments.csv',assignments)
    np.savez_compressed(out/'integration_bases.npz',**bases)
    write_json(out/'warnings.json',notices)
    summary=[]
    for name,panel in panels.items():
        condition='semi' if name.startswith('semi_') else 'manual'
        summary.extend(summarize([r for r in rows if r['condition']==condition],{name:panel}))
    write_csv(out/'summary.csv',summary)
    image_effects(rows,data['coverage'],out)
    write_json(out/'panels.json',{k:dict(images=sorted(v[0]),max_k=v[1]) for k,v in panels.items()})
    write_json(out/'field_contract.json',dict(schema='worker_count_composition_v1',
        per_image_fields=list(dict.fromkeys(k for r in rows for k in r)),
        ref_symdiff_ref='E[area(F xor G)] / area(G) = omission_ref + extension_ref; can exceed 1; NOT 1-IoU',
        member_symdiff_union='E[area(F_A xor F_B)] / fixed_all_worker_union = 2 sum area*q*(1-q)/union; independent subset draws may overlap',
        squared_bias_union='sum integral (q-g)^2 / union; reference area outside worker union included; error= squared_bias + half member_symdiff',
        add_one_symdiff_union='Uniform k subset plus one uniformly drawn unseen member, with vote threshold updated; null at k=N',
        next_person_loss_union='Current uniform k fusion versus one unseen individual annotation, not a new consensus; null at k=N',
        higher_fraction='Actual h/k; at large k the attainable extremes converge, not evidence types became equivalent',
        full_pool='At k=N, independent regrouping variation is exactly 0 by finite-pool exhaustion; no claim of external stability',
        normalization='h2: camera-height squared; ref denominator fixed reference area, union denominator fixed all-worker union',
        summary='Fixed image set for each panel/max_k. image and building weights both reported; paired reference rows only same available dual-reference images. Add-one/next-person summary is null if any image has exhausted its pool; never silently average fewer images',
        failures='Whole candidate pool unavailable if any candidate geometry is unavailable; no dropping bad members',
        calibration='Target-building GT never used to assign groups. Common10 development block and external buildings reported separately',
        image_effects='Existing difficulty/model/scope/detail descriptions beside paired original-reference error changes; negative means error reduced. No missing difficulty imputation, regression, causal claim or new classification',
        source='Current manifest source, existing confirmed/default ring policy. Historical probability module reused without mutation',
        reuse='No new mean-IoU estimator or population confidence interval'))
    figures(summary,out)
    report(data,summary,panels,out)
    return rows,summary


def figures(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':9})
    fields=[('ref_symdiff_ref','参考面积误差／参考面积'),('member_symdiff_union','同人数换组差异／全员并集'),('add_one_symdiff_union','增加一人后变化／全员并集')]
    fig,axes=plt.subplots(2,3,figsize=(14,8))
    for axs,panel in zip(axes,('manual_n20','semi_n20')):
        for ax,(field,label) in zip(axs,fields):
            for method in METHODS:
                rs=sorted([r for r in summary if r['panel']==panel and r['scenario']=='uniform' and r['version']=='original' and r['method']==method and r['weighting']=='image'],key=lambda r:r['k'])
                ax.plot([r['k'] for r in rs],[r[field] for r in rs],'.-',label=method)
            ax.set(title=f'{panel}：固定{rs[0]["image_n"]}图',xlabel='人数',ylabel=label,xticks=[1,4,8,12,16,20])
            ax.grid(alpha=.2);ax.legend()
    fig.suptitle('固定图片、固定人员池的精确面积期望；Manual与Semi不是随机对照')
    fig.tight_layout();fig.savefig(out/'count_curves.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for axs,method in zip(axes,METHODS):
        for ax,(field,label) in zip(axs,fields[:2]):
            for strategy,title in [('lower_rich','偏下半组'),('balanced','约半构成'),('higher_rich','偏上半组')]:
                rs=sorted([r for r in summary if r['panel']=='common10' and r['scenario']=='composition' and r['policy']=='original' and r['version']=='original' and r['method']==method and r['strategy']==strategy and r['weighting']=='image'],key=lambda r:r['k'])
                ax.plot([r['k'] for r in rs],[r[field] for r in rs],'.-',label=title)
            ax.axvline(12,color='gray',linestyle=':',linewidth=1)
            ax.set(title=method,xlabel='人数（12人后纯组不再可行）',ylabel=label,xticks=[2,4,8,12,16,20,24])
            ax.grid(alpha=.2);ax.legend()
    fig.suptitle('固定24人×10图；超过12人比较可行极端构成，24人三条线必然重合')
    fig.tight_layout();fig.savefig(out/'composition_curves.png',dpi=150);plt.close(fig)


def report(data,summary,panels,out):
    lines=['# 高人数面板：人员构成、参考误差与成员波动','',
           '2026-10-06。本轮实际计算；BEV声明底面、Lee等权投票。沿用当前预处理、环序、人员资格与GT版本，不新增人员分类或总分。','',
           '## 范围','', '| 面板 | 固定图数 | 比较至人数 |','|---|---:|---:|']
    for name,(images,limit) in panels.items():
        lines.append(f'|{name}|{len(images)}|{limit}|')
    failures=[r for r in data['coverage'] if r['status'] not in ('selected','outside_main_quality')]
    lines+=['',f'整池不可用／参考不可用：{failures}。其人员未被删除以换取成功。',
            '', '## 随机抽人：固定图片上的人数变化','',
            '误差为期望对称差面积／参考面积，**不是1−IoU**；换组量为两次独立抽组的区域差异／全员并集。两者量纲分母不同，不直接互比。','',
            '| 面板 | 规则 | k | 图数 | 参考误差 | 换组差异 |','|---|---|---:|---:|---:|---:|']
    for r in summary:
        if r['panel'] in ('manual_n20','semi_n20','common10') and r['scenario']=='uniform' and r['weighting']=='image' and r['version']=='original' and r['k'] in (1,4,8,12,16,20,24):
            lines.append(f'|{r["panel"]}|{r["method"]}|{r["k"]}|{r["image_n"]}|{r["ref_symdiff_ref"]:.6f}|{r["member_symdiff_union"]:.6f}|')
    lines+=['','![人数曲线](count_curves.png)','', '## 构成比较：同图、同人数、同校准政策','',
            '| 面板 | 规则 | k | 构成 | 实际上半比例均值 | 参考误差 | 换组差异 |','|---|---|---:|---|---:|---:|---:|']
    for r in summary:
        if r['panel'] in ('common10','manual_external_n16') and r['scenario']=='composition' and r['policy']=='original' and r['weighting']=='image' and r['version']=='original' and r['k'] in (4,8,12,16,20,24):
            lines.append(f'|{r["panel"]}|{r["method"]}|{r["k"]}|{r["strategy"]}|{r["higher_fraction"]:.3f}|{r["ref_symdiff_ref"]:.6f}|{r["member_symdiff_union"]:.6f}|')
    lines+=['','![构成曲线](composition_curves.png)','', '## 解读范围','',
        '- Common10沿用外建筑校准。新增建筑用共同10图校准；同属校准建筑的新增图仍剔除整栋。Semi只做人数研究，不借Manual分组解释Semi人员类型。',
        '- 12人以上不能维持全上半／全下半；24人换组波动为零是有限池穷尽，不能宣布真实人数停止点。奇偶门槛引起的锯齿由两规则并列展示。',
        '- 同k换组、增加一人后的融合变化、当前融合与下一位人员的差异分别计算。变动小不等于参考正确，也不等于预测新人员准确。',
        '- 原GT／手工修订在相同双参考图片并列；分组原GT／修订优先两政策也分别保留。图片／建筑等权汇总同时输出；没有新增总体显著性或置信区间。',
        '- 新增精确的是面积期望与概率，不是平均IoU。已有136图IoU曲线未重跑；本轮不会用期望交并比冒充平均IoU。',
        '- 只测试新增概率接线、面积计算、目标建筑隔离和大人数可行构成；不重跑108点基线或全库输入审核。','',
        '## 文件','',
        '`design.json`是计算前的设计；`input.json`含当前名单与坐标摘录；`coverage.csv`保留高人数资格／失败；`per_image.csv`、`summary.csv`为逐图与固定面板结果；`assignments.csv`为楼外校准名单；`integration_bases.npz`保存可复用积分基底；`field_contract.json`定义分母与缺失；`warnings.json`保留几何库警告。','',
        '复算：`python -B -m tools.thesis_main.analysis.worker_count_composition_20261006 --out analysis_results/NEW_worker_count`。新输出目录必须不存在。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args()
    run(args.out)
