"""标签盲的模型代理难度分数，与按建筑留出的主观校准分别保存。"""
from itertools import product
from collections import defaultdict, Counter
import json

import numpy as np
from scipy.stats import spearmanr

from .research_artifact_io import ROOT, read_csv, write_csv, write_json

OUT = ROOT / 'analysis_results/objective_difficulty_20261009'
LABELS = {'简单': 0, '中等': 1, '困难': 2}


def empirical_percentiles(query, reference):
    """只用reference归一化；相同值取经验分布的中秩。"""
    query, reference = np.asarray(query, float), np.asarray(reference, float)
    if query.ndim != 2 or reference.ndim != 2 or query.shape[1] != reference.shape[1] or not len(reference):
        raise ValueError('percentile_shape')
    if not np.isfinite(query).all() or not np.isfinite(reference).all():
        raise ValueError('percentile_requires_finite_complete_features')
    result = np.empty_like(query)
    for j in range(query.shape[1]):
        values = np.sort(reference[:, j])
        result[:, j] = (np.searchsorted(values, query[:, j], side='left')
                        + np.searchsorted(values, query[:, j], side='right')) / (2 * len(values))
    return result


def weight_grid(dimensions):
    weights = [tuple(v/4 for v in w) for w in product(range(5), repeat=dimensions) if sum(w) == 4]
    uniform = tuple([1/dimensions] * dimensions)
    if uniform not in weights:
        weights.append(uniform)
    return np.asarray(weights, float)


def balanced_loss(prediction, labels, buildings):
    errors = (np.asarray(prediction) - np.asarray(labels) / 2) ** 2
    return float(np.mean([np.mean(errors[np.asarray(buildings) == b]) for b in sorted(set(buildings))]))


def calibrate_weights(x, labels, buildings):
    x = np.asarray(x, float)
    uniform = np.full(x.shape[1], 1 / x.shape[1])
    grid = weight_grid(x.shape[1])
    best = min(grid, key=lambda w: (round(balanced_loss(x @ w, labels, buildings), 12),
                                   float(np.sum((w - uniform) ** 2)), tuple(w)))
    return best


def select_inner_weights(x, labels, buildings, train):
    grid = weight_grid(x.shape[1])
    uniform = np.full(x.shape[1], 1 / x.shape[1])
    inner_errors = []
    for inner in sorted(set(buildings[train])):
        inner_train = train & (buildings != inner)
        inner_test = train & (buildings == inner) & np.isfinite(labels)
        if not inner_train.any() or not inner_test.any():
            continue
        ranks = empirical_percentiles(x[inner_test], x[inner_train])
        inner_errors.append(np.mean((ranks @ grid.T - labels[inner_test, None] / 2) ** 2, axis=0))
    if len(inner_errors) < 2:
        return uniform, len(inner_errors), 'insufficient_inner_buildings_uniform'
    losses = np.mean(inner_errors, axis=0)
    ix = min(range(len(grid)), key=lambda i: (round(float(losses[i]), 12),
                float(np.sum((grid[i] - uniform) ** 2)), tuple(grid[i])))
    status = 'inner_selected_uniform' if np.allclose(grid[ix], uniform) else 'inner_building_calibrated'
    return grid[ix], len(inner_errors), status


def building_holdout(rows):
    """外层测试建筑标签隔离；权重由内层留建筑预测误差选择。"""
    x = np.asarray([r['x'] for r in rows], float)
    buildings = np.asarray([r['building'] for r in rows])
    labels = np.asarray([np.nan if r['label'] is None else r['label'] for r in rows])
    uniform = np.full(x.shape[1], 1 / x.shape[1])
    outputs = []
    for heldout in sorted(set(buildings)):
        train = buildings != heldout
        test = ~train
        training_buildings = sorted(set(buildings[train]))
        if not train.any():
            continue
        weights, inner_n, status = select_inner_weights(x, labels, buildings, train)
        ranks = empirical_percentiles(x[test], x[train])
        for row, p, baseline, calibrated in zip(np.asarray(rows, object)[test], ranks, ranks @ uniform, ranks @ weights):
            outputs.append(dict(image=row['image'], building=heldout, label=row['label'],
                baseline_score=float(100 * baseline), calibrated_score=float(100 * calibrated),
                weights=weights.tolist(), training_buildings=training_buildings,
                inner_validation_buildings=inner_n, calibration_status=status,
                component_scores=(100*p).tolist()))
    return sorted(outputs, key=lambda r: r['image'])


