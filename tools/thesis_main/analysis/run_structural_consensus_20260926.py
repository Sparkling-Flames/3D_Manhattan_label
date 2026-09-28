"""40图结构共识独立实验；生成、留出评价和参考评价分离，不回写标注。"""
from __future__ import annotations

from collections import Counter
import gzip
import html
import json
import math
import os
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/structural_consensus_20260926'
SEED = 20260926


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text=json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n'
    if path.suffix=='.gz':
        with gzip.open(path,'wt',encoding='utf8') as stream:
            stream.write(text)
    else:
        path.write_text(text,encoding='utf8')


def split_workers(records, seed=SEED):
    workers = sorted({r['worker'] for r in records})
    if len(workers) < 3:
        return []
    rng = np.random.default_rng(seed)
    result = []
    for number in range(4):
        order = rng.permutation(workers).tolist()
        k = max(2, int(math.floor(.75*len(order))))
        result.append(dict(split=number, train=sorted(order[:k]), test=sorted(order[k:])))
    return result


def reference_agreement(first, second):
    """只在评价器调用；指定参考不是已独立确认的唯一正确空间。"""
    try:
        a, b = Polygon(first), Polygon(second)
        if any(not p.is_valid or p.is_empty or p.area <= 0 for p in [a, b]):
            raise ValueError('invalid_or_empty_polygon')
        return dict(status='conditional_reference_agreement', iou=a.intersection(b).area/a.union(b).area)
    except (ValueError, TypeError) as exc:
        return dict(status='unavailable', reason=str(exc), iou=None)


def candidate_holdout(candidates, heldout, point_tol=.2):
    from tools.thesis_main.analysis.structural_consensus_20260926 import score_candidate
    details = [score_candidate(c['floor'], heldout, point_tol=point_tol) for c in candidates]
    covered = sorted({w for d in details for w in d['workers']})
    return dict(test_workers=[r['worker'] for r in heldout], covered_workers=covered,
                coverage=len(covered)/len(heldout) if heldout else None, candidate_support=details,
                coverage_denominator='computable_heldout_workers')


def budgeted_candidates(candidates, train, limit=6):
    from tools.thesis_main.analysis.structural_consensus_20260926 import score_candidate, match_ring
    ranked = sorted(enumerate(candidates), key=lambda pair: (
        -score_candidate(pair[1]['floor'],train)['whole_ring_support'], pair[0]))
    selected=[]
    for _, candidate in ranked:
        if not any(match_ring(candidate['floor'],other['floor'],1e-9)['matched'] for other in selected):
            selected.append(candidate)
        if len(selected)==limit:
            break
    return selected


def add_cluster_pool(result, records):
    from tools.thesis_main.analysis.local_structure_edits_20260926 import cluster_pool_probe
    result['cluster_pool_sensitivity']={outside: cluster_pool_probe(records,outside_mode=outside)
                                        for outside in ['soft','hard']}
    for split in result['splits']:
        train=[r for r in records if r['worker'] in split['train']]
        heldout=[r for r in records if r['worker'] in split['test']]
        probe=cluster_pool_probe(train)
        split['cluster_pool']=probe
        evaluate_pool_outputs(split,train,heldout)


def evaluate_pool_outputs(split,train,heldout):
    pool=split['cluster_pool']['candidates']
    split['cluster_pool_evaluation']=candidate_holdout(pool,heldout)
    searched=[c for c in pool if c['status']!='rare_input_candidate_not_searched']
    candidates={'structured':split['structured']['modes'],'local':split['local']['candidates'],
                'cluster_pool':pool,'cluster_pool_searched':searched}
    split['budget6']={}
    for name, values in candidates.items():
        selected=budgeted_candidates(values,train)
        split['budget6'][name]=dict(candidate_count=len(selected),
                selection='train_whole_ring_support_desc; exact_ring_dedup; at_most_six',
                **candidate_holdout(selected,heldout))


