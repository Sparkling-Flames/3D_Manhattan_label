"""八图并集减法实验：前缀独立拟合，多分支保留；GT只进入评价器。"""
from __future__ import annotations

from collections import Counter
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from shapely.geometry import Polygon, mapping

from tools.thesis_main.analysis.run_structural_consensus_20260926 import save

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/union_branch_consensus_20260926'
SEED = 20260926


def worker_orders(workers, repeats=25, seed=SEED):
    workers = sorted(workers)
    if len(workers) != len(set(workers)):
        raise ValueError('duplicate_worker')
    rng = np.random.default_rng(seed)
    return [rng.permutation(workers).tolist() for _ in range(repeats)]


def polygon(floor):
    if floor is None:
        return None
    p = Polygon(floor)
    return p if p.is_valid and not p.is_empty and p.area > 0 else None


def iou(a, b):
    return float(a.intersection(b).area / a.union(b).area)


def distribution_parts(branches, denominator):
    if denominator <= 0 or sum(b['support'] for b in branches) > denominator:
        raise ValueError('invalid_support_denominator')
    parts = [(polygon(b['floor']), b['support'] / denominator) for b in branches]
    missing = denominator - sum(b['support'] for b in branches)
    if missing:
        parts.append((None, missing / denominator))
    return parts


def distribution_distance(first, n_first, second, n_second):
    """空间分布 OT 的不可计算代价包络，不将无效布局合成零距离桶。"""
    a, b = distribution_parts(first, n_first), distribution_parts(second, n_second)
    lower, upper = np.zeros((len(a), len(b))), np.ones((len(a), len(b)))
    for i, (pa, _) in enumerate(a):
        for j, (pb, _) in enumerate(b):
            if pa is not None and pb is not None:
                lower[i, j] = upper[i, j] = np.clip(1 - iou(pa, pb), 0, 1)
    rows = np.kron(np.eye(len(a)), np.ones((1, len(b))))
    cols = np.tile(np.eye(len(b)), (1, len(a)))
    mass = [w for _, w in a] + [w for _, w in b]
    constraints = np.vstack([rows, cols])
    values = []
    for cost in (lower, upper):
        result = linprog(cost.ravel(), A_eq=constraints, b_eq=mass, bounds=(0, None), method='highs')
        if not result.success:
            raise RuntimeError('transport_solver_failed:' + result.message)
        values.append(float(np.clip(result.fun, 0, 1)))
    return dict(lower=values[0], upper=values[1],
                first_unknown_mass=sum(w for p, w in a if p is None),
                second_unknown_mass=sum(w for p, w in b if p is None))


def reference_summary(branches, denominator, reference):
    ref = polygon(reference)
    scores = [iou(p, ref) if (p := polygon(b['floor'])) is not None and ref is not None else None
              for b in branches]
    known_count = sum(b['support'] for b, s in zip(branches, scores) if s is not None)
    unknown = (denominator - known_count) / denominator
    lower = sum(b['support'] / denominator * s for b, s in zip(branches, scores) if s is not None)
    main = scores[0] if scores else None  # 核心按人数排序；同票的规范次序不看GT。
    top = [s for b, s in zip(branches, scores) if b['support'] == branches[0]['support']]
    computable_top = [s for s in top if s is not None]
    return dict(weighted_iou_lower=lower, weighted_iou_upper=min(1., lower + unknown),
                unknown_mass=unknown, dominant_iou=main, dominant_tie_count=len(top),
                tied_dominant_iou_range=[min(computable_top), max(computable_top)] if computable_top else None,
                tied_dominant_unknown_count=len(top)-len(computable_top),
                tied_dominant_bounds=[0., 1.] if len(top) != len(computable_top) else
                    [min(computable_top), max(computable_top)] if computable_top else None)


def reference_floors(record):
    from tools.thesis_main.analysis.layout_real_case_probe_20260926 import floor_points
    result = {}
    for ref in record['references']:
        coords = None
        reason = ref.get('reason')
        if ref['pairs'] is not None:
            try:
                coords = floor_points(np.asarray(ref['pairs'], float)).tolist()
            except ValueError as exc:
                reason = str(exc)
        result[ref['name']] = dict(floor=coords, source=ref.get('source'),
                                   status=ref['status'], reason=reason)
    return result