def rank_metrics(scores, targets):
    scores, targets = np.asarray(scores, float), np.asarray(targets, float)
    if len(scores) < 2 or len(set(targets)) < 2:
        return dict(n=len(scores), spearman=None, concordance=None, comparable_pairs=0)
    correct, pairs = 0., 0
    for i in range(len(scores)):
        for j in range(i):
            if targets[i] == targets[j]:
                continue
            delta = (scores[i] - scores[j]) * (targets[i] - targets[j])
            correct += 1 if delta > 0 else .5 if delta == 0 else 0
            pairs += 1
    rho = float(spearmanr(scores, targets).statistic) if len(scores)>=3 and len(set(scores))>=2 else None
    return dict(n=len(scores), spearman=rho,
                concordance=correct / pairs if pairs else None, comparable_pairs=pairs)


def evaluate_subjective(rows, feature_names=()):
    labelled = [r for r in rows if r['label'] is not None]
    result = []
    for field in ('baseline_score', 'calibrated_score', *feature_names):
        def value(r):
            return r['component_scores'][feature_names.index(field)] if field in feature_names else r[field]
        metrics = rank_metrics([value(r) for r in labelled], [r['label'] for r in labelled])
        per_building = defaultdict(list)
        for r in labelled:
            per_building[r['building']].append(r)
        losses = [np.mean([(value(r)/100-r['label']/2)**2 for r in group]) for group in per_building.values()]
        result.append(dict(score=field, **metrics, buildings=len(per_building),
                           building_equal_mse=float(np.mean(losses)) if losses else None))
    return result


def load_comparison_metadata():
    inventory = json.loads((ROOT/'analysis_results/review_source_audit_20261004/corrected_inventory/input.json').read_text(encoding='utf-8'))
    original = {r['image']: r for r in inventory['images']}
    recent = {}
    for relative in ('analysis_results/difficulty_consensus_20261006/user_review.json',
                     'analysis_results/difficulty_full_20261007/updated/human_review.json'):
        payload = json.loads((ROOT/relative).read_text(encoding='utf-8-sig'))
        for r in payload['decisions']:
            if r['difficulty'] in LABELS and r['updated_at']:
                recent[r['image_code']] = relative
    groups = defaultdict(list)
    for r in read_csv(ROOT/'analysis_results/difficulty_full_20261007/updated/coverage.csv'):
        groups[r['image']].append(r)
    result = {}
    for image, group in groups.items():
        labels, scenes = {r['difficulty'] for r in group}, {r['scene'] for r in group}
        if len(labels) != 1 or len(scenes) != 1:
            raise ValueError('inconsistent_image_metadata:' + image)
        prior = original[image]
        if image in recent:
            source, definition = recent[image], '后续用户主观难度及原备注，未进行新盲标'
        elif prior['difficulty_text_review']:
            source, definition = 'resolved_image_comment', '后审图级原话的明确难度'
        elif (prior['difficulty_later_review'].get('status') == 'resolved'
              and prior['difficulty_later_review'].get('difficulty', 'unrecorded') != 'unrecorded'):
            source, definition = 'resolved_image_traits', '后审图级主观难度，非独立盲标'
        elif prior['difficulty_legacy'] in LABELS:
            source, definition = inventory['sources']['human'], '9/13审图预期：较早稳定／可能稳定多簇／观察内持续变化；不是固有执行难度'
        else:
            source, definition = 'no_resolved_three_level_label', '未知／未记录，未用于校准'
        result[image] = dict(subjective_label=next(iter(labels)), scene=next(iter(scenes)),
                             subjective_source=source, subjective_definition=definition)
    return result


def score_features(features, names):
    """共同完整特征面板才给总分；单轴覆盖和总分覆盖明确区分。"""
    complete = [r for r in features if all(r[k] is not None for k in names)]
    if not complete:
        raise ValueError('no_complete_feature_panel')
    reference = np.asarray([[r[k] for k in names] for r in complete], float)
    ranks = empirical_percentiles(reference, reference)
    lookup = {r['image']: dict(x=[r[k] for k in names], score=float(100*p.mean()), ranks=p)
              for r, p in zip(complete, ranks)}
    output = []
    for r in features:
        state = lookup.get(r['image'])
        row = dict(r, baseline_score=state['score'] if state else None,
                   score_status='complete' if state else 'missing_features',
                   missing_features='|'.join(k for k in names if r[k] is None))
        for k in names:
            values = np.asarray([[f[k]] for f in features if f[k] is not None], float)
            row[k+'_available_percentile'] = float(100*empirical_percentiles([[r[k]]], values)[0, 0]) if r[k] is not None else None
        output.append(row)
    return output, lookup