def evaluate_image(image, references, cohort):
    from tools.thesis_main.analysis.structural_consensus_20260926 import fit_consensus
    from tools.thesis_main.analysis.local_structure_edits_20260926 import local_edit_probe
    from tools.thesis_main.analysis.layout_real_case_probe_20260926 import floor_points
    from tools.thesis_main.analysis.layout_consensus_probe_20260926 import bev_aggregate

    conditions = {'manual', 'oos'} if cohort == 'manual_oos' else {'semi'}
    inventory = [r for r in image['annotations'] if r['raw_condition'] in conditions]
    records = [r['core_record'] for r in inventory if r['core_record'] is not None]
    if len({r['worker'] for r in records}) != len(records):
        raise ValueError('duplicate_worker_within_cohort:'+image['code'])
    out = dict(code=image['code'], image_id=image['image_id'], cohort=cohort, strata=image['strata'],
               input_annotations=len(inventory), computable_annotations=len(records),
               input_unavailable_count=len(inventory)-len(records),
               conditions=dict(Counter(r['raw_condition'] for r in inventory)),
               unavailable=[dict(id=r['canonical_annotation_id'], status=r['status'])
                            for r in inventory if r['core_record'] is None],
               formal_geometry_confirmation=False, parameter_sensitivity={}, splits=[])
    variants = {'default': (.2, .1, .02), 'tol_010': (.1, .1, .02),
                'tol_040': (.4, .1, .02), 'no_geometry': (.2, 0., 0.), 'no_height': (.2, .1, 0.)}
    for name, (tol, gw, hw) in variants.items():
        out['parameter_sensitivity'][name] = fit_consensus(records, point_tol=tol, geometry_weight=gw, height_weight=hw)
    out['local_edit_sensitivity'] = {
        str(t): local_edit_probe(records, point_tol=.2, support_threshold=t, max_steps=2, beam_width=3)
        for t in [.35, .5, .65]}
    for split in split_workers(records):
        train = [r for r in records if r['worker'] in split['train']]
        heldout = [r for r in records if r['worker'] in split['test']]
        fitted = fit_consensus(records, heldout_workers=split['test'])
        local = local_edit_probe(train, point_tol=.2, support_threshold=.5, max_steps=2, beam_width=3)
        out['splits'].append(dict(**split, structured=fitted, local=local,
                                 structured_evaluation=candidate_holdout(fitted['modes'], heldout),
                                 local_evaluation=candidate_holdout(local['candidates'], heldout)))
    add_cluster_pool(out,records)
    # 所有拟合与留出验证完成后才读取参考；没有按GT选择模式、参数或人物。
    refs = {}
    for ref in references['references']:
        if ref['pairs'] is None:
            refs[ref['name']] = dict(status='unavailable', reason=ref['status'])
            continue
        try:
            coords = floor_points(np.asarray(ref['pairs'], float)).tolist()
            refs[ref['name']] = dict(status='unconfirmed_source_ring', floor=coords, source=ref['source'])
        except ValueError as exc:
            refs[ref['name']] = dict(status='unavailable', reason=str(exc))
    out['references_for_evaluation_only'] = refs
    candidates=out['parameter_sensitivity']['default']['modes']
    candidates=candidates+[c for v in out['local_edit_sensitivity'].values() for c in v['candidates']]
    candidates=candidates+[c for v in out['cluster_pool_sensitivity'].values() for c in v['candidates']]
    for mode in candidates:
        mode['reference_evaluation'] = {name: reference_agreement(mode['floor'], ref['floor'])
                                        if 'floor' in ref else dict(status='unavailable', iou=None)
                                        for name, ref in refs.items()}
    valid = [Polygon(r['floor']) for r in records if Polygon(r['floor']).is_valid and Polygon(r['floor']).area > 0]
    if valid:
        mv = bev_aggregate(valid, 'mv50')
        out['mv_baseline'] = dict(status='valid_input_subset_only', used_annotations=len(valid),
                                 not_used=len(records)-len(valid), geometry_type=mv.geom_type,
                                 denominator_note='valid polygon subset of computable records; adapter-unavailable inventory listed separately',
                                 empty=mv.is_empty, area=mv.area,
                                 reference_iou={name: float(mv.intersection(Polygon(ref['floor'])).area /
                                                           mv.union(Polygon(ref['floor'])).area)
                                                if 'floor' in ref and Polygon(ref['floor']).is_valid and Polygon(ref['floor']).area > 0
                                                else None for name, ref in refs.items()})
    else:
        out['mv_baseline'] = dict(status='unavailable_no_valid_polygon', used_annotations=0, not_used=len(records))
    return out