def branch_aggregation(branch, records, refs):
    """簇内区域切片为独立基线；保留孔洞/多分量，不强折成单个3D房间。"""
    from tools.thesis_main.analysis.layout_consensus_probe_20260926 import bev_aggregate
    members = [r for r in records if r['worker'] in branch['support_workers']]
    polys = [polygon(r['floor']) for r in members]
    output = dict(member_count=len(members), invalid_members=sum(p is None for p in polys),
                  median_reference={name: reference_summary([branch], branch['support'], ref['floor'])
                                    for name, ref in refs.items()},
                  corner_medoid_reference={name: reference_summary(
                      [dict(floor=branch['representative_floor'], support=branch['support'])], branch['support'], ref['floor'])
                      for name, ref in refs.items()})
    if any(p is None for p in polys):
        output['tile_status'] = 'unavailable_invalid_member_polygon_no_subset_renormalization'
        return output
    output['tile_status'] = 'all_members_computable'
    output['methods'] = {}
    for method in ('medoid', 'mv50', 'mv_strict'):
        result = bev_aggregate(polys, method)
        parts = [result] if result.geom_type == 'Polygon' else list(result.geoms)
        output['methods'][method] = dict(geometry=mapping(result), area=float(result.area),
            geometry_type=result.geom_type, components=sum(p.geom_type == 'Polygon' for p in parts),
            holes=sum(len(p.interiors) for p in parts if p.geom_type == 'Polygon'),
            reference_iou={name: iou(result, rp) if (rp := polygon(ref['floor'])) is not None else None
                           for name, ref in refs.items()},
            height_status='not_reconstructed_for_tile_boundary')
        if method == 'medoid':
            output['methods'][method]['source_id'] = members[next(i for i, p in enumerate(polys)
                                                                 if p.equals(result))]['id']
    return output


def curve_row(fitted, denominator, refs):
    branches = fitted['branches']
    supports = [b['support'] / denominator for b in branches]
    computable = sum(b['support'] for b in branches)
    geometry_bad = sum(b['support'] for b in branches
                       if b['geometry_status'] == 'invalid_3d_candidate' or not b['geometry']['camera_inside'])
    return dict(n=denominator, n_computable=computable, mode_count=len(branches),
        top_support=(supports + [0, 0, 0])[:3],
        singleton_mass=sum(b['support'] for b in branches if b['support'] == 1) / denominator,
        missing_mass=(denominator - computable) / denominator,
        geometry_unusable_mass=geometry_bad / denominator,
        reference={name: reference_summary(branches, denominator, ref['floor']) for name, ref in refs.items()})


def evaluate_image(image, reference_record, repeats=25):
    from tools.thesis_main.analysis.union_branch_consensus_20260926 import fit_union_branches
    inventory = [r for r in image['annotations'] if r['raw_condition'] in {'manual', 'oos'}]
    indexed = {r['worker_id']: r for r in inventory}
    if len(indexed) != len(inventory):
        raise ValueError('duplicate_worker_within_image:' + image['code'])
    records = [r['core_record'] for r in inventory if r['core_record'] is not None]
    full = {str(tol): fit_union_branches(records, point_tol_deg=tol) for tol in (2.5, 5., 10.)}
    # 拟合接口不接受 GT；下列参考只用于评价。
    refs = reference_floors(reference_record)
    for fitted in full.values():
        for branch in fitted['branches']:
            branch['reference_evaluation'] = {name: reference_summary([branch], branch['support'], ref['floor'])
                                              for name, ref in refs.items()}
            shared = branch['shared_feature_candidate']
            shared['reference_evaluation'] = {name: reference_summary(
                [dict(floor=shared['floor'], support=branch['support'])], branch['support'], ref['floor'])
                for name, ref in refs.items()}
    for branch in full['5.0']['branches']:
        branch['aggregation_comparison'] = branch_aggregation(branch, records, refs)
    cache = {tuple(sorted(indexed)): full['5.0']}

    def fit_subset(workers):
        key = tuple(sorted(workers))
        if key not in cache:
            subset = [indexed[w]['core_record'] for w in key if indexed[w]['core_record'] is not None]
            fitted = fit_union_branches(subset, point_tol_deg=5.)
            # ponytail: 仅缓存本图子样本分支；更大面板再考虑有界缓存。
            cache[key] = dict(branches=fitted['branches'])
        return cache[key]

    orders = worker_orders(indexed, repeats=repeats)
    curves, stability = [], []
    max_half = len(indexed) // 2
    disjoint_sizes = sorted({n for n in [2, 4, 6, 8, 10, 12, max_half] if 1 <= n <= max_half})
    for repeat, order in enumerate(orders):
        for n in range(1, len(order) + 1):
            fitted = fit_subset(order[:n])
            curves.append(dict(repeat=repeat, workers=order[:n], **curve_row(fitted, n, refs)))
        for n in disjoint_sizes:
            first, second = order[:n], order[-n:]
            if set(first) & set(second):
                raise AssertionError('disjoint_worker_split_failed')
            a, b = fit_subset(first), fit_subset(second)
            stability.append(dict(repeat=repeat, n=n, first_workers=first, second_workers=second,
                **distribution_distance(a['branches'], n, b['branches'], n)))
    revisions = [r['revised_core_record'] for r in inventory if r.get('revised_core_record') is not None]
    # 借点结果仅全样本敏感性展示；不当作与 donor 独立的重放票。
    borrowed = None
    if revisions:
        borrowed = fit_union_branches(records + revisions, point_tol_deg=5.)
    return dict(code=image['code'], image_id=image['image_id'], strata=image['strata'],
        n_input=len(inventory), n_computable=len(records),
        conditions=dict(Counter(r['raw_condition'] for r in inventory)),
        unavailable=[dict(worker=r['worker_id'], id=r['canonical_annotation_id'], reason=r.get('reason'))
                     for r in inventory if r['core_record'] is None],
        excluded_inventory_count=len(image['previously_excluded_inventory']),
        semi_inventory=[r['canonical_annotation_id'] for r in image['annotations'] if r['raw_condition'] == 'semi'],
        references=refs, fits=full, curves=curves, disjoint_stability=stability,
        orders=orders, borrowed_full_sample_sensitivity=borrowed,
        fitted_subsets=len(cache), full_summary=curve_row(full['5.0'], len(inventory), refs))


