"""并集减法八图的静态交付；展示现有输出，不在展示层改分支或选参数。"""
from collections import defaultdict
import gzip
import html
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from tools.thesis_main.analysis.run_structural_consensus_20260926 import ROOT, svg_room
from tools.thesis_main.analysis.structural_consensus_20260926 import geometry_diagnostics


LABELS = {'oos': 'OOS', 'doorway': '门洞交界', 'difficult': '困难图',
          'invalid_3d_candidate': '几何不可用；保留人数与分支',
          'geometry_review': '几何告警；需要检查',
          'no_flag_under_exploratory_checks': '当前探索检查未告警（不等于正确）',
          'existing_pairing_unavailable': '缺已有上下配对',
          'borrowed_point_not_independent_geometric_vote': '补点借自其他人，不作独立几何票',
          'gt_original': '原GT', 'gt_revised': '修订GT',
          'medoid': '簇内区域 medoid', 'mv50': '簇内区域 ≥50%票', 'mv_strict': '簇内区域 >50%票'}


def esc(value):
    return html.escape(str(value))


def label(value):
    return esc(LABELS.get(value, value))


def number(value, digits=3):
    return '不可评价' if value is None else f'{value:.{digits}f}'


def load(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf8') as stream:
        return json.load(stream)


def svg_top_view(points, reference=None, features=None):
    """同一坐标比例显示分支和参考；点池只画点，不暗造全局邻接。"""
    points = np.asarray(points, float)
    reference = None if reference is None else np.asarray(reference, float)
    all_points = np.vstack([points, [[0., 0.]]] + ([] if reference is None else [reference]))
    low, high = all_points.min(axis=0), all_points.max(axis=0)
    scale = min(280 / max(high[0] - low[0], .01), 190 / max(high[1] - low[1], .01))
    def project(q):
        return (q - (low + high) / 2) * scale + [160, 115]
    def ring(q, color, dashed=False):
        pairs = ' '.join(f'{x:.2f},{y:.2f}' for x, y in project(np.vstack([q, q[0]])))
        return f'<polyline points="{pairs}" fill="none" stroke="{color}" stroke-width="2"' + (' stroke-dasharray="5 4"' if dashed else '') + '/>'
    shapes = ring(reference, '#bd862a', True) if reference is not None else ''
    if features is None:
        shapes += ring(points, '#126782')
    else:
        for point, feature in zip(project(points), features):
            x, y = point
            radius = 2 + np.sqrt(feature['support'])
            shapes += (f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="#126782" fill-opacity=".6">'
                       f'<title>{esc(feature["feature_id"])} · {feature["support"]}人</title></circle>'
                       f'<text x="{x + 5:.2f}" y="{y - 5:.2f}" font-size="9">{esc(feature["feature_id"])}</text>')
    x, y = project(np.array([0., 0.]))
    shapes += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#c0392b"><title>相机</title></circle>'
    return '<svg viewBox="0 0 320 230" role="img" aria-label="共享坐标的地面结构或角点身份点云">' + shapes + '</svg>'


def stats(rows, value):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['n']].append(value(row))
    ns, means, lows, highs, valid = [], [], [], [], []
    for n, items in sorted(grouped.items()):
        data = np.array([x for x in items if x is not None], float)
        ns.append(n)
        valid.append(len(data))
        means.append(float(data.mean()) if len(data) else np.nan)
        lows.append(float(np.quantile(data, .1)) if len(data) else np.nan)
        highs.append(float(np.quantile(data, .9)) if len(data) else np.nan)
    return tuple(np.array(x) for x in (ns, means, lows, highs, valid))