def svg_room(points, heights=None, three_d=False):
    """简洁静态结构图；坐标是条件重建，不声称恢复了遮挡处真值。"""
    if three_d and heights is None:
        return '<svg viewBox="0 0 200 200"><text x="10" y="100" font-size="12">缺少高度，未生成三维图</text></svg>'
    p = np.asarray(points, float)
    h = np.asarray(heights, float) if heights is not None else np.full(len(p), 2.7)
    base = np.c_[p[:, 0]-.65*p[:, 1], .35*p[:, 0]+.5*p[:, 1]] if three_d else p.copy()
    top = base-np.c_[np.zeros(len(p)), h] if three_d else base
    allp = np.vstack([base, top, [[0, 0]]])
    lo, hi = allp.min(0), allp.max(0)
    scale = 160/max(float(np.max(hi-lo)), .01)
    def projected(q):
        z = (q-(lo+hi)/2)*scale+[100, 100]
        return ' '.join(f'{a:.2f},{b:.2f}' for a, b in z)
    line = lambda q: f'<polyline points="{projected(np.vstack([q,q[0]]))}" fill="none" stroke="#256b86" stroke-width="2"/>'
    shapes = line(base)
    if three_d:
        shapes += line(top)
        for a, b in zip(base, top):
            shapes += f'<polyline points="{projected(np.array([a,b]))}" stroke="#7a9fac" fill="none"/>'
    else:
        camera = (np.array([0., 0.])-(lo+hi)/2)*scale+[100,100]
        shapes += f'<circle cx="{camera[0]:.2f}" cy="{camera[1]:.2f}" r="3" fill="#c0392b"/>'
    return f'<svg viewBox="0 0 200 200" role="img" aria-label="条件布局结构图">{shapes}</svg>'


def summary_row(result):
    modes = result['parameter_sensitivity']['default']['modes']
    local = result['local_edit_sensitivity']['0.5']['candidates']
    covered = lambda key: float(np.mean([s[key]['coverage'] for s in result['splits']])) if result['splits'] else None
    pool=result['cluster_pool_sensitivity']['soft']['candidates']
    return dict(code=result['code'], cohort=result['cohort'], strata=result['strata'],
                n_input=result['input_annotations'], n_computable=result['computable_annotations'],
                modes=len(modes), modes_support_ge3=sum(m['train_support'] >= 3 for m in modes),
                modes_support_ge5=sum(m['train_support'] >= 5 for m in modes),
                supported_invalid=sum(m['train_support'] >= 3 and m['geometry']['polygon_status'] != 'valid' for m in modes),
                structured_holdout=covered('structured_evaluation'), local_holdout=covered('local_evaluation'),
                local_candidates=len(local), local_unseen=sum(c['whole_ring_support']==0 for c in local),
                local_edit_actions=sum(len(c['actions']) for c in local),
                pool_candidates=len(pool),pool_unseen=sum(c['whole_ring_support']==0 for c in pool),
                pool_edit_actions=sum(len(c['actions']) for c in pool),
                pool_holdout=covered('cluster_pool_evaluation'),
                budget6_holdout={name:float(np.mean([s['budget6'][name]['coverage'] for s in result['splits']]))
                                if result['splits'] else None for name in ['structured','local','cluster_pool','cluster_pool_searched']},
                modes_by_tolerance={k: len(result['parameter_sensitivity'][k]['modes']) for k in ['tol_010','default','tol_040']})