def response_comparison(scores):
    """复用现有Lee结果，固定k面板；从不据评价结果调整评分。"""
    score_lookup = {r['image']: r for r in scores if r['baseline_score'] is not None}
    summary, joined = [], []
    curves = read_csv(ROOT/'analysis_results/difficulty_full_20261007/updated/curves.csv')
    for method in ('mv50', 'mv_strict'):
        for limit in (8, 16, 20):
            groups = defaultdict(dict)
            for r in curves:
                if (r['image'] in score_lookup and r['condition']=='manual' and r['version']=='original'
                    and r['quality_compatible']=='True' and r['scene']=='ordinary'
                    and r['method']==method and int(r['n']) >= limit and int(r['k']) <= limit):
                    if int(r['k']) in groups[r['image']]:
                        raise ValueError('duplicate_response_pool:' + r['image'])
                    groups[r['image']][int(r['k'])] = r
            entries = []
            for image, curve in sorted(groups.items()):
                if set(curve) != set(range(1, limit+1)):
                    raise ValueError('missing_response_prefix:' + image)
                entry = dict(image=image, building=score_lookup[image]['building'], method=method,
                    limit=limit, baseline_score=score_lookup[image]['baseline_score'],
                    D1=float(curve[1]['D']), D_limit=float(curve[limit]['D']),
                    V_limit=float(curve[limit]['V']),
                    gain_1_limit=float(curve[1]['D'])-float(curve[limit]['D']),
                    gain_4_limit=float(curve[4]['D'])-float(curve[limit]['D']),
                    n=int(curve[1]['n']))
                entries.append(entry)
                joined.append(entry)
            for target in ('D1', 'D_limit', 'V_limit', 'gain_1_limit', 'gain_4_limit'):
                metrics = rank_metrics([r['baseline_score'] for r in entries], [r[target] for r in entries])
                summary.append(dict(method=method, limit=limit, target=target,
                    **metrics, buildings=len({r['building'] for r in entries}),
                    images='|'.join(r['image'] for r in entries),
                    interpretation='fixed_k_ordinary_manual_existing_pool_association'))
    raw = read_csv(ROOT/'analysis_results/consensus_response_20261006/all_pool_summary.csv')
    members = [r for r in raw if r['image'] in score_lookup and r['condition']=='manual'
               and r['version']=='original' and r['method']=='mv50'
               and score_lookup[r['image']]['scene']=='ordinary']
    summary.append(dict(method='raw_answers', limit=0, target='raw_pairwise_union',
        **rank_metrics([score_lookup[r['image']]['baseline_score'] for r in members],
                       [float(r['raw_pairwise_union']) for r in members]),
        buildings=len({score_lookup[r['image']]['building'] for r in members}),
        images='|'.join(r['image'] for r in members),
        interpretation='existing_high_count_pools_variable_N_descriptive_only'))
    return joined, summary