def plot_curves(cases, out):
    plt.rcParams.update({'font.family': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    fig, axes = plt.subplots(len(cases), 3, figsize=(18, 3.4 * len(cases)), squeeze=False)
    colors = ['#126782', '#cc6b31', '#688b31']
    for row, case in zip(axes, cases):
        ax = row[0]
        for rank, color in enumerate(colors):
            n, mean, low, high, _ = stats(case['curves'], lambda r: r['top_support'][rank])
            ax.plot(n, mean, color=color, label=f'第{rank + 1}大分支')
            ax.fill_between(n, low, high, color=color, alpha=.13)
        n, mean, *_ = stats(case['curves'], lambda r: r['missing_mass'])
        ax.plot(n, mean, color='#7a7a7a', ls=':', label='缺几何占比')
        ax.set_title(case['code'] + ' · 支持秩（人数 / n）')
        for ax, reference in zip(row[1:], ('gt_original', 'gt_revised')):
            def tie_end(row, endpoint):
                bounds = row['reference'][reference]['tied_dominant_bounds']
                return None if bounds is None else bounds[endpoint]
            n, tie_low, _, _, count = stats(case['curves'], lambda r: tie_end(r, 0))
            _, tie_high, *_ = stats(case['curves'], lambda r: tie_end(r, 1))
            _, lower, *_ = stats(case['curves'], lambda r: r['reference'][reference]['weighted_iou_lower'])
            _, upper, *_ = stats(case['curves'], lambda r: r['reference'][reference]['weighted_iou_upper'])
            reference_evaluable = np.any(upper - lower < 1 - 1e-10)
            if reference_evaluable:
                ax.fill_between(n, lower, upper, color='#e6bb71', alpha=.42, label='支持加权IoU未知量界')
                ax.plot(n, lower, color='#bd862a', lw=1)
                ax.plot(n, upper, color='#bd862a', lw=1)
            if reference_evaluable and count.any():
                ax.plot(n, tie_low, color='#126782', label='最多支持集合IoU下界均值')
                ax.plot(n, tie_high, color='#126782', ls='--', label='最多支持集合IoU上界均值')
                ax.fill_between(n, tie_low, tie_high, color='#126782', alpha=.16)
                ax.text(.03, .03, f'同票范围包络，非置信区间；每n有界排列{count.min()}–{count.max()}',
                        transform=ax.transAxes, fontsize=8, color='#53616a')
            else:
                ax.text(.5, .5, '参考不可计算；没有GT一致性估计', ha='center',
                        transform=ax.transAxes, color='#6b502b')
            ax.set_title(case['code'] + ' · ' + LABELS[reference] + '一致性')
        for ax in row:
            ax.set(xlim=(1, case['n_input']), ylim=(-.025, 1.025), xlabel='进入人数 n（含缺几何作答）')
            ax.grid(alpha=.2)
            if ax.get_legend_handles_labels()[0]:
                ax.legend(loc='upper right', fontsize=7, framealpha=.75)
    fig.suptitle('人数重放：支持分布与单一参考一致性分开解释\n'
                 f'{len(cases[0]["orders"])}个有限池进入排列；阴影不是人口置信区间；n=N相同是用完同一批人，不代表已证明收敛', fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .975))
    fig.savefig(out / 'curves.png', dpi=145)
    plt.close(fig)

    fig, axes = plt.subplots(4, 2, figsize=(14, 15), squeeze=False)
    for ax, case in zip(axes.ravel(), cases):
        n, lower, *_ = stats(case['disjoint_stability'], lambda r: r['lower'])
        _, upper, *_ = stats(case['disjoint_stability'], lambda r: r['upper'])
        ax.plot(n, lower, 'o-', color='#126782', label='未知代价下界均值')
        ax.plot(n, upper, 'o-', color='#bd862a', label='未知代价上界均值')
        ax.fill_between(n, lower, upper, color='#c9dce4', alpha=.65)
        ax.set(title=case['code'], xlabel='每组人数（两组人员不相交）',
               ylabel='空间分布 OT 距离；越低越一致', ylim=(-.025, 1.025), xticks=n)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('不相交人员组的多分支空间分布差异\n'
                 '代价=1−地面IoU；无效或缺失几何保留未知代价上下界；均值不等于真值置信区间', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(out / 'disjoint_stability.png', dpi=150)
    plt.close(fig)


def coordinate_table(branch):
    shared = branch['shared_feature_candidate']
    medoid_geometry = geometry_diagnostics(branch['representative_floor'], branch['representative_heights'])
    alternatives = [('簇内角点中位数（默认）', branch['geometry'], branch['reference_evaluation']),
                    ('全体共享身份坐标中位数', shared['geometry'], shared['reference_evaluation']),
                    ('簇内角点 medoid', medoid_geometry, branch['aggregation_comparison']['corner_medoid_reference'])]
    rows = ['<div class="scroll"><table><tr><th>坐标合成方式</th><th>方向残差</th><th>原GT IoU</th><th>修订GT IoU</th></tr>']
    for name, geometry, references in alternatives:
        rows += [f'<tr><td>{esc(name)}</td><td>{number(geometry["weighted_direction_residual_deg"], 2)}°</td>'
                 f'<td>{number(references["gt_original"]["dominant_iou"])}</td>'
                 f'<td>{number(references["gt_revised"]["dominant_iou"])}</td></tr>']
    return ''.join(rows) + ('</table></div><small>共享身份点票：' + esc(shared['point_support_counts']) +
                           '。这些局部票不能加成整环支持；所有对照沿用原分支人数。medoid未依据GT挑选。</small>')


def aggregation_table(branch):
    aggregation = branch['aggregation_comparison']
    if aggregation['tile_status'] != 'all_members_computable':
        return (f'<p class="note">区域投票基线不可用：{aggregation["invalid_members"]} / '
                f'{aggregation["member_count"]}份成员地面多边形无效；没有删除这些成员后重新归一化。</p>')
    rows = ['<table><thead><tr><th>簇内合成方式</th><th>原GT IoU</th><th>修订GT IoU</th>'
            '<th>分量 / 孔洞</th></tr></thead><tbody>']
    refs = branch['reference_evaluation']
    rows += [f'<tr><td>角点坐标中位数（本分支）</td><td>{number(refs["gt_original"]["dominant_iou"])}</td>'
             f'<td>{number(refs["gt_revised"]["dominant_iou"])}</td><td>按给定环，见几何状态</td></tr>']
    for method, result in aggregation['methods'].items():
        rows += [f'<tr><td>{label(method)}</td><td>{number(result["reference_iou"]["gt_original"])}</td>'
                 f'<td>{number(result["reference_iou"]["gt_revised"])}</td>'
                 f'<td>{result["components"]} / {result["holes"]}</td></tr>']
    return ''.join(rows) + '</tbody></table><small>区域切片允许孔洞和多分量；未把其边界强行重建为单房间3D。</small>'


def gallery(panel, summary, cases, out):
    indexed = {image['code']: image for image in panel['images']}
    body = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>八图并集减法 · 多分支共识探索</title><style>'
            'body{font:16px/1.65 system-ui,sans-serif;max-width:1480px;margin:28px auto;padding:0 18px;background:#f4f6f7;color:#20333e}'
            'h1,h2,h3{line-height:1.3}section{background:#fff;border:1px solid #d9e1e4;border-radius:10px;padding:22px;margin:24px 0}'
            '.note,small{color:#526974}.notice{background:#f8edda;padding:14px;border-left:4px solid #bd862a}.pano{width:100%;max-height:530px;object-fit:contain}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}.card{border:1px solid #ccd8df;padding:14px;border-radius:8px;overflow-wrap:anywhere}'
            '.views{display:flex}.views figure{width:50%;margin:0;text-align:center}.views svg{width:100%;height:200px}'
            'table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:7px;border-bottom:1px solid #dbe2e5;text-align:left;vertical-align:top}'
            '.sensitivity{font-size:17px;background:#eff5f8}.scroll{overflow-x:auto}summary{cursor:pointer;color:#126782}code{overflow-wrap:anywhere}a{color:#126782}'
            '.feature-list{columns:3;column-gap:24px}.feature-list p{break-inside:avoid}.chart{width:100%;height:auto}'
            '@media(max-width:650px){.grid{grid-template-columns:1fr}.feature-list{columns:1}body{padding:0 9px}section{padding:12px}}</style></head><body>',
            '<h1>八图并集减法：保留多分支的条件实验</h1>',
            '<p>先识别全体角点身份，再对每个已观察分支删除不属于它的身份；簇内坐标取中位数。人数决定排序，'
            '几何另列告警。少人支持不等于错误，多人支持也不证明正确。没有把并集硬连成一个房间。</p>',
            '<p class="notice">本页使用用户指定、默认角点顺序已确认的八图；不表示每份布局或GT已被确认正确。'
            '参数5°尚未校准，2.5°与10°结果必须同时看。所有分支（含单人分支）均保留，未强行合成唯一共识。</p>',
            '<p><a href="README.md">研究说明</a> · <a href="results.json">汇总数据</a> · '
            '<a href="input_panel.json">来源与分母清单</a> · <a href="curves.png">人数曲线原图</a> · '
            '<a href="disjoint_stability.png">不相交样本稳定性原图</a></p>',
            '<details><summary>按图片跳转</summary><p>' + ' · '.join(f'<a href="#{esc(c["code"])}">{esc(c["code"])}</a>' for c in cases) + '</p></details>',
            '<details><summary>如何读曲线</summary><p>左列的第1/2/3大分支是每个n重新排序后的秩，不是同一语义分支的固定身份。'
            '每个前缀仅用已进入人员重建点身份和分支，不借未来点集。支持分母n包含不可计算作答，但缺失质量不算反对票。</p>'
            '<p>原GT、修订GT分开评价。每个n把全部并列最多支持分支保留为集合，不看GT选择赢家。'
            '蓝色包络是各排列中这个集合IoU上下界的均值；若同票候选几何不可评价，其范围放宽至[0,1]。蓝色不是置信区间，'
            '也不是人为挑选一个同票分支得到的收敛线；没有可评价参考时直接显示不可评价。金色界限对支持加权IoU保留缺失/无效几何的不确定量。'
            '这些范围来自同一有限人员池的进入顺序，不是新增人员或人口置信区间。</p>'
            '<p>OT图比较两组不相交人员的整个空间分布；无需把多个房间平均成一个。OT低可以表示稳定的多模态分布，'
            '不能证明每种标法合理。n=N重放曲线自然重合，因为最后使用同一批人，不能据此宣称收敛。</p></details>',
            '<details><summary>展开全部人数曲线</summary><a href="curves.png"><img class="chart" src="curves.png" alt="八图支持率与两类GT一致性人数曲线" loading="lazy"></a></details>',
            '<details><summary>展开不相交样本稳定性</summary><a href="disjoint_stability.png"><img class="chart" src="disjoint_stability.png" alt="八图不相交人员组的空间分布距离上下界" loading="lazy"></a></details>']
    for case in cases:
        meta, fit = indexed[case['code']], case['fits']['5.0']
        image_url = os.path.relpath(ROOT / meta['image_path'], out).replace('\\', '/')
        body += [f'<section id="{esc(case["code"])}"><h2>{esc(case["code"])} · {" / ".join(label(s) for s in case["strata"])}</h2>',
                 f'<p>已接收 {case["n_input"]} 人；独立可计算 {case["n_computable"]} 人；历史排除 {case["excluded_inventory_count"]} 份（单列）。'
                 '用户确认默认点序，不新增换序。</p>',
                 f'<img class="pano" src="{esc(image_url)}" alt="{esc(case["code"])} 全景原图" loading="lazy">',
                 '<h3>点身份阈值敏感性（未用GT挑选阈值）</h3><table class="sensitivity"><tr><th>角距阈值</th><th>并集身份数</th><th>分支数</th><th>最多支持人数</th></tr>']
        for tolerance in ('2.5', '5.0', '10.0'):
            value = case['fits'][tolerance]
            body += [f'<tr><td>{tolerance}°{"（主展示）" if tolerance == "5.0" else ""}</td><td>{len(value["features"])}</td>'
                     f'<td>{len(value["branches"])}</td><td>{max((b["support"] for b in value["branches"]), default=0)}</td></tr>']
        body += ['</table>']
        for reference, value in case['full_summary']['reference'].items():
            span = value['tied_dominant_iou_range']
            span_text = '不可评价' if span is None else f'{span[0]:.3f}–{span[1]:.3f}'
            body += [f'<p class="notice">{label(reference)}：全样本并列最多支持分支 {value["dominant_tie_count"]} 个；'
                     f'其中可评价者IoU范围 {span_text}。蓝色曲线保留整个并列最多支持集合，不能解读为唯一共识。</p>']
        if case['unavailable']:
            body += ['<p class="notice">缺失几何作答：' + '；'.join(f'{esc(r["worker"])}：{label(r["reason"])}' for r in case['unavailable']) + '。这些人不被判作反对某个分支。</p>']
        pool_points = [np.median([m['floor'] for m in feature['members']], axis=0) for feature in fit['features']]
        body += ['<h3>并集角点身份点云（没有全局连线）</h3><div style="max-width:720px">' +
                 svg_top_view(pool_points, features=fit['features']) + '</div><p class="note">每个身份用成员地面点中位数显示；点大小随支持人数增加。红点是相机。身份标签拥挤时可查下方票表。</p>']
        body += [f'<details><summary>并集角点身份与人数（{len(fit["features"])}个；不连全局多边形）</summary>'
                 '<p class="note">身份只在本图本次阈值拟合内有效；每人同一身份最多一票。上下端点球面角距最大值用于匹配，同人两个角点不能合并。</p><div class="feature-list">']
        for feature in fit['features']:
            body += [f'<p><b>{esc(feature["feature_id"])}：{feature["support"]}人</b><br><small>{esc(", ".join(feature["support_workers"]))}</small></p>']
        body += ['</div></details><h3>按支持人数排序的全部分支（5°）</h3><div class="grid">']
        for branch in fit['branches']:
            support, geo = branch['support'], branch['geometry']
            refs = branch['reference_evaluation']
            body += [f'<article class="card"><h3>{esc(branch["branch_id"])} · {len(branch["feature_ids"])}角 · {support}人</h3>',
                     f'<p><b>全体支持 {support}/{case["n_input"]} = {support / case["n_input"]:.1%}</b><br>'
                     f'可计算人员内 {support}/{case["n_computable"]} = {support / case["n_computable"]:.1%}</p>',
                     f'<p>{label(branch["geometry_status"])}<br>方向残差 {number(geo["weighted_direction_residual_deg"], 2)}°；'
                     f'高度相对MAD {number(geo["height_relative_mad"])}；相机在房间内：{"是" if geo["camera_inside"] else "否"}</p>',
                     f'<p>原GT IoU {number(refs["gt_original"]["dominant_iou"])}；修订GT IoU {number(refs["gt_revised"]["dominant_iou"])}（仅评价）</p>',
                     '<div class="views"><figure>' + svg_top_view(branch['floor'], case['references']['gt_original']['floor']) + '<figcaption>俯视；金虚线=原GT</figcaption></figure><figure>' +
                     svg_room(branch['floor'], branch['heights'], True) + '<figcaption>条件3D线框</figcaption></figure></div>',
                     '<small>俯视图内候选与原GT采用同坐标比例；卡片之间和3D线框独立缩放，不能直接比屏幕大小。原GT只是一个参考解释。</small>',
                     f'<p>保留环：<code>{esc(" → ".join(branch["feature_ids"]))} → 首点</code><br>'
                     f'并集删去：<code>{esc(", ".join(branch["deleted_feature_ids"])) or "无"}</code></p>']
            parents = branch['parent_deletions']
            body += ['<p>已观察父分支减法：' + ('；'.join(f'{esc(p["parent_branch_id"])} 删 {esc(", ".join(p["deleted_feature_ids"]))}' for p in parents) if parents else '没有直接父分支') + '。父分支人数不重复计给子分支。</p>',
                     '<details><summary>成员与来源</summary><p>' + esc(', '.join(branch['support_workers'])) + '</p><p><code>' +
                     esc(', '.join(branch['source_ids'])) + '</code></p></details>',
                     '<details><summary>簇内 / 跨簇共享身份 / 角点medoid坐标对照</summary>' + coordinate_table(branch) + '</details>',
                     '<details><summary>GT评价与簇内区域投票对照（不参与构造）</summary>' + aggregation_table(branch) + '</details></article>']
        body += ['</div>']
        if case['borrowed_full_sample_sensitivity'] is not None:
            borrowed = case['borrowed_full_sample_sensitivity']
            body += [f'<p class="notice">W031借用W033点的全样本描述性敏感性：纳入后 {borrowed["vote_denominator"]} 份几何记录、'
                     f'{len(borrowed["branches"])} 个分支。它与donor有依赖，不加入独立人员重放；保留原始修订事实。</p>']
        body += ['</section>']
    body += ['</body></html>']
    (out / 'index.html').write_text('\n'.join(body), encoding='utf8')


def build(out=ROOT / 'analysis_results/union_branch_consensus_20260926'):
    out = Path(out)
    panel, summary = load(out / 'input_panel.json'), load(out / 'results.json')
    cases = [load(out / path) for path in summary['case_files']]
    if len(cases) != 8 or {case['code'] for case in cases} != {image['code'] for image in panel['images']}:
        raise ValueError('eight_image_presentation_schema_drift')
    for case in cases:
        if sum(b['support'] for b in case['fits']['5.0']['branches']) != case['n_computable']:
            raise ValueError('branch_support_partition_drift')
    plot_curves(cases, out)
    gallery(panel, summary, cases, out)
    return dict(images=len(cases), branches=sum(len(c['fits']['5.0']['branches']) for c in cases),
                outputs=['index.html', 'curves.png', 'disjoint_stability.png'])


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