def build_gallery(panel, results, out):
    indexed = {x['image_id']:x for x in panel['images']}
    labels={'manual_oos':'Manual/OOS','semi':'Semi（单列）','doorway_hold':'门洞暂缓',
            'oos_hold':'既有OOS暂缓','low_corner_count_control':'低点数对照',
            'user_named_structural_example':'用户指定案例','scope_difference_records':'范围差异意见',
            'detail_omission_records':'细节遗漏意见','supported_candidate':'有支持的候选，合理性待定',
            'supported_geometry_review':'有支持，几何待审','minority_candidate':'少数候选',
            'fitted_support_reduced_review':'拟合后支持减少，待审',
            'unsupported_fitted_candidate_review':'拟合后无整环匹配，待审',
            'observed_ring_candidate':'存在整环匹配','unsupported_joint_candidate':'局部拼接，暂无整环匹配',
            'rare_input_candidate_not_searched':'少数原作答保留，未搜索',
            'invalid_input_seed_kept_for_review':'原环几何不可用，保留待审',
            'minimum':'最少点起步','maximum':'最多点起步','valid':'有效多边形','invalid':'无效多边形'}
    label=lambda value:html.escape(labels.get(value,value))
    body = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>结构共识 · 40图条件实验</title>',
            '<style>body{font:16px/1.6 system-ui;margin:32px auto;max-width:1400px;color:#203138;background:#f5f7f8}h1,h2{line-height:1.3}section{background:white;padding:24px;margin:28px 0;border:1px solid #ddd;border-radius:12px}.pano{width:100%;max-height:450px;object-fit:contain}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.card{border:1px solid #cad7dd;border-radius:8px;padding:12px}.views{display:flex}.views svg{width:50%;height:180px}small{color:#566a75}summary{cursor:pointer}code{overflow-wrap:anywhere}a{color:#12677e}</style>',
            '<h1>结构共识：40图条件实验</h1><p>每张图独立展示；全部模式保留。红点为相机。俯视与三维线框按既有环重建，非终审真值；缺高度的局部编辑候选只展示俯视图。各小图独立缩放，不能直接用屏幕尺寸比较面积。面积和质心不参与候选构造。同一人可能匹配多个候选，卡片支持人数不能直接相加。</p>',
            '<p><a href="README.md">研究解释与方法限制</a> · <a href="results.json">全量输出</a></p>']
    body += ['<details><summary>按图片跳转</summary><p>'+' · '.join(
        f'<a href="#{r["code"]}_{r["cohort"]}">{r["code"]} {label(r["cohort"])}</a>' for r in results)+'</p></details>']
    for result in results:
        meta = indexed[result['image_id']]
        row = summary_row(result)
        image_url = os.path.relpath(ROOT/meta['image_path'], out).replace('\\','/')
        title = html.escape(result['code'])+' · '+label(result['cohort'])
        body += [f'<section id="{html.escape(result["code"]+"_"+result["cohort"])}"><h2>{title}</h2>',
                 f'<p>标签：{"、".join(label(s) for s in meta["strata"])}。库存 {row["n_input"]} 份，可计算 {row["n_computable"]} 份；几何与连接均待复核。</p>',
                 f'<img class="pano" src="{html.escape(image_url)}" loading="lazy" alt="{title}原图">',
                 '<h3>保留整环支持的多模式拟合</h3><div class="grid">']
        for mode in result['parameter_sensitivity']['default']['modes']:
            residual=mode['geometry']['weighted_direction_residual_deg']
            residual_text='不可计算' if residual is None else f'{residual:.2f}°'
            body += [f'<article class="card"><b>{mode["mode_id"]} · {mode["n_corners"]} 角 · 整环支持 {mode["train_support"]}/{row["n_computable"]}</b>',
                     '<div class="views">'+svg_room(mode['floor'])+svg_room(mode['floor'],mode['heights'],True)+'</div>',
                     f'<small>{label(mode["status"])}；{label(mode["geometry"]["polygon_status"])}；方向残差 {residual_text}</small>',
                     f'<details><summary>成员与局部支持</summary><p>{html.escape(", ".join(mode["supporters"]))}</p><p>点支持 {mode["point_support_counts"]}<br>相邻边支持 {mode["edge_support_counts"]}</p></details></article>']
        body += ['</div><h3>实际局部增删：从最少／最多点起步</h3><div class="grid">']
        for cand in result['local_edit_sensitivity']['0.5']['candidates']:
            body += [f'<article class="card"><b>{label(str(cand["seed_kind"]))} · {len(cand["floor"])} 角 · 整环支持 {cand["whole_ring_support"]}</b>',
                     svg_room(cand['floor']), f'<p>{label(cand["status"])}；{len(cand["actions"])} 个增删动作</p></article>']
        body += ['</div><h3>全体点池、按簇加权增删</h3><div class="grid">']
        for cand in result['cluster_pool_sensitivity']['soft']['candidates']:
            body += [f'<article class="card"><b>{html.escape(cand["cluster_id"])} · {len(cand["floor"])} 角 · 整环支持 {cand["whole_ring_support"]}</b>',
                     svg_room(cand['floor']),f'<p>{label(cand["status"])}；{len(cand["actions"])} 个增删动作</p></article>']
        body += ['</div>', f'<p>默认参数全部候选留出覆盖：整环 {row["structured_holdout"]}；局部增删 {row["local_holdout"]}；按簇加权 {row["pool_holdout"]}。这是同图人员复现，不是正确率。候选数不同会影响覆盖，统一最多6个的对照见报告。</p></section>']
    body.append('</html>')
    (out/'index.html').write_text('\n'.join(body),encoding='utf8')