def plot_results(scores, holdout, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    for font in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC'):
        if font in available:
            plt.rcParams['font.sans-serif'] = [font]
            break
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    known = [r for r in scores if r['baseline_score'] is not None and r['subjective_label'] in LABELS and r['scene']=='ordinary']
    rng = np.random.default_rng(20261009)
    axes[0].scatter([LABELS[r['subjective_label']]+rng.uniform(-.12,.12) for r in known],
                    [r['baseline_score'] for r in known], alpha=.7, s=22)
    axes[0].set(xticks=[0,1,2], xticklabels=list(LABELS), ylabel='标签盲基线分数（0—100）',
                title='客观模型代理与主观感受：普通场景')
    known = [r for r in holdout if r['label'] is not None]
    axes[1].scatter([r['baseline_score'] for r in known], [r['calibrated_score'] for r in known], s=22, alpha=.7)
    axes[1].plot([0,100], [0,100], color='grey', linestyle='--', linewidth=1)
    axes[1].set(xlim=(0,100), ylim=(0,100), xlabel='外层留出：等权基线', ylabel='外层留出：主观校准',
                title='两版分数分别保存，调参不等于验证成功')
    fig.savefig(out/'comparison.png', dpi=160)
    plt.close(fig)


def run():
    from .difficulty_features_20261009 import extract_features, SCORE_FEATURES, FEATURE_DEFINITIONS
    features = extract_features()
    names = tuple(SCORE_FEATURES)
    scores, complete = score_features(features, names)
    metadata = load_comparison_metadata()
    if set(metadata) != {r['image'] for r in scores}:
        raise ValueError('score_image_inventory_mismatch')
    for row in scores:
        row.update(metadata[row['image']])
    # 主观校准只在普通场景；OOS、门洞分数保留，适配问题另列。
    ordinary = [dict(image=r['image'], building=r['building'], x=complete[r['image']]['x'],
                     label=LABELS.get(r['subjective_label']))
                for r in scores if r['image'] in complete and r['scene']=='ordinary']
    holdout = building_holdout(ordinary)
    subjective = evaluate_subjective(holdout, names)
    reference_x = np.asarray([r['x'] for r in ordinary], float)
    weights, inner_n, fit_status = select_inner_weights(reference_x,
        np.asarray([np.nan if r['label'] is None else r['label'] for r in ordinary]),
        np.asarray([r['building'] for r in ordinary]), np.ones(len(ordinary), dtype=bool))
    for r in scores:
        r['subjective_calibrated_candidate_score'] = (float(100*empirical_percentiles(
            [complete[r['image']]['x']], reference_x)[0] @ weights) if r['image'] in complete else None)
    # 嵌套结构作为JSON保留，避免CSV中出现不可解析的Python repr。
    csv_scores = [dict(r, provenance=json.dumps(r['provenance'], ensure_ascii=False, sort_keys=True)) for r in scores]
    response_rows, response_metrics = response_comparison(scores)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT/'features_and_scores.csv', csv_scores)
    write_json(OUT/'reference.json', dict(schema='objective_difficulty_reference_v1', features=names,
        weights=[1/len(names)]*len(names), rows=[dict(image=r['image'], building=r['building'],
        values=complete[r['image']]['x']) for r in scores if r['image'] in complete],
        formula='score=100*mean(empirical_mid_percentiles(query,reference)); reference freezes this run, no labels'))
    write_json(OUT/'calibrated_reference.json', dict(schema='subjective_calibrated_reference_v1', features=names,
        weights=weights.tolist(), fit_status=fit_status, inner_validation_buildings=inner_n,
        rows=[dict(image=r['image'], building=r['building'], values=r['x']) for r in ordinary],
        target='mixed_historical_subjective_expectation_not_ground_truth',
        evaluation='性能只看外层holdout文件；本文件使用完整普通面板拟合，不能用其训练内匹配评估性能',
        applicability='仅共同完整特征面板；虽然权重可能为零，暂不扩到缺其他轴的图以改变已评价分母'))
    write_json(OUT/'holdout_predictions.json', holdout)
    holdout_csv = [dict(r, weights='|'.join(map(str,r['weights'])), training_buildings='|'.join(r['training_buildings']),
        component_scores=json.dumps(r['component_scores'])) for r in holdout]
    if holdout_csv:
        write_csv(OUT/'holdout_predictions.csv', holdout_csv)
    write_csv(OUT/'subjective_comparison.csv', subjective)
    if response_rows:
        write_csv(OUT/'response_comparison.csv', response_rows)
    write_csv(OUT/'response_metrics.csv', response_metrics)
    contract = dict(schema='objective_difficulty_20261009_v1', features=names,
        feature_definitions=FEATURE_DEFINITIONS,
        unit='图片；分数为模型代理难度的样本相对百分位，不是固有难度或错误概率',
        baseline='特征越大暂定代理难度越高；共同完整特征面板经验中秩/样本量，各轴等权均值乘100；不读人工标签/人员作答/GT；reference.json冻结参照，holdout文件的baseline另用外层训练普通场景参照，不混称同一数值',
        missing='缺任一评分特征总分为null；可用单轴百分位另列，不补0、不改权重、不比较缺失组合的总分',
        subjective='简单/中等/困难编码0/1/2；是主观评价，不是真值；仅普通场景校准',
        subjective_source_counts=dict(Counter(r['subjective_source'] for r in scores if r['scene']=='ordinary'
                                             and r['image'] in complete and r['subjective_label'] in LABELS)),
        subjective_construct='历史标签混合审图对共识过程的预期和后续主观难度；未证实统一执行难度口径，不宣称盲标',
        calibration='外层整建筑留出；内层整建筑留出，每折仅训练建筑特征经验分布；非负权重步长0.25且和1，另含等权候选；最小建筑等权MSE，标签映射0/0.5/1；不足两内层标签建筑回退等权',
        evaluation='外层留出预测与等权同折基线比较；Spearman、序对一致率及建筑等权MSE；无显著性或因果结论，已见历史资料的回顾性检验；上游模型训练和静态特征库没有在每折重训，故不是全链条新建筑独立验证',
        validation='已有Lee普通Manual质量兼容、原GT、固定k面板；两规则分别；相关不分离人员/图片噪声，不用于评分调参',
        sources=['analysis_results/research_input_20260929/manifest.json',
                 'analysis_results/difficulty_full_20261007/updated/coverage.csv',
                 'analysis_results/difficulty_full_20261007/updated/curves.csv',
                 'analysis_results/consensus_response_20261006/all_pool_summary.csv'],
        counts=dict(images=len(scores), complete=len(complete), ordinary_complete=len(ordinary),
                    ordinary_labelled=sum(r['label'] is not None for r in ordinary)),
        calibrated_weights=weights.tolist(),
        deployment='保留标签盲基线为研究v1；calibrated_reference保存全普通面板选权后的主观校准候选，不默认替换基线；性能仅从外层留出评价；未拟合自然难度等级或通用阈值')
    write_json(OUT/'field_contract.json', contract)
    write_json(OUT/'summary.json', dict(counts=contract['counts'], subjective=subjective, response=response_metrics,
        calibrated_weights=weights.tolist(), subjective_sources=contract['subjective_source_counts']))
    plot_results(scores, holdout, OUT)
    write_report(contract, subjective, response_metrics, scores)
    print(contract['counts'])


