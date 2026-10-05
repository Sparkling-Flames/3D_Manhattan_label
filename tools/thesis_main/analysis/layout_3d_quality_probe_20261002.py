"""排序后3D质量探针；只读预处理输入，不拟合或写回标注。"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from tools.label_studio.panorama_studio.geometry import heading_frame
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
from tools.thesis_main.analysis.layout_metric_response_20261001 import measure

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'analysis_results/layout_metric_response_20261001/results.json'


def prepare_record(record):
    """人员/人工GT未确认环按共享x稳定排序；原始GT保留参考环。"""
    r = copy.deepcopy(record)
    if r.get('points') is None:
        r['order_used'] = 'unavailable'
        return r
    if r.get('ring_confirmed') or r.get('version') == 'original':
        r['order_used'] = 'human_confirmed' if r.get('ring_confirmed') else 'original_gt_reference'
        return r
    p = np.asarray(r['points'], float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) % 2 or not np.isfinite(p).all():
        raise ValueError('invalid_preprocessed_points')
    pairs = p.reshape(-1, 2, 2)
    if not np.allclose(pairs[:, 0, 0], pairs[:, 1, 0], rtol=0, atol=1e-9):
        raise ValueError('preprocessed_shared_x_mismatch')
    order = np.argsort(pairs[:, 0, 0], kind='stable').tolist()
    r['points'] = pairs[order].reshape(-1, 2).tolist()
    for key in ('source_pair_indices', 'source_point_indices', 'source_point_labels'):
        if r.get(key) is not None:
            stride = 1 if key == 'source_pair_indices' else 2
            if len(r[key]) != stride*len(order):
                raise ValueError('source_identity_length_mismatch')
            r[key] = [r[key][stride*i+j] for i in order for j in range(stride)]
    r['order_used'] = 'default_x_unreviewed'
    return r


def height_stats(p, h):
    p, h = np.asarray(p, float), np.asarray(h, float)
    length = np.linalg.norm(np.roll(p, -1, axis=0)-p, axis=1)
    if not np.isfinite(h).all() or np.any(h <= 0) or length.sum() <= 0:
        raise ValueError('invalid_wall_height_or_perimeter')
    nxt = np.roll(h, -1)
    mean = float(np.average((h+nxt)/2, weights=length))
    a, b = h-mean, nxt-mean
    rms = float(np.sqrt(np.average((a*a+a*b+b*b)/3, weights=length)))
    return dict(mean_h=mean, rms_h=rms, rms_relative=rms/mean,
                max_deviation_h=float(np.max(abs(h-mean))), range_h=float(np.ptp(h)))


def direction_stats(p, axis):
    edges = np.roll(p, -1, axis=0)-p
    length = np.linalg.norm(edges, axis=1)
    if np.any(length <= 1e-12):
        return dict(status='unavailable', reason='zero_length_edge')
    residual = np.degrees(abs((np.arctan2(edges[:, 1], edges[:, 0])-axis+np.pi/4) % (np.pi/2)-np.pi/4))
    return dict(status='ok', reason=None, axis_deg=float(np.degrees(axis)),
                per_edge_deg=residual.tolist(), edge_lengths_h=length.tolist(),
                mean_deg=float(np.average(residual, weights=length)),
                rms_deg=float(np.sqrt(np.average(residual**2, weights=length))), max_deg=float(residual.max()))


def diagnostics(record):
    g = reconstruct(record)
    valid = g['representations']['declared_footprint']['status'] == 'ok'
    out = dict(status='ok' if valid and g['wall_top_available'] else 'unavailable',
               reason=None if valid and g['wall_top_available'] else g['reason'],
               floor=g['floor'].tolist() if g['floor'] is not None else None,
               heights=g['heights'].tolist() if g['heights'] is not None else None,
               representations=g['representations'], camera_relation=g['camera_relation'],
               bottom_horizon_margin_deg=g.get('bottom_horizon_margin_deg'),
               height=None, direction_self=None)
    if valid:
        p = g['floor']
        if np.any(np.linalg.norm(np.roll(p, -1, axis=0)-p, axis=1) <= 1e-12):
            out['direction_self'] = dict(status='unavailable', reason='zero_length_edge')
        else:
            out['direction_self'] = direction_stats(p, heading_frame(p))
        if g['wall_top_available']:
            out['height'] = height_stats(p, g['heights'])
    return out


def compare(a, b):
    if b is None:
        return dict(status='unavailable', reason='reference_version_absent')
    base = measure(a, b)
    da, db = diagnostics(a), diagnostics(b)
    base.update(status='ok' if base['bev']['status']=='ok' else 'unavailable',
                reason=base['bev'].get('reason'), diagnostics_a=da, diagnostics_b=db)
    base['direction_to_reference'] = dict(status='unavailable', reason='reference_axis_unavailable')
    if da['direction_self'] and db['direction_self'] and db['direction_self']['status']=='ok':
        base['direction_to_reference'] = direction_stats(np.asarray(da['floor']), np.radians(db['direction_self']['axis_deg']))
    volume = dict(status='unavailable', reason='footprint_or_height_unavailable', iou=None)
    if base['bev']['status']=='ok' and da['height'] is not None and db['height'] is not None:
        bev = base['bev']; ha, hb = da['height']['mean_h'], db['height']['mean_h']
        area_a, area_b = bev['area_a_h2'], bev['area_b_h2']
        intersection = area_a*bev['coverage_of_a']*min(ha, hb)
        volume = dict(status='ok', reason=None, iou=intersection/(area_a*ha+area_b*hb-intersection),
                      volume_a_h3=area_a*ha, volume_b_h3=area_b*hb,
                      height_signed_h=ha-hb, height_absolute_h=abs(ha-hb))
    base['model_volume'] = volume
    return base


def restore_initial(source, evidence, final_ids):
    """审核绑定标签映射到最终预处理点对；不使用历史坐标。"""
    record = source['order_record']
    binding = json.loads(record.get('previous_record', record)['binding'])
    current = [tuple(source['point_labels'][i] for i in pair) for pair in source['links_zero_based']]
    old = [tuple(binding['labels'][i] for i in pair) for pair in binding['links']]
    if len(set(current)) != len(current) or set(old) != set(current):
        raise ValueError('historical_pair_identity_mismatch')
    before, after = [json.loads(evidence[k]) if isinstance(evidence[k], str) else evidence[k]
                     for k in ('initial_order', 'final_order')]
    if sorted(before) != list(range(len(old))) or sorted(after) != list(range(len(old))):
        raise ValueError('invalid_historical_ring')
    mapped = [current.index(old[i]) for i in after]
    if mapped != final_ids:
        raise ValueError('final_ring_binding_mismatch')
    indices = [current.index(old[i]) for i in before]
    point_indices = [i for j in indices for i in source['links_zero_based'][j]]
    return dict(points=[source['preprocessed_points'][i] for i in point_indices],
                source_pair_indices=indices, source_point_indices=point_indices,
                ring_confirmed=False, order_used='historical_adjacency_on_final_points')


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def flat(row):
    m = row['metrics']; a = m.get('diagnostics_a', {}); h = a.get('height') or {}
    d = a.get('direction_self') or {}; ref = m.get('direction_to_reference', {})
    return dict(image=row['image'], id=row['id'], worker=row['a'].get('worker'),
        condition=row['a'].get('condition'), quality_candidate=row['a'].get('quality_candidate'),
        order_used=row['a']['order_used'], reference_version=row['reference_version'],
        status=m['status'], reason=m.get('reason'), bev_iou=m.get('bev', {}).get('bev_range_iou'),
        column_iou=m.get('column', {}).get('1024x512', {}).get('iou'),
        model_volume_iou=m.get('model_volume', {}).get('iou'),
        volume_reason=m.get('model_volume', {}).get('reason'),
        height_mean_h=h.get('mean_h'), height_rms_h=h.get('rms_h'), height_rms_relative=h.get('rms_relative'),
        height_max_deviation_h=h.get('max_deviation_h'),
        height_signed_h=m.get('model_volume', {}).get('height_signed_h'),
        direction_self_rms_deg=d.get('rms_deg'), direction_reference_rms_deg=ref.get('rms_deg'),
        direction_self_reason=d.get('reason'), direction_reference_reason=ref.get('reason'))


def csv_write(path, rows):
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def run(out):
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle = load_current_bundle(); panel, mapping = project_bundle(bundle)
    saved = json.loads(OLD.read_text(encoding='utf-8'))
    codes = sorted({r['image'] for r in saved['real']})
    sources = {mapping['records'][o['object_id']]:o for o in bundle['data']['objects']}
    evidence = {mapping['records'][r['object_id']]:r for r in bundle['research']['annotations']}
    rows, orders, objects = [], [], []
    for im in panel['images']:
        if im['code'] not in codes:
            continue
        prepared = {}
        for r in im['annotations']+im['references']:
            r['source_pair_indices'] = sources[r['id']]['ordered_source_pair_indices']
            prepared[r['id']] = prepare_record(r)
        references = {r['version']:prepared[r['id']] for r in im['references']}
        for original in im['annotations']:
            a = prepared[original['id']]
            objects.append(dict(image=im['code'], record=a, diagnostics=diagnostics(a)))
            for version in ('original', 'manual_revision'):
                b = references.get(version)
                rows.append(dict(image=im['code'], id=a['id'], reference_version=version,
                                 a=a, b=b, metrics=compare(a, b)))
            ev = evidence[a['id']]
            if ev['order_change'] == 'adjacency_changed':
                entry = dict(image=im['code'], id=a['id'], evidence=ev['order_change_evidence'], after=a)
                try:
                    before = restore_initial(sources[a['id']], ev['order_change_evidence'], a['source_pair_indices'])
                except ValueError as exc:
                    entry.update(status='unavailable', reason=str(exc))
                else:
                    entry.update(status='ok', reason=None, before=before, change=compare(before, a),
                                 references={v:dict(before=compare(before, b), after=compare(a, b)) for v,b in references.items()})
                orders.append(entry)
    # 原12图嵌入比较逐项核验底面、边界及墙带，避免新探针悄悄改变既有基线。
    checked = 0
    for r in saved['real']:
        if r['b'] is None:
            continue
        for rec in (r['a'], r['b']):
            source = sources[rec['id']]
            if rec['points'] != source['points_1024x512'] or rec['source_pair_indices'] != source['ordered_source_pair_indices']:
                raise ValueError('saved_source_binding_drift:'+rec['id'])
        now = measure(r['a'], r['b'])
        for key in ('bev', 'boundary', 'column'):
            if now[key] != r['metrics'][key]:
                raise ValueError('saved_metric_drift:'+r['id']+':'+key)
        checked += 1
    out.mkdir(parents=True, exist_ok=True)
    result = dict(schema='layout_3d_quality_probe_v1', images=codes, objects=objects, real=rows, orders=orders,
                  baseline_comparisons_verified=checked,
                  counts=dict(records=len(objects), comparisons=len(rows),
                    missing_reference=sum(r['b'] is None for r in rows),
                    order_used=dict(Counter(o['record']['order_used'] for o in objects)),
                    order_cases=len(orders), order_bound=sum(o['status']=='ok' for o in orders)))
    dump(out/'results.json', result)
    csv_write(out/'metrics.csv', [flat(r) for r in rows])
    order_rows = [dict(image=r['image'], id=r['id'], status=r['status'], reason=r['reason'],
                      before_after_bev_iou=r.get('change', {}).get('bev', {}).get('bev_range_iou'),
                      before_after_volume_iou=r.get('change', {}).get('model_volume', {}).get('iou')) for r in orders]
    csv_write(out/'order_comparisons.csv', order_rows)
    dump(out/'experiment_plan.json', dict(source='analysis_results/research_input_20260929/manifest.json',
        selection='existing 12 stage2 images; ALL annotations, including unconfirmed and excluded as diagnostic rows; no worker scoring',
        images=codes, order='confirmed ring retained; unconfirmed annotation/manual GT stable shared-x sort; original GT reference ring retained',
        units='camera height h=1; h, h2, h3 and degrees',
        heights='exact arclength integral of piecewise linear wall-top height; flat-top prism is a model, not observed volume',
        axes='each reference version best axis for reference diagnostics only; own best axis separately; no point fitting',
        scope='no worker classification, consensus, eligibility change or raw writeback'))
    dump(out/'field_contract.json', dict(schema=result['schema'], metrics_csv=list(flat(rows[0])),
        order_csv=list(order_rows[0]), missing='null in JSON, empty in CSV; status/reason retained per metric in results.json',
        primary='results.json retains input identities, points, gates, per-edge directions and each representation status',
        volume='same floor level; area_intersection*min(mean_height_a,mean_height_b) / volume_union',
        heights='mean=integral(h ds)/perimeter; RMS=sqrt(integral((h-mean)^2 ds)/perimeter)',
        geometry='direction residual is model consistency, not a distance between complete layouts; wall verticality and floor flatness are imposed',
        applicability='mathematical axes reported even in non-Manhattan scenes as diagnostics, never automatic worker errors',
        review='unmarked is unknown; order confirmation is not quality eligibility; excluded rows are diagnostics only'))
    plots(out, result)
    report(out, result)
    return result


def plots(out, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    valid = [r for r in result['real'] if r['reference_version']=='original' and r['metrics'].get('model_volume', {}).get('status')=='ok']
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for state, marker in [('human_confirmed','o'), ('default_x_unreviewed','x')]:
        rs = [r for r in valid if r['a']['order_used']==state]
        ax[0].scatter([r['metrics']['bev']['bev_range_iou'] for r in rs], [r['metrics']['model_volume']['iou'] for r in rs], s=18, marker=marker, label=state)
        ax[1].scatter([r['metrics']['diagnostics_a']['height']['rms_relative'] for r in rs], [r['metrics']['model_volume']['height_signed_h'] for r in rs], s=18, marker=marker)
    ax[0].plot([0,1],[0,1],color='gray',linewidth=.8); ax[0].legend(fontsize=7)
    ax[0].set(xlabel='BEV IoU', ylabel='Flat-top model volume IoU')
    ax[1].set(xlabel='Wall-height RMS / mean', ylabel='Signed mean-height difference [h]')
    fig.savefig(out/'metric_comparison.png', dpi=150); plt.close(fig)
    for code in sorted({r['image'] for r in result['orders']}):
        candidates = sorted((r for r in result['orders'] if r['image']==code and r['status']=='ok'), key=lambda r:r['id'])
        if not candidates:
            continue
        r = candidates[0]; fig, ax = plt.subplots(1, 3, figsize=(12, 3.8), layout='constrained')
        for label, rec in [('before',r['before']),('after',r['after'])]:
            d = diagnostics(rec); p = np.asarray(d['floor']); h = np.asarray(d['heights'])
            if p.ndim != 2:
                continue
            ax[0].plot(*np.vstack([p,p[0]]).T, '.-', label=label)
            lengths = np.linalg.norm(np.roll(p,-1,axis=0)-p, axis=1); s = np.r_[0,np.cumsum(lengths)]
            if h.ndim == 1:
                ax[1].plot(s/s[-1], np.r_[h,h[0]], '.-', label=label)
            dr = d['direction_self']
            if dr and dr['status']=='ok':
                ax[2].plot(range(len(p)), dr['per_edge_deg'], '.-', label=label)
        ax[0].set_aspect('equal'); ax[0].legend(); ax[0].set(xlabel='X [h]',ylabel='Z [h]')
        ax[1].set(xlabel='Normalized perimeter (own ring)',ylabel='Wall-top height [h]')
        ax[2].set(xlabel='Edge index (own ring)',ylabel='Own-axis residual [deg]')
        fig.suptitle(code+' / '+r['id']+'; same preprocessed points, different adjacency')
        fig.savefig(out/('order_'+code+'.png'), dpi=150); plt.close(fig)


def report(out, result):
    lines = ['# 排序后的3D质量增量实验（2026-10-02）','',
        '本轮接续阶段2质量衡量研究。底面已有基线；新增墙体方向、沿边长积分的墙高诊断和水平顶面模型体积。没有拟合或修正原标注，没有人员分类、融合或候选生成。','',
        '## 样本与排序','',
        f"沿用12图，扩展到这些图的全部{result['counts']['records']}份作答。两种参考版本分别保留，共{result['counts']['comparisons']}行，其中{result['counts']['missing_reference']}行缺参考。",
        f"排序状态：{result['counts']['order_used']}。未人工确认的人员环按预处理共享x稳定升序；原始GT保留来源参考环。人工确认环保持原样。排除和受限场景保留作诊断，不恢复资格。",
        f"邻接改变{len(result['orders'])}份，身份成功绑定{result['counts']['order_bound']}份；只在最终坐标上恢复旧邻接，不冒充历史坐标复算。既有15个有效比较的底面、边界和墙带逐字段核对通过：{result['baseline_comparisons_verified']}个。",'',
        '## 原始GT比较的描述统计','',
        '|作答层|记录数|模型体积可计算|BEV IoU中位数|体积IoU中位数|墙高相对RMS中位数|自身轴RMS中位数/度|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for state in ('human_confirmed','default_x_unreviewed'):
        rs = [r for r in result['real'] if r['reference_version']=='original' and r['a']['order_used']==state]
        fs = [flat(r) for r in rs]
        def med(key):
            values = [f[key] for f in fs if f[key] is not None]
            return f'{np.median(values):.6f}' if values else 'NA'
        lines.append(f"|{state}|{len(rs)}|{sum(f['model_volume_iou'] is not None for f in fs)}|{med('bev_iou')}|{med('model_volume_iou')}|{med('height_rms_relative')}|{med('direction_self_rms_deg')}|")
    lines += ['', '各列按本指标可用作答计算，中位数差不是配对方法增益；完整状态和分母见CSV/JSON。该面板定向覆盖特殊情况，两个排序层不是随机分组，不能比较哪组人员更好，也不推断总体比例。','',
        '## 改序的空间影响','', '|图片|记录|绑定|旧环与新环BEV IoU|','|---|---|---|---:|']
    for r in result['orders']:
        v = r.get('change',{}).get('bev',{}).get('bev_range_iou')
        lines.append(f"|{r['image']}|{r['id']}|{r['reason'] or 'ok'}|{v if v is not None else 'NA'}|")
    paired = [r['references']['original'] for r in result['orders'] if r['status']=='ok']
    differences = [r['after']['bev']['bev_range_iou']-r['before']['bev']['bev_range_iou']
                   for r in paired if all(r[k]['bev'].get('bev_range_iou') is not None for k in ('before','after'))]
    comparable = [r for r in result['real'] if r['reference_version']=='original' and r['metrics'].get('model_volume',{}).get('status')=='ok']
    gaps = [r['metrics']['bev']['bev_range_iou']-r['metrics']['model_volume']['iou'] for r in comparable]
    lines += ['', '## 本轮可以支持的发现','',
        f"- {len(differences)}份可比较改序中，{sum(x>1e-10 for x in differences)}份相对原始GT的BEV IoU提高；增量范围{min(differences):.6f}–{max(differences):.6f}。这是两张定向图片的同坐标邻接对照，不是改序必然改善的一般证明。",
        f"- {len(gaps)}份原始GT可比较作答中，BEV IoU减模型体积IoU的配对差中位数{np.median(gaps):.6f}、最大值{max(gaps):.6f}。体积纳入高度后确实改变测量，但分数更低不证明更有效。",
        '- 墙高整体偏差与内部高度起伏分别展示；底面、模型体积及自洽诊断不是同一个评价维度。当前数据不能据此选出最终质量权重。',
        '', '![指标比较](metric_comparison.png)', '',
        '改序图中每条曲线使用自身环序的边编号／归一化周长，横轴不是已建立的跨环墙面对应。', '',
        *[f'![改序对照 {code}](order_{code}.png)' for code in sorted({r['image'] for r in result['orders'] if r['status']=='ok'})],
        '', '## 解释与边界','',
        '- 墙方向同时报告自身最佳轴与对应参考GT轴；低自洽残差不能证明接近GT。各版本GT轴只用于评价，不进入后续共识。',
        '- 底面水平、墙面竖直由重建假设强制满足，不将其零残差计作质量证据。墙高是上下点结合固定相机高度推导的量。',
        '- 水平顶面模型体积保留原底面，采用墙顶沿周长的平均高度；不是实测封闭体积。非平顶的信息必须同时看RMS、最大偏差及原高度数组。此模型不能表达顶面局部形状。',
        '- 同高度时体积IoU退化为BEV IoU；不同高度下增加的是模型高度不一致信息，并非独立的新质量证据。体积IoU较低不代表评价更正确。',
        '- 改序既改变区域，又改变边长和高度积分权重；即使各点高度不变，平均墙高也可能变化。不能把该变化解释为重新点击了顶点。',
        '- 原始/人工GT分开，默认未审不冒充确认。近地平线、真实调平及停止范围解释限制保留；不自动判定人员错误。',
        '- 本轮没有建立真实角点/整墙对应，因此没有新增真实点位RMSE或完整墙面距离。', '',
        '## 复算与下一步','',
        '`python -B -m tools.thesis_main.analysis.layout_3d_quality_probe_20261002 --out analysis_results/layout_3d_quality_probe_20261002`','',
        'results.json保留逐项输入、资格、失败、参考版本与逐边结果；metrics.csv为摘要，order_comparisons.csv为改序对照。experiment_plan.json及field_contract.json说明口径。', '',
        '先审阅指标分歧案例，再决定质量测量保留项；本轮不冻结总分、门限或体积方法。分片封顶、人员分类和人数曲线未启动。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out)['counts'], ensure_ascii=False))