def write_report(payload, out):
    rows=payload['summary']
    primary=[r for r in rows if r['cohort']=='manual_oos']
    f=lambda x: '不可评价' if x is None else f'{x:.3f}'
    lines=['# 多结构共识与人员质量：40图本地探索', '',
           '**本轮实现三个原型：A保留整环支持的分模式拟合；B最少／最多点起步的实际局部增删；C全体点池、按簇差异加权的增删。**', '',
           '这是开发面板上的条件实验。没有独立确认每张图的允许范围，也没有恢复未审的真实邻接，因此不能把输出数量称为“已证明的合理共识数量”。', '',
           '[查看全部图片、俯视与三维线框](index.html) · [机器结果](results.json) · [原始来源核验](input_panel.json) · [六图只读视觉观察](visual_notes.json) · [验证记录](VALIDATION.json)', '',
           '## 1. 人员质量、分簇与共识为何相似，但不能混同', '',
           '| 研究 | 研究对象与问题 | 当前方法和输出 |', '|---|---|---|',
           '| 分簇 | 同图有哪些相似的结构表达？ | 输出分组、成员和差异位置；相似不等于正确。 |',
           '| 共识 | 多人信息能否形成一个或多个可复现布局？ | 输出实际布局候选、完整／局部支持和留出复现；需要检查拼接是否合法。 |',
           '| 人员质量 | 可比图片、同一允许解释下，谁更准确／稳定？ | 跨图定位误差、系统偏差与重复性；不能用簇大小或与单一GT的距离直接替代能力。 |', '',
           '旧页面复用的历史分簇采用 shared-x、同点数硬门、周期 ERP 最大端点距离 25.6 px；比较 complete-linkage 与直径约束的二次亲近度全局 MILP，'
           '后者不是 Affinity Propagation，也不是 IoU 聚类。历史结果只在当前有效点匹配时复用。本轮没有重写旧分簇或更新人工裁决。', '',
           '新整环路线使用共同相机高度单位下的对应角点距离。它确实以分簇作为上游，再估计簇内代表，因此看起来相近；'
           '但分组和估计新坐标仍是不同步骤。局部增删路线另行实现，不借用分簇结果当目标。人员质量本轮不产生新排名。', '',
           '## 2. IoU＋质心与不确定性', '',
           'IoU＋质心可测与指定参考的差异，不能从单一 GT 自动区分合理范围选择与实际标错。质心、RMSE 或更复杂的加权函数均不能补齐未定义的参考集合。'
           '若同一组“8人选A、4人选B”的观测既能由两个合理范围解释，也能由一组人共同误解解释，仅靠这些标注无法唯一辨认两种机制。', '',
           '应先区分范围模式选择，再研究模式内定位。一个可说明辨识条件的模型为 `误差(w,i,m,r)=人员项(w)+图片/模式项(i,m)+人员×图片项(w,i)+重复操作项(w,i,r)`。'
           '图片和人员需要交叉且连通；同人同图间隔重复才有助于进一步拆分交互与随机操作波动。一次观测无法完全拆开后两项。'
           '图片平均效应不是直接测得的数据不确定性，人员平均效应也不是模型的 epistemic uncertainty。', '',
           '语义分割同样可能有多种合理答案；[Probabilistic U-Net](https://arxiv.org/abs/1806.05034)研究的是合理分割及其出现频率的分布。'
           '[Lee 等](https://ceur-ws.org/Vol-2173/paper10.pdf)也区分语义歧义、语义错误和边界不精确；其最大簇路线不等于保留所有合理 layout。'
           '[Welinder 等](https://proceedings.neurips.cc/paper_files/paper/2010/hash/0f9cafd014db7a619ddb4276af0d692c-Abstract.html)将人员能力、偏差和图片因素分别建模。', '',
           '## 3. 实际算法与尚未解决的部分', '',
           '**A：整环约束路线。** 同点数完整环以循环换起点／反向等价匹配，不改变邻接、不平移缩放对齐；complete-linkage 后用中位数和软 Manhattan 项拟合，'
           '高度一致性权重低于方向项。短边连续降低方向约束权重，近180°只诊断。每个候选重新统计全训练集的点支持、真实相邻边支持及整环支持。'
           '最少／最多点到已观察目标的动态规划增删是受限重建路径，不能把它说成自动发现未知拓扑。', '',
           '原分簇成员互斥；拟合后的候选支持重新查询全部训练者，因此支持集合可以重叠，不能把各候选人数相加。'
           'C的“至少3人启动搜索”使用原分簇成员数，不能与拟合候选整环支持数混用。', '',
           '**B：实际局部增删路线。** 从最少／最多点原环独立起步，依据其他人员给定环里的连续短链提出插入；依据有票支持的跨边或精确共线证据提出删除。'
           '按局部支持及弱几何项做有限束搜索；候选生成不使用 A 的整环目标。没有完整环支持的新拼接保留警告，不升级为合理真值。'
           '每次最多2步、束宽3、连续短链长度和提案数量另有限制，机器结果保留截断情况。B目前只生成地面结构，未推断新增点的高度；'
           '完整3D高度项仅在A中验证。这是明确受限原型，不是完整拓扑空间最优解。', '',
           '**C：全点池、按簇加权。** 整理全部训练者的点位、来源和原连边；针对每个训练簇，以其原环为骨架，使用整个点池中的连续链做局部增删。'
           '簇内权重1，簇外原始权重 `0.25·exp(−D/0.20)`，D为双向最近点均距加点数差惩罚；簇外总权重再限制为簇内的0.25倍。'
           '另跑簇外权重为0的硬分簇对照。权重和不叫作人数，原始整数支持单独保留。少于3人的簇保留原候选并明确未搜索；'
           '这是计算和证据限制，不把它们判成错误。这个上限有意保护少数，保护成功本身不能证明少数正确。', '',
           '三条路线均不把 IoU、质心或目标 GT 放入构造参数。去掉这些参数不等于不需要位置匹配：同样正交但位置不同的房间必须能区分。'
           '默认角点容差0.20，相机高度为1；敏感性为0.10/0.20/0.40，局部支持阈值为0.35/0.50/0.65，未根据 GT 选最佳值。'
           '3票和5票仅为描述分档，不是正式共识资格门槛。', '',
           'A仍对点数敏感：同空间的共线冗余点也可能分出不同表示模式；远处深度敏感、未审点序和整环最大距离门限也可能碎裂模式。'
           'B/C可能漏掉需要超过两步恢复的结构，局部多数还可能拼出无人整体认可的组合。C继承原分簇误差，且仍未生成高度。'
           '所有失败保留，不能把所有小簇叫作新合理空间。', '',
           '## 4. 面板、分母与留出', '',
           '事前纳入全部33张既有门洞/OOS暂缓图片，加入B6ByNegPMKs-11、e9zR4mvMWw7-19、wc2JMjhGNzB-30，以及4张低点数对照，共40图。'
           '门洞/OOS标记是既有复核意见；低点数不等于已确认简单。没有根据本次算法输出或GT分数换图。', '',
           '605份accepted作答逐份核验原始导出：377 manual、192 oos、36 semi。另40份历史排除只作库存记录。'
           '586份可投影条件环、19份不可用，均保留在分母；17份缺已有配对，2份已有点修订不进入本次raw来源拟合。', '',
           f'Manual/OOS合并探索涉及{len(primary)}图，{sum(r["n_input"] for r in primary)}份库存、{sum(r["n_computable"] for r in primary)}份可计算。'
           'Semi单列；B6ByNegPMKs-22为全Semi图；S9hNv5qa7GM-07主线四份均缺既有配对，不能静默剔除。', '',
           '每图固定4次约75%训练/25%留出人员划分，整个候选生成仅用训练者。留出者不能建立角点池、模式或影响参数。'
           '同一人不能同时进入训练与测试；多次划分不是新增独立人员或建筑。表中覆盖率的分母仅为可投影输入中的留出人员，19份适配器不可用不进入该比例、另报缺失；'
           '覆盖率是这些留出作答能匹配任一候选的比例，'
           '不代表候选正确率；输出更多候选可能提高覆盖，须同时看候选数量及零支持输出。', '',
           '## 5. 全部主线结果', '',
           'A/B/C全部候选覆盖可能受输出数量影响。因此下表统一按训练集整环支持排序、仅去掉完全相同环、最多保留6个候选再评留出者。'
           '未用测试者或GT选候选；实际候选不足6时不补造。完整不限数量结果在机器记录。', '',
           'C额外区分全部保留候选与确实经过簇条件搜索的候选，防止保留原始少数作答带来的覆盖被误称为“新共识生成成功”。', '',
           '| 图 | 库存/可算 | A候选数 | A≥3票 / ≥5票 | A留出≤6 | B留出≤6 | C全部≤6 | C已搜索≤6 | C候选/零整环支持 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in primary:
        lines.append(f'| {r["code"]} | {r["n_input"]}/{r["n_computable"]} | {r["modes"]} | '
                     f'{r["modes_support_ge3"]}/{r["modes_support_ge5"]} | {f(r["budget6_holdout"]["structured"])} | '
                     f'{f(r["budget6_holdout"]["local"])} | {f(r["budget6_holdout"]["cluster_pool"])} | '
                     f'{f(r["budget6_holdout"]["cluster_pool_searched"])} | '
                     f'{r["pool_candidates"]}/{r["pool_unseen"]} |')
    evaluable=[r for r in primary if r['budget6_holdout']['structured'] is not None]
    means={name:float(np.mean([r['budget6_holdout'][name] for r in evaluable]))
           for name in ['structured','local','cluster_pool','cluster_pool_searched']}
    lines += ['', f'可做留出的主线图片有{len(evaluable)}张。按图片等权的描述性平均覆盖为：'
              f'A={means["structured"]:.1%}，B={means["local"]:.1%}，C全部候选={means["cluster_pool"]:.1%}，'
              f'C仅已搜索候选={means["cluster_pool_searched"]:.1%}。这不是准确率，也不是外建筑验证。'
              '当前原型尚不能据此声称生成了几种可靠合理的房间共识；C也未显示出普遍优于A的复现结果。', '',
              '![逐图留出覆盖与分簇容差敏感性](coverage_and_tolerance.png)', '',
              '**一个实质性失败：**低点数对照7y3sRwLe3Va-04在默认完整环门限下24人可合为一组，'
              '但局部增删会反复借用同一房间其他边的路径，拼成窄条或近重叠折返。其方向残差仍可很小、局部票仍高。'
              '图中既展示高IoU但多余折返的候选，也展示空间范围塌缩的候选。仅有点/边边际票与Manhattan自洽并不足以保护完整结构。', '',
              '失败图是在计算后按原GT一致性的高低选取用于诊断展示，不参与算法选解、调参或总体准确率估计。', '',
              '![局部支持与小残差仍可能产生折返](local_edit_failure.png)', '',
              '这里的“零整环支持”严格指当前点数与对应门限下无匹配，不能一概解释为没有人会接受该空间。'
              '新增冗余点或一个人都没完整画准的正确融合也可能零匹配。因此一方面要防混合结构，另一方面也不能把“必须有人完整标过”作为正确性的充分必要条件。', '']
    lines += ['', '每图详单、各容差、几何/高度消融、每次留出成员及真实局部增删轨迹均在 cases/ 的压缩JSON中。'
              '既有 GT 仅在拟合完成后计算条件参考一致性；6份修订GT没有确认配对，明确不可评价。'
              'MV基线只对有效多边形子集计算，记录所用人数；未与包含无效环的路线冒充相同分母准确率比较。', '',
              '门洞/OOS并不逻辑上阻止群体共识。但暂时无稳定输出可能来自范围歧义、模型不适用、人员不足、匹配门限或未审连接，'
              '不能从本次某个算法失败推导“这张图不可能有共识”。同理，稳定且正交的输出也可能遗漏真正结构。', '',
              '## 6. 尽量少人工的 human-in-the-loop', '',
              '人工可以从逐份人员打分，转为按图片审范围定义、参考冲突和少量随机对照。审核时先盲化人员身份、支持人数和算法名称，'
              '对照原图及可用的扫描／相邻视点证据；保留审核者分歧和unknown。不能把所有观测簇追加为合理GT，或为使算法通过而改参考。', '',
              '优先自动执行：来源核验、投影和几何诊断、跨人员留出、重复标注一致性、参考版本敏感性、局部支持与完整结构冲突检查。'
              '人工集中于新模式、任务范围冲突和表示失败，另外保留随机抽审以发现未被报警覆盖的错误。候选生成者与独立合理性评价分开。', '',
              '如果完全不进行独立合理性核验，也没有扫描等外部证据，研究仍可以客观报告群体解释、可复现性及条件一致性；'
              '但人员绝对准确性与“合理共识”应标为未知。客观性来自可复算、预先规则、独立证据和公开不确定，而不是把主观判断藏进算法阈值。', '',
              '## 7. 边界与复算', '',
              '当前只做离线探索。没有新排除人员、没有改原始点、GT或正式合同；全量排序与风险筛选继续搁置。'
              '需要已确认范围与连接、同人重复及外建筑数据，才能进一步验证人员质量和对新图片的泛化。', '',
              '```powershell',
              'D:/anaconda/python.exe -m tools.thesis_main.analysis.structural_consensus_panel_20260926',
              'D:/anaconda/python.exe -m tools.thesis_main.analysis.run_structural_consensus_20260926',
              '```', '',
              '新增源文件：structural_consensus_20260926.py、local_structure_edits_20260926.py、structural_consensus_panel_20260926.py、run_structural_consensus_20260926.py；对应tests各一份。'
              '验证命令与通过数量见VALIDATION.json。目录地图与README仅登记探索入口；未运行全仓库测试，因为未修改正式运行核心。', '']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf8')


def plot_results(payload, cases, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei']
    plt.rcParams['axes.unicode_minus']=False
    rows=[r for r in payload['summary'] if r['cohort']=='manual_oos']
    fig,axes=plt.subplots(1,2,figsize=(13,17),layout='constrained',sharey=True)
    y=np.arange(len(rows))
    for offset,(name,label,color) in enumerate([
        ('structured','A 整环拟合','#157a91'),('local','B 全体局部票','#df8020'),
        ('cluster_pool','C 按簇加权（含保留原作答）','#7864a6'),
        ('cluster_pool_searched','C 仅已搜索候选','#3d9b54')]):
        xs=[r['budget6_holdout'][name] if r['budget6_holdout'][name] is not None else np.nan for r in rows]
        axes[0].scatter(xs,y+(offset-1.5)*.15,s=19,label=label,color=color)
    for offset,(name,label,color) in enumerate([('tol_010','0.10','#a9bece'),('default','0.20','#296588'),('tol_040','0.40','#bd743b')]):
        axes[1].scatter([r['modes_by_tolerance'][name] for r in rows],y+(offset-1)*.18,s=18,label=label,color=color)
    axes[0].set(yticks=y,yticklabels=[r['code'] for r in rows],xlim=(-.03,1.03),xlabel='留出匹配比例：最多6个候选；不是正确率')
    axes[0].invert_yaxis()
    axes[1].set_xlabel('完整环表示模式数（不等于合理空间数）')
    for ax in axes:
        ax.grid(alpha=.2);ax.legend(loc='lower left',bbox_to_anchor=(0,1.01),ncol=2,fontsize=8)
    fig.suptitle('固定面板：主线39图；缺少可用输入或人数不足时留出不作评价')
    fig.savefig(out/'coverage_and_tolerance.png',dpi=150);plt.close(fig)
    example=next(r for r in cases if r['code']=='7y3sRwLe3Va-04' and r['cohort']=='manual_oos')
    baseline=example['parameter_sensitivity']['default']['modes'][0]
    local=example['local_edit_sensitivity']['0.5']['candidates']
    reference=example['references_for_evaluation_only']['gt_original']['floor']
    by_iou=sorted(local,key=lambda c:reference_agreement(c['floor'],reference)['iou'])
    selected=[('A：整环拟合',baseline),('B：较高面积重叠的折返',by_iou[-1]),('B：区域塌缩的候选',by_iou[0])]
    fig,axes=plt.subplots(1,3,figsize=(13.5,4.8),layout='constrained')
    for ax,(label,c) in zip(axes,selected):
        p=np.array(c['floor']);q=np.array(reference)
        q=np.vstack([q,q[0]])
        ax.plot(q[:,0],q[:,1],'--',color='#888',label='源GT（条件参考）')
        ring=np.vstack([p,p[0]])
        ax.fill(ring[:,0],ring[:,1],color='#dd865b',alpha=.25)
        ax.plot(ring[:,0],ring[:,1],'-o',color='#bc542c',ms=3)
        labelled=set()
        for i,point in enumerate(p):
            if i in labelled:
                continue
            close=[j for j in range(len(p)) if j not in labelled and np.linalg.norm(p[j]-point)<.06]
            labelled.update(close)
            ax.annotate('/'.join(str(j+1) for j in close),point,xytext=(4,4),textcoords='offset points',fontsize=8)
        ax.scatter([0],[0],marker='x',color='black')
        iou=reference_agreement(p,reference)['iou']
        residual=c['geometry']['weighted_direction_residual_deg']
        ax.set_title(f'{label}\nIoU={iou:.4f}；方向残差={residual:.2f}°',fontsize=10)
        ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('相机高度单位')
    fig.suptitle('局部票和低方向残差不能保证完整结构；灰虚线为源GT，×为相机；未回写标注')
    fig.savefig(out/'local_edit_failure.png',dpi=170);plt.close(fig)


def run(out=OUT):
    out=Path(out)
    panel=json.loads((out/'input_panel.json').read_text(encoding='utf8'))
    refs={r['image_id']:r for r in panel['references_for_evaluation_only']}
    results=[]
    for image in panel['images']:
        for cohort, conditions in [('manual_oos',{'manual','oos'}),('semi',{'semi'})]:
            if not any(r['raw_condition'] in conditions for r in image['annotations']):
                continue
            value=evaluate_image(image,refs[image['image_id']],cohort)
            save(out/'cases'/f'{image["code"]}_{cohort}.json.gz',value)
            results.append(value)
        print(image['code'],flush=True)
    payload=dict(schema='structural_consensus_real_experiment_20260926_v1',seed=SEED,
                 status='development_panel_conditional_not_accuracy_validation',
                 input_counts=panel['counts'],summary=[summary_row(r) for r in results],
                 case_files=[f'cases/{r["code"]}_{r["cohort"]}.json.gz' for r in results],
                 no_source_writeback=True,no_new_ordering=True,no_gt_in_fitting=True,
                 no_worker_quality_ranking=True,
                 parameters=dict(point_tolerance_grid=[.1,.2,.4],local_support_grid=[.35,.5,.65],
                                 local_max_steps=2,local_beam_width=3,split_fraction=.75,n_splits=4,
                                 pool_outside_modes=['soft','hard'],comparison_candidate_cap=6),
                 notes=['同图重划分非独立图片或外建筑验证。','未依据GT选图或选择最优参数。',
                        '门洞/OOS标签是既有暂缓意见，非本轮新裁决。','完整环模式数受点数/匹配容差/未审邻接影响。'])
    save(out/'results.json',payload)
    build_gallery(panel,results,out)
    plot_results(payload,results,out)
    write_report(payload,out)
    return payload


if __name__=='__main__':
    run()