def write_report(contract, subjective, response_metrics, scores):
    counts = contract['counts']
    lines = ['# 图片客观难度评分：首轮实算', '',
        '2026-10-09。用户要求先探究客观标准，再与主观感受对比调参。本轮独立计算标签盲基线，随后完成按建筑内外层留出的主观校准。评分仅为可复现的模型代理候选，不宣称已识别图片固有难度。', '',
        '## 评分标准与覆盖', '',
        f"统一259图库存：实际读取{counts['images']}图，完整评分{counts['complete']}图；普通场景完整{counts['ordinary_complete']}图，其中主观三档{counts['ordinary_labelled']}图。缺特征不补零，不用不一样的特征组合混排。", '',
        '特征按预设正方向取经验中秩百分位；仅完整特征共同面板等权平均得到0—100分。正方向和等权都是待验证假设，不是已经证明的难度规律。reference.json冻结参照集和原始数值，以便新图按相同参照计算。分数高表示这些代理信号较强，不等于人一定难标。', '',
        '| 特征 | 定义 |', '|---|---|']
    for name in contract['features']:
        lines.append(f"|{name}|{contract['feature_definitions'][name]['meaning']}|")
    lines += ['', '## 与主观感受对比及调参', '',
        '主观标签未参与基线。校准只用普通场景；外层目标建筑标签和特征均不参与训练参照或选权重。内层留建筑选非负少量权重，保留每折名单。标签映射0/0.5/1用于校准损失，是工作约定，不说明等级天然等距。', '',
        f"标签来源：{contract['subjective_source_counts']}。9/13审查台将难度解释为对歧义和共识稳定过程的主观预期；后续标签也是人类主观判断。因此本轮检验的是对历史主观三档的匹配，不是认证固有人类执行难度。", '',
        '| 外层留出结果 | 有标签图数 | 建筑数 | Spearman | 序对一致率 | 建筑等权MSE |',
        '|---|---:|---:|---:|---:|---:|']
    for r in subjective:
        values = [r['score'], str(r['n']), str(r['buildings'])] + [('N/A' if r[k] is None else f"{r[k]:.4f}") for k in ('spearman','concordance','building_equal_mse')]
        lines.append('|'+'|'.join(values)+'|')
    improved = (subjective[1]['building_equal_mse'] is not None and subjective[1]['building_equal_mse'] < subjective[0]['building_equal_mse'])
    lines += ['', ('本轮校准的建筑等权损失低于等权基线；仍需结合秩关系及后续验证，不以一项下降认证评分。' if improved else
                   '本轮校准没有降低建筑等权损失；不能宣布主观调参有效，标签盲基线继续保留。'), '',
        f"全普通面板的内层留建筑选权为{contract['calibrated_weights']}，特征顺序见上表。calibrated_reference.json冻结此主观校准候选；它已经使用标签，不能改称独立标签盲客观基线。若只偏好点数，说明这批标签下其它代理没有增加校准收益，不证明真实难度只由点数决定。", '',
        '## 与既有实际任务结果连接', '',
        '以下只复用普通Manual、质量兼容、原GT的Lee区域结果。同一人数窗口内图片固定，分数未由这些结果调参；不同窗口不拼接。相关关系不识别独立图片效应。D不是1−IoU。', '',
        '|规则|人数窗口|结果量|图数|建筑数|Spearman|', '|---|---:|---|---:|---:|---:|']
    for r in response_metrics:
        rho = 'N/A' if r['spearman'] is None else f"{r['spearman']:.4f}"
        lines.append(f"|{r['method']}|{r['limit']}|{r['target']}|{r['n']}|{r['buildings']}|{rho}|")
    lines += ['', '本轮与参考差异水平及部分原作答分歧有关；后段改善量的关系随投票规则、人数窗口变化，没有一致支持高分图增人后收敛更慢。gain为起点D减终点D，正值表示参考差异下降；它受起始误差影响，不等于达到同一目标所需人数。', '',
        '## 科学边界与后续判断', '',
        '- 点对数受模型后处理与四角回退影响，只是表达复杂度代理；实际回退证据未知时不推断正常或遮挡。',
        '- d_model保持历史特征距离含义；BiLayout差异保持已核查表示定义。两者不是GT或独立人员票。',
        '- 范围参考差、定位、细节遗漏及任务可标性分别解释；低范围误差不能认证简单，远离GT不能直接归因难度。',
        '- OOS、门洞与未定状态保留，未纳入普通场景主观校准；分数对这些场景仍是模型代理。',
        '- 多次人数抽组不是新增图片；表内相关、序对数和折数不作为独立证据数量。部分标签来自事后审核，不能宣称盲标验证。',
        '- 特征缺失及模型版本覆盖会选择样本；当前分数不能外推到全部259图。',
        '- 上游静态特征库、PCA及模型checkpoint没有按本轮每折重新拟合；留建筑评价只隔离本轮归一化和主观调参，不能宣称全链条新建筑独立验证。',
        '- 本轮没有自动划分简单／中等／困难，也没有从主观标签推导真值；评分方向、等权及特征有效性仍是待检验标准。',
        '- 下一步围绕分数与人工判断显著不一致的图核对真实结构、遗漏与回退证据，区分特征无效和主观口径不同；不按目标GT或主观意见逐图改分。', '',
        '## 文件与复算', '',
        '`features_and_scores.csv`保存全图库存、原特征、来源、单轴百分位、基线、主观标签与全数据拟合的校准候选；`reference.json`冻结无标签参照，`calibrated_reference.json`冻结主观校准候选；`holdout_predictions.json/csv`保存外层预测、权重和训练建筑；`response_comparison.csv`与`response_metrics.csv`保留人数对照；`field_contract.json`固定公式和边界。全库标签盲基线、全普通校准候选和外层留出基线的归一化参照不同，数值不能混用。', '',
        '方法依据：调参和性能评价分开，参见[Cawley与Talbot关于模型选择偏差](https://www.jmlr.org/papers/v11/cawley10a.html)；预处理仅在训练侧拟合，参见[交叉验证文档](https://scikit-learn.org/stable/modules/cross_validation.html#data-transformation-with-held-out-data)。本轮分组单位依据仓库统计计划使用建筑。', '',
        '复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_score_20261009`。未重建研究输入、运行模型或改源标签、GT、人员资格、融合规则。图为保留的科研产物；本轮没有临时截图。', '',
        '![客观分数与主观对照](comparison.png)', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    run()