def write_report(out=OUT):
    out = Path(out)
    result = json.loads((out / 'results.json').read_text(encoding='utf8'))
    cases = []
    for filename in result['case_files']:
        with gzip.open(out / filename, 'rt', encoding='utf8') as stream:
            cases.append(json.load(stream))
    rows, comparison, stability_rows = [], [], []
    gains = {method: [] for method in ('median_vs_corner_medoid', 'shared_vs_median', 'mv50_vs_area_medoid')}
    for case in cases:
        fits = case['fits']
        default = fits['5.0']['branches']
        rows.append(f"| {case['code']} | {case['n_input']}/{case['n_computable']} | "
                    + '/'.join(str(len(fits[t]['branches'])) for t in ('2.5', '5.0', '10.0'))
                    + f" | {default[0]['support']}/{case['n_input']} | "
                    + f"{fits['10.0']['branches'][0]['support']}/{case['n_input']} |")
        ss = case['disjoint_stability']
        n = max(r['n'] for r in ss)
        ss = [r for r in ss if r['n'] == n]
        stability_rows.append(f"| {case['code']} | {n} | "
                              f"{np.mean([r['lower'] for r in ss]):.3f}–{np.mean([r['upper'] for r in ss]):.3f} |")
        for b in default:
            if b['support'] < 2:
                continue
            ac = b['aggregation_comparison']
            median = b['reference_evaluation']['gt_original']['dominant_iou']
            medoid = ac['corner_medoid_reference']['gt_original']['dominant_iou']
            shared = b['shared_feature_candidate']['reference_evaluation']['gt_original']['dominant_iou']
            if median is not None and medoid is not None:
                gains['median_vs_corner_medoid'].append(median-medoid)
            if shared is not None and median is not None:
                gains['shared_vs_median'].append(shared-median)
            if 'methods' in ac:
                gains['mv50_vs_area_medoid'].append(ac['methods']['mv50']['reference_iou']['gt_original'] -
                                                   ac['methods']['medoid']['reference_iou']['gt_original'])
    for name, values in gains.items():
        labels = dict(median_vs_corner_medoid='簇内中位数 − 角点代表标注',
                      shared_vs_median='共享身份中位数 − 簇内中位数',
                      mv50_vs_area_medoid='≥50%区域投票 − 区域代表标注')
        comparison.append(f"| {labels[name]} | {len(values)} | {sum(v > 1e-8 for v in values)} / "
                          f"{sum(v < -1e-8 for v in values)} / {sum(abs(v) <= 1e-8 for v in values)} | "
                          f"{np.mean(values):+.4f} |")
    content = r'''# 并集减法、多分支共识与人数曲线：八图初步实验

本轮按用户澄清后的想法重做独立原型。**集合减法过程已验证；真实八图尚未证明能自动获得几种可靠、合理的共识。当前最明显的问题是跨人角点身份匹配和结构分组碎片化。**这不等于否定“人数优先、多分支保留”的思路。

[逐图并集、删点、3D与曲线](index.html) · [人数曲线](curves.png) · [不相交人员组的空间稳定性](disjoint_stability.png) · [机器结果](results.json) · [ABC符号例](symbolic_example.json)

**用户的想法如何落地。** 并集 U 是点身份集合，不把所有点强行连成一个房间。A=123456、B=123478、C=12345，各有10/8/2人：分别从U删78、56、678；C也可以从A再删6。原话第二次“删78”按得到B的含义解释为“删56”。三条分支都保留，票数严格为10/8/2。C是A的删点后代不意味着继承A的10票。符号例的虚构坐标仅检验集合、邻接和计票，不证明对应房间合理。

每个真实角点由上下端点组成，先沿用既有循环配对和共享x，再比较上下端点球面角距的最大值。完全连接匹配使用2.5°/5°/10°三个未校准阈值，默认5°只作探索；同一人的两个角点禁止合成一个身份。周期接缝自然由球面射线处理。分支要求保留身份及循环邻接相同，循环起点和反向等价，不交换连接关系。

**这里有一项很重要的实现限制：**真实图中当前自动分支是“身份＋邻接完全相同”的分组，不是直接采用用户已经认可的语义/空间簇。真实的同一标法可能被点匹配误差拆开。分支数不能解释成合理标法数；新人员加入也可能改变旧点的完全连接分组，因此主支持率下降包含表示变化，不能全部解释成图片困难或人员分歧。

本轮生成观测到的分支及其删点父子关系，没有穷举全部2^|U|子集或搜索新连接。它忠实检验了ABC过程，但尚不是经过验证的全局最优共识算法。

**删点确定结构；聚合坐标才可能改善单人结果。** 对每条分支比较以下方法，全部不看GT构造：

- 簇内同身份坐标中位数：主结果，完整环的支持人数来自该簇。
- 共享身份坐标中位数：跨簇汇集同一保留身份的所有观测，保持本分支连接。共享1/2/3/4可各有20票，但A整环仍只有10票。匹配若把不同物理墙角混淆，此方法也可能变差。
- 簇内代表标注：按对齐角点距离选medoid；另有按区域互相IoU选出的区域medoid。两者都不使用GT选人。
- 区域切片MV：叠加同簇地面多边形，切成精确tiles，分别保留支持比例≥1/2、>1/2的区域。两人时前者包括平票区域、后者只保留两人共同支持区域。保留多分量、孔洞，不硬拼成一个3D闭室；有成员多边形非法则该分支的tile对照不可用，不悄悄改成有效子集投票。

Lee论文聚合的是区域tiles，默认结合聚类后选最大簇；“保留多个拓扑分支、共享角点”是本研究扩展。当前MV仅为BEV区域投票基线，不是Lee整套EM/greedy方法复现。[Lee等原文](https://ceur-ws.org/Vol-2173/paper10.pdf)

**人数强度与几何状态分开。** 输出(人数m、比例m/n、几何诊断)，人数优先排序。自交、退化边、相机位置、墙方向残差和高度诊断都保留；不能因为2人画得方正，就让其群众支持超过10人的分支。多数共同画错仍然是描述性人群共识，几何异常则标记为不适合直接作为空间结果。少数且几何较好的分支建议称“少数支持、几何未触发告警”，不要把它混称为与多数相当的支持强度。

5°方向残差仅为本次告警线，没有校准成正确率。短边连续降低方向诊断权重，不删细节；高度有单独MAD，不拿层高去压过墙角信息。相机在选定区域外可能来自门洞/OOS范围选择，属于闭室模型适用性提醒，不能据此宣布标注错误。几何没有触发告警也不证明正确：本批q9v04唯一无告警分支残差4.686°，对原GT IoU约0.0156；另一个残差9.102°的分支IoU约0.8657。这只说明几何与参考范围是不同维度，不证明GT一定正确。

**输入和人数分母。** 八图由用户指定并确认默认角点顺序；没有开展全量排序或自动修序。160份现有accepted标注全部复读原件，153份可以独立构造几何。6份无可用配对；uNb59的W031补点借自W033，主分析不作独立几何票，保留全样本描述性敏感性。11份历史excluded仅列清单，不重新裁决。本批没有Semi。

人数曲线n包含进入前缀的所有accepted人员；缺失几何是未知质量，不是反对票或弱共识。页面同时列m/n和m/n_computable。原GT8份可按来源配对，修订GT7份可配对；q9v04修订GT未定义配对，标为NA。GT仅作指定参考解释的评价，不参与匹配、删点、排名或参数选择。所有3D均以相机离地高度=1重建，不是米制实测。

| 图片 | 输入/独立可计算 | 分支数2.5°/5°/10° | 5°最大支持/全部输入 | 10°最大支持/全部输入 |
|---|---:|---:|---:|---:|
__TABLE__

默认5°共130个精确分支，各图最大仅1–4人。这首先暴露身份识别/分支定义的局限，不能包装成已经找到130个合理共识，也不能仅因此宣布这些图无法形成共识。uNb52分支数从23降到18再到8，最大支持也随阈值改变，说明参数影响很大；不得选“最接近GT”的阈值当成功结果。

**聚合是否已经胜过代表标注？** 下表只比较默认分支中至少2人支持的分支，对原GT的一致性变化。正数为更贴该参考，负数为更远；单人分支不凑作改进证据。各分支并非独立实验单位，这只是描述性对照，不作显著性检验。

| 对照 | 可比较分支 | 提高/降低/不变 | IoU差均值 |
|---|---:|---:|---:|
__COMPARISON__

这张表不能证明共享点或MV一定改善真实质量：GT可能只代表其中一种范围。若要主张“优于最佳单人”，还需独立参考和预先固定评价；不能用GT挑一个最有利的输出，再叫无监督共识。

**多共识曲线如何画。** 不把几个不同房间的坐标平均成一个房间。保留离散分布：P_n = Σ_k (m_kn/n) δ_(C_kn)，不可计算质量单列。输出几组各有明确含义的曲线：

1. 支持率：按人数排列的前三分支比例、单人分支比例、分支数量。排名是角色，不代表跨n始终是同一个语义分支。要持续跟踪具体语义模式，需要另行明确模式匹配、出生/拆分/合并记录，不能靠branch_id相同硬连。
2. 几何：各分支方向/高度诊断及闭室模型检查未通过的支持比例，与支持率并排，不相乘压成无含义总分。
3. GT一致性：并列最大支持分支的IoU范围，以及Σ_k (m_kn/n) IoU(C_kn,GT)。后者是随机抽到的人所支持分支与该GT的一致性期望，不是多数分支准确率；合理替代空间也可能拉低它。不可计算质量u时显示[已知加权和, 已知加权和+u]。
4. 空间分布稳定性：取两组不相交的n人，各自独立形成全部分支，再比较这两个带支持权重的布局分布。即使多种标法持续存在，分布也可能稳定，不能把“不是唯一共识”等同于“不稳定”。

每图25个固定无放回排列，每个前缀重新建点并集和分支；没有用全样本点池/簇回灌早期拟合。曲线范围是当前有限人员池的进入顺序/子样本差异，不是总体置信区间。n达到总人数时所有排列相同是设计必然，不证明已收敛。本批没有用户确认的简单图对照，不能由这八图验证“简单更快、困难更慢”的组间结论。

q9v04默认9个分支都是1人支持：原GT同票范围0.0156–0.8657。规范排序第一个恰为0.7425，但不存在人数明确支持的唯一主分支。因此图中保留并列范围，不能选最贴GT的一个冒充主共识。

**不相交人员组的空间距离。** 两个可计算布局之间代价为1−BEV IoU，通过最优运输匹配各分支的支持质量；这不是角点拓扑距离。凡任一布局不可计算，该代价未知，以0、1分别求最小运输，得到严格上下界。两组全不可计算时为[0,1]，不会伪称稳定。下面是最大可用n下25对划分的上下界均值；区间不是置信区间，各图n也不同，不据此直接排名图片难度。

| 图片 | 每组人数，两组不相交 | 空间分布距离下界–上界均值，低表示更接近 |
|---|---:|---:|
__STABILITY__

OOS的uNb52对当前原GT支持加权IoU为[0.8408,0.8824]；两组各2到12人的空间距离均值从[0.1155,0.1755]变为[0.0696,0.1530]。这是“点结构表示碎片多、空间范围仍相对一致”的实例。它不能支持“OOS一定不贴GT/一定无法稳定”。反过来，即使所有人画同一个错误矩形，支持100%、残差0且分布稳定，仍然可能是共同错误。

**分簇、共识和人员质量研究的对象不同。** 分簇分开当前图的相似解释；共识综合每种解释并记录支持分布；人员质量研究同一个人在多图上的系统偏差、定位精度和失误。用单GT的IoU或质心分差直接回归人员质量，会把合理范围选择混进去。几何残差只是约束自洽性，也不能单独替代质量。若想分离图片和人员因素，需要跨图重复、人员交叉覆盖、保留模式选择与模式内定位两个层次，再用独立证据校验，当前八图实验未完成这种归因。

小规模human-in-the-loop适合审查定义不清的范围、点身份和极端候选，而不是让人随意为算法输出打分。若采用，应预先写清范围规则、独立盲评、保留多种可接受解释和分歧，再把固定规则应用于其余数据。客观性来自可复核定义和独立验证，不能靠完全不让人参与自动获得。

**下一步应解决的具体问题。** 固定一批独立核验的“同一物理角点”对应和空间簇，比较当前身份构造的拆分/误合情况，再决定宽容的分支兼容规则。只做局部对应确认，不开展用户暂缓的全量重排序。此后用建筑外数据校准容差与轻度几何筛查，并以分布稳定、少数模式保留和独立参考一致性分别验证；不要为画出预期曲线调参。

**复算、字段与边界。** 当前方法合同仍为consensus_research_20260923_v1。本轮探索不改真源标注、GT、既有裁决或人员资格，不替换旧40图结果。

```powershell
D:/anaconda/python.exe -m tools.thesis_main.analysis.run_union_branch_consensus_20260926
D:/anaconda/python.exe -m pytest tests/test_union_branch_consensus_20260926.py tests/test_union_branch_panel_20260926.py tests/test_run_union_branch_consensus_20260926.py -q -p no:cacheprovider
```

输入面板包含来源核对与不可计算原因；各cases/*.json.gz包含三容差的features/branches/assignments、支持者、保留/删除身份、父删除关系、几何与聚合对照、25次完整人员顺序、prefix指标及不相交划分。参考只在reference相关字段。results.json列出文件清单、参数与分母定义。所有数值JSON禁用NaN/Infinity。shared_feature_candidate是敏感性候选，不回写主分支坐标；MV50/mv_strict不带重建墙高。geometry_unusable_mass是本次闭室模型检查标记，非通用标注错误率。

新增四个分析模块与三项测试文件，README索引及项目地图只作探索入口登记。验证记录见VALIDATION.json。未运行训练、Label Studio运营或全仓测试，因为未修改相应路径；未新增部署或采集操作。静态图为交付研究图，不是临时检查截图。
'''
    content = content.replace('__TABLE__', '\n'.join(rows)).replace('__COMPARISON__', '\n'.join(comparison))
    content = content.replace('__STABILITY__', '\n'.join(stability_rows))
    (out / 'README.md').write_text(content, encoding='utf8')
    return dict(aggregation_gains=gains)


def run(repeats=25):
    from tools.thesis_main.analysis.union_branch_panel_20260926 import run as build_panel
    panel = build_panel(OUT)
    refs = {r['image_id']: r for r in panel['references_for_evaluation_only']}
    summaries, case_files = [], []
    for image in panel['images']:
        result = evaluate_image(image, refs[image['image_id']], repeats)
        path = OUT / 'cases' / (image['code'] + '.json.gz')
        save(path, result)
        case_files.append(str(path.relative_to(OUT)).replace('\\', '/'))
        row = dict(code=result['code'], strata=result['strata'], **result['full_summary'],
            mode_counts={tol: len(fit['branches']) for tol, fit in result['fits'].items()},
            top_counts=[b['support'] for b in result['fits']['5.0']['branches']],
            union_count=len(result['fits']['5.0']['features']),
            unavailable=result['unavailable'], fitted_subsets=result['fitted_subsets'])
        summaries.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = dict(schema='union_branch_experiment_20260926_v1', seed=SEED, repeats=repeats,
        case_files=case_files, images=summaries,
        construction='current prefix only; independent feature union; observed ring branches; within-branch median',
        evaluation='GT only evaluation; median/medoid/tile baselines; spatial OT bounds for disjoint groups',
        support_denominator='all accepted manual/oos inventory in prefix; missing geometry mass retained',
        tolerance_deg=[2.5, 5., 10.], default_tolerance_deg=5., calibrated=False,
        status='exploratory_user_named_eight_images_not_formal_adjudication')
    save(OUT / 'results.json', summary)
    write_report(OUT)
    from tools.thesis_main.analysis.union_branch_presentation_20260926 import build
    build(OUT)
    return summary


if __name__ == '__main__':
    run()
